"""Persist administrator-configurable response and escalation targets."""

from alembic import op
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, inspect

revision = "0002_service_policies"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    if "service_policies" not in inspect(op.get_bind()).get_table_names():
        op.create_table(
            "service_policies",
            Column("category", String(80), primary_key=True),
            Column("deadline_hours", Integer(), nullable=False, server_default="72"),
            Column("escalation_grace_hours", Integer(), nullable=False, server_default="24"),
            Column("updated_by_id", Integer(), ForeignKey("users.id"), nullable=True),
            Column("updated_at", DateTime(), nullable=False),
        )


def downgrade():
    if "service_policies" in inspect(op.get_bind()).get_table_names():
        op.drop_table("service_policies")
