"""Internal API for the Approval service. Not reachable through the public ingress; every call needs a service token."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from procurehub_common.contracts.approval import DecisionNotice
from procurehub_common.contracts.purchase_request import PurchaseRequestPage, PurchaseRequestRef
from procurehub_common.fastapi_support import service_caller
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import service
from ..database import get_db
from ..models import PurchaseRequest, Status


def _secret(request: Request) -> str | None:
    s = request.app.state.settings.internal_jwt_secret
    return s.get_secret_value() if s else None


router = APIRouter(prefix="/internal/v1", tags=["internal"], include_in_schema=False)
READERS = {"quotation-service", "purchase-order-service", "si-talker-service", "mcp-server"}  # services that may read requests


@router.post("/purchase-requests/{request_id}/decision")
def apply_decision(request_id: str, body: DecisionNotice, _: str = Depends(service_caller(_secret, {"approval-service"})), db: Session = Depends(get_db)):
    req = service.apply_decision(db, request_id, body)
    return {"status": req.status}


def to_ref(req: PurchaseRequest) -> PurchaseRequestRef:
    return PurchaseRequestRef.model_validate({
        "id": req.id, "number": req.number, "title": req.title, "justification": req.justification, "department": req.department, "priority": req.priority,
        "currency": req.currency, "total_amount": req.total_amount, "needed_by": req.needed_by, "status": req.status, "requester_name": req.requester_name,
        "decided_at": req.decided_at, "decided_by_name": req.decided_by_name,
        "items": [{"line_no": i.line_no, "description": i.description, "quantity": i.quantity, "unit": i.unit, "unit_price": i.unit_price,
                   "line_total": service.line_total(i.quantity, i.unit_price)} for i in req.items]})


@router.get("/purchase-requests/approved", response_model=PurchaseRequestPage)
def approved(q: str | None = Query(default=None, max_length=100), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
             _: str = Depends(service_caller(_secret, READERS)), db: Session = Depends(get_db)):
    """Approved requests, newest decision first. The RFQ service uses this to offer procurement the requests that can go out for quotation."""
    stmt = select(PurchaseRequest).where(PurchaseRequest.status == Status.APPROVED.value)
    if q and q.strip():
        like = service._like(q.strip())
        stmt = stmt.where(func.lower(PurchaseRequest.title).like(like, escape="\\") | func.lower(PurchaseRequest.number).like(like, escape="\\"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(PurchaseRequest.decided_at.desc(), PurchaseRequest.id).offset((page - 1) * page_size).limit(page_size)).all()
    return PurchaseRequestPage(items=[to_ref(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/purchase-requests/{request_id}", response_model=PurchaseRequestRef)
def get_request(request_id: str, _: str = Depends(service_caller(_secret, READERS)), db: Session = Depends(get_db)):
    req = db.scalar(select(PurchaseRequest).where(PurchaseRequest.id == request_id))
    if req is None:
        raise HTTPException(404, "Purchase request not found.")
    return to_ref(req)
