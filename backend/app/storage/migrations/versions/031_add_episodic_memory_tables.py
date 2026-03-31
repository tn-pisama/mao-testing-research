"""Add episodic memory tables for per-tenant adaptive detection.

Creates tenant_detector_stats and tenant_pattern_cache tables that enable
Pisama to learn from feedback and adjust detection thresholds per tenant."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "031_add_episodic_memory"
down_revision: Union[str, None] = "030_add_project_limit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_detector_stats",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("detection_type", sa.String(64), nullable=False),
        sa.Column("framework", sa.String(32), nullable=True),

        # Detection counts (rolling window)
        sa.Column("total_detections", sa.Integer, server_default="0", nullable=False),
        sa.Column("true_positives", sa.Integer, server_default="0", nullable=False),
        sa.Column("false_positives", sa.Integer, server_default="0", nullable=False),
        sa.Column("false_negatives", sa.Integer, server_default="0", nullable=False),
        sa.Column("true_negatives", sa.Integer, server_default="0", nullable=False),

        # Computed rates
        sa.Column("precision", sa.Float, server_default="0.5", nullable=False),
        sa.Column("recall", sa.Float, server_default="0.5", nullable=False),
        sa.Column("f1", sa.Float, server_default="0.5", nullable=False),

        # Threshold adjustments
        sa.Column("base_threshold", sa.Float, server_default="0.5", nullable=False),
        sa.Column("adjusted_threshold", sa.Float, server_default="0.5", nullable=False),
        sa.Column("threshold_adjustment_reason", sa.Text, nullable=True),

        # Frequency tracking
        sa.Column("detection_frequency_24h", sa.Integer, server_default="0", nullable=False),
        sa.Column("detection_frequency_7d", sa.Integer, server_default="0", nullable=False),
        sa.Column("last_detection_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_feedback_at", sa.DateTime(timezone=True), nullable=True),

        # FP suppression
        sa.Column("suppressed_patterns", JSONB, server_default="[]", nullable=False),

        # Config
        sa.Column("learning_enabled", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        sa.UniqueConstraint("tenant_id", "detection_type", "framework", name="uq_tenant_detector_stats"),
    )

    op.create_index("idx_tds_tenant", "tenant_detector_stats", ["tenant_id"])
    op.create_index("idx_tds_tenant_type", "tenant_detector_stats", ["tenant_id", "detection_type"])

    op.create_table(
        "tenant_pattern_cache",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("detection_type", sa.String(64), nullable=False),
        sa.Column("framework", sa.String(32), nullable=True),
        sa.Column("pattern_hash", sa.String(64), nullable=False),
        sa.Column("pattern_summary", sa.Text, nullable=False),
        sa.Column("pattern_type", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, server_default="0.5", nullable=False),
        sa.Column("occurrence_count", sa.Integer, server_default="1", nullable=False),
        sa.Column("source_detection_id", UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("idx_tpc_tenant_type", "tenant_pattern_cache", ["tenant_id", "detection_type"])
    op.create_index("idx_tpc_pattern_hash", "tenant_pattern_cache", ["tenant_id", "pattern_hash"])


def downgrade() -> None:
    op.drop_table("tenant_pattern_cache")
    op.drop_table("tenant_detector_stats")
