"""Add golden_dataset_entries table

Revision ID: 20260228_golden_entries
Revises: 20260202_add_billing
Create Date: 2026-02-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20260228_golden_entries'
down_revision = '20260202_add_billing'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create golden_dataset_entries table for calibration/training data."""
    op.create_table(
        'golden_dataset_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('entry_key', sa.String(255), nullable=False, unique=True),
        sa.Column('detection_type', sa.String(64), nullable=False),
        sa.Column('input_data', postgresql.JSONB, nullable=False),
        sa.Column('expected_detected', sa.Boolean, nullable=False),
        sa.Column('expected_confidence_min', sa.Float, server_default='0.0'),
        sa.Column('expected_confidence_max', sa.Float, server_default='1.0'),
        sa.Column('description', sa.Text, server_default=''),
        sa.Column('source', sa.String(64), server_default='manual'),
        sa.Column('tags', postgresql.JSONB, server_default='[]'),
        sa.Column('difficulty', sa.String(16), server_default='easy'),
        sa.Column('split', sa.String(16), server_default='train'),
        sa.Column('source_trace_id', sa.String(255), nullable=True),
        sa.Column('source_workflow_id', sa.String(255), nullable=True),
        sa.Column('augmentation_method', sa.String(128), nullable=True),
        sa.Column('human_verified', sa.Boolean, server_default='false'),
        sa.Column('entry_metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes for common query patterns
    op.create_index('idx_gde_tenant', 'golden_dataset_entries', ['tenant_id'])
    op.create_index('idx_gde_detection_type', 'golden_dataset_entries', ['detection_type'])
    op.create_index('idx_gde_split', 'golden_dataset_entries', ['split'])
    op.create_index('idx_gde_source', 'golden_dataset_entries', ['source'])
    op.create_index('idx_gde_difficulty', 'golden_dataset_entries', ['difficulty'])
    op.create_index('idx_gde_type_split', 'golden_dataset_entries',
                     ['detection_type', 'split'])
    op.create_index('idx_gde_type_detected', 'golden_dataset_entries',
                     ['detection_type', 'expected_detected'])
    op.create_index('idx_gde_tenant_type', 'golden_dataset_entries',
                     ['tenant_id', 'detection_type'])
    op.create_index('idx_gde_tags', 'golden_dataset_entries', ['tags'],
                     postgresql_using='gin')
    op.create_index('idx_gde_created', 'golden_dataset_entries', ['created_at'])


def downgrade() -> None:
    """Drop golden_dataset_entries table."""
    op.drop_table('golden_dataset_entries')
