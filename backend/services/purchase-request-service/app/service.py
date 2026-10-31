"""Business rules for purchase requests. Routers stay thin; everything that decides who may do what lives here."""
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from procurehub_common.contracts.approval import DecisionNotice
from procurehub_common.permissions import has_permission
from procurehub_common.tokens import TokenClaims
from sqlalchemy import ColumnElement, false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    NumberSequence,
    PurchaseRequest,
    PurchaseRequestDocument,
    PurchaseRequestHistory,
    PurchaseRequestItem,
    Status,
    utcnow,
)
from .schemas import MAX_DOCUMENTS, CancelIn, DocumentIn, ItemIn, RequestIn

log = logging.getLogger("purchase_requests")
CENT = Decimal("0.01")

SORTABLE = {"created_at": PurchaseRequest.created_at, "total_amount": PurchaseRequest.total_amount, "needed_by": PurchaseRequest.needed_by,
            "number": PurchaseRequest.number, "status": PurchaseRequest.status, "updated_at": PurchaseRequest.updated_at}


def line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(CENT, rounding=ROUND_HALF_UP)


def _err(code: int, detail: str | list[str]) -> HTTPException:
    return HTTPException(code, detail)


# ---- who can see what ------------------------------------------------------------------------------
def scope(principal: TokenClaims) -> ColumnElement[bool]:
    """Employees see only their own requests; procurement sees only approved ones; nobody else sees any."""
    if has_permission(principal.role, "purchase_request:read_own"):
        return PurchaseRequest.requester_id == principal.sub
    if has_permission(principal.role, "purchase_request:read_approved"):
        return PurchaseRequest.status == Status.APPROVED.value
    return false()


def get_visible(db: Session, principal: TokenClaims, request_id: str) -> PurchaseRequest:
    req = db.scalar(select(PurchaseRequest).where(PurchaseRequest.id == request_id, scope(principal)))
    if req is None:
        raise _err(status.HTTP_404_NOT_FOUND, "Purchase request not found.")  # same answer whether it does not exist or is not yours
    return req


def _get_own_for_write(db: Session, principal: TokenClaims, request_id: str) -> PurchaseRequest:
    """Only the requester may change a request. The row is locked so two edits cannot interleave."""
    req = db.scalar(select(PurchaseRequest).where(PurchaseRequest.id == request_id, PurchaseRequest.requester_id == principal.sub).with_for_update())
    if req is None:
        raise _err(status.HTTP_404_NOT_FOUND, "Purchase request not found.")
    return req


# ---- numbering -------------------------------------------------------------------------------------
def next_number(db: Session, year: int) -> str:
    """PR-<year>-<6 digits>. Call before adding anything else to the session."""
    for _ in range(4):
        seq = db.scalar(select(NumberSequence).where(NumberSequence.year == year).with_for_update())
        if seq is not None:
            seq.last_value += 1
            db.flush()
            return f"PR-{year}-{seq.last_value:06d}"
        db.add(NumberSequence(year=year, last_value=0))
        try:
            db.flush()
        except IntegrityError:  # another request created the counter first; try again and lock it
            db.rollback()
    raise RuntimeError("could not allocate a request number")


# ---- helpers ---------------------------------------------------------------------------------------
def _apply(req: PurchaseRequest, body: RequestIn) -> None:
    req.title, req.justification, req.department = body.title, body.justification, body.department
    req.priority, req.needed_by, req.currency = body.priority.value, body.needed_by, body.currency
    req.items = [_item(i, n) for n, i in enumerate(body.items, start=1)]
    req.total_amount = sum((line_total(i.quantity, i.unit_price) for i in body.items), Decimal("0.00"))


def _item(i: ItemIn, line_no: int) -> PurchaseRequestItem:
    return PurchaseRequestItem(line_no=line_no, description=i.description, quantity=i.quantity, unit=i.unit, unit_price=i.unit_price, notes=i.notes)


def _log_change(req: PurchaseRequest, actor_id: str, actor_name: str, from_status: str | None, to_status: str, note: str | None = None) -> None:
    req.history.append(PurchaseRequestHistory(
        seq=len(req.history) + 1, from_status=from_status, to_status=to_status, actor_id=actor_id, actor_name=actor_name or "Unknown", note=note))


def _history(req: PurchaseRequest, principal: TokenClaims, from_status: str | None, to_status: str, note: str | None = None) -> None:
    _log_change(req, principal.sub, principal.name, from_status, to_status, note)


def _require_draft(req: PurchaseRequest, action: str) -> None:
    if req.status != Status.DRAFT.value:
        raise _err(status.HTTP_409_CONFLICT, f"Only drafts can be {action}. This request is {req.status}.")


# ---- commands --------------------------------------------------------------------------------------
def create(db: Session, principal: TokenClaims, body: RequestIn) -> PurchaseRequest:
    number = next_number(db, date.today().year)
    req = PurchaseRequest(number=number, requester_id=principal.sub, requester_name=principal.name or "Unknown", requester_email=principal.email, status=Status.DRAFT.value)
    _apply(req, body)
    _history(req, principal, None, Status.DRAFT.value, "Draft created")
    db.add(req)
    db.commit()
    db.refresh(req)
    log.info("request_created", extra={"event": "request_created", "request_id": req.id, "number": number, "actor_id": principal.sub})
    return req


def update(db: Session, principal: TokenClaims, request_id: str, body: RequestIn, version: int) -> PurchaseRequest:
    req = _get_own_for_write(db, principal, request_id)
    _require_draft(req, "edited")
    if req.version != version:
        raise _err(status.HTTP_409_CONFLICT, "This request was changed somewhere else. Reload it and try again.")
    _apply(req, body)
    req.version += 1
    db.commit()
    db.refresh(req)
    return req


def problems_for_submit(req: PurchaseRequest) -> list[str]:
    out = []
    if not req.department.strip():
        out.append("Enter the department.")
    if not req.justification.strip():
        out.append("Explain why this purchase is needed.")
    if not req.items:
        out.append("Add at least one item.")
    elif req.total_amount <= 0:
        out.append("The total must be greater than zero.")
    if req.needed_by is not None and req.needed_by < date.today():
        out.append("The needed-by date has passed. Choose a new date.")
    return out


def submit(db: Session, principal: TokenClaims, request_id: str) -> PurchaseRequest:
    req = _get_own_for_write(db, principal, request_id)
    _require_draft(req, "submitted")
    problems = problems_for_submit(req)
    if problems:
        raise _err(422, problems)
    req.status = Status.SUBMITTED.value
    req.submitted_at = utcnow()
    req.version += 1
    _history(req, principal, Status.DRAFT.value, Status.SUBMITTED.value, "Submitted for approval")
    db.commit()
    db.refresh(req)
    log.info("request_submitted", extra={"event": "request_submitted", "request_id": req.id, "number": req.number, "actor_id": principal.sub, "total": str(req.total_amount)})
    return req


def cancel(db: Session, principal: TokenClaims, request_id: str, body: CancelIn) -> PurchaseRequest:
    req = _get_own_for_write(db, principal, request_id)
    if req.status == Status.DRAFT.value:
        raise _err(status.HTTP_409_CONFLICT, "Delete a draft instead of cancelling it.")
    if req.status != Status.SUBMITTED.value:
        raise _err(status.HTTP_409_CONFLICT, f"A {req.status} request cannot be cancelled.")
    previous = req.status
    req.status = Status.CANCELLED.value
    req.cancel_reason = body.reason
    req.version += 1
    _history(req, principal, previous, Status.CANCELLED.value, body.reason)
    db.commit()
    db.refresh(req)
    log.info("request_cancelled", extra={"event": "request_cancelled", "request_id": req.id, "actor_id": principal.sub})
    return req


def apply_decision(db: Session, request_id: str, notice: DecisionNotice) -> PurchaseRequest:
    """Called only by the Approval service. Idempotent: repeating the same decision changes nothing."""
    req = db.scalar(select(PurchaseRequest).where(PurchaseRequest.id == request_id).with_for_update())
    if req is None:
        raise _err(status.HTTP_404_NOT_FOUND, "Purchase request not found.")
    if req.status == notice.decision:
        return req
    if req.status != Status.SUBMITTED.value:
        raise _err(status.HTTP_409_CONFLICT, f"Request is {req.status}; only a submitted request can be decided.")
    decided = notice.decided_at
    if decided.tzinfo is not None:
        decided = decided.astimezone(UTC).replace(tzinfo=None)
    previous = req.status
    req.status, req.decided_at, req.decided_by_name, req.decision_note = notice.decision, decided, notice.actor_name, notice.note
    req.version += 1
    _log_change(req, notice.actor_id, notice.actor_name, previous, notice.decision, notice.note or notice.decision.capitalize())
    db.commit()
    db.refresh(req)
    log.info("request_decided", extra={"event": "request_decided", "request_id": req.id, "number": req.number, "decision": notice.decision, "actor_id": notice.actor_id})
    return req


def delete_draft(db: Session, principal: TokenClaims, request_id: str) -> None:
    req = _get_own_for_write(db, principal, request_id)
    _require_draft(req, "deleted")
    db.delete(req)
    db.commit()
    log.info("draft_deleted", extra={"event": "draft_deleted", "request_id": request_id, "actor_id": principal.sub})


def add_document(db: Session, principal: TokenClaims, request_id: str, body: DocumentIn) -> PurchaseRequestDocument:
    req = _get_own_for_write(db, principal, request_id)
    _require_draft(req, "changed")
    if len(req.documents) >= MAX_DOCUMENTS:
        raise _err(status.HTTP_409_CONFLICT, f"A request can have at most {MAX_DOCUMENTS} documents.")
    doc = PurchaseRequestDocument(
        position=max((d.position for d in req.documents), default=0) + 1, file_name=body.file_name, content_type=body.content_type,
        size_bytes=body.size_bytes, storage_key=f"purchase-requests/{req.id}/{uuid4()}", content_stored=False)
    req.documents.append(doc)
    db.commit()
    return doc


def remove_document(db: Session, principal: TokenClaims, request_id: str, document_id: str) -> None:
    req = _get_own_for_write(db, principal, request_id)
    _require_draft(req, "changed")
    doc = next((d for d in req.documents if d.id == document_id), None)
    if doc is None:
        raise _err(status.HTTP_404_NOT_FOUND, "Document not found.")
    req.documents.remove(doc)
    db.commit()


# ---- queries ---------------------------------------------------------------------------------------
def _like(term: str) -> str:
    return "%" + term.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_requests(db: Session, principal: TokenClaims, *, status_: str | None, priority: str | None, q: str | None, created_from: date | None,
                  created_to: date | None, sort: str, order: str, page: int, page_size: int) -> tuple[list[PurchaseRequest], int]:
    stmt = select(PurchaseRequest).where(scope(principal))
    if status_:
        stmt = stmt.where(PurchaseRequest.status == status_)
    if priority:
        stmt = stmt.where(PurchaseRequest.priority == priority)
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(or_(func.lower(PurchaseRequest.number).like(like, escape="\\"), func.lower(PurchaseRequest.title).like(like, escape="\\"),
                              func.lower(PurchaseRequest.requester_name).like(like, escape="\\")))
    if created_from:
        stmt = stmt.where(PurchaseRequest.created_at >= datetime.combine(created_from, datetime.min.time()))
    if created_to:
        stmt = stmt.where(PurchaseRequest.created_at < datetime.combine(created_to + timedelta(days=1), datetime.min.time()))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = SORTABLE[sort]
    ordering = [col.desc() if order == "desc" else col.asc(), PurchaseRequest.id]
    rows = db.scalars(stmt.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)).all()
    return list(rows), total


def summary(db: Session, principal: TokenClaims) -> tuple[dict[str, int], dict[str, Decimal], list[tuple[str, int]]]:
    counts = {s.value: 0 for s in Status}
    for st, n in db.execute(select(PurchaseRequest.status, func.count()).where(scope(principal)).group_by(PurchaseRequest.status)):
        counts[st] = n
    open_value: dict[str, Decimal] = {}
    for cur, total in db.execute(select(PurchaseRequest.currency, func.sum(PurchaseRequest.total_amount))
                                 .where(scope(principal), PurchaseRequest.status == Status.SUBMITTED.value).group_by(PurchaseRequest.currency)):
        open_value[cur] = Decimal(total or 0).quantize(CENT)
    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    since = datetime(months[0][0], months[0][1], 1)
    per_month = {f"{y:04d}-{m:02d}": 0 for y, m in months}
    for (created,) in db.execute(select(PurchaseRequest.created_at).where(scope(principal), PurchaseRequest.created_at >= since)):
        key = f"{created.year:04d}-{created.month:02d}"
        if key in per_month:
            per_month[key] += 1
    return counts, open_value, list(per_month.items())
