from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _clean(v: str) -> str:
    return "".join(ch for ch in v if ch == "\n" or ch >= " " and ch != "\x7f").strip()


class ApproveIn(BaseModel):
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("comment")
    @classmethod
    def _c(cls, v: str | None) -> str | None:
        return (_clean(v) or None) if v else None


class RejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def _r(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 3:
            raise ValueError("Give a short reason")
        return v


class DelegateIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)
    note: str | None = Field(default=None, max_length=300)

    @field_validator("note")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return (_clean(v) or None) if v else None


class StepOut(BaseModel):
    id: str
    level: int
    status: str
    assigned_to_id: str | None
    assigned_to_name: str | None
    decided_by_name: str | None
    decided_at: datetime | None
    comment: str | None
    activated_at: datetime | None
    escalated_at: datetime | None


class HistoryOut(BaseModel):
    id: str
    seq: int
    action: str
    level: int | None
    actor_name: str
    note: str | None
    created_at: datetime


class ItemOut(BaseModel):
    line_no: int
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    line_total: Decimal


class ApprovalSummaryOut(BaseModel):
    id: str
    request_id: str
    request_number: str
    title: str
    requester_name: str
    department: str
    priority: str
    currency: str
    total_amount: Decimal
    needed_by: date | None
    status: str
    current_level: int
    total_levels: int
    waiting_for: str | None  # who must act now
    overdue: bool
    created_at: datetime
    decided_at: datetime | None


class ApprovalOut(ApprovalSummaryOut):
    justification: str
    requester_id: str
    requester_email: str
    items: list[ItemOut]
    steps: list[StepOut]
    history: list[HistoryOut]
    can_decide: bool  # whether the signed-in user may approve, reject or delegate right now
    blocked_reason: str | None
    decision_sync: str
    last_sync_error: str | None


class ApprovalPage(BaseModel):
    items: list[ApprovalSummaryOut]
    total: int
    page: int
    page_size: int


class MonthCount(BaseModel):
    month: str
    count: int


class SummaryOut(BaseModel):
    waiting_for_me: int
    overdue_for_me: int
    delegated_to_me: int
    decided_by_me_30d: int
    approved_30d: int
    rejected_30d: int
    approved_value_30d: dict[str, Decimal]
    avg_decision_hours_30d: float | None
    monthly: list[MonthCount]


View = Literal["queue", "mine", "all"]
