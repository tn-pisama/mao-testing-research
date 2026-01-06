"""Add detection feedback table for threshold tuning.

Revision ID: 20250105_feedback
Revises: (depends on existing migrations)
Create Date: 2025-01-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '20250105_feedback'
down_revision = None  # Update with actual previous migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'detection_feedback',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('detection_id', UUID(as_uuid=True), sa.ForeignKey('detections.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('feedback_type', sa.String(32), nullable=False),
        sa.Column('detection_confidence', sa.Integer(), nullable=False),
        sa.Column('detection_method', sa.String(32), nullable=False),
        sa.Column('framework', sa.String(32), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('severity_rating', sa.Integer(), nullable=True),
        sa.Column('submitted_by', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index('idx_feedback_tenant', 'detection_feedback', ['tenant_id'])
    op.create_index('idx_feedback_type', 'detection_feedback', ['feedback_type'])
    op.create_index('idx_feedback_framework', 'detection_feedback', ['framework'])
    op.create_index('idx_feedback_created', 'detection_feedback', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_feedback_created', 'detection_feedback')
    op.drop_index('idx_feedback_framework', 'detection_feedback')
    op.drop_index('idx_feedback_type', 'detection_feedback')
    op.drop_index('idx_feedback_tenant', 'detection_feedback')
    op.drop_table('detection_feedback')
