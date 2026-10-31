"""Internal API for the Approval service. Not reachable through the public ingress; every call needs a service token."""
from fastapi import APIRouter, Depends, Request
from procurehub_common.contracts.approval import DecisionNotice
from procurehub_common.fastapi_support import service_caller
from sqlalchemy.orm import Session

from .. import service
from ..database import get_db


def _secret(request: Request) -> str | None:
    s = request.app.state.settings.internal_jwt_secret
    return s.get_secret_value() if s else None


router = APIRouter(prefix="/internal/v1", tags=["internal"], include_in_schema=False)


@router.post("/purchase-requests/{request_id}/decision")
def apply_decision(request_id: str, body: DecisionNotice, _: str = Depends(service_caller(_secret, {"approval-service"})), db: Session = Depends(get_db)):
    req = service.apply_decision(db, request_id, body)
    return {"status": req.status}
