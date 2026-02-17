"""Add Dify instance and app tables

Revision ID: 011_add_dify_tables
Revises: 010_add_openclaw_tables
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '011_add_dify_tables'
down_revision = '010_add_openclaw_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'dify_instances',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('base_url', sa.String(512), nullable=False),
        sa.Column('api_key_encrypted', sa.Text, nullable=False),
        sa.Column('dify_version', sa.String(32), nullable=True),
        sa.Column('app_types_configured', JSONB, server_default='[]'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_dify_instances_tenant', 'dify_instances', ['tenant_id'])
    op.create_unique_constraint('uq_dify_instance_name', 'dify_instances', ['tenant_id', 'name'])

    op.create_table(
        'dify_apps',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('instance_id', UUID(as_uuid=True), sa.ForeignKey('dify_instances.id'), nullable=False),
        sa.Column('app_id', sa.String(255), nullable=False),
        sa.Column('app_name', sa.String(255), nullable=True),
        sa.Column('app_type', sa.String(64), nullable=False),
        sa.Column('webhook_secret', sa.String(255), nullable=True),
        sa.Column('monitoring_enabled', sa.Boolean, server_default='true'),
        sa.Column('detection_overrides', JSONB, server_default='{}'),
        sa.Column('total_runs', sa.Integer, server_default='0'),
        sa.Column('total_tokens', sa.Integer, server_default='0'),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_dify_apps_tenant', 'dify_apps', ['tenant_id'])
    op.create_index('idx_dify_apps_instance', 'dify_apps', ['instance_id'])
    op.create_unique_constraint('uq_dify_app', 'dify_apps', ['tenant_id', 'instance_id', 'app_id'])


def downgrade() -> None:
    op.drop_table('dify_apps')
    op.drop_table('dify_instances')
