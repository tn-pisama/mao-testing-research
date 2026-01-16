"""Add staged deployment and rollback support for n8n fixes.

Revision ID: 20250116_staged
Revises: 20250116_n8n_conn
Create Date: 2025-01-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '20250116_staged'
down_revision = '20250116_n8n_conn'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns to healing_records for n8n workflow tracking
    op.add_column('healing_records',
        sa.Column('workflow_id', sa.String(255), nullable=True))
    op.add_column('healing_records',
        sa.Column('n8n_connection_id', UUID(as_uuid=True), sa.ForeignKey('n8n_connections.id'), nullable=True))
    op.add_column('healing_records',
        sa.Column('deployment_stage', sa.String(32), nullable=True))  # staged, promoted, rejected
    op.add_column('healing_records',
        sa.Column('staged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('healing_records',
        sa.Column('promoted_at', sa.DateTime(timezone=True), nullable=True))

    # Index for querying by workflow
    op.create_index('idx_healing_workflow', 'healing_records', ['workflow_id'])
    op.create_index('idx_healing_connection', 'healing_records', ['n8n_connection_id'])
    op.create_index('idx_healing_stage', 'healing_records', ['deployment_stage'])

    # Create workflow_versions table for version history
    op.create_table(
        'workflow_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('workflow_id', sa.String(255), nullable=False),
        sa.Column('connection_id', UUID(as_uuid=True), sa.ForeignKey('n8n_connections.id'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('workflow_snapshot', JSONB(), nullable=False),
        sa.Column('healing_id', UUID(as_uuid=True), sa.ForeignKey('healing_records.id'), nullable=True),
        sa.Column('change_type', sa.String(32), nullable=False),  # fix_applied, rollback, promoted, rejected, restored
        sa.Column('change_description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Indexes for workflow_versions
    op.create_index('idx_wv_tenant', 'workflow_versions', ['tenant_id'])
    op.create_index('idx_wv_workflow', 'workflow_versions', ['workflow_id'])
    op.create_index('idx_wv_connection', 'workflow_versions', ['connection_id'])
    op.create_index('idx_wv_healing', 'workflow_versions', ['healing_id'])
    op.create_unique_constraint(
        'uq_workflow_version_number',
        'workflow_versions',
        ['tenant_id', 'workflow_id', 'version_number']
    )


def downgrade() -> None:
    # Drop workflow_versions table
    op.drop_constraint('uq_workflow_version_number', 'workflow_versions', type_='unique')
    op.drop_index('idx_wv_healing', 'workflow_versions')
    op.drop_index('idx_wv_connection', 'workflow_versions')
    op.drop_index('idx_wv_workflow', 'workflow_versions')
    op.drop_index('idx_wv_tenant', 'workflow_versions')
    op.drop_table('workflow_versions')

    # Drop healing_records columns
    op.drop_index('idx_healing_stage', 'healing_records')
    op.drop_index('idx_healing_connection', 'healing_records')
    op.drop_index('idx_healing_workflow', 'healing_records')
    op.drop_column('healing_records', 'promoted_at')
    op.drop_column('healing_records', 'staged_at')
    op.drop_column('healing_records', 'deployment_stage')
    op.drop_column('healing_records', 'n8n_connection_id')
    op.drop_column('healing_records', 'workflow_id')
