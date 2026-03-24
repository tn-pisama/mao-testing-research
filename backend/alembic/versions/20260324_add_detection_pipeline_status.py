"""Add detection pipeline status fields to traces

Revision ID: 20260324_detection_status
Revises: 20260312_api_audit
Create Date: 2026-03-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20260324_detection_status'
down_revision = '20260312_api_audit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('traces', sa.Column('detection_status', sa.String(32), server_default='pending'))
    op.add_column('traces', sa.Column('detection_metadata', postgresql.JSONB(), server_default='{}'))
    op.create_index('idx_traces_detection_status', 'traces', ['detection_status'])


def downgrade() -> None:
    op.drop_index('idx_traces_detection_status', table_name='traces')
    op.drop_column('traces', 'detection_metadata')
    op.drop_column('traces', 'detection_status')
