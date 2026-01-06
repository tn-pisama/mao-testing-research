"""Add healing_records table for self-healing tracking.

Revision ID: 004_add_healing_records
Revises: 003_add_conversation_turns
Create Date: 2026-01-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_add_healing_records'
down_revision = '003_add_conversation_turns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create healing_records table."""
    op.create_table(
        'healing_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('detection_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('fix_type', sa.String(64), nullable=False),
        sa.Column('fix_id', sa.String(64), nullable=False),
        sa.Column('fix_suggestions', postgresql.JSONB(), nullable=False),
        sa.Column('applied_fixes', postgresql.JSONB(), server_default='{}'),
        sa.Column('original_state', postgresql.JSONB(), server_default='{}'),
        sa.Column('rollback_available', sa.Boolean(), server_default='true'),
        sa.Column('validation_status', sa.String(32), nullable=True),
        sa.Column('validation_results', postgresql.JSONB(), server_default='{}'),
        sa.Column('approval_required', sa.Boolean(), server_default='false'),
        sa.Column('approved_by', sa.String(128), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rolled_back_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['detection_id'], ['detections.id']),
    )

    # Create indexes for common query patterns
    op.create_index('idx_healing_tenant', 'healing_records', ['tenant_id'])
    op.create_index('idx_healing_detection', 'healing_records', ['detection_id'])
    op.create_index('idx_healing_status', 'healing_records', ['status'])
    op.create_index('idx_healing_created', 'healing_records', ['created_at'])


def downgrade() -> None:
    """Drop healing_records table."""
    op.drop_index('idx_healing_created', table_name='healing_records')
    op.drop_index('idx_healing_status', table_name='healing_records')
    op.drop_index('idx_healing_detection', table_name='healing_records')
    op.drop_index('idx_healing_tenant', table_name='healing_records')
    op.drop_table('healing_records')
