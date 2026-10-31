"""approvals, steps, history, event outbox

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("request_number", sa.String(20), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("justification", sa.Text, nullable=False),
        sa.Column("department", sa.String(80), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("needed_by", sa.Date, nullable=True),
        sa.Column("requester_id", sa.String(36), nullable=False),
        sa.Column("requester_name", sa.String(120), nullable=False),
        sa.Column("requester_email", sa.String(254), nullable=False),
        sa.Column("items_json", sa.Text, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("current_level", sa.Integer, nullable=False),
        sa.Column("total_levels", sa.Integer, nullable=False),
        sa.Column("decision_sync", sa.String(10), nullable=False),
        sa.Column("sync_attempts", sa.Integer, nullable=False),
        sa.Column("last_sync_error", sa.String(300), nullable=True),
        sa.Column("submitted_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("decided_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False))
    op.create_index("ix_approvals_request_number", "approvals", ["request_number"])
    op.create_index("ix_approvals_requester_id", "approvals", ["requester_id"])
    op.create_index("ix_approvals_status_created", "approvals", ["status", "created_at"])

    op.create_table("approval_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("approval_id", sa.String(36), sa.ForeignKey("approvals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("required_role", sa.String(20), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("assigned_to_id", sa.String(36), nullable=True),
        sa.Column("assigned_to_name", sa.String(120), nullable=True),
        sa.Column("decided_by_id", sa.String(36), nullable=True),
        sa.Column("decided_by_name", sa.String(120), nullable=True),
        sa.Column("decided_at", sa.DateTime, nullable=True),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column("activated_at", sa.DateTime, nullable=True),
        sa.Column("escalated_at", sa.DateTime, nullable=True))
    op.create_index("ix_approval_steps_approval_id", "approval_steps", ["approval_id"])
    op.create_index("ix_approval_steps_assigned_to_id", "approval_steps", ["assigned_to_id"])
    op.create_index("ix_approval_steps_decided_by_id", "approval_steps", ["decided_by_id"])

    op.create_table("approval_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("approval_id", sa.String(36), sa.ForeignKey("approvals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("level", sa.Integer, nullable=True),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("actor_name", sa.String(120), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False))
    op.create_index("ix_approval_history_approval_id", "approval_history", ["approval_id"])

    op.create_table("approval_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("approval_id", sa.String(36), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("published_at", sa.DateTime, nullable=True))
    op.create_index("ix_approval_events_type", "approval_events", ["type"])
    op.create_index("ix_approval_events_approval_id", "approval_events", ["approval_id"])
    op.create_index("ix_approval_events_created_at", "approval_events", ["created_at"])


def downgrade() -> None:
    for t in ("approval_events", "approval_history", "approval_steps", "approvals"):
        op.drop_table(t)
