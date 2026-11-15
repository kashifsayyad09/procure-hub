"""Internal API for other services (RFQ, purchase orders, SI-Talker). Not reachable through the public ingress; every call needs a service token."""
from fastapi import APIRouter, Depends, HTTPException, Request
from procurehub_common.contracts.vendor import VendorLookup, VendorRef
from procurehub_common.fastapi_support import service_caller
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import service
from ..database import get_db
from ..models import Vendor

# Services that may read vendor references. Later phases add themselves here by name.
ALLOWED_CALLERS = {"quotation-service", "purchase-order-service", "invoice-service", "si-talker-service", "mcp-server"}


def _secret(request: Request) -> str | None:
    s = request.app.state.settings.internal_jwt_secret
    return s.get_secret_value() if s else None


router = APIRouter(prefix="/internal/v1", tags=["internal"], include_in_schema=False)
CALLER = Depends(service_caller(_secret, ALLOWED_CALLERS))


@router.get("/vendors/by-owner/{user_id}", response_model=VendorRef)
def get_by_owner(user_id: str, _: str = CALLER, db: Session = Depends(get_db)):
    """The vendor record owned by an auth user. Lets a service turn a signed-in vendor user into a vendor without trusting an id sent by the browser."""
    v = db.scalar(select(Vendor).where(Vendor.owner_id == user_id))
    if v is None:
        raise HTTPException(404, "No vendor is registered for this user.")
    return service.to_ref(v)


@router.get("/vendors/{vendor_id}", response_model=VendorRef)
def get_vendor(vendor_id: str, _: str = CALLER, db: Session = Depends(get_db)):
    v = db.scalar(select(Vendor).where(Vendor.id == vendor_id))
    if v is None:
        raise HTTPException(404, "Vendor not found.")
    return service.to_ref(v)


@router.post("/vendors/lookup", response_model=list[VendorRef])
def lookup(body: VendorLookup, _: str = CALLER, db: Session = Depends(get_db)):
    """Returns the vendors that exist, with their status, so a caller can refuse anyone who is not verified. Unknown ids are left out."""
    return [service.to_ref(v) for v in service.lookup(db, body.ids)]
