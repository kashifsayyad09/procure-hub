import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .catalog import CATEGORIES, MAX_CATEGORIES, MAX_CONTACTS

Currency = Literal["INR", "USD", "EUR", "GBP"]
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
_PHONE = re.compile(r"^\+?[0-9][0-9 ()\-.]{4,28}$")
_WEBSITE = re.compile(r"^https?://[^\s/$.?#][^\s]*$", re.IGNORECASE)
_TAX = re.compile(r"[^A-Z0-9]")


def _clean(v: str) -> str:
    return _CONTROL.sub("", v).strip()


def _opt(v: str | None) -> str | None:
    if v is None:
        return None
    v = _clean(v)
    return v or None


def normalise_tax_id(v: str) -> str:
    """Upper case, letters and digits only, so 'ab-123 45' and 'AB12345' are the same vendor."""
    return _TAX.sub("", v.upper())


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    job_title: str | None = Field(default=None, max_length=80)
    email: str = Field(max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    is_primary: bool = False

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("Enter the contact's name")
        return v

    @field_validator("job_title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        return _opt(v)

    @field_validator("email")
    @classmethod
    def _email_ok(cls, v: str) -> str:
        v = _clean(v).lower()
        if not _EMAIL.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("phone")
    @classmethod
    def _phone_ok(cls, v: str | None) -> str | None:
        v = _opt(v)
        if v is not None and not _PHONE.match(v):
            raise ValueError("Enter a valid phone number, for example +91 98765 43210")
        return v


class ProfileIn(BaseModel):
    """Everything is optional except the legal name, so a vendor can save a draft and come back. Submitting needs the rest."""

    legal_name: str = Field(min_length=2, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    tax_id: str | None = Field(default=None, max_length=40)
    registration_number: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=200)
    description: str = Field(default="", max_length=2000)
    address_line1: str = Field(default="", max_length=150)
    address_line2: str | None = Field(default=None, max_length=150)
    city: str = Field(default="", max_length=80)
    state: str = Field(default="", max_length=80)
    postal_code: str = Field(default="", max_length=20)
    country: str = Field(default="IN", min_length=2, max_length=2)
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    currency: Currency = "INR"
    categories: list[str] = Field(default_factory=list, max_length=MAX_CATEGORIES)
    contacts: list[ContactIn] = Field(default_factory=list, max_length=MAX_CONTACTS)

    @field_validator("legal_name")
    @classmethod
    def _legal(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 2:
            raise ValueError("Enter the registered company name")
        return v

    @field_validator("trade_name", "registration_number", "address_line2")
    @classmethod
    def _optional_text(cls, v: str | None) -> str | None:
        return _opt(v)

    @field_validator("address_line1", "city", "state", "postal_code")
    @classmethod
    def _text(cls, v: str) -> str:
        return _clean(v)

    @field_validator("description")
    @classmethod
    def _multi_line(cls, v: str) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v).strip()

    @field_validator("tax_id")
    @classmethod
    def _tax_id(cls, v: str | None) -> str | None:
        v = _opt(v)
        if v is None:
            return None
        n = normalise_tax_id(v)
        if not 5 <= len(n) <= 30:
            raise ValueError("Enter a tax ID of 5 to 30 letters and digits")
        return n

    @field_validator("website")
    @classmethod
    def _website_ok(cls, v: str | None) -> str | None:
        v = _opt(v)
        if v is not None and not _WEBSITE.match(v):
            raise ValueError("Enter a web address starting with http:// or https://")
        return v

    @field_validator("country")
    @classmethod
    def _country(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", v):
            raise ValueError("Use a two-letter country code, for example IN")
        return v

    @field_validator("categories")
    @classmethod
    def _categories(cls, v: list[str]) -> list[str]:
        bad = [c for c in v if c not in CATEGORIES]
        if bad:
            raise ValueError("Unknown category: " + ", ".join(bad))
        return list(dict.fromkeys(v))  # drop duplicates, keep order

    @model_validator(mode="after")
    def _contacts_make_sense(self) -> "ProfileIn":
        emails = [c.email for c in self.contacts]
        if len(set(emails)) != len(emails):
            raise ValueError("Each contact needs a different email address")
        primaries = [c for c in self.contacts if c.is_primary]
        if len(primaries) > 1:
            raise ValueError("Choose one primary contact")
        if self.contacts and not primaries:
            self.contacts[0].is_primary = True  # the first contact is the primary one unless told otherwise
        return self


class ProfileUpdate(ProfileIn):
    version: int = Field(ge=1)


class ReviewIn(BaseModel):
    version: int = Field(ge=1)  # the version the reviewer looked at; a changed profile must be reviewed again
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def _note(cls, v: str | None) -> str | None:
        return _opt(v)


class ReasonIn(BaseModel):
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def _reason(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 3:
            raise ValueError("Give a short reason")
        return v


class CategoryOut(BaseModel):
    id: str
    label: str


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    job_title: str | None
    email: str
    phone: str | None
    is_primary: bool


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    seq: int
    action: str
    from_status: str | None
    to_status: str
    actor_name: str
    note: str | None
    created_at: datetime


class VendorSummaryOut(BaseModel):
    id: str
    number: str
    legal_name: str
    trade_name: str | None
    status: str
    country: str
    city: str
    categories: list[str]
    primary_contact_name: str | None
    primary_contact_email: str | None
    has_account: bool  # a vendor user owns this record
    created_at: datetime
    submitted_at: datetime | None
    verified_at: datetime | None


class Completeness(BaseModel):
    percent: int
    missing: list[str]


Action = Literal["edit", "submit", "verify", "reject", "suspend", "reinstate"]


class VendorOut(VendorSummaryOut):
    tax_id: str | None
    registration_number: str | None
    website: str | None
    description: str
    address_line1: str
    address_line2: str | None
    state: str
    postal_code: str
    payment_terms_days: int
    currency: str
    status_note: str | None
    verified_by_name: str | None
    created_by_name: str
    version: int
    updated_at: datetime
    contacts: list[ContactOut]
    history: list[HistoryOut]
    completeness: Completeness
    actions: list[Action]
    blocked_reason: str | None  # why a review action is not offered to this caller


class VendorPage(BaseModel):
    items: list[VendorSummaryOut]
    total: int
    page: int
    page_size: int


class MonthCount(BaseModel):
    month: str
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class SummaryOut(BaseModel):
    counts: dict[str, int]
    verified_by_category: list[CategoryCount]
    monthly: list[MonthCount]


