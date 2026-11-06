"""Vendor service -> other services. Read-only reference to a vendor, used by later services (RFQ invitations, purchase orders)
so they never read vendor_db. Services call `/internal/v1/vendors` with a service token."""
from typing import Literal

from pydantic import BaseModel, Field

CONTRACT_VERSION = 1
VendorStatusName = Literal["draft", "pending", "verified", "rejected", "suspended"]


class VendorRef(BaseModel):
    contract_version: int = CONTRACT_VERSION
    id: str
    number: str
    legal_name: str
    trade_name: str | None = None
    status: VendorStatusName
    country: str
    currency: str
    payment_terms_days: int
    categories: list[str] = Field(default_factory=list)
    primary_contact_name: str | None = None
    primary_contact_email: str | None = None


class VendorLookup(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)
