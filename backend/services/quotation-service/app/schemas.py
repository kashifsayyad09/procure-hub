import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

CURRENCIES = ("INR", "USD", "EUR", "GBP")
Currency = Literal["INR", "USD", "EUR", "GBP"]
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_MULTILINE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _iso_utc(v: datetime) -> str:
    return v.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


UtcDt = Annotated[datetime, PlainSerializer(_iso_utc, return_type=str)]  # naive UTC from the database, sent with a Z so browsers read it correctly
Money = Annotated[Decimal, PlainSerializer(lambda d: format(d, "f"), return_type=str)]  # exact decimals as strings, never floats


def _clean(v: str) -> str:
    return _CONTROL.sub("", v).strip()


def _text(v: str) -> str:
    return _MULTILINE_CONTROL.sub("", v).strip()


def _opt(v: str | None) -> str | None:
    if v is None:
        return None
    v = _clean(v)
    return v or None


def to_utc_naive(v: datetime) -> datetime:
    """Accepts a timezone-aware time (converted to UTC) or a naive one (taken as UTC)."""
    return v.astimezone(UTC).replace(tzinfo=None) if v.tzinfo else v


# ---- requests --------------------------------------------------------------------------------------
class ItemSpecIn(BaseModel):
    """Procurement may clarify what is being asked for. Quantities and units come from the approved request and are not editable."""

    line_no: int = Field(ge=1)
    description: str = Field(min_length=1, max_length=300)
    specification: str | None = Field(default=None, max_length=1000)

    @field_validator("description")
    @classmethod
    def _description(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("Cannot be blank")
        return v

    @field_validator("specification")
    @classmethod
    def _spec(cls, v: str | None) -> str | None:
        return (_text(v) or None) if v else None


class RfqCreate(BaseModel):
    purchase_request_id: str = Field(min_length=1, max_length=36)
    title: str | None = Field(default=None, min_length=3, max_length=150)  # defaults to the request's title
    description: str = Field(default="", max_length=4000)
    requirements: str = Field(default="", max_length=4000)
    deadline: datetime
    items: list[ItemSpecIn] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        return _opt(v)

    @field_validator("description", "requirements")
    @classmethod
    def _long(cls, v: str) -> str:
        return _text(v)

    @field_validator("deadline")
    @classmethod
    def _deadline(cls, v: datetime) -> datetime:
        return to_utc_naive(v)


class RfqUpdate(BaseModel):
    version: int = Field(ge=1)
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(default="", max_length=4000)
    requirements: str = Field(default="", max_length=4000)
    deadline: datetime
    items: list[ItemSpecIn] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 3:
            raise ValueError("Enter a title of at least 3 characters")
        return v

    @field_validator("description", "requirements")
    @classmethod
    def _long(cls, v: str) -> str:
        return _text(v)

    @field_validator("deadline")
    @classmethod
    def _deadline(cls, v: datetime) -> datetime:
        return to_utc_naive(v)


class ExtendIn(BaseModel):
    version: int = Field(ge=1)
    deadline: datetime

    @field_validator("deadline")
    @classmethod
    def _deadline(cls, v: datetime) -> datetime:
        return to_utc_naive(v)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def _reason(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 3:
            raise ValueError("Give a short reason")
        return v


class InviteIn(BaseModel):
    vendor_ids: list[str] = Field(min_length=1, max_length=50)

    @field_validator("vendor_ids")
    @classmethod
    def _ids(cls, v: list[str]) -> list[str]:
        v = [i.strip() for i in v]
        if any(not i or len(i) > 36 for i in v):
            raise ValueError("Each vendor id must be 1 to 36 characters")
        return list(dict.fromkeys(v))


class QuoteLineIn(BaseModel):
    rfq_item_id: str = Field(min_length=1, max_length=36)
    unit_price: Decimal | None = Field(default=None, ge=0, le=100_000_000, max_digits=14, decimal_places=4)  # null means "not quoted"
    note: str | None = Field(default=None, max_length=300)

    @field_validator("unit_price")
    @classmethod
    def _finite(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and not v.is_finite():
            raise ValueError("Enter a number")
        return v

    @field_validator("note")
    @classmethod
    def _note(cls, v: str | None) -> str | None:
        return _opt(v)


class QuotationIn(BaseModel):
    currency: Currency = "INR"
    lead_time_days: int | None = Field(default=None, ge=1, le=730)
    valid_until: date | None = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    terms: str = Field(default="", max_length=4000)
    items: list[QuoteLineIn] = Field(default_factory=list, max_length=100)

    @field_validator("terms")
    @classmethod
    def _terms(cls, v: str) -> str:
        return _text(v)

    @model_validator(mode="after")
    def _no_duplicate_lines(self) -> "QuotationIn":
        ids = [i.rfq_item_id for i in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("Each RFQ item can be quoted only once")
        return self


class QuotationCreate(QuotationIn):
    rfq_id: str = Field(min_length=1, max_length=36)


class QuotationUpdate(QuotationIn):
    version: int = Field(ge=1)


class EvaluationIn(BaseModel):
    """The evaluator's own judgements, 0 to 10. A score needs a note saying why, so the decision can be audited later."""

    compliance_score: int | None = Field(default=None, ge=0, le=10)
    compliance_note: str | None = Field(default=None, max_length=1000)
    terms_score: int | None = Field(default=None, ge=0, le=10)
    terms_note: str | None = Field(default=None, max_length=1000)
    version: int | None = Field(default=None, ge=1)  # required when changing an existing evaluation

    @field_validator("compliance_note", "terms_note")
    @classmethod
    def _notes(cls, v: str | None) -> str | None:
        return (_text(v) or None) if v else None

    @model_validator(mode="after")
    def _scores_need_reasons(self) -> "EvaluationIn":
        if self.compliance_score is not None and not self.compliance_note:
            raise ValueError("Say why you gave the compliance score")
        if self.terms_score is not None and not self.terms_note:
            raise ValueError("Say why you gave the commercial terms score")
        return self


class SelectIn(BaseModel):
    quotation_id: str = Field(min_length=1, max_length=36)
    justification: str = Field(min_length=10, max_length=2000)
    acknowledge_missing_items: bool = False

    @field_validator("justification")
    @classmethod
    def _justification(cls, v: str) -> str:
        v = _text(v)
        if len(v) < 10:
            raise ValueError("Explain the decision in at least 10 characters")
        return v


class RevokeIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("reason")
    @classmethod
    def _reason(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 5:
            raise ValueError("Give a reason of at least 5 characters")
        return v


# ---- responses -------------------------------------------------------------------------------------
class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    line_no: int
    description: str
    specification: str | None
    quantity: Money
    unit: str


class StaffItemOut(ItemOut):
    estimated_unit_price: Money


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    seq: int
    action: str
    from_status: str | None
    to_status: str
    actor_name: str
    note: str | None
    created_at: UtcDt


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    vendor_id: str
    vendor_number: str
    vendor_name: str
    status: str
    invited_by_name: str
    invited_at: UtcDt
    sent_at: UtcDt | None
    responded_at: UtcDt | None
    withdrawn_at: UtcDt | None
    quotation_status: str | None = None  # draft or submitted, so procurement can see who has responded; never any amounts here


class RfqSummaryOut(BaseModel):
    id: str
    number: str
    title: str
    purchase_request_id: str
    purchase_request_number: str
    department: str
    status: str
    currency: str
    deadline: UtcDt
    deadline_passed: bool
    invited: int
    submitted: int
    created_by_name: str
    created_at: UtcDt


class SelectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    seq: int
    quotation_id: str
    vendor_id: str
    vendor_name: str
    status: str
    justification: str
    acknowledged_missing_items: bool
    currency: str
    total_amount: Money
    selected_by_name: str
    selected_at: UtcDt
    revoked_by_name: str | None
    revoked_at: UtcDt | None
    revoke_reason: str | None


RfqAction = Literal["edit", "invite", "publish", "extend", "close", "cancel", "compare", "select", "revoke"]


class RfqOut(RfqSummaryOut):
    description: str
    requirements: str
    needed_by: date | None
    budget_amount: Money
    version: int
    issued_at: UtcDt | None
    closed_at: UtcDt | None
    cancel_reason: str | None
    updated_at: UtcDt
    items: list[StaffItemOut]
    invitations: list[InvitationOut]
    history: list[HistoryOut]
    quotations_open: bool  # prices may be viewed (the deadline has passed or the RFQ is closed)
    selection: SelectionOut | None
    actions: list[RfqAction]


class RfqPage(BaseModel):
    items: list[RfqSummaryOut]
    total: int
    page: int
    page_size: int


class RfqCounts(BaseModel):
    counts: dict[str, int]
    awaiting_comparison: int  # issued RFQs whose deadline has passed, or closed ones with nothing selected


class EligibleRequestOut(BaseModel):
    id: str
    number: str
    title: str
    department: str
    priority: str
    currency: str
    total_amount: Money
    needed_by: date | None
    decided_at: UtcDt | None
    decided_by_name: str | None
    item_count: int
    rfq_id: str | None  # set when this request already has a live RFQ
    rfq_number: str | None


class EligiblePage(BaseModel):
    items: list[EligibleRequestOut]
    total: int
    page: int
    page_size: int


class QuoteLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rfq_item_id: str
    line_no: int
    quantity: Money
    unit_price: Money | None
    line_total: Money | None
    note: str | None


class QuotationOut(BaseModel):
    id: str
    number: str
    rfq_id: str
    rfq_number: str
    rfq_title: str
    vendor_id: str
    vendor_name: str
    currency: str
    lead_time_days: int | None
    valid_until: date | None
    payment_terms_days: int | None
    terms: str
    total_amount: Money
    status: str
    revision: int
    version: int
    submitted_at: UtcDt | None
    updated_at: UtcDt
    items: list[QuoteLineOut]
    complete: bool
    missing_items: list[int]  # line numbers with no price
    problems: list[str]  # what still stops this draft from being submitted
    can_edit: bool
    can_submit: bool
    can_withdraw: bool


class QuotationRowOut(BaseModel):
    """One line of the staff list. Amounts stay hidden (null) until quotations are open."""

    id: str | None
    number: str | None
    vendor_id: str
    vendor_name: str
    invitation_status: str
    status: str | None  # none, draft, submitted, selected, not_selected
    submitted_at: UtcDt | None
    currency: str | None
    total_amount: Money | None
    lead_time_days: int | None


class QuotationList(BaseModel):
    quotations_open: bool
    rows: list[QuotationRowOut]


class VendorQuotationSummary(BaseModel):
    id: str
    number: str
    status: str
    total_amount: Money
    currency: str
    updated_at: UtcDt


class VendorRfqSummaryOut(BaseModel):
    id: str
    number: str
    title: str
    status: str
    currency: str
    deadline: UtcDt
    deadline_passed: bool
    invitation_status: str
    quotation: VendorQuotationSummary | None
    can_quote: bool


class VendorRfqPage(BaseModel):
    items: list[VendorRfqSummaryOut]
    total: int
    page: int
    page_size: int


class VendorRfqOut(VendorRfqSummaryOut):
    description: str
    requirements: str
    needed_by: date | None
    items: list[ItemOut]
    blocked_reason: str | None
    issued_at: UtcDt | None


class MyQuotationRow(BaseModel):
    id: str
    number: str
    rfq_id: str
    rfq_number: str
    rfq_title: str
    status: str
    currency: str
    total_amount: Money
    deadline: UtcDt
    updated_at: UtcDt


class MyQuotationPage(BaseModel):
    items: list[MyQuotationRow]
    total: int
    page: int
    page_size: int


class EvaluationOut(BaseModel):
    compliance_score: int | None
    compliance_note: str | None
    terms_score: int | None
    terms_note: str | None
    evaluator_name: str
    version: int
    updated_at: UtcDt


class ScoresOut(BaseModel):
    price: Money | None  # calculated
    delivery: Money | None  # calculated
    compliance: Money | None  # entered by the evaluator (0 to 10, shown as 0 to 100)
    terms: Money | None  # entered by the evaluator
    total: Money | None
    missing: list[str]


class CompareLine(BaseModel):
    rfq_item_id: str
    line_no: int
    unit_price: Money | None
    line_total: Money | None


class CompareQuotation(BaseModel):
    id: str
    number: str
    vendor_id: str
    vendor_number: str
    vendor_name: str
    vendor_status: str | None  # from the vendor service, now; null when it could not be reached
    currency: str
    status: str
    total_amount: Money
    lead_time_days: int | None
    valid_until: date | None
    payment_terms_days: int | None
    terms: str
    submitted_at: UtcDt | None
    complete: bool
    missing_items: list[int]
    lines: list[CompareLine]
    scores: ScoresOut
    rank: int | None  # within the same currency
    lowest_price: bool
    fastest: bool
    within_budget: bool | None  # only judged when the quotation is in the RFQ's currency
    evaluation: EvaluationOut | None


class CompareRfq(BaseModel):
    id: str
    number: str
    title: str
    status: str
    currency: str
    deadline: UtcDt
    budget_amount: Money
    version: int
    items: list[StaffItemOut]


class ComparisonOut(BaseModel):
    rfq: CompareRfq
    currencies: list[str]
    mixed_currencies: bool
    note: str | None
    weights: dict[str, int]
    vendor_info_available: bool
    quotations: list[CompareQuotation]
    selection: SelectionOut | None
    can_select: bool
    can_revoke: bool


class SelectionHistory(BaseModel):
    items: list[SelectionOut]
