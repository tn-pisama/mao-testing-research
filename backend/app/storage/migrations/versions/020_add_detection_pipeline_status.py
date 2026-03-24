"""Add detection_status and detection_metadata to traces.

Tracks per-trace detection pipeline progress so partial results
survive detector failures (checkpoint-per-detector pattern).

Revision ID: 020_add_detection_pipeline_status
Revises: 019_add_cognitive_memory
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "020_add_detection_pipeline_status"
down_revision = "019_add_cognitive_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "traces",
        sa.Column("detection_status", sa.String(32), server_default="pending", nullable=True),
    )
    op.add_column(
        "traces",
        sa.Column("detection_metadata", JSONB, server_default="{}", nullable=True),
    )
    op.create_index("idx_traces_detection_status", "traces", ["detection_status"])


def downgrade() -> None:
    op.drop_index("idx_traces_detection_status", table_name="traces")
    op.drop_column("traces", "detection_metadata")
    op.drop_column("traces", "detection_status")
