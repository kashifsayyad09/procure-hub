from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

CONTRACT_VERSION = 1


class ItemSnapshot(BaseModel):
    line_no: int
    description: str = Field(min_length=1, max_length=300)
    quantity: Decimal
    unit: str = Field(max_length=20)
    unit_price: Decimal
    line_total: Decimal


class ApprovalRegistration(BaseModel):
    """Purchase Request service -> Approval service, when a request is submitted. Idempotent on request_id."""

    contract_version: int = CONTRACT_VERSION
    request_id: str = Field(min_length=1, max_length=36)
    request_number: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=150)
    justification: str = Field(max_length=2000)
    department: str = Field(max_length=80)
    priority: Literal["low", "normal", "high", "urgent"]
    currency: Literal["INR", "USD", "EUR", "GBP"]
    total_amount: Decimal
    needed_by: date | None = None
    requester_id: str = Field(min_length=1, max_length=36)
    requester_name: str = Field(min_length=1, max_length=120)
    requester_email: str = Field(max_length=254)
    submitted_at: datetime | None = None
    items: list[ItemSnapshot] = Field(default_factory=list, max_length=100)


class DecisionNotice(BaseModel):
    """Approval service -> Purchase Request service, when the final decision is made. Idempotent."""

    contract_version: int = CONTRACT_VERSION
    decision: Literal["approved", "rejected"]
    actor_id: str = Field(min_length=1, max_length=36)
    actor_name: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    decided_at: datetime


class CancelNotice(BaseModel):
    """Purchase Request service -> Approval service, when the requester cancels. Idempotent."""

    contract_version: int = CONTRACT_VERSION
    actor_name: str = Field(max_length=120)
    reason: str | None = Field(default=None, max_length=500)


class ManagerRef(BaseModel):
    """Auth service -> Approval service: who can be given a delegated approval."""

    id: str
    full_name: str
    email: str
