from fastapi import APIRouter, Depends, Query, Request
from procurehub_common.permissions import has_permission
from procurehub_common.tokens import TokenClaims
from sqlalchemy.orm import Session

from .. import outputs, service
from ..common import Clients, vendor_for_user
from ..database import get_db
from ..deps import require_any_permission
from ..schemas import MyQuotationPage, QuotationCreate, QuotationOut, QuotationUpdate

router = APIRouter(prefix="/api/v1/quotations", tags=["quotations"])

VENDOR = require_any_permission("quotation:submit")
EITHER = require_any_permission("quotation:submit", "quotation:compare")


def _clients(request: Request) -> Clients:
    return request.app.state.clients


def vendor_ctx(principal: TokenClaims = Depends(VENDOR), c: Clients = Depends(_clients)) -> dict:
    return vendor_for_user(c, principal)


def _invitation(db: Session, rfq_id: str, vendor_id: str):
    return service.invitation_of(db, rfq_id, vendor_id)


@router.get("/mine", response_model=MyQuotationPage)
def mine(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), vendor: dict = Depends(vendor_ctx), db: Session = Depends(get_db)):
    rows, total = service.my_quotations(db, vendor, page, page_size)
    return MyQuotationPage(items=[outputs.my_row(q, r) for q, r in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=QuotationOut, status_code=201)
def create(body: QuotationCreate, principal: TokenClaims = Depends(VENDOR), vendor: dict = Depends(vendor_ctx), db: Session = Depends(get_db)):
    q = service.create_quotation(db, principal, vendor, body)
    return outputs.quotation_out(q, service.get_rfq(db, q.rfq_id), _invitation(db, q.rfq_id, vendor["id"]), vendor)


@router.get("/{quotation_id}", response_model=QuotationOut)
def get(quotation_id: str, principal: TokenClaims = Depends(EITHER), db: Session = Depends(get_db), c: Clients = Depends(_clients)):
    """A vendor reads their own quotation. Procurement reads submitted ones, and only once prices are open."""
    if has_permission(principal.role, "quotation:compare"):
        q, rfq = service.get_quotation_for_staff(db, quotation_id)
        return outputs.quotation_out(q, rfq)
    vendor = vendor_for_user(c, principal)
    q, rfq = service.vendor_get_quotation(db, vendor, quotation_id)
    return outputs.quotation_out(q, rfq, _invitation(db, rfq.id, vendor["id"]), vendor)


def _mine(db: Session, q, vendor: dict) -> QuotationOut:
    rfq = service.get_rfq(db, q.rfq_id)
    return outputs.quotation_out(q, rfq, _invitation(db, rfq.id, vendor["id"]), vendor)


@router.put("/{quotation_id}", response_model=QuotationOut)
def update(quotation_id: str, body: QuotationUpdate, vendor: dict = Depends(vendor_ctx), db: Session = Depends(get_db)):
    return _mine(db, service.update_quotation(db, vendor, quotation_id, body, body.version), vendor)


@router.post("/{quotation_id}/submit", response_model=QuotationOut)
def submit(quotation_id: str, vendor: dict = Depends(vendor_ctx), db: Session = Depends(get_db)):
    return _mine(db, service.submit_quotation(db, vendor, quotation_id), vendor)


@router.post("/{quotation_id}/withdraw", response_model=QuotationOut)
def withdraw(quotation_id: str, vendor: dict = Depends(vendor_ctx), db: Session = Depends(get_db)):
    return _mine(db, service.withdraw_quotation(db, vendor, quotation_id), vendor)
