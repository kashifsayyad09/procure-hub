import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Naive UTC (MySQL DATETIME has no timezone)."""
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid.uuid4())


class Status(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"   # set by the Approval service (Phase 4)
    REJECTED = "rejected"   # set by the Approval service (Phase 4)
    CANCELLED = "cancelled"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Base(DeclarativeBase):
    pass


class NumberSequence(Base):
    """One counter per year, locked while a number is allocated so concurrent requests never share a number."""

    __tablename__ = "number_sequences"
    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_value: Mapped[int] = mapped_column(Integer, default=0)


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"
    __table_args__ = (Index("ix_pr_requester_status", "requester_id", "status"), Index("ix_pr_status_created", "status", "created_at"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    requester_id: Mapped[str] = mapped_column(String(36), index=True)  # a user id from the auth service; deliberately not a foreign key
    requester_name: Mapped[str] = mapped_column(String(120))
    requester_email: Mapped[str] = mapped_column(String(254))
    department: Mapped[str] = mapped_column(String(80), default="")
    title: Mapped[str] = mapped_column(String(150))
    justification: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(10), default=Priority.NORMAL.value)
    needed_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(20), default=Status.DRAFT.value)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    items: Mapped[list["PurchaseRequestItem"]] = relationship(cascade="all, delete-orphan", order_by="PurchaseRequestItem.line_no", lazy="selectin")
    documents: Mapped[list["PurchaseRequestDocument"]] = relationship(cascade="all, delete-orphan", order_by="PurchaseRequestDocument.position", lazy="selectin")
    history: Mapped[list["PurchaseRequestHistory"]] = relationship(
        cascade="all, delete-orphan", order_by="PurchaseRequestHistory.seq", lazy="selectin")


class PurchaseRequestItem(Base):
    __tablename__ = "purchase_request_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_requests.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(20), default="each")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PurchaseRequestDocument(Base):
    """Metadata only. `content_stored` becomes true when file upload to object storage exists."""

    __tablename__ = "purchase_request_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_requests.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)  # explicit order: timestamps only have 1-second precision in MySQL
    file_name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(200))
    content_stored: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PurchaseRequestHistory(Base):
    __tablename__ = "purchase_request_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_requests.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)  # explicit order: timestamps only have 1-second precision in MySQL
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str] = mapped_column(String(36))
    actor_name: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
