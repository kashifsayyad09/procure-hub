"""Hand-off to the Approval service. The Purchase Request service stays the only writer of its own database;
the Approval service keeps its own records. If the Approval service is down, the request stays submitted and
`approval_registered` stays false until the retry loop gets through. Registration is idempotent on the other side."""
import logging

from procurehub_common.contracts.approval import ApprovalRegistration, CancelNotice, ItemSnapshot
from procurehub_common.service_client import ServiceClient, ServiceRejected, ServiceUnavailable
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import service
from .models import PurchaseRequest, Status

log = logging.getLogger("approvals")


def snapshot(req: PurchaseRequest) -> ApprovalRegistration:
    return ApprovalRegistration(
        request_id=req.id, request_number=req.number, title=req.title, justification=req.justification, department=req.department,
        priority=req.priority, currency=req.currency, total_amount=req.total_amount, needed_by=req.needed_by,
        requester_id=req.requester_id, requester_name=req.requester_name, requester_email=req.requester_email, submitted_at=req.submitted_at,
        items=[ItemSnapshot(line_no=i.line_no, description=i.description, quantity=i.quantity, unit=i.unit, unit_price=i.unit_price,
                            line_total=service.line_total(i.quantity, i.unit_price)) for i in req.items],
    )


def register(db: Session, client: ServiceClient, req: PurchaseRequest) -> bool:
    try:
        client.post("/internal/v1/approvals", json=snapshot(req).model_dump(mode="json"))
    except ServiceUnavailable as e:
        log.warning("approval_registration_deferred", extra={"event": "approval_registration_deferred", "request_id": req.id, "reason": str(e)[:200]})
        return False
    except ServiceRejected as e:
        log.error("approval_registration_rejected", extra={"event": "approval_registration_rejected", "request_id": req.id, "status": e.status_code, "detail": str(e.detail)[:200]})
        return False
    req.approval_registered = True
    db.commit()
    log.info("approval_registered", extra={"event": "approval_registered", "request_id": req.id, "number": req.number})
    return True


def reconcile_once(db: Session, client: ServiceClient, limit: int = 50) -> int:
    """Registers submitted requests the Approval service has not accepted yet. Returns how many were registered."""
    pending = db.scalars(select(PurchaseRequest).where(PurchaseRequest.status == Status.SUBMITTED.value, PurchaseRequest.approval_registered.is_(False))
                         .order_by(PurchaseRequest.submitted_at).limit(limit)).all()
    return sum(1 for req in pending if register(db, client, req))


def notify_cancel(client: ServiceClient, req: PurchaseRequest, actor_name: str, reason: str | None) -> None:
    """Best effort. If it fails the Approval service refuses a later decision on this cancelled request."""
    try:
        client.post(f"/internal/v1/approvals/{req.id}/cancel", json=CancelNotice(actor_name=actor_name or "Requester", reason=reason).model_dump(mode="json"))
    except (ServiceUnavailable, ServiceRejected) as e:
        log.warning("approval_cancel_not_delivered", extra={"event": "approval_cancel_not_delivered", "request_id": req.id, "reason": str(e)[:200]})
