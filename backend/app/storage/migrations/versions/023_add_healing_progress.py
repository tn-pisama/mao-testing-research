"""Add detector_progress JSONB field to healing_records.

Tracks per-detector before/after confidence and fix status for
progress reporting across the healing pipeline.

Revision ID: 023_add_healing_progress
Revises: 022_add_harness_aware_fields
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "023_add_healing_progress"
down_revision = "022_add_harness_aware_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "healing_records",
        sa.Column("detector_progress", JSONB, server_default="{}", nullable=True),
    )


def downgrade() -> None:
    op.drop_column("healing_records", "detector_progress")
