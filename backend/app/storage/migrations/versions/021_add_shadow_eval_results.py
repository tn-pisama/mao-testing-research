"""Add shadow_eval_results table for runtime judge drift detection.

Stores results from periodically injecting golden-dataset samples into
the live detection pipeline, enabling drift monitoring.

Revision ID: 021_add_shadow_eval_results
Revises: 020_add_detection_pipeline_status
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "021_add_shadow_eval_results"
down_revision = "020_add_detection_pipeline_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shadow_eval_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("detector_type", sa.String(64), nullable=False),
        sa.Column("golden_entry_id", sa.String(255), nullable=False),
        sa.Column("expected_detected", sa.Boolean, nullable=False),
        sa.Column("actual_detected", sa.Boolean, nullable=False),
        sa.Column("expected_confidence_min", sa.Float, server_default="0.0"),
        sa.Column("expected_confidence_max", sa.Float, server_default="1.0"),
        sa.Column("actual_confidence", sa.Float, nullable=False),
        sa.Column("match", sa.Boolean, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_shadow_eval_detector", "shadow_eval_results", ["detector_type"])
    op.create_index("idx_shadow_eval_created", "shadow_eval_results", ["created_at"])
    op.create_index("idx_shadow_eval_match", "shadow_eval_results", ["detector_type", "match"])


def downgrade() -> None:
    op.drop_index("idx_shadow_eval_match", table_name="shadow_eval_results")
    op.drop_index("idx_shadow_eval_created", table_name="shadow_eval_results")
    op.drop_index("idx_shadow_eval_detector", table_name="shadow_eval_results")
    op.drop_table("shadow_eval_results")
