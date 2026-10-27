"""purchase requests, items, documents, history, number sequence

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
    op.create_table("number_sequences",
        sa.Column("year", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("last_value", sa.Integer, nullable=False))
    op.create_table("purchase_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("requester_id", sa.String(36), nullable=False),
        sa.Column("requester_name", sa.String(120), nullable=False),
        sa.Column("requester_email", sa.String(254), nullable=False),
        sa.Column("department", sa.String(80), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("justification", sa.Text, nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("needed_by", sa.Date, nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("cancel_reason", sa.String(500), nullable=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("submitted_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False))
    op.create_index("ix_purchase_requests_requester_id", "purchase_requests", ["requester_id"])
    op.create_index("ix_purchase_requests_created_at", "purchase_requests", ["created_at"])
    op.create_index("ix_pr_requester_status", "purchase_requests", ["requester_id", "status"])
    op.create_index("ix_pr_status_created", "purchase_requests", ["status", "created_at"])

    op.create_table("purchase_request_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer, nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True))
    op.create_index("ix_purchase_request_items_request_id", "purchase_request_items", ["request_id"])

    op.create_table("purchase_request_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("file_name", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("storage_key", sa.String(200), nullable=False),
        sa.Column("content_stored", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False))
    op.create_index("ix_purchase_request_documents_request_id", "purchase_request_documents", ["request_id"])

    op.create_table("purchase_request_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor_name", sa.String(120), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False))
    op.create_index("ix_purchase_request_history_request_id", "purchase_request_history", ["request_id"])


def downgrade() -> None:
    for t in ("purchase_request_history", "purchase_request_documents", "purchase_request_items", "purchase_requests", "number_sequences"):
        op.drop_table(t)
