"""Add replay_bundles and replay_results tables

Revision ID: 008_add_replay_tables
Revises: 007_add_workflow_groups
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '008_add_replay_tables'
down_revision = '007_add_workflow_groups'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'replay_bundles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('trace_id', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='ready'),
        sa.Column('event_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duration_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('models_used', JSONB(), nullable=True),
        sa.Column('tools_used', JSONB(), nullable=True),
        sa.Column('agents_involved', JSONB(), nullable=True),
        sa.Column('bundle_data', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_replay_bundles_tenant', 'replay_bundles', ['tenant_id'])
    op.create_index('idx_replay_bundles_trace', 'replay_bundles', ['trace_id'])

    op.create_table(
        'replay_results',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('bundle_id', UUID(as_uuid=True), sa.ForeignKey('replay_bundles.id'), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('mode', sa.String(32), nullable=False, server_default='deterministic'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('events_replayed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('events_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('matches', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('mismatches', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('similarity_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('diffs', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_replay_results_bundle', 'replay_results', ['bundle_id'])
    op.create_index('idx_replay_results_tenant', 'replay_results', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('idx_replay_results_tenant', table_name='replay_results')
    op.drop_index('idx_replay_results_bundle', table_name='replay_results')
    op.drop_table('replay_results')

    op.drop_index('idx_replay_bundles_trace', table_name='replay_bundles')
    op.drop_index('idx_replay_bundles_tenant', table_name='replay_bundles')
    op.drop_table('replay_bundles')
