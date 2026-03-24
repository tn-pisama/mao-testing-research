"""Add harness-aware schema fields to traces and states

Revision ID: 20260324_harness_schema
Revises: 20260324_detection_status
Create Date: 2026-03-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260324_harness_schema'
down_revision = '20260324_detection_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trace: harness type classification
    op.add_column('traces', sa.Column('harness_type', sa.String(32), nullable=True))

    # State: agent role, sprint boundary, context reset
    op.add_column('states', sa.Column('agent_role', sa.String(32), nullable=True))
    op.add_column('states', sa.Column('sprint_id', sa.String(64), nullable=True))
    op.add_column('states', sa.Column('context_reset', sa.Boolean(), server_default='false'))


def downgrade() -> None:
    op.drop_column('states', 'context_reset')
    op.drop_column('states', 'sprint_id')
    op.drop_column('states', 'agent_role')
    op.drop_column('traces', 'harness_type')
