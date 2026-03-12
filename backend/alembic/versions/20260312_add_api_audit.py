"""Add api_audit table for API mutation logging

Revision ID: 20260312_api_audit
Revises: 20260228_golden_entries
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20260312_api_audit'
down_revision = '20260228_golden_entries'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'api_audit',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('path', sa.String(500), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('correlation_id', sa.String(64), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_api_audit_tenant', 'api_audit', ['tenant_id'])
    op.create_index('idx_api_audit_created', 'api_audit', ['created_at'])
    op.create_index('idx_api_audit_method', 'api_audit', ['method'])


def downgrade() -> None:
    op.drop_index('idx_api_audit_method')
    op.drop_index('idx_api_audit_created')
    op.drop_index('idx_api_audit_tenant')
    op.drop_table('api_audit')
