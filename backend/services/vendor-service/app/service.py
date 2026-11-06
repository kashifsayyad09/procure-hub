"""Business rules for vendors. Routers stay thin; everything that decides who may do what lives here."""
import json
import logging
from datetime import date, datetime

from fastapi import HTTPException, status
from procurehub_common.contracts.vendor import VendorRef
from procurehub_common.permissions import has_permission
from procurehub_common.tokens import TokenClaims
from sqlalchemy import ColumnElement, false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .catalog import CATEGORIES
from .models import NumberSequence, Vendor, VendorCategory, VendorContact, VendorEvent, VendorHistory, VendorStatus, utcnow
from .schemas import ProfileIn, ReasonIn, ReviewIn

log = logging.getLogger("vendors")

SORTABLE = {"created_at": Vendor.created_at, "legal_name": Vendor.legal_name, "number": Vendor.number, "status": Vendor.status,
            "submitted_at": Vendor.submitted_at, "verified_at": Vendor.verified_at}
# Changing any of these on a verified vendor means a reviewer must look again.
IDENTITY_FIELDS = {"legal_name": "company name", "tax_id": "tax ID", "registration_number": "registration number", "country": "country"}
EDITABLE_BY_OWNER = {VendorStatus.DRAFT.value, VendorStatus.PENDING.value, VendorStatus.VERIFIED.value, VendorStatus.REJECTED.value}


def _err(code: int, detail: str | list[str]) -> HTTPException:
    return HTTPException(code, detail)


def is_staff(principal: TokenClaims) -> bool:
    return has_permission(principal.role, "vendor:read")


def can_manage(principal: TokenClaims) -> bool:
    return has_permission(principal.role, "vendor:manage")


# ---- who can see what ------------------------------------------------------------------------------
def scope(principal: TokenClaims) -> ColumnElement[bool]:
    """Procurement and administrators see every vendor. A vendor user sees only the record they own. Nobody else sees any."""
    if has_permission(principal.role, "vendor:read"):
        return Vendor.id.is_not(None)
    if has_permission(principal.role, "vendor_profile:manage"):
        return Vendor.owner_id == principal.sub
    return false()


def get_visible(db: Session, principal: TokenClaims, vendor_id: str, *, lock: bool = False) -> Vendor:
    stmt = select(Vendor).where(Vendor.id == vendor_id, scope(principal))
    v = db.scalar(stmt.with_for_update() if lock else stmt)
    if v is None:
        raise _err(status.HTTP_404_NOT_FOUND, "Vendor not found.")  # same answer whether it does not exist or is not yours
    return v


def get_own(db: Session, principal: TokenClaims) -> Vendor:
    v = db.scalar(select(Vendor).where(Vendor.owner_id == principal.sub))
    if v is None:
        raise _err(status.HTTP_404_NOT_FOUND, "You have not registered a vendor profile yet.")
    return v


# ---- numbering -------------------------------------------------------------------------------------
def next_number(db: Session, year: int) -> str:
    """VND-<year>-<6 digits>. Call before adding anything else to the session."""
    for _ in range(4):
        seq = db.scalar(select(NumberSequence).where(NumberSequence.year == year).with_for_update())
        if seq is not None:
            seq.last_value += 1
            db.flush()
            return f"VND-{year}-{seq.last_value:06d}"
        db.add(NumberSequence(year=year, last_value=0))
        try:
            db.flush()
        except IntegrityError:  # another request created the counter first; try again and lock it
            db.rollback()
    raise RuntimeError("could not allocate a vendor number")


# ---- helpers ---------------------------------------------------------------------------------------
def primary_contact(v: Vendor) -> VendorContact | None:
    return next((c for c in v.contacts if c.is_primary), v.contacts[0] if v.contacts else None)


def completeness(v: Vendor) -> tuple[int, list[str]]:
    """Returns the percentage complete and what is still missing. Submitting for verification needs all of it."""
    checks = [
        ("Company name", bool(v.legal_name.strip())), ("Tax ID", bool(v.tax_id)), ("Street address", bool(v.address_line1.strip())),
        ("City", bool(v.city.strip())), ("Country", bool(v.country)), ("At least one category", bool(v.categories)),
        ("A contact person with an email address", bool(v.contacts)),
    ]
    missing = [label for label, ok in checks if not ok]
    return round(100 * (len(checks) - len(missing)) / len(checks)), missing


def _event(db: Session, kind: str, v: Vendor, **extra) -> None:
    payload = {"vendor_id": v.id, "number": v.number, "legal_name": v.legal_name, "status": v.status, **extra}
    db.add(VendorEvent(type=kind, vendor_id=v.id, payload=json.dumps(payload, default=str)))


def _log(v: Vendor, principal: TokenClaims, action: str, from_status: str | None, note: str | None = None) -> None:
    v.history.append(VendorHistory(seq=len(v.history) + 1, action=action, from_status=from_status, to_status=v.status,
                                   actor_id=principal.sub, actor_name=principal.name or "Unknown", note=note))


def _apply(v: Vendor, body: ProfileIn, db: Session | None = None) -> None:
    v.legal_name, v.trade_name, v.tax_id, v.registration_number = body.legal_name, body.trade_name, body.tax_id, body.registration_number
    v.website, v.description = body.website, body.description
    v.address_line1, v.address_line2, v.city, v.state, v.postal_code = body.address_line1, body.address_line2, body.city, body.state, body.postal_code
    v.country, v.payment_terms_days, v.currency = body.country, body.payment_terms_days, body.currency
    if v.categories and db is not None:
        v.categories = []
        db.flush()  # delete the old rows first: (vendor, category) is unique, and an insert would otherwise run before the delete
    v.categories = [VendorCategory(position=n, category=c) for n, c in enumerate(body.categories, start=1)]
    v.contacts = [VendorContact(position=n, name=c.name, job_title=c.job_title, email=c.email, phone=c.phone, is_primary=c.is_primary)
                  for n, c in enumerate(body.contacts, start=1)]


def _tax_id_free(db: Session, tax_id: str | None, except_id: str | None = None) -> None:
    if not tax_id:
        return
    stmt = select(Vendor.id).where(Vendor.tax_id == tax_id)
    if except_id:
        stmt = stmt.where(Vendor.id != except_id)
    if db.scalar(stmt) is not None:
        raise _err(status.HTTP_409_CONFLICT, "A vendor with this tax ID is already registered. Contact procurement if this is your company.")


def _conflict(exc: IntegrityError) -> HTTPException:
    text = str(exc.orig).lower()
    if "tax_id" in text:
        return _err(status.HTTP_409_CONFLICT, "A vendor with this tax ID is already registered. Contact procurement if this is your company.")
    if "owner_id" in text:
        return _err(status.HTTP_409_CONFLICT, "You already have a vendor profile.")
    return _err(status.HTTP_409_CONFLICT, "This vendor could not be saved because it clashes with an existing record.")


def _commit(db: Session, *, flush_only: bool = False) -> None:
    """The unique indexes are the final guard against two requests racing past the checks above, whether the clash
    surfaces on flush or on commit."""
    try:
        db.flush() if flush_only else db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _conflict(exc) from None


# ---- commands --------------------------------------------------------------------------------------
def _create(db: Session, principal: TokenClaims, body: ProfileIn, owner_id: str | None) -> Vendor:
    if owner_id is not None and db.scalar(select(Vendor.id).where(Vendor.owner_id == owner_id)) is not None:
        raise _err(status.HTTP_409_CONFLICT, "You already have a vendor profile.")
    _tax_id_free(db, body.tax_id)
    number = next_number(db, date.today().year)
    v = Vendor(number=number, owner_id=owner_id, created_by_id=principal.sub, created_by_name=principal.name or "Unknown", status=VendorStatus.DRAFT.value)
    _apply(v, body)
    _log(v, principal, "created", None, "Registered by the vendor" if owner_id else "Registered by staff")
    db.add(v)
    _commit(db, flush_only=True)
    _event(db, "vendor_registered", v, actor_id=principal.sub, owned=owner_id is not None)
    _commit(db)
    db.refresh(v)
    log.info("vendor_registered", extra={"event": "vendor_registered", "vendor_id": v.id, "number": number, "actor_id": principal.sub})
    return v


def register_own(db: Session, principal: TokenClaims, body: ProfileIn) -> Vendor:
    return _create(db, principal, body, principal.sub)


def register_for(db: Session, principal: TokenClaims, body: ProfileIn) -> Vendor:
    return _create(db, principal, body, None)


def _writable(db: Session, principal: TokenClaims, vendor_id: str) -> Vendor:
    """The vendor's owner, or staff who manage vendors. The row is locked so two edits cannot interleave."""
    v = get_visible(db, principal, vendor_id, lock=True)
    if not is_staff(principal) and v.owner_id != principal.sub:
        raise _err(status.HTTP_404_NOT_FOUND, "Vendor not found.")
    return v


def _stale(v: Vendor, version: int) -> None:
    if v.version != version:
        raise _err(status.HTTP_409_CONFLICT, "This vendor was changed somewhere else. Reload it and try again.")


def update(db: Session, principal: TokenClaims, vendor_id: str, body: ProfileIn, version: int) -> Vendor:
    v = _writable(db, principal, vendor_id)
    _stale(v, version)
    if v.status == VendorStatus.SUSPENDED.value and not is_staff(principal):
        raise _err(status.HTTP_409_CONFLICT, "A suspended vendor cannot change its profile. Contact procurement.")
    _tax_id_free(db, body.tax_id, except_id=v.id)
    before = {f: getattr(v, f) for f in IDENTITY_FIELDS}
    _apply(v, body, db)
    changed = [label for f, label in IDENTITY_FIELDS.items() if before[f] != getattr(v, f)]
    previous = v.status
    if v.status == VendorStatus.VERIFIED.value and changed:
        v.status = VendorStatus.PENDING.value
        v.submitted_by_id, v.submitted_at, v.verified_at, v.verified_by_name = principal.sub, utcnow(), None, None
        note = "Changed after verification: " + ", ".join(changed) + ". A reviewer must verify the profile again."
        _log(v, principal, "reverification_required", previous, note)
        _event(db, "vendor_reverification_required", v, actor_id=principal.sub, changed=changed)
    else:
        _log(v, principal, "updated", previous, "Profile updated")
        _event(db, "vendor_updated", v, actor_id=principal.sub)
    v.version += 1
    _commit(db)
    db.refresh(v)
    log.info("vendor_updated", extra={"event": "vendor_updated", "vendor_id": v.id, "actor_id": principal.sub})
    return v


def problems_for_submit(v: Vendor) -> list[str]:
    return [f"Missing: {m}." for m in completeness(v)[1]]


def submit(db: Session, principal: TokenClaims, vendor_id: str) -> Vendor:
    v = _writable(db, principal, vendor_id)
    if v.status not in (VendorStatus.DRAFT.value, VendorStatus.REJECTED.value):
        raise _err(status.HTTP_409_CONFLICT, f"A {v.status} vendor cannot be submitted for verification.")
    problems = problems_for_submit(v)
    if problems:
        raise _err(422, problems)
    previous = v.status
    v.status, v.status_note = VendorStatus.PENDING.value, None
    v.submitted_by_id, v.submitted_at = principal.sub, utcnow()
    v.version += 1
    _log(v, principal, "submitted", previous, "Submitted for verification")
    _event(db, "vendor_submitted", v, actor_id=principal.sub)
    _commit(db)
    db.refresh(v)
    log.info("vendor_submitted", extra={"event": "vendor_submitted", "vendor_id": v.id, "actor_id": principal.sub})
    return v


def _reviewable(db: Session, principal: TokenClaims, vendor_id: str, version: int, *, expect: VendorStatus, verb: str) -> Vendor:
    v = get_visible(db, principal, vendor_id, lock=True)
    if v.status != expect.value:
        raise _err(status.HTTP_409_CONFLICT, f"Only a {expect.value} vendor can be {verb}. This vendor is {v.status}.")
    _stale(v, version)
    return v


def _not_own_submission(v: Vendor, principal: TokenClaims) -> None:
    if v.submitted_by_id == principal.sub:
        raise _err(status.HTTP_403_FORBIDDEN, "Another reviewer must decide on a profile you submitted.")


def verify(db: Session, principal: TokenClaims, vendor_id: str, body: ReviewIn) -> Vendor:
    v = _reviewable(db, principal, vendor_id, body.version, expect=VendorStatus.PENDING, verb="verified")
    _not_own_submission(v, principal)
    previous = v.status
    v.status, v.status_note = VendorStatus.VERIFIED.value, None
    v.verified_at, v.verified_by_name = utcnow(), principal.name or "Unknown"
    v.version += 1
    _log(v, principal, "verified", previous, body.note)
    _event(db, "vendor_verified", v, actor_id=principal.sub)
    db.commit()
    db.refresh(v)
    log.info("vendor_verified", extra={"event": "vendor_verified", "vendor_id": v.id, "actor_id": principal.sub})
    return v


def reject(db: Session, principal: TokenClaims, vendor_id: str, body: ReasonIn) -> Vendor:
    v = _reviewable(db, principal, vendor_id, body.version, expect=VendorStatus.PENDING, verb="rejected")
    _not_own_submission(v, principal)
    previous = v.status
    v.status, v.status_note = VendorStatus.REJECTED.value, body.reason
    v.version += 1
    _log(v, principal, "rejected", previous, body.reason)
    _event(db, "vendor_rejected", v, actor_id=principal.sub, reason=body.reason)
    db.commit()
    db.refresh(v)
    log.info("vendor_rejected", extra={"event": "vendor_rejected", "vendor_id": v.id, "actor_id": principal.sub})
    return v


def suspend(db: Session, principal: TokenClaims, vendor_id: str, body: ReasonIn) -> Vendor:
    v = _reviewable(db, principal, vendor_id, body.version, expect=VendorStatus.VERIFIED, verb="suspended")
    previous = v.status
    v.status, v.status_note = VendorStatus.SUSPENDED.value, body.reason
    v.version += 1
    _log(v, principal, "suspended", previous, body.reason)
    _event(db, "vendor_suspended", v, actor_id=principal.sub, reason=body.reason)
    db.commit()
    db.refresh(v)
    log.info("vendor_suspended", extra={"event": "vendor_suspended", "vendor_id": v.id, "actor_id": principal.sub})
    return v


def reinstate(db: Session, principal: TokenClaims, vendor_id: str, body: ReviewIn) -> Vendor:
    v = _reviewable(db, principal, vendor_id, body.version, expect=VendorStatus.SUSPENDED, verb="reinstated")
    previous = v.status
    v.status, v.status_note = VendorStatus.VERIFIED.value, None
    v.version += 1
    _log(v, principal, "reinstated", previous, body.note)
    _event(db, "vendor_reinstated", v, actor_id=principal.sub)
    db.commit()
    db.refresh(v)
    log.info("vendor_reinstated", extra={"event": "vendor_reinstated", "vendor_id": v.id, "actor_id": principal.sub})
    return v


# ---- what a caller may do next ---------------------------------------------------------------------
def actions_for(v: Vendor, principal: TokenClaims) -> tuple[list[str], str | None]:
    """Computed on the server from the same rules the commands enforce, so the screen never offers something that will be refused."""
    acts: list[str] = []
    blocked: str | None = None
    owner = v.owner_id == principal.sub and has_permission(principal.role, "vendor_profile:manage")
    manager = can_manage(principal)
    if (owner and v.status in EDITABLE_BY_OWNER) or manager:
        acts.append("edit")
    if (owner or manager) and v.status in (VendorStatus.DRAFT.value, VendorStatus.REJECTED.value):
        acts.append("submit")
    if has_permission(principal.role, "vendor:verify"):
        if v.status == VendorStatus.PENDING.value:
            if v.submitted_by_id == principal.sub:
                blocked = "Another reviewer must decide on a profile you submitted."
            else:
                acts += ["verify", "reject"]
        elif v.status == VendorStatus.VERIFIED.value:
            acts.append("suspend")
        elif v.status == VendorStatus.SUSPENDED.value:
            acts.append("reinstate")
    return acts, blocked


# ---- queries ---------------------------------------------------------------------------------------
def _like(term: str) -> str:
    return "%" + term.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_vendors(db: Session, principal: TokenClaims, *, status_: str | None, category: str | None, country: str | None, q: str | None,
                 sort: str, order: str, page: int, page_size: int) -> tuple[list[Vendor], int]:
    stmt = select(Vendor).where(scope(principal))
    if status_:
        stmt = stmt.where(Vendor.status == status_)
    if category:
        stmt = stmt.where(Vendor.id.in_(select(VendorCategory.vendor_id).where(VendorCategory.category == category)))
    if country:
        stmt = stmt.where(Vendor.country == country.upper())
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(or_(*(func.lower(c).like(like, escape="\\") for c in (Vendor.legal_name, Vendor.trade_name, Vendor.number, Vendor.tax_id, Vendor.city))))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = SORTABLE[sort]
    rows = db.scalars(stmt.order_by(col.desc() if order == "desc" else col.asc(), Vendor.id).offset((page - 1) * page_size).limit(page_size)).all()
    return list(rows), total


def summary(db: Session) -> tuple[dict[str, int], list[tuple[str, int]], list[tuple[str, int]]]:
    counts = {s.value: 0 for s in VendorStatus}
    for st, n in db.execute(select(Vendor.status, func.count()).group_by(Vendor.status)):
        counts[st] = n
    by_cat = db.execute(select(VendorCategory.category, func.count()).join(Vendor, Vendor.id == VendorCategory.vendor_id)
                        .where(Vendor.status == VendorStatus.VERIFIED.value).group_by(VendorCategory.category)
                        .order_by(func.count().desc(), VendorCategory.category)).all()
    today = date.today()
    months, y, m = [], today.year, today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    since = datetime(months[0][0], months[0][1], 1)
    per_month = {f"{y:04d}-{m:02d}": 0 for y, m in months}
    for (created,) in db.execute(select(Vendor.created_at).where(Vendor.created_at >= since)):
        key = f"{created.year:04d}-{created.month:02d}"
        if key in per_month:
            per_month[key] += 1
    return counts, [(c, n) for c, n in by_cat], list(per_month.items())


# ---- for other services ----------------------------------------------------------------------------
def to_ref(v: Vendor) -> VendorRef:
    pc = primary_contact(v)
    return VendorRef(id=v.id, number=v.number, legal_name=v.legal_name, trade_name=v.trade_name, status=v.status, country=v.country,  # type: ignore[arg-type]
                     currency=v.currency, payment_terms_days=v.payment_terms_days, categories=[c.category for c in v.categories],
                     primary_contact_name=pc.name if pc else None, primary_contact_email=pc.email if pc else None)


def lookup(db: Session, ids: list[str]) -> list[Vendor]:
    return list(db.scalars(select(Vendor).where(Vendor.id.in_(set(ids)))).all())


def category_options() -> list[dict[str, str]]:
    return [{"id": k, "label": v} for k, v in CATEGORIES.items()]
