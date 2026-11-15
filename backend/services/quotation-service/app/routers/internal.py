"""Internal API for other services. Not reachable through the public ingress; every call needs a service token."""
from fastapi import APIRouter, Depends, Request
from procurehub_common.contracts.quotation import AwardRef
from procurehub_common.fastapi_support import service_caller
from sqlalchemy.orm import Session

from .. import evaluation
from ..database import get_db

# Services that may read an award. The purchase order service (Phase 7) builds the order from it.
ALLOWED_CALLERS = {"purchase-order-service", "si-talker-service", "mcp-server"}


def _secret(request: Request) -> str | None:
    s = request.app.state.settings.internal_jwt_secret
    return s.get_secret_value() if s else None


router = APIRouter(prefix="/internal/v1", tags=["internal"], include_in_schema=False)


@router.get("/rfqs/{rfq_id}/award", response_model=AwardRef)
def get_award(rfq_id: str, _: str = Depends(service_caller(_secret, ALLOWED_CALLERS)), db: Session = Depends(get_db)):
    """The active award for an RFQ: who won, the quoted lines and totals, the terms and the justification. 404 while there is none."""
    return evaluation.award_ref(db, rfq_id)
