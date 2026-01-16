"""Add n8n_connections table for self-healing integration.

Revision ID: 20250116_n8n_conn
Revises: 20250105_feedback
Create Date: 2025-01-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '20250116_n8n_conn'
down_revision = '20250105_feedback'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'n8n_connections',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('instance_url', sa.String(512), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('idx_n8n_connections_tenant', 'n8n_connections', ['tenant_id'])
    op.create_unique_constraint('uq_n8n_connection_name', 'n8n_connections', ['tenant_id', 'name'])


def downgrade() -> None:
    op.drop_constraint('uq_n8n_connection_name', 'n8n_connections', type_='unique')
    op.drop_index('idx_n8n_connections_tenant', 'n8n_connections')
    op.drop_table('n8n_connections')
