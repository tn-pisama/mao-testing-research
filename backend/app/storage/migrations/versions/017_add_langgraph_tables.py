"""Add LangGraph deployment and assistant tables, plus healing FK columns

Revision ID: 017_add_langgraph_tables
Revises: 016_add_golden_dataset_entries
Create Date: 2026-03-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '017_add_langgraph_tables'
down_revision = '016_add_golden_dataset_entries'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # LangGraph deployments (mirrors DifyInstance / OpenClawInstance)
    op.create_table(
        'langgraph_deployments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('api_url', sa.String(512), nullable=False),
        sa.Column('api_key_encrypted', sa.Text, nullable=False),
        sa.Column('deployment_id', sa.String(255), nullable=True),
        sa.Column('graph_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('ingestion_mode', sa.String(20), server_default='full', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_lg_deployments_tenant', 'langgraph_deployments', ['tenant_id'])
    op.create_unique_constraint('uq_lg_deployment_name', 'langgraph_deployments', ['tenant_id', 'name'])

    # LangGraph assistants (mirrors DifyApp / OpenClawAgent)
    op.create_table(
        'langgraph_assistants',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('deployment_id', UUID(as_uuid=True), sa.ForeignKey('langgraph_deployments.id'), nullable=False),
        sa.Column('assistant_id', sa.String(255), nullable=False),
        sa.Column('graph_id', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('webhook_secret', sa.String(255), nullable=True),
        sa.Column('monitoring_enabled', sa.Boolean, server_default='true'),
        sa.Column('detection_overrides', JSONB, server_default='{}'),
        sa.Column('ingestion_mode', sa.String(20), nullable=True),
        sa.Column('total_runs', sa.Integer, server_default='0'),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_lg_assistants_tenant', 'langgraph_assistants', ['tenant_id'])
    op.create_index('idx_lg_assistants_deployment', 'langgraph_assistants', ['deployment_id'])
    op.create_unique_constraint('uq_lg_assistant', 'langgraph_assistants', ['tenant_id', 'deployment_id', 'assistant_id'])

    # Add framework FK columns to healing_records for rollback support
    op.add_column('healing_records', sa.Column(
        'dify_instance_id', UUID(as_uuid=True),
        sa.ForeignKey('dify_instances.id'), nullable=True,
    ))
    op.add_column('healing_records', sa.Column(
        'openclaw_instance_id', UUID(as_uuid=True),
        sa.ForeignKey('openclaw_instances.id'), nullable=True,
    ))
    op.add_column('healing_records', sa.Column(
        'langgraph_deployment_id', UUID(as_uuid=True),
        sa.ForeignKey('langgraph_deployments.id'), nullable=True,
    ))
    op.create_index('idx_healing_dify', 'healing_records', ['dify_instance_id'])
    op.create_index('idx_healing_openclaw', 'healing_records', ['openclaw_instance_id'])
    op.create_index('idx_healing_langgraph', 'healing_records', ['langgraph_deployment_id'])


def downgrade() -> None:
    op.drop_index('idx_healing_langgraph', 'healing_records')
    op.drop_index('idx_healing_openclaw', 'healing_records')
    op.drop_index('idx_healing_dify', 'healing_records')
    op.drop_column('healing_records', 'langgraph_deployment_id')
    op.drop_column('healing_records', 'openclaw_instance_id')
    op.drop_column('healing_records', 'dify_instance_id')
    op.drop_table('langgraph_assistants')
    op.drop_table('langgraph_deployments')
