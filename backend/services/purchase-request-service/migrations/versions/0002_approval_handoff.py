"""approval hand-off: registration flag and decision details

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows get approval_registered = false, so submitted requests from before this phase are picked up
    # by the retry loop and registered with the Approval service automatically.
    op.add_column("purchase_requests", sa.Column("approval_registered", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("purchase_requests", sa.Column("decided_at", sa.DateTime, nullable=True))
    op.add_column("purchase_requests", sa.Column("decided_by_name", sa.String(120), nullable=True))
    op.add_column("purchase_requests", sa.Column("decision_note", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("purchase_requests") as batch:
        for col in ("decision_note", "decided_by_name", "decided_at", "approval_registered"):
            batch.drop_column(col)
