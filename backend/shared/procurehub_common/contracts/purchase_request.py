"""Purchase Request service -> other services (RFQ now, purchase orders later): a read-only view of a request.
Services call `/internal/v1/purchase-requests` with a service token and never read purchase_request_db."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from .approval import ItemSnapshot

CONTRACT_VERSION = 1


class PurchaseRequestRef(BaseModel):
    contract_version: int = CONTRACT_VERSION
    id: str
    number: str
    title: str
    justification: str = ""
    department: str = ""
    priority: Literal["low", "normal", "high", "urgent"]
    currency: Literal["INR", "USD", "EUR", "GBP"]
    total_amount: Decimal
    needed_by: date | None = None
    status: Literal["draft", "submitted", "approved", "rejected", "cancelled"]
    requester_name: str
    decided_at: datetime | None = None
    decided_by_name: str | None = None
    items: list[ItemSnapshot] = Field(default_factory=list)


class PurchaseRequestPage(BaseModel):
    items: list[PurchaseRequestRef]
    total: int
    page: int
    page_size: int
