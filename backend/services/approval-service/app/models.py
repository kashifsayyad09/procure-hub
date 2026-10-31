import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Naive UTC (MySQL DATETIME has no timezone)."""
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Approval(Base):
    """One approval workflow per purchase request. Holds a snapshot of what the managers are deciding on, so this
    service never reads another service's database."""

    __tablename__ = "approvals"
    __table_args__ = (Index("ix_approvals_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)  # id in the Purchase Request service; deliberately not a foreign key
    request_number: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(150))
    justification: Mapped[str] = mapped_column(Text, default="")
    department: Mapped[str] = mapped_column(String(80), default="")
    priority: Mapped[str] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    needed_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    requester_id: Mapped[str] = mapped_column(String(36), index=True)
    requester_name: Mapped[str] = mapped_column(String(120))
    requester_email: Mapped[str] = mapped_column(String(254))
    items_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending, approved, rejected, cancelled
    current_level: Mapped[int] = mapped_column(Integer, default=1)
    total_levels: Mapped[int] = mapped_column(Integer, default=1)
    decision_sync: Mapped[str] = mapped_column(String(10), default="not_needed")  # not_needed, pending, synced, conflict
    sync_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_sync_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    steps: Mapped[list["ApprovalStep"]] = relationship(cascade="all, delete-orphan", order_by="ApprovalStep.level", lazy="selectin")
    history: Mapped[list["ApprovalHistory"]] = relationship(cascade="all, delete-orphan", order_by="ApprovalHistory.seq", lazy="selectin")


class ApprovalStep(Base):
    __tablename__ = "approval_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    approval_id: Mapped[str] = mapped_column(String(36), ForeignKey("approvals.id", ondelete="CASCADE"), index=True)
    level: Mapped[int] = mapped_column(Integer)
    required_role: Mapped[str] = mapped_column(String(20), default="manager")
    status: Mapped[str] = mapped_column(String(10), default="waiting")  # waiting, pending, approved, rejected, skipped
    assigned_to_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)  # set when delegated
    assigned_to_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decided_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    decided_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApprovalHistory(Base):
    __tablename__ = "approval_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    approval_id: Mapped[str] = mapped_column(String(36), ForeignKey("approvals.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)  # explicit order: MySQL timestamps only have one-second precision
    action: Mapped[str] = mapped_column(String(20))
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ApprovalEvent(Base):
    """Outbox. Every state change writes a row in the same transaction. Phase 10 (notifications, audit) and Phase 11
    (SQS) publish these; `published_at` stays empty until then."""

    __tablename__ = "approval_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(40), index=True)
    approval_id: Mapped[str] = mapped_column(String(36), index=True)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
