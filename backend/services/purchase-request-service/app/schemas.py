import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import Priority

Currency = Literal["INR", "USD", "EUR", "GBP"]
ALLOWED_CONTENT_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "text/plain", "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_ITEMS = 100
MAX_DOCUMENTS = 10
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

Text150 = Annotated[str, Field(max_length=150)]


def _clean(v: str) -> str:
    return _CONTROL.sub("", v).strip()


class ItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: Decimal = Field(gt=0, le=1_000_000, max_digits=12, decimal_places=3)
    unit: str = Field(default="each", min_length=1, max_length=20)
    unit_price: Decimal = Field(ge=0, le=100_000_000, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("description", "unit")
    @classmethod
    def _text(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("Cannot be blank")
        return v

    @field_validator("notes")
    @classmethod
    def _notes(cls, v: str | None) -> str | None:
        return (_clean(v) or None) if v else None


class RequestIn(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    justification: str = Field(default="", max_length=2000)
    department: str = Field(default="", max_length=80)
    priority: Priority = Priority.NORMAL
    needed_by: date | None = None
    currency: Currency = "INR"
    items: list[ItemIn] = Field(default_factory=list, max_length=MAX_ITEMS)

    @field_validator("title", "department")
    @classmethod
    def _single_line(cls, v: str) -> str:
        return _clean(v)

    @field_validator("justification")
    @classmethod
    def _multi_line(cls, v: str) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v).strip()

    @field_validator("needed_by")
    @classmethod
    def _not_past(cls, v: date | None) -> date | None:
        if v is not None and v < date.today():
            raise ValueError("The needed-by date cannot be in the past")
        return v


class RequestUpdate(RequestIn):
    version: int = Field(ge=1)


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def _clean_reason(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 3:
            raise ValueError("Give a short reason")
        return v


class DocumentIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=200)
    content_type: str = Field(max_length=100)
    size_bytes: int = Field(ge=1, le=MAX_DOCUMENT_BYTES)

    @field_validator("file_name")
    @classmethod
    def _safe_name(cls, v: str) -> str:
        v = _clean(v.replace("\\", "/").split("/")[-1])  # drop any path the browser or an attacker supplied
        if not v or v in {".", ".."}:
            raise ValueError("Enter a valid file name")
        return v

    @field_validator("content_type")
    @classmethod
    def _allowed(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ALLOWED_CONTENT_TYPES:
            raise ValueError("This file type is not allowed. Use PDF, PNG, JPEG, TXT, CSV, DOCX or XLSX.")
        return v


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    line_no: int
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    notes: str | None
    line_total: Decimal


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    file_name: str
    content_type: str
    size_bytes: int
    content_stored: bool
    created_at: datetime


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    from_status: str | None
    to_status: str
    actor_name: str
    note: str | None
    created_at: datetime


class RequestSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    number: str
    title: str
    department: str
    priority: str
    status: str
    currency: str
    total_amount: Decimal
    needed_by: date | None
    requester_name: str
    item_count: int
    created_at: datetime
    submitted_at: datetime | None
    updated_at: datetime


class RequestOut(RequestSummaryOut):
    justification: str
    requester_id: str
    requester_email: str
    cancel_reason: str | None
    version: int
    items: list[ItemOut]
    documents: list[DocumentOut]
    history: list[HistoryOut]


class RequestPage(BaseModel):
    items: list[RequestSummaryOut]
    total: int
    page: int
    page_size: int


class MonthCount(BaseModel):
    month: str
    count: int


class SummaryOut(BaseModel):
    counts: dict[str, int]
    open_value: dict[str, Decimal]  # per currency; different currencies are never added together
    monthly: list[MonthCount]
