"""RFQ lifecycle, invitations and quotations. Routers stay thin; everything that decides who may do what lives here.

RFQ:        draft -> issued -> closed -> awarded      (cancel from draft, issued or closed; revoke takes awarded back to closed)
Quotation:  draft <-> submitted -> selected / not_selected
Invitation: invited -> declined (by the vendor) or withdrawn (by procurement)
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from procurehub_common.service_client import ServiceRejected
from procurehub_common.tokens import TokenClaims
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .common import Clients, call, commit, err, event, line_total, log_history, next_number, quotations_open, vendor_lookup
from .config import Settings
from .models import (
    Invitation,
    InvitationStatus,
    Quotation,
    QuotationItem,
    QuotationStatus,
    Rfq,
    RfqItem,
    RfqStatus,
    Selection,
    SelectionStatus,
    utcnow,
)
from .schemas import ExtendIn, ItemSpecIn, QuotationCreate, QuotationIn, RfqCreate, RfqUpdate

log = logging.getLogger("quotations")
MAX_INVITATIONS = 50
LIVE_QUOTATION = (QuotationStatus.SUBMITTED.value, QuotationStatus.SELECTED.value, QuotationStatus.NOT_SELECTED.value)


def _like(term: str) -> str:
    return "%" + term.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# ---- RFQ lookups -----------------------------------------------------------------------------------
def get_rfq(db: Session, rfq_id: str, *, lock: bool = False) -> Rfq:
    stmt = select(Rfq).where(Rfq.id == rfq_id)
    rfq = db.scalar(stmt.with_for_update() if lock else stmt)
    if rfq is None:
        raise err(404, "RFQ not found.")
    return rfq


def _check_deadline(settings: Settings, deadline: datetime, now: datetime) -> None:
    if deadline < now + timedelta(hours=settings.min_deadline_hours):
        raise err(422, f"The deadline must be at least {settings.min_deadline_hours} hour{'s' if settings.min_deadline_hours != 1 else ''} from now.")
    if deadline > now + timedelta(days=settings.max_deadline_days):
        raise err(422, f"The deadline cannot be more than {settings.max_deadline_days} days away.")


def _stale(rfq: Rfq, version: int) -> None:
    if rfq.version != version:
        raise err(409, "This RFQ was changed somewhere else. Reload it and try again.")


def rfq_actions(rfq: Rfq, now: datetime, has_selection: bool) -> list[str]:
    """What procurement can do next. Computed from the same state the commands check, so the screen never offers a refused step."""
    st = rfq.status
    passed = rfq.deadline <= now
    acts: list[str] = []
    if st == RfqStatus.DRAFT.value:
        acts += ["edit", "invite", "publish", "cancel"]
    elif st == RfqStatus.ISSUED.value:
        if not passed:
            acts += ["invite", "extend"]
        acts += ["close", "cancel"]
        if passed:
            acts += ["compare", "select"]
    elif st == RfqStatus.CLOSED.value:
        acts += ["compare", "select", "cancel"]
    elif st == RfqStatus.AWARDED.value:
        acts += ["compare", "revoke"]
    return acts


# ---- RFQ commands ----------------------------------------------------------------------------------
def _spec_map(specs: list[ItemSpecIn], items: list[RfqItem]) -> dict[int, ItemSpecIn]:
    known = {i.line_no for i in items}
    out: dict[int, ItemSpecIn] = {}
    for s in specs:
        if s.line_no not in known:
            raise err(422, f"There is no item {s.line_no} on this RFQ.")
        if s.line_no in out:
            raise err(422, f"Item {s.line_no} appears twice.")
        out[s.line_no] = s
    return out


def live_rfq_for(db: Session, request_id: str) -> Rfq | None:
    """The RFQ in progress for a purchase request, if any (cancelled ones do not count)."""
    return db.scalar(select(Rfq).where(Rfq.active_request_id == request_id))


def create_rfq(db: Session, principal: TokenClaims, body: RfqCreate, clients: Clients, settings: Settings) -> Rfq:
    now = utcnow()
    _check_deadline(settings, body.deadline, now)
    try:
        pr = call(clients.request_service().get, f"/internal/v1/purchase-requests/{body.purchase_request_id}")
    except ServiceRejected as e:
        if e.status_code == 404:
            raise err(422, "That purchase request does not exist.") from None
        raise err(502, "The purchase request service refused the request.") from None
    if pr["status"] != "approved":
        raise err(422, f"Only approved purchase requests can go out for quotation. {pr['number']} is {pr['status']}.")
    existing = live_rfq_for(db, pr["id"])
    if existing is not None:
        raise err(409, f"{pr['number']} already has an RFQ in progress ({existing.number}). Cancel it first to start another.")
    if not pr["items"]:
        raise err(422, "That purchase request has no items.")

    number = next_number(db, "RFQ", now.year)
    rfq = Rfq(number=number, purchase_request_id=pr["id"], purchase_request_number=pr["number"], department=pr.get("department") or "",
              needed_by=date.fromisoformat(pr["needed_by"]) if pr.get("needed_by") else None, active_request_id=pr["id"],
              budget_amount=Decimal(str(pr["total_amount"])), currency=pr["currency"], title=body.title or pr["title"], description=body.description,
              requirements=body.requirements, deadline=body.deadline, status=RfqStatus.DRAFT.value, created_by_id=principal.sub, created_by_name=principal.name or "Unknown")
    rfq.items = [RfqItem(line_no=i["line_no"], description=i["description"], quantity=Decimal(str(i["quantity"])), unit=i["unit"],
                         estimated_unit_price=Decimal(str(i["unit_price"]))) for i in pr["items"]]
    specs = _spec_map(body.items, rfq.items)
    for it in rfq.items:
        if it.line_no in specs:
            it.description, it.specification = specs[it.line_no].description, specs[it.line_no].specification
    log_history(rfq, principal, "created", None, f"Created from {pr['number']}")
    db.add(rfq)
    commit(db, flush_only=True)
    event(db, "rfq_created", rfq, actor_id=principal.sub, purchase_request_number=pr["number"])
    commit(db)
    db.refresh(rfq)
    log.info("rfq_created", extra={"event": "rfq_created", "rfq_id": rfq.id, "number": number, "actor_id": principal.sub})
    return rfq


def update_rfq(db: Session, principal: TokenClaims, rfq_id: str, body: RfqUpdate, settings: Settings) -> Rfq:
    rfq = get_rfq(db, rfq_id, lock=True)
    if rfq.status != RfqStatus.DRAFT.value:
        raise err(409, f"An RFQ can only be edited while it is a draft. This one is {rfq.status}.")
    _stale(rfq, body.version)
    _check_deadline(settings, body.deadline, utcnow())
    specs = _spec_map(body.items, rfq.items)
    for it in rfq.items:
        if it.line_no in specs:
            it.description, it.specification = specs[it.line_no].description, specs[it.line_no].specification
    rfq.title, rfq.description, rfq.requirements, rfq.deadline = body.title, body.description, body.requirements, body.deadline
    rfq.version += 1
    log_history(rfq, principal, "updated", rfq.status, "RFQ updated")
    event(db, "rfq_updated", rfq, actor_id=principal.sub)
    commit(db)
    db.refresh(rfq)
    return rfq


def publish(db: Session, principal: TokenClaims, rfq_id: str, clients: Clients, settings: Settings) -> Rfq:
    rfq = get_rfq(db, rfq_id, lock=True)
    if rfq.status != RfqStatus.DRAFT.value:
        raise err(409, f"Only a draft RFQ can be issued. This one is {rfq.status}.")
    now = utcnow()
    problems: list[str] = []
    if rfq.deadline < now + timedelta(hours=settings.min_deadline_hours):
        problems.append("The deadline is too close or has passed. Edit the RFQ and set a later one.")
    invited = [i for i in rfq.invitations if i.status == InvitationStatus.INVITED.value]
    if not invited:
        problems.append("Invite at least one vendor.")
    if not rfq.items:
        problems.append("The RFQ has no items.")
    if problems:
        raise err(422, problems)
    found = vendor_lookup(clients, [i.vendor_id for i in invited])  # a vendor suspended since it was invited must not receive the RFQ
    bad = [i.vendor_name for i in invited if found.get(i.vendor_id, {}).get("status") != "verified"]
    if bad:
        raise err(409, "These vendors are no longer verified. Withdraw their invitations first: " + ", ".join(bad) + ".")
    for i in invited:
        i.sent_at = now
    previous = rfq.status
    rfq.status, rfq.issued_at = RfqStatus.ISSUED.value, now
    rfq.version += 1
    log_history(rfq, principal, "issued", previous, f"Issued to {len(invited)} vendor{'s' if len(invited) != 1 else ''}")
    event(db, "rfq_issued", rfq, actor_id=principal.sub, vendor_ids=[i.vendor_id for i in invited])  # Phase 10: notify each invited vendor
    commit(db)
    db.refresh(rfq)
    log.info("rfq_issued", extra={"event": "rfq_issued", "rfq_id": rfq.id, "actor_id": principal.sub})
    return rfq


def close(db: Session, principal: TokenClaims, rfq_id: str) -> Rfq:
    rfq = get_rfq(db, rfq_id, lock=True)
    if rfq.status != RfqStatus.ISSUED.value:
        raise err(409, f"Only an issued RFQ can be closed. This one is {rfq.status}.")
    _close(rfq, principal, "Closed by procurement")
    event(db, "rfq_closed", rfq, actor_id=principal.sub)
    commit(db)
    db.refresh(rfq)
    return rfq


def _close(rfq: Rfq, principal: TokenClaims, note: str) -> None:
    previous = rfq.status
    rfq.status, rfq.closed_at = RfqStatus.CLOSED.value, utcnow()
    rfq.version += 1
    log_history(rfq, principal, "closed", previous, note)


def cancel(db: Session, principal: TokenClaims, rfq_id: str, reason: str) -> Rfq:
    rfq = get_rfq(db, rfq_id, lock=True)
    if rfq.status == RfqStatus.AWARDED.value:
        raise err(409, "Revoke the award before cancelling this RFQ.")
    if rfq.status == RfqStatus.CANCELLED.value:
        raise err(409, "This RFQ is already cancelled.")
    previous = rfq.status
    rfq.status, rfq.cancel_reason, rfq.active_request_id = RfqStatus.CANCELLED.value, reason, None  # frees the purchase request for a new RFQ
    rfq.version += 1
    log_history(rfq, principal, "cancelled", previous, reason)
    event(db, "rfq_cancelled", rfq, actor_id=principal.sub, reason=reason)
    commit(db)
    db.refresh(rfq)
    return rfq


def extend(db: Session, principal: TokenClaims, rfq_id: str, body: ExtendIn, settings: Settings) -> Rfq:
    rfq = get_rfq(db, rfq_id, lock=True)
    now = utcnow()
    if rfq.status != RfqStatus.ISSUED.value:
        raise err(409, f"Only an issued RFQ can have its deadline extended. This one is {rfq.status}.")
    if rfq.deadline <= now:
        raise err(409, "The deadline has passed and prices may already have been opened, so it cannot be extended. Issue a new RFQ instead.")
    _stale(rfq, body.version)
    if body.deadline <= rfq.deadline:
        raise err(422, "The new deadline must be later than the current one.")
    _check_deadline(settings, body.deadline, now)
    old, rfq.deadline = rfq.deadline, body.deadline
    rfq.version += 1
    log_history(rfq, principal, "deadline_extended", rfq.status, f"Deadline moved from {old:%Y-%m-%d %H:%M} to {body.deadline:%Y-%m-%d %H:%M} UTC")
    event(db, "rfq_deadline_extended", rfq, actor_id=principal.sub, deadline=body.deadline.isoformat())
    commit(db)
    db.refresh(rfq)
    return rfq


# ---- invitations -----------------------------------------------------------------------------------
def invite(db: Session, principal: TokenClaims, rfq_id: str, vendor_ids: list[str], clients: Clients) -> Rfq:
    rfq = get_rfq(db, rfq_id, lock=True)
    now = utcnow()
    if rfq.status not in (RfqStatus.DRAFT.value, RfqStatus.ISSUED.value) or (rfq.status == RfqStatus.ISSUED.value and rfq.deadline <= now):
        raise err(409, "Vendors can only be invited to a draft RFQ, or to an issued one before its deadline.")
    live = {i.vendor_id: i for i in rfq.invitations}
    already = [live[v].vendor_name for v in vendor_ids if v in live and live[v].status == InvitationStatus.INVITED.value]
    if already:
        raise err(409, "Already invited: " + ", ".join(already) + ".")
    if len([i for i in rfq.invitations if i.status == InvitationStatus.INVITED.value]) + len(vendor_ids) > MAX_INVITATIONS:
        raise err(422, f"An RFQ can have at most {MAX_INVITATIONS} invited vendors.")
    found = vendor_lookup(clients, vendor_ids)
    missing = [v for v in vendor_ids if v not in found]
    if missing:
        raise err(422, "These vendors do not exist: " + ", ".join(missing) + ".")
    unverified = [found[v]["legal_name"] for v in vendor_ids if found[v]["status"] != "verified"]
    if unverified:
        raise err(422, "Only verified vendors can be invited. Not verified: " + ", ".join(unverified) + ".")
    for vid in vendor_ids:
        v = found[vid]
        sent = now if rfq.status == RfqStatus.ISSUED.value else None
        if vid in live:  # a withdrawn or declined invitation is invited again rather than duplicated
            inv = live[vid]
            inv.status, inv.invited_by_id, inv.invited_by_name, inv.invited_at = InvitationStatus.INVITED.value, principal.sub, principal.name or "Unknown", now
            inv.sent_at, inv.responded_at, inv.withdrawn_at = sent, None, None
        else:
            rfq.invitations.append(Invitation(vendor_id=vid, vendor_number=v["number"], vendor_name=v["legal_name"], invited_by_id=principal.sub,
                                              invited_by_name=principal.name or "Unknown", invited_at=now, sent_at=sent))
    names = ", ".join(found[v]["legal_name"] for v in vendor_ids)
    log_history(rfq, principal, "vendors_invited", rfq.status, f"Invited: {names}")
    event(db, "vendors_invited", rfq, actor_id=principal.sub, vendor_ids=vendor_ids, sent=rfq.status == RfqStatus.ISSUED.value)  # Phase 10: notify when sent
    commit(db)
    db.refresh(rfq)
    return rfq


def withdraw_invitation(db: Session, principal: TokenClaims, rfq_id: str, invitation_id: str) -> Rfq:
    rfq = get_rfq(db, rfq_id, lock=True)
    inv = next((i for i in rfq.invitations if i.id == invitation_id), None)
    if inv is None:
        raise err(404, "Invitation not found.")
    if rfq.status not in (RfqStatus.DRAFT.value, RfqStatus.ISSUED.value, RfqStatus.CLOSED.value):
        raise err(409, f"Invitations cannot be changed on an RFQ that is {rfq.status}.")
    if inv.status != InvitationStatus.INVITED.value:
        raise err(409, f"This invitation is already {inv.status}.")
    q = db.scalar(select(Quotation).where(Quotation.rfq_id == rfq.id, Quotation.vendor_id == inv.vendor_id))
    if q is not None and q.status != QuotationStatus.DRAFT.value:
        raise err(409, "This vendor has already submitted a quotation, so the invitation cannot be withdrawn.")
    inv.status, inv.withdrawn_at = InvitationStatus.WITHDRAWN.value, utcnow()
    log_history(rfq, principal, "invitation_withdrawn", rfq.status, f"Withdrew the invitation to {inv.vendor_name}")
    event(db, "invitation_withdrawn", rfq, actor_id=principal.sub, vendor_id=inv.vendor_id)
    commit(db)
    db.refresh(rfq)
    return rfq


# ---- staff queries ---------------------------------------------------------------------------------
def list_rfqs(db: Session, *, status_: str | None, q: str | None, sort: str, order: str, page: int, page_size: int) -> tuple[list[Rfq], int]:
    stmt = select(Rfq)
    if status_:
        stmt = stmt.where(Rfq.status == status_)
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(or_(func.lower(Rfq.title).like(like, escape="\\"), func.lower(Rfq.number).like(like, escape="\\"),
                              func.lower(Rfq.purchase_request_number).like(like, escape="\\")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = {"created_at": Rfq.created_at, "deadline": Rfq.deadline, "number": Rfq.number, "title": Rfq.title}[sort]
    rows = db.scalars(stmt.order_by(col.desc() if order == "desc" else col.asc(), Rfq.id).offset((page - 1) * page_size).limit(page_size)).all()
    return list(rows), total


def submitted_counts(db: Session, rfq_ids: list[str]) -> dict[str, int]:
    if not rfq_ids:
        return {}
    rows = db.execute(select(Quotation.rfq_id, func.count()).where(Quotation.rfq_id.in_(rfq_ids), Quotation.status.in_(LIVE_QUOTATION)).group_by(Quotation.rfq_id))
    return {r: n for r, n in rows}


def summary(db: Session) -> tuple[dict[str, int], int]:
    counts = {s.value: 0 for s in RfqStatus}
    for st, n in db.execute(select(Rfq.status, func.count()).group_by(Rfq.status)):
        counts[st] = n
    now = utcnow()
    waiting = db.scalar(select(func.count()).select_from(Rfq).where(or_(Rfq.status == RfqStatus.CLOSED.value, (Rfq.status == RfqStatus.ISSUED.value) & (Rfq.deadline <= now)))) or 0
    return counts, waiting


def eligible_requests(db: Session, clients: Clients, q: str | None, page: int, page_size: int) -> dict:
    """Approved purchase requests, read from the purchase request service, marked with any RFQ already in progress for them."""
    params = {"page": page, "page_size": page_size, **({"q": q} if q and q.strip() else {})}
    data = call(clients.request_service().get, "/internal/v1/purchase-requests/approved", params=params)
    ids = [r["id"] for r in data["items"]]
    live = {r.active_request_id: r for r in db.scalars(select(Rfq).where(Rfq.active_request_id.in_(ids)))} if ids else {}
    return {"total": data["total"], "page": data["page"], "page_size": data["page_size"],
            "items": [{**r, "item_count": len(r["items"]), "rfq_id": live[r["id"]].id if r["id"] in live else None,
                       "rfq_number": live[r["id"]].number if r["id"] in live else None} for r in data["items"]]}


def active_selection(db: Session, rfq_id: str) -> Selection | None:
    return db.scalar(select(Selection).where(Selection.rfq_id == rfq_id, Selection.status == SelectionStatus.AWARDED.value))


# ---- the vendor's side -----------------------------------------------------------------------------
def invitation_for(db: Session, vendor_id: str, rfq_id: str) -> tuple[Rfq, Invitation]:
    """The RFQ and invitation only if this vendor was invited and the RFQ has been sent. Anything else is a 404, so a vendor
    cannot learn that another RFQ exists."""
    row = db.execute(select(Rfq, Invitation).join(Invitation, Invitation.rfq_id == Rfq.id).where(
        Rfq.id == rfq_id, Invitation.vendor_id == vendor_id, Invitation.sent_at.is_not(None), Invitation.status != InvitationStatus.WITHDRAWN.value)).first()
    if row is None:
        raise err(404, "RFQ not found.")
    return row[0], row[1]


def quote_block(rfq: Rfq, inv: Invitation, vendor: dict, now: datetime) -> tuple[int, str] | None:
    """Why this vendor cannot quote right now (HTTP status, message), or None if it can."""
    if rfq.status == RfqStatus.CANCELLED.value:
        return 409, "This RFQ was cancelled."
    if rfq.status != RfqStatus.ISSUED.value or rfq.deadline <= now:
        return 409, "The deadline has passed. This RFQ is no longer taking quotations."
    if inv.status == InvitationStatus.DECLINED.value:
        return 409, "You declined this invitation."
    if vendor["status"] != "verified":
        return 403, "Your vendor profile is not verified, so you cannot send quotations."
    return None


def list_invited(db: Session, vendor: dict, page: int, page_size: int) -> tuple[list[tuple[Rfq, Invitation, Quotation | None]], int]:
    base = select(Rfq, Invitation).join(Invitation, Invitation.rfq_id == Rfq.id).where(
        Invitation.vendor_id == vendor["id"], Invitation.sent_at.is_not(None), Invitation.status != InvitationStatus.WITHDRAWN.value)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(base.order_by(Rfq.deadline.desc(), Rfq.id).offset((page - 1) * page_size).limit(page_size)).all()
    quotes = {q.rfq_id: q for q in db.scalars(select(Quotation).where(Quotation.vendor_id == vendor["id"], Quotation.rfq_id.in_([r.id for r, _ in rows])))} if rows else {}
    return [(r, i, quotes.get(r.id)) for r, i in rows], total


def quotation_of(db: Session, rfq_id: str, vendor_id: str) -> Quotation | None:
    return db.scalar(select(Quotation).where(Quotation.rfq_id == rfq_id, Quotation.vendor_id == vendor_id))


def invitation_of(db: Session, rfq_id: str, vendor_id: str) -> Invitation | None:
    return db.scalar(select(Invitation).where(Invitation.rfq_id == rfq_id, Invitation.vendor_id == vendor_id))


def decline(db: Session, vendor: dict, rfq_id: str) -> Invitation:
    rfq = get_rfq(db, rfq_id, lock=True)
    inv = next((i for i in rfq.invitations if i.vendor_id == vendor["id"] and i.sent_at is not None and i.status != InvitationStatus.WITHDRAWN.value), None)
    if inv is None:
        raise err(404, "RFQ not found.")
    if inv.status != InvitationStatus.INVITED.value:
        raise err(409, f"This invitation is already {inv.status}.")
    if rfq.status != RfqStatus.ISSUED.value or rfq.deadline <= utcnow():
        raise err(409, "This RFQ is no longer taking responses.")
    q = db.scalar(select(Quotation).where(Quotation.rfq_id == rfq.id, Quotation.vendor_id == vendor["id"]))
    if q is not None and q.status != QuotationStatus.DRAFT.value:
        raise err(409, "You have submitted a quotation. Withdraw it before declining.")
    inv.status, inv.responded_at = InvitationStatus.DECLINED.value, utcnow()
    event(db, "invitation_declined", rfq, vendor_id=vendor["id"])
    commit(db)
    db.refresh(inv)
    return inv


# ---- quotations ------------------------------------------------------------------------------------
def missing_lines(q: Quotation) -> list[int]:
    return [i.line_no for i in q.items if i.unit_price is None]


def is_complete(q: Quotation) -> bool:
    return bool(q.items) and not missing_lines(q)


def problems_for_submit(q: Quotation, rfq: Rfq) -> list[str]:
    out: list[str] = []
    if not q.lead_time_days:
        out.append("Enter the delivery lead time in days.")
    if q.valid_until is None:
        out.append("Enter how long the quotation is valid.")
    elif q.valid_until < max(utcnow().date(), rfq.deadline.date()):
        out.append("The quotation must stay valid at least until the RFQ deadline.")
    if all(i.unit_price is None for i in q.items):
        out.append("Price at least one item.")
    return out


def _apply_quote(q: Quotation, rfq: Rfq, body: QuotationIn, db: Session) -> None:
    """Copies what the vendor may set. Quantities always come from the RFQ, and every RFQ line gets a row, priced or not."""
    by_id = {i.id: i for i in rfq.items}
    unknown = [li.rfq_item_id for li in body.items if li.rfq_item_id not in by_id]
    if unknown:
        raise err(422, "These items are not on the RFQ: " + ", ".join(unknown) + ".")
    sent = {li.rfq_item_id: li for li in body.items}
    if body.valid_until is not None and body.valid_until < max(utcnow().date(), rfq.deadline.date()):
        raise err(422, "The quotation must stay valid at least until the RFQ deadline.")
    if body.valid_until is not None and body.valid_until > utcnow().date() + timedelta(days=730):
        raise err(422, "A quotation cannot be valid for more than two years.")
    q.currency, q.lead_time_days, q.valid_until, q.payment_terms_days, q.terms = body.currency, body.lead_time_days, body.valid_until, body.payment_terms_days, body.terms
    if q.items:
        q.items = []
        db.flush()  # delete the old lines first: (quotation, RFQ item) is unique, and the new rows would otherwise be inserted before the old ones go
    total = Decimal("0.00")
    for it in rfq.items:
        li = sent.get(it.id)
        price = li.unit_price if li else None
        lt = line_total(it.quantity, price) if price is not None else None
        if lt is not None:
            total += lt
        q.items.append(QuotationItem(rfq_item_id=it.id, line_no=it.line_no, quantity=it.quantity, unit_price=price, line_total=lt, note=li.note if li else None))
    q.total_amount = total


def _own_quotation(db: Session, vendor: dict, quotation_id: str, *, lock: bool = False) -> Quotation:
    stmt = select(Quotation).where(Quotation.id == quotation_id, Quotation.vendor_id == vendor["id"])
    q = db.scalar(stmt.with_for_update() if lock else stmt)
    if q is None:
        raise err(404, "Quotation not found.")  # the same answer whether it does not exist or belongs to another vendor
    return q


def _require_open_for_quoting(rfq: Rfq, inv: Invitation, vendor: dict) -> None:
    block = quote_block(rfq, inv, vendor, utcnow())
    if block:
        raise err(*block)


def create_quotation(db: Session, principal: TokenClaims, vendor: dict, body: QuotationCreate) -> Quotation:
    rfq, inv = invitation_for(db, vendor["id"], body.rfq_id)
    rfq = get_rfq(db, rfq.id, lock=True)  # lock so two first drafts cannot interleave
    _require_open_for_quoting(rfq, inv, vendor)
    if db.scalar(select(Quotation.id).where(Quotation.rfq_id == rfq.id, Quotation.vendor_id == vendor["id"])) is not None:
        raise err(409, "You already have a quotation for this RFQ. Open it to continue.")
    number = next_number(db, "QTN", utcnow().year)
    q = Quotation(number=number, rfq_id=rfq.id, vendor_id=vendor["id"], vendor_number=vendor["number"], vendor_name=vendor["legal_name"],
                  created_by_id=principal.sub, created_by_name=principal.name or "Unknown", status=QuotationStatus.DRAFT.value)
    _apply_quote(q, rfq, body, db)
    db.add(q)
    commit(db, flush_only=True)
    event(db, "quotation_drafted", rfq, vendor_id=vendor["id"], quotation_id=q.id)
    commit(db)
    db.refresh(q)
    return q


def update_quotation(db: Session, vendor: dict, quotation_id: str, body: QuotationIn, version: int) -> Quotation:
    q = _own_quotation(db, vendor, quotation_id, lock=True)
    rfq, inv = invitation_for(db, vendor["id"], q.rfq_id)
    if q.status != QuotationStatus.DRAFT.value:
        raise err(409, "Only a draft can be edited. Withdraw a submitted quotation to change it.")
    if q.version != version:
        raise err(409, "This quotation was changed somewhere else. Reload it and try again.")
    _require_open_for_quoting(rfq, inv, vendor)
    _apply_quote(q, rfq, body, db)
    q.version += 1
    commit(db)
    db.refresh(q)
    return q


def submit_quotation(db: Session, vendor: dict, quotation_id: str) -> Quotation:
    q = _own_quotation(db, vendor, quotation_id, lock=True)
    rfq, inv = invitation_for(db, vendor["id"], q.rfq_id)
    if q.status != QuotationStatus.DRAFT.value:
        raise err(409, f"This quotation is already {q.status.replace('_', ' ')}.")  # a second submit never creates a second quotation
    _require_open_for_quoting(rfq, inv, vendor)
    problems = problems_for_submit(q, rfq)
    if problems:
        raise err(422, problems)
    q.status, q.submitted_at = QuotationStatus.SUBMITTED.value, utcnow()
    q.version += 1
    event(db, "quotation_submitted", rfq, vendor_id=vendor["id"], quotation_id=q.id, revision=q.revision)  # Phase 10: notify procurement
    commit(db)
    db.refresh(q)
    log.info("quotation_submitted", extra={"event": "quotation_submitted", "rfq_id": rfq.id, "quotation_id": q.id})
    return q


def withdraw_quotation(db: Session, vendor: dict, quotation_id: str) -> Quotation:
    q = _own_quotation(db, vendor, quotation_id, lock=True)
    rfq, inv = invitation_for(db, vendor["id"], q.rfq_id)
    if q.status != QuotationStatus.SUBMITTED.value:
        raise err(409, "Only a submitted quotation can be withdrawn for changes.")
    _require_open_for_quoting(rfq, inv, vendor)
    q.status, q.submitted_at = QuotationStatus.DRAFT.value, None
    q.revision += 1
    q.version += 1
    event(db, "quotation_withdrawn", rfq, vendor_id=vendor["id"], quotation_id=q.id)
    commit(db)
    db.refresh(q)
    return q


def my_quotations(db: Session, vendor: dict, page: int, page_size: int) -> tuple[list[tuple[Quotation, Rfq]], int]:
    base = select(Quotation, Rfq).join(Rfq, Rfq.id == Quotation.rfq_id).where(Quotation.vendor_id == vendor["id"])
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(base.order_by(Quotation.updated_at.desc(), Quotation.id).offset((page - 1) * page_size).limit(page_size)).all()
    return [(q, r) for q, r in rows], total


def get_quotation_for_staff(db: Session, quotation_id: str) -> tuple[Quotation, Rfq]:
    q = db.scalar(select(Quotation).where(Quotation.id == quotation_id))
    if q is None or q.status not in LIVE_QUOTATION:
        raise err(404, "Quotation not found.")  # drafts are private to the vendor
    rfq = get_rfq(db, q.rfq_id)
    if not quotations_open(rfq, utcnow()):
        raise err(409, "Quotations stay sealed until the deadline passes or the RFQ is closed.")
    return q, rfq


def vendor_get_quotation(db: Session, vendor: dict, quotation_id: str) -> tuple[Quotation, Rfq]:
    q = _own_quotation(db, vendor, quotation_id)
    return q, get_rfq(db, q.rfq_id)


def quotation_flags(q: Quotation, rfq: Rfq, inv: Invitation | None, vendor: dict | None) -> tuple[bool, bool, bool]:
    """can_edit, can_submit, can_withdraw for the vendor, using the same rule the commands enforce."""
    if vendor is None or inv is None or quote_block(rfq, inv, vendor, utcnow()):
        return False, False, False
    draft = q.status == QuotationStatus.DRAFT.value
    return draft, draft and not problems_for_submit(q, rfq), q.status == QuotationStatus.SUBMITTED.value
