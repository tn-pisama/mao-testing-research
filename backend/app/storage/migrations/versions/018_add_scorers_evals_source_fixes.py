"""Add custom_scorers, scorer_results, conversation_evaluations, source_fixes tables

Revision ID: 018_add_scorers_evals_source_fixes
Revises: 017_add_langgraph_tables
Create Date: 2026-03-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '018_add_scorers_evals_source_fixes'
down_revision = '017_add_langgraph_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- custom_scorers ---
    op.create_table(
        'custom_scorers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('prompt_template', sa.Text, nullable=False),
        sa.Column('scoring_criteria', JSONB, server_default='[]'),
        sa.Column('scoring_rubric', sa.Text, nullable=True),
        sa.Column('model_key', sa.String(64), server_default='sonnet-4'),
        sa.Column('score_range_min', sa.Integer, server_default='1'),
        sa.Column('score_range_max', sa.Integer, server_default='5'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_custom_scorers_tenant', 'custom_scorers', ['tenant_id'])
    op.create_index('idx_custom_scorers_active', 'custom_scorers', ['tenant_id', 'is_active'])

    # --- scorer_results ---
    op.create_table(
        'scorer_results',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('scorer_id', UUID(as_uuid=True), sa.ForeignKey('custom_scorers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('trace_id', UUID(as_uuid=True), sa.ForeignKey('traces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score', sa.Integer, nullable=False),
        sa.Column('confidence', sa.Integer, server_default='50'),
        sa.Column('verdict', sa.String(16), nullable=False),
        sa.Column('reasoning', sa.Text, nullable=True),
        sa.Column('evidence', JSONB, server_default='[]'),
        sa.Column('suggestions', JSONB, server_default='[]'),
        sa.Column('model_used', sa.String(128), nullable=True),
        sa.Column('tokens_used', sa.Integer, server_default='0'),
        sa.Column('cost_usd', sa.Integer, server_default='0'),
        sa.Column('latency_ms', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_scorer_results_scorer', 'scorer_results', ['scorer_id'])
    op.create_index('idx_scorer_results_tenant', 'scorer_results', ['tenant_id'])
    op.create_index('idx_scorer_results_trace', 'scorer_results', ['trace_id'])
    op.create_index('idx_scorer_results_verdict', 'scorer_results', ['verdict'])

    # --- conversation_evaluations ---
    op.create_table(
        'conversation_evaluations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('trace_id', UUID(as_uuid=True), sa.ForeignKey('traces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('overall_score', sa.Float, nullable=False),
        sa.Column('overall_grade', sa.String(2), nullable=False),
        sa.Column('dimension_scores', JSONB, nullable=False),
        sa.Column('scoring_method', sa.String(32), nullable=False),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('turn_annotations', JSONB, server_default='[]'),
        sa.Column('total_turns', sa.Integer, server_default='0'),
        sa.Column('total_participants', sa.Integer, server_default='0'),
        sa.Column('conversation_duration_ms', sa.Integer, nullable=True),
        sa.Column('eval_cost_usd', sa.Float, server_default='0.0'),
        sa.Column('eval_tokens_used', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_conv_eval_tenant', 'conversation_evaluations', ['tenant_id'])
    op.create_index('idx_conv_eval_trace', 'conversation_evaluations', ['trace_id'])
    op.create_index('idx_conv_eval_grade', 'conversation_evaluations', ['overall_grade'])
    op.create_index('idx_conv_eval_tenant_created', 'conversation_evaluations', ['tenant_id', 'created_at'])

    # --- source_fixes ---
    op.create_table(
        'source_fixes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('detection_id', UUID(as_uuid=True), sa.ForeignKey('detections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('language', sa.String(32), nullable=False),
        sa.Column('original_code', sa.Text, nullable=False),
        sa.Column('fixed_code', sa.Text, nullable=False),
        sa.Column('unified_diff', sa.Text, nullable=False),
        sa.Column('explanation', sa.Text, nullable=False),
        sa.Column('root_cause', sa.Text, nullable=True),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('breaking_risk', sa.String(16), server_default='low'),
        sa.Column('requires_testing', sa.Boolean, server_default='true'),
        sa.Column('framework_specific', sa.Boolean, server_default='false'),
        sa.Column('model_used', sa.String(128), nullable=True),
        sa.Column('generation_cost_usd', sa.Float, server_default='0.0'),
        sa.Column('generation_tokens', sa.Integer, server_default='0'),
        sa.Column('status', sa.String(32), server_default='generated'),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('applied_by', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_source_fix_tenant', 'source_fixes', ['tenant_id'])
    op.create_index('idx_source_fix_detection', 'source_fixes', ['detection_id'])
    op.create_index('idx_source_fix_status', 'source_fixes', ['status'])
    op.create_index('idx_source_fix_language', 'source_fixes', ['language'])
    op.create_index('idx_source_fix_created', 'source_fixes', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_source_fix_created', 'source_fixes')
    op.drop_index('idx_source_fix_language', 'source_fixes')
    op.drop_index('idx_source_fix_status', 'source_fixes')
    op.drop_index('idx_source_fix_detection', 'source_fixes')
    op.drop_index('idx_source_fix_tenant', 'source_fixes')
    op.drop_table('source_fixes')

    op.drop_index('idx_conv_eval_tenant_created', 'conversation_evaluations')
    op.drop_index('idx_conv_eval_grade', 'conversation_evaluations')
    op.drop_index('idx_conv_eval_trace', 'conversation_evaluations')
    op.drop_index('idx_conv_eval_tenant', 'conversation_evaluations')
    op.drop_table('conversation_evaluations')

    op.drop_index('idx_scorer_results_verdict', 'scorer_results')
    op.drop_index('idx_scorer_results_trace', 'scorer_results')
    op.drop_index('idx_scorer_results_tenant', 'scorer_results')
    op.drop_index('idx_scorer_results_scorer', 'scorer_results')
    op.drop_table('scorer_results')

    op.drop_index('idx_custom_scorers_active', 'custom_scorers')
    op.drop_index('idx_custom_scorers_tenant', 'custom_scorers')
    op.drop_table('custom_scorers')
