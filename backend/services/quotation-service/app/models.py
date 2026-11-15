import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Naive UTC (MySQL DATETIME has no timezone)."""
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid.uuid4())


class RfqStatus(StrEnum):
    DRAFT = "draft"          # being prepared; invitations are chosen but not sent
    ISSUED = "issued"        # invited vendors can see it and quote until the deadline
    CLOSED = "closed"        # no more quotations; submitted ones can be compared and one selected
    AWARDED = "awarded"      # a supplier is selected (an active selection exists)
    CANCELLED = "cancelled"  # abandoned; the purchase request can go out for quotation again


class InvitationStatus(StrEnum):
    INVITED = "invited"
    DECLINED = "declined"    # the vendor said no
    WITHDRAWN = "withdrawn"  # procurement took the invitation back


class QuotationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    SELECTED = "selected"
    NOT_SELECTED = "not_selected"


class SelectionStatus(StrEnum):
    AWARDED = "awarded"
    REVOKED = "revoked"


class Base(DeclarativeBase):
    pass


class NumberSequence(Base):
    """One counter per kind (RFQ, QTN) and year, locked while a number is allocated."""

    __tablename__ = "number_sequences"
    kind: Mapped[str] = mapped_column(String(3), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_value: Mapped[int] = mapped_column(Integer, default=0)


class Rfq(Base):
    __tablename__ = "rfqs"
    __table_args__ = (Index("ix_rfqs_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    # The approved purchase request this RFQ came from. A copy of what is needed is kept here; the id is not a foreign key (another service's database).
    purchase_request_id: Mapped[str] = mapped_column(String(36), index=True)
    purchase_request_number: Mapped[str] = mapped_column(String(20))
    department: Mapped[str] = mapped_column(String(80), default="")
    needed_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Set to the purchase request id while this RFQ is in use and cleared when it is cancelled, so a unique index allows
    # one live RFQ per request (MySQL has no partial unique indexes).
    active_request_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # internal budget: never shown to vendors
    currency: Mapped[str] = mapped_column(String(3))
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default=RfqStatus.DRAFT.value)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by_id: Mapped[str] = mapped_column(String(36))
    created_by_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    items: Mapped[list["RfqItem"]] = relationship(cascade="all, delete-orphan", order_by="RfqItem.line_no", lazy="selectin")
    invitations: Mapped[list["Invitation"]] = relationship(cascade="all, delete-orphan", order_by="Invitation.invited_at", lazy="selectin")
    history: Mapped[list["RfqHistory"]] = relationship(cascade="all, delete-orphan", order_by="RfqHistory.seq", lazy="selectin")


class RfqItem(Base):
    __tablename__ = "rfq_items"
    __table_args__ = (UniqueConstraint("rfq_id", "line_no", name="uq_rfq_item_line"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rfq_id: Mapped[str] = mapped_column(String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(300))
    specification: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(20))
    estimated_unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # internal estimate from the request: never shown to vendors


class Invitation(Base):
    __tablename__ = "rfq_invitations"
    __table_args__ = (UniqueConstraint("rfq_id", "vendor_id", name="uq_invitation_rfq_vendor"), Index("ix_invitations_vendor", "vendor_id", "status"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rfq_id: Mapped[str] = mapped_column(String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), index=True)
    vendor_id: Mapped[str] = mapped_column(String(36))  # vendor service id; not a foreign key
    vendor_number: Mapped[str] = mapped_column(String(20))
    vendor_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default=InvitationStatus.INVITED.value)
    invited_by_id: Mapped[str] = mapped_column(String(36))
    invited_by_name: Mapped[str] = mapped_column(String(120))
    invited_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # set when the RFQ is issued; until then the vendor cannot see it
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Quotation(Base):
    __tablename__ = "quotations"
    __table_args__ = (UniqueConstraint("rfq_id", "vendor_id", name="uq_quotation_rfq_vendor"), Index("ix_quotations_rfq_status", "rfq_id", "status"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    rfq_id: Mapped[str] = mapped_column(String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), index=True)
    vendor_id: Mapped[str] = mapped_column(String(36), index=True)
    vendor_number: Mapped[str] = mapped_column(String(20))
    vendor_name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3))
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_terms_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    terms: Mapped[str] = mapped_column(Text, default="")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))  # computed by the server from the priced lines
    status: Mapped[str] = mapped_column(String(20), default=QuotationStatus.DRAFT.value)
    revision: Mapped[int] = mapped_column(Integer, default=1)  # goes up each time a submitted quotation is withdrawn for changes
    version: Mapped[int] = mapped_column(Integer, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[str] = mapped_column(String(36))
    created_by_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    items: Mapped[list["QuotationItem"]] = relationship(cascade="all, delete-orphan", order_by="QuotationItem.line_no", lazy="selectin")


class QuotationItem(Base):
    __tablename__ = "quotation_items"
    __table_args__ = (UniqueConstraint("quotation_id", "rfq_item_id", name="uq_quotation_item"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    quotation_id: Mapped[str] = mapped_column(String(36), ForeignKey("quotations.id", ondelete="CASCADE"), index=True)
    rfq_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("rfq_items.id", ondelete="CASCADE"))
    line_no: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))  # copied from the RFQ line; the vendor cannot change what is being asked for
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)  # null means "not quoted"
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)


class Evaluation(Base):
    """The two judgements a person makes (compliance and commercial terms). Price and delivery scores are calculated when read,
    so they can never disagree with the quotations."""

    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rfq_id: Mapped[str] = mapped_column(String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), index=True)
    quotation_id: Mapped[str] = mapped_column(String(36), ForeignKey("quotations.id", ondelete="CASCADE"), unique=True)
    compliance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0 to 10, entered by the evaluator
    compliance_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    terms_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0 to 10, entered by the evaluator
    terms_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    evaluator_id: Mapped[str] = mapped_column(String(36))
    evaluator_name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Selection(Base):
    """The award decision. Rows are never edited except to mark them revoked, so the history of awards stays whole."""

    __tablename__ = "selections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rfq_id: Mapped[str] = mapped_column(String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=1)  # 1 for the first award of this RFQ, 2 for the next after a revoke, and so on
    quotation_id: Mapped[str] = mapped_column(String(36), ForeignKey("quotations.id", ondelete="CASCADE"))
    vendor_id: Mapped[str] = mapped_column(String(36))
    vendor_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default=SelectionStatus.AWARDED.value)
    # Set to the RFQ id while the award stands, cleared on revoke: a unique index means an RFQ can never have two final awards.
    active_rfq_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    justification: Mapped[str] = mapped_column(Text)
    acknowledged_missing_items: Mapped[bool] = mapped_column(Boolean, default=False)
    currency: Mapped[str] = mapped_column(String(3))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    score_snapshot: Mapped[str] = mapped_column(Text)  # JSON: the scores and weights as they were when the decision was made
    selected_by_id: Mapped[str] = mapped_column(String(36))
    selected_by_name: Mapped[str] = mapped_column(String(120))
    selected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    revoked_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class RfqHistory(Base):
    __tablename__ = "rfq_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rfq_id: Mapped[str] = mapped_column(String(36), ForeignKey("rfqs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)  # explicit order: timestamps only have 1-second precision in MySQL
    action: Mapped[str] = mapped_column(String(30))
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str] = mapped_column(String(36))
    actor_name: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class QuotationEvent(Base):
    """Outbox. Every state change writes a row in the same transaction. Phases 10 and 11 publish these (notifications, audit);
    `published_at` stays empty until then."""

    __tablename__ = "quotation_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(40), index=True)
    rfq_id: Mapped[str] = mapped_column(String(36), index=True)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
