import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from procurehub_common.contracts.approval import ManagerRef
from procurehub_common.service_client import ServiceRejected, ServiceUnavailable
from procurehub_common.tokens import TokenClaims
from sqlalchemy.orm import Session

from .. import service
from ..database import get_db
from ..deps import require_any_permission
from ..models import Approval
from ..schemas import (
    ApprovalOut,
    ApprovalPage,
    ApprovalSummaryOut,
    ApproveIn,
    DelegateIn,
    HistoryOut,
    ItemOut,
    MonthCount,
    RejectIn,
    StepOut,
    SummaryOut,
    View,
)

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

CAN_READ = require_any_permission("approval:read")
CAN_DECIDE = require_any_permission("approval:decide")
CAN_DELEGATE = require_any_permission("approval:delegate")


def _summary(ap: Approval) -> ApprovalSummaryOut:
    step = service.current_step(ap) if ap.status == "pending" else None
    data = {k: getattr(ap, k) for k in ApprovalSummaryOut.model_fields if k not in ("waiting_for", "overdue")}
    return ApprovalSummaryOut(**data, waiting_for=(step.assigned_to_name or "Any manager") if step else None, overdue=bool(step and step.escalated_at))


def _out(ap: Approval, user: TokenClaims) -> ApprovalOut:
    problem = service.blocked_reason(ap, user)
    return ApprovalOut(
        **_summary(ap).model_dump(), justification=ap.justification, requester_id=ap.requester_id, requester_email=ap.requester_email,
        items=[ItemOut(**i) for i in json.loads(ap.items_json)], steps=[StepOut.model_validate(s, from_attributes=True) for s in ap.steps],
        history=[HistoryOut.model_validate(h, from_attributes=True) for h in ap.history], can_decide=problem is None, blocked_reason=problem[1] if problem else None,
        decision_sync=ap.decision_sync, last_sync_error=ap.last_sync_error,
    )


def _managers(request: Request) -> list[ManagerRef]:
    client = request.app.state.auth_client
    if client is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The list of managers is not available right now.")
    try:
        return [ManagerRef(**m) for m in client.get("/internal/v1/users", params={"role": "manager"})]
    except (ServiceUnavailable, ServiceRejected):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The list of managers is not available right now. Try again in a moment.") from None


@router.get("/summary", response_model=SummaryOut)
def get_summary(principal: TokenClaims = Depends(CAN_READ), db: Session = Depends(get_db)):
    s = service.summary(db, principal)
    return SummaryOut(**{**s, "monthly": [MonthCount(month=m, count=c) for m, c in s["monthly"]]})


@router.get("/delegates", response_model=list[ManagerRef])
def list_delegates(request: Request, principal: TokenClaims = Depends(CAN_DELEGATE)):
    """Managers an approval can be delegated to (never yourself)."""
    return [m for m in _managers(request) if m.id != principal.sub]


@router.get("", response_model=ApprovalPage)
def list_approvals(
    view: View = "queue",
    status_: Literal["pending", "approved", "rejected", "cancelled"] | None = Query(default=None, alias="status"),
    priority: Literal["low", "normal", "high", "urgent"] | None = None,
    q: str | None = Query(default=None, max_length=100),
    sort: Literal["created_at", "total_amount", "needed_by", "request_number", "decided_at"] = "created_at",
    order: Literal["asc", "desc"] = "asc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    principal: TokenClaims = Depends(CAN_READ),
    db: Session = Depends(get_db),
):
    rows, total = service.list_approvals(db, principal, view=view, status_=status_, priority=priority, q=q, sort=sort, order=order, page=page, page_size=page_size)
    return ApprovalPage(items=[_summary(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/{approval_id}", response_model=ApprovalOut)
def get_approval(approval_id: str, principal: TokenClaims = Depends(CAN_READ), db: Session = Depends(get_db)):
    return _out(service.get_approval(db, approval_id), principal)


def _after_decision(request: Request, db: Session, ap: Approval) -> None:
    service.sync_decision(db, request.app.state.purchase_client, ap)  # if this fails, the retry loop delivers it later


@router.post("/{approval_id}/approve", response_model=ApprovalOut)
def approve(approval_id: str, body: ApproveIn, request: Request, principal: TokenClaims = Depends(CAN_DECIDE), db: Session = Depends(get_db)):
    ap = service.approve(db, principal, approval_id, body.comment)
    _after_decision(request, db, ap)
    return _out(ap, principal)


@router.post("/{approval_id}/reject", response_model=ApprovalOut)
def reject(approval_id: str, body: RejectIn, request: Request, principal: TokenClaims = Depends(CAN_DECIDE), db: Session = Depends(get_db)):
    ap = service.reject(db, principal, approval_id, body.reason)
    _after_decision(request, db, ap)
    return _out(ap, principal)


@router.post("/{approval_id}/delegate", response_model=ApprovalOut)
def delegate(approval_id: str, body: DelegateIn, request: Request, principal: TokenClaims = Depends(CAN_DELEGATE), db: Session = Depends(get_db)):
    target = next((m for m in _managers(request) if m.id == body.user_id), None)
    if target is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose an active manager.")
    return _out(service.delegate(db, principal, approval_id, target, body.note), principal)
