from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from procurehub_common.tokens import TokenClaims
from sqlalchemy.orm import Session

from .. import service
from ..database import get_db
from ..deps import require_any_permission
from ..models import Priority, PurchaseRequest, Status
from ..schemas import (
    CancelIn,
    DocumentIn,
    DocumentOut,
    HistoryOut,
    ItemOut,
    MonthCount,
    RequestIn,
    RequestOut,
    RequestPage,
    RequestSummaryOut,
    RequestUpdate,
    SummaryOut,
)

router = APIRouter(prefix="/api/v1/purchase-requests", tags=["purchase-requests"])

CAN_READ = require_any_permission("purchase_request:read_own", "purchase_request:read_approved")
CAN_CREATE = require_any_permission("purchase_request:create")
CAN_SUBMIT = require_any_permission("purchase_request:submit")
CAN_UPLOAD = require_any_permission("document:upload")


def _summary(r: PurchaseRequest) -> RequestSummaryOut:
    data = {c: getattr(r, c) for c in RequestSummaryOut.model_fields if c != "item_count"}
    return RequestSummaryOut(**data, item_count=len(r.items))


def _out(r: PurchaseRequest) -> RequestOut:
    base = _summary(r).model_dump()
    items = [ItemOut(id=i.id, line_no=i.line_no, description=i.description, quantity=i.quantity, unit=i.unit, unit_price=i.unit_price, notes=i.notes,
                     line_total=service.line_total(i.quantity, i.unit_price)) for i in r.items]
    return RequestOut(**base, justification=r.justification, requester_id=r.requester_id, requester_email=r.requester_email, cancel_reason=r.cancel_reason,
                      version=r.version, items=items, documents=[DocumentOut.model_validate(d) for d in r.documents],
                      history=[HistoryOut.model_validate(h) for h in r.history])


@router.get("/summary", response_model=SummaryOut)
def get_summary(principal: TokenClaims = Depends(CAN_READ), db: Session = Depends(get_db)):
    counts, open_value, monthly = service.summary(db, principal)
    return SummaryOut(counts=counts, open_value=open_value, monthly=[MonthCount(month=m, count=c) for m, c in monthly])


@router.get("", response_model=RequestPage)
def list_requests(
    status_: Status | None = Query(default=None, alias="status"),
    priority: Priority | None = None,
    q: str | None = Query(default=None, max_length=100),
    created_from: date | None = None,
    created_to: date | None = None,
    sort: Literal["created_at", "total_amount", "needed_by", "number", "status", "updated_at"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    principal: TokenClaims = Depends(CAN_READ),
    db: Session = Depends(get_db),
):
    rows, total = service.list_requests(db, principal, status_=status_.value if status_ else None, priority=priority.value if priority else None, q=q,
                                        created_from=created_from, created_to=created_to, sort=sort, order=order, page=page, page_size=page_size)
    return RequestPage(items=[_summary(r) for r in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(body: RequestIn, principal: TokenClaims = Depends(CAN_CREATE), db: Session = Depends(get_db)):
    return _out(service.create(db, principal, body))


@router.get("/{request_id}", response_model=RequestOut)
def get_request(request_id: str, principal: TokenClaims = Depends(CAN_READ), db: Session = Depends(get_db)):
    return _out(service.get_visible(db, principal, request_id))


@router.put("/{request_id}", response_model=RequestOut)
def update_request(request_id: str, body: RequestUpdate, principal: TokenClaims = Depends(CAN_CREATE), db: Session = Depends(get_db)):
    return _out(service.update(db, principal, request_id, body, body.version))


@router.post("/{request_id}/submit", response_model=RequestOut)
def submit_request(request_id: str, principal: TokenClaims = Depends(CAN_SUBMIT), db: Session = Depends(get_db)):
    return _out(service.submit(db, principal, request_id))


@router.post("/{request_id}/cancel", response_model=RequestOut)
def cancel_request(request_id: str, body: CancelIn, principal: TokenClaims = Depends(CAN_SUBMIT), db: Session = Depends(get_db)):
    return _out(service.cancel(db, principal, request_id, body))


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request(request_id: str, principal: TokenClaims = Depends(CAN_CREATE), db: Session = Depends(get_db)):
    service.delete_draft(db, principal, request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{request_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def add_document(request_id: str, body: DocumentIn, principal: TokenClaims = Depends(CAN_UPLOAD), db: Session = Depends(get_db)):
    return DocumentOut.model_validate(service.add_document(db, principal, request_id, body))


@router.delete("/{request_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(request_id: str, document_id: str, principal: TokenClaims = Depends(CAN_UPLOAD), db: Session = Depends(get_db)):
    service.remove_document(db, principal, request_id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
