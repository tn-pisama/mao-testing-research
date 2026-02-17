"""Add OpenClaw instance and agent tables

Revision ID: 010_add_openclaw_tables
Revises: 009_widen_overall_grade
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '010_add_openclaw_tables'
down_revision = '009_widen_overall_grade'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'openclaw_instances',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('gateway_url', sa.String(512), nullable=False),
        sa.Column('api_key_encrypted', sa.Text, nullable=False),
        sa.Column('openclaw_version', sa.String(32), nullable=True),
        sa.Column('channels_configured', JSONB, server_default='[]'),
        sa.Column('agents_mapping', JSONB, server_default='{}'),
        sa.Column('otel_endpoint', sa.String(512), nullable=True),
        sa.Column('otel_enabled', sa.Boolean, server_default='false'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_openclaw_instances_tenant', 'openclaw_instances', ['tenant_id'])
    op.create_unique_constraint('uq_openclaw_instance_name', 'openclaw_instances', ['tenant_id', 'name'])

    op.create_table(
        'openclaw_agents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('instance_id', UUID(as_uuid=True), sa.ForeignKey('openclaw_instances.id'), nullable=False),
        sa.Column('agent_key', sa.String(255), nullable=False),
        sa.Column('agent_name', sa.String(255), nullable=True),
        sa.Column('model', sa.String(128), nullable=True),
        sa.Column('workspace', sa.String(512), nullable=True),
        sa.Column('webhook_secret', sa.String(255), nullable=True),
        sa.Column('monitoring_enabled', sa.Boolean, server_default='true'),
        sa.Column('detection_overrides', JSONB, server_default='{}'),
        sa.Column('total_sessions', sa.Integer, server_default='0'),
        sa.Column('total_messages', sa.Integer, server_default='0'),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_openclaw_agents_tenant', 'openclaw_agents', ['tenant_id'])
    op.create_index('idx_openclaw_agents_instance', 'openclaw_agents', ['instance_id'])
    op.create_unique_constraint('uq_openclaw_agent', 'openclaw_agents', ['tenant_id', 'instance_id', 'agent_key'])


def downgrade() -> None:
    op.drop_table('openclaw_agents')
    op.drop_table('openclaw_instances')
