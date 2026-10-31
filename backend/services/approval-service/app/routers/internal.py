"""Internal API for the Purchase Request service. Not reachable through the public ingress; every call needs a service token."""
from fastapi import APIRouter, Depends, Request
from procurehub_common.contracts.approval import ApprovalRegistration, CancelNotice
from procurehub_common.fastapi_support import service_caller
from sqlalchemy.orm import Session

from .. import service
from ..database import get_db


def _secret(request: Request) -> str | None:
    return request.app.state.settings.internal_jwt_secret.get_secret_value()


router = APIRouter(prefix="/internal/v1", tags=["internal"], include_in_schema=False)
CALLER = Depends(service_caller(_secret, {"purchase-request-service"}))


@router.post("/approvals")
def register_approval(body: ApprovalRegistration, request: Request, _: str = CALLER, db: Session = Depends(get_db)):
    ap = service.register(db, body, request.app.state.settings.approval_thresholds)
    return {"id": ap.id, "status": ap.status, "total_levels": ap.total_levels}


@router.post("/approvals/{request_id}/cancel")
def cancel_approval(request_id: str, body: CancelNotice, _: str = CALLER, db: Session = Depends(get_db)):
    ap = service.cancel_by_request(db, request_id, body)
    return {"status": ap.status if ap else "unknown"}
