"""vendors, categories, contacts, history, outbox, number sequence

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
    op.create_table("vendors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("owner_id", sa.String(36), nullable=True, unique=True),
        sa.Column("created_by_id", sa.String(36), nullable=False),
        sa.Column("created_by_name", sa.String(120), nullable=False),
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("trade_name", sa.String(200), nullable=True),
        sa.Column("tax_id", sa.String(30), nullable=True, unique=True),
        sa.Column("registration_number", sa.String(50), nullable=True),
        sa.Column("website", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("address_line1", sa.String(150), nullable=False),
        sa.Column("address_line2", sa.String(150), nullable=True),
        sa.Column("city", sa.String(80), nullable=False),
        sa.Column("state", sa.String(80), nullable=False),
        sa.Column("postal_code", sa.String(20), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("payment_terms_days", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("status_note", sa.String(500), nullable=True),
        sa.Column("submitted_by_id", sa.String(36), nullable=True),
        sa.Column("submitted_at", sa.DateTime, nullable=True),
        sa.Column("verified_at", sa.DateTime, nullable=True),
        sa.Column("verified_by_name", sa.String(120), nullable=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False))
    op.create_index("ix_vendors_legal_name", "vendors", ["legal_name"])
    op.create_index("ix_vendors_country", "vendors", ["country"])
    op.create_index("ix_vendors_created_at", "vendors", ["created_at"])
    op.create_index("ix_vendors_status_created", "vendors", ["status", "created_at"])

    op.create_table("vendor_categories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vendor_id", sa.String(36), sa.ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.UniqueConstraint("vendor_id", "category", name="uq_vendor_category"))
    op.create_index("ix_vendor_categories_vendor_id", "vendor_categories", ["vendor_id"])
    op.create_index("ix_vendor_categories_category", "vendor_categories", ["category"])

    op.create_table("vendor_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vendor_id", sa.String(36), sa.ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("job_title", sa.String(80), nullable=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("is_primary", sa.Boolean, nullable=False))
    op.create_index("ix_vendor_contacts_vendor_id", "vendor_contacts", ["vendor_id"])

    op.create_table("vendor_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vendor_id", sa.String(36), sa.ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor_name", sa.String(120), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False))
    op.create_index("ix_vendor_history_vendor_id", "vendor_history", ["vendor_id"])

    op.create_table("vendor_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("vendor_id", sa.String(36), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("published_at", sa.DateTime, nullable=True))
    op.create_index("ix_vendor_events_type", "vendor_events", ["type"])
    op.create_index("ix_vendor_events_vendor_id", "vendor_events", ["vendor_id"])
    op.create_index("ix_vendor_events_created_at", "vendor_events", ["created_at"])


def downgrade() -> None:
    for t in ("vendor_events", "vendor_history", "vendor_contacts", "vendor_categories", "vendors", "number_sequences"):
        op.drop_table(t)
