from typing import Literal

from fastapi import APIRouter, Depends, Query
from procurehub_common.tokens import TokenClaims
from sqlalchemy.orm import Session

from .. import service
from ..catalog import CATEGORIES
from ..database import get_db
from ..deps import require_any_permission
from ..models import Vendor, VendorStatus
from ..schemas import (
    CategoryCount,
    CategoryOut,
    Completeness,
    ContactOut,
    HistoryOut,
    MonthCount,
    ProfileIn,
    ProfileUpdate,
    ReasonIn,
    ReviewIn,
    SummaryOut,
    VendorOut,
    VendorPage,
    VendorSummaryOut,
)

router = APIRouter(prefix="/api/v1/vendors", tags=["vendors"])

CAN_SEE = require_any_permission("vendor:read", "vendor_profile:manage")
CAN_BROWSE = require_any_permission("vendor:read")
CAN_REGISTER_SELF = require_any_permission("vendor_profile:manage")
CAN_MANAGE = require_any_permission("vendor:manage", "vendor_profile:manage")  # staff or the vendor's own user; the service narrows it
CAN_MANAGE_STAFF = require_any_permission("vendor:manage")
CAN_VERIFY = require_any_permission("vendor:verify")


def _summary(v: Vendor) -> VendorSummaryOut:
    pc = service.primary_contact(v)
    return VendorSummaryOut(
        id=v.id, number=v.number, legal_name=v.legal_name, trade_name=v.trade_name, status=v.status, country=v.country, city=v.city,
        categories=[c.category for c in v.categories], primary_contact_name=pc.name if pc else None, primary_contact_email=pc.email if pc else None,
        has_account=v.owner_id is not None, created_at=v.created_at, submitted_at=v.submitted_at, verified_at=v.verified_at)


def _out(v: Vendor, principal: TokenClaims) -> VendorOut:
    percent, missing = service.completeness(v)
    actions, blocked = service.actions_for(v, principal)
    return VendorOut(
        **_summary(v).model_dump(), tax_id=v.tax_id, registration_number=v.registration_number, website=v.website, description=v.description,
        address_line1=v.address_line1, address_line2=v.address_line2, state=v.state, postal_code=v.postal_code, payment_terms_days=v.payment_terms_days,
        currency=v.currency, status_note=v.status_note, verified_by_name=v.verified_by_name, created_by_name=v.created_by_name, version=v.version,
        updated_at=v.updated_at, contacts=[ContactOut.model_validate(c) for c in v.contacts], history=[HistoryOut.model_validate(h) for h in v.history],
        completeness=Completeness(percent=percent, missing=missing), actions=actions, blocked_reason=blocked)  # type: ignore[arg-type]


@router.get("/categories", response_model=list[CategoryOut])
def categories(_: TokenClaims = Depends(CAN_SEE)):
    return service.category_options()


@router.get("/summary", response_model=SummaryOut)
def get_summary(_: TokenClaims = Depends(CAN_BROWSE), db: Session = Depends(get_db)):
    counts, by_cat, monthly = service.summary(db)
    return SummaryOut(counts=counts, verified_by_category=[CategoryCount(category=c, count=n) for c, n in by_cat],
                      monthly=[MonthCount(month=m, count=n) for m, n in monthly])


@router.get("/me", response_model=VendorOut)
def get_mine(principal: TokenClaims = Depends(CAN_REGISTER_SELF), db: Session = Depends(get_db)):
    return _out(service.get_own(db, principal), principal)


@router.get("", response_model=VendorPage)
def list_vendors(
    status_: VendorStatus | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None, max_length=40),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    q: str | None = Query(default=None, max_length=100),
    sort: Literal["created_at", "legal_name", "number", "status", "submitted_at", "verified_at"] = "legal_name",
    order: Literal["asc", "desc"] = "asc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    principal: TokenClaims = Depends(CAN_BROWSE),
    db: Session = Depends(get_db),
):
    if category is not None and category not in CATEGORIES:
        return VendorPage(items=[], total=0, page=page, page_size=page_size)
    rows, total = service.list_vendors(db, principal, status_=status_.value if status_ else None, category=category, country=country, q=q,
                                       sort=sort, order=order, page=page, page_size=page_size)
    return VendorPage(items=[_summary(v) for v in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=VendorOut, status_code=201)
def register_own(body: ProfileIn, principal: TokenClaims = Depends(CAN_REGISTER_SELF), db: Session = Depends(get_db)):
    """A vendor user registers their own company. One record per vendor user."""
    return _out(service.register_own(db, principal, body), principal)


@router.post("/onboard", response_model=VendorOut, status_code=201)
def register_for_vendor(body: ProfileIn, principal: TokenClaims = Depends(CAN_MANAGE_STAFF), db: Session = Depends(get_db)):
    """Procurement or an administrator registers a vendor that has no account yet."""
    return _out(service.register_for(db, principal, body), principal)


@router.get("/{vendor_id}", response_model=VendorOut)
def get_vendor(vendor_id: str, principal: TokenClaims = Depends(CAN_SEE), db: Session = Depends(get_db)):
    return _out(service.get_visible(db, principal, vendor_id), principal)


@router.put("/{vendor_id}", response_model=VendorOut)
def update_vendor(vendor_id: str, body: ProfileUpdate, principal: TokenClaims = Depends(CAN_MANAGE), db: Session = Depends(get_db)):
    return _out(service.update(db, principal, vendor_id, body, body.version), principal)


@router.post("/{vendor_id}/submit", response_model=VendorOut)
def submit_vendor(vendor_id: str, principal: TokenClaims = Depends(CAN_MANAGE), db: Session = Depends(get_db)):
    return _out(service.submit(db, principal, vendor_id), principal)


@router.post("/{vendor_id}/verify", response_model=VendorOut)
def verify_vendor(vendor_id: str, body: ReviewIn, principal: TokenClaims = Depends(CAN_VERIFY), db: Session = Depends(get_db)):
    return _out(service.verify(db, principal, vendor_id, body), principal)


@router.post("/{vendor_id}/reject", response_model=VendorOut)
def reject_vendor(vendor_id: str, body: ReasonIn, principal: TokenClaims = Depends(CAN_VERIFY), db: Session = Depends(get_db)):
    return _out(service.reject(db, principal, vendor_id, body), principal)


@router.post("/{vendor_id}/suspend", response_model=VendorOut)
def suspend_vendor(vendor_id: str, body: ReasonIn, principal: TokenClaims = Depends(CAN_VERIFY), db: Session = Depends(get_db)):
    return _out(service.suspend(db, principal, vendor_id, body), principal)


@router.post("/{vendor_id}/reinstate", response_model=VendorOut)
def reinstate_vendor(vendor_id: str, body: ReviewIn, principal: TokenClaims = Depends(CAN_VERIFY), db: Session = Depends(get_db)):
    return _out(service.reinstate(db, principal, vendor_id, body), principal)
