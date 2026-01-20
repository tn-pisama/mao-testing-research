"""Add n8n_connections table

Revision ID: 006_add_n8n_connections
Revises: 005_add_mast_trace_embeddings
Create Date: 2026-01-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "006_add_n8n_connections"
down_revision = "005_add_mast_trace_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "n8n_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("instance_url", sa.String(512), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_n8n_connections_tenant", "n8n_connections", ["tenant_id"])
    op.create_unique_constraint("uq_n8n_connection_name", "n8n_connections", ["tenant_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_n8n_connection_name", "n8n_connections", type_="unique")
    op.drop_index("idx_n8n_connections_tenant", table_name="n8n_connections")
    op.drop_table("n8n_connections")
