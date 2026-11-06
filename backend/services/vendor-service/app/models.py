import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Naive UTC (MySQL DATETIME has no timezone)."""
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid.uuid4())


class VendorStatus(StrEnum):
    DRAFT = "draft"          # being filled in
    PENDING = "pending"      # submitted, waiting for a reviewer
    VERIFIED = "verified"    # may be invited to RFQs (Phase 6)
    REJECTED = "rejected"    # reviewer sent it back with a reason; the vendor can fix and resubmit
    SUSPENDED = "suspended"  # blocked by procurement or an administrator


class Base(DeclarativeBase):
    pass


class NumberSequence(Base):
    """One counter per year, locked while a number is allocated so concurrent registrations never share a number."""

    __tablename__ = "number_sequences"
    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_value: Mapped[int] = mapped_column(Integer, default=0)


class Vendor(Base):
    __tablename__ = "vendors"
    __table_args__ = (Index("ix_vendors_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    # The auth user who owns this record. Deliberately not a foreign key (different database). Unique: one record per vendor user.
    # Null for a vendor that staff registered before anyone from the company has an account.
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    created_by_id: Mapped[str] = mapped_column(String(36))
    created_by_name: Mapped[str] = mapped_column(String(120))

    legal_name: Mapped[str] = mapped_column(String(200), index=True)
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)  # normalised: upper case, letters and digits only
    registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    address_line1: Mapped[str] = mapped_column(String(150), default="")
    address_line2: Mapped[str | None] = mapped_column(String(150), nullable=True)
    city: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(80), default="")
    postal_code: Mapped[str] = mapped_column(String(20), default="")
    country: Mapped[str] = mapped_column(String(2), default="IN", index=True)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    status: Mapped[str] = mapped_column(String(20), default=VendorStatus.DRAFT.value)
    status_note: Mapped[str | None] = mapped_column(String(500), nullable=True)  # reason for the latest rejection or suspension
    submitted_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # the reviewer must be someone else
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    categories: Mapped[list["VendorCategory"]] = relationship(cascade="all, delete-orphan", order_by="VendorCategory.position", lazy="selectin")
    contacts: Mapped[list["VendorContact"]] = relationship(cascade="all, delete-orphan", order_by="VendorContact.position", lazy="selectin")
    history: Mapped[list["VendorHistory"]] = relationship(cascade="all, delete-orphan", order_by="VendorHistory.seq", lazy="selectin")


class VendorCategory(Base):
    __tablename__ = "vendor_categories"
    __table_args__ = (UniqueConstraint("vendor_id", "category", name="uq_vendor_category"), Index("ix_vendor_categories_category", "category"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vendor_id: Mapped[str] = mapped_column(String(36), ForeignKey("vendors.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(40))


class VendorContact(Base):
    __tablename__ = "vendor_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vendor_id: Mapped[str] = mapped_column(String(36), ForeignKey("vendors.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(120))
    job_title: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class VendorHistory(Base):
    """Who did what to the record and when. Never edited or deleted while the vendor exists."""

    __tablename__ = "vendor_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vendor_id: Mapped[str] = mapped_column(String(36), ForeignKey("vendors.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)  # explicit order: timestamps only have 1-second precision in MySQL
    action: Mapped[str] = mapped_column(String(30))
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str] = mapped_column(String(36))
    actor_name: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class VendorEvent(Base):
    """Outbox. Every state change writes a row in the same transaction. Phases 10 and 11 publish these;
    `published_at` stays empty until then."""

    __tablename__ = "vendor_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(40), index=True)
    vendor_id: Mapped[str] = mapped_column(String(36), index=True)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
