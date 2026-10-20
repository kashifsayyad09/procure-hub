import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Naive UTC. MySQL DATETIME has no timezone, so every timestamp in this service is UTC."""
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid.uuid4())


def later(**kw: float) -> datetime:
    return utcnow() + timedelta(**kw)


class Role(StrEnum):
    # Same identifiers the frontend uses in src/types/roles.ts
    EMPLOYEE = "employee"
    MANAGER = "manager"
    PROCUREMENT = "procurement"
    VENDOR = "vendor"
    FINANCE = "finance"
    ADMIN = "admin"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class RefreshToken(Base):
    """Only the SHA-256 of the token is stored. Tokens in one login share a family_id for reuse detection."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[str] = mapped_column(String(36), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replaced_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
