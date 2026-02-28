"""Add golden_dataset_entries table for calibration and training data.

Revision ID: 016_add_golden_dataset_entries
Revises: 015_add_quality_healing_records
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "016_add_golden_dataset_entries"
down_revision = "015_add_quality_healing_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "golden_dataset_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("entry_key", sa.String(255), nullable=False, unique=True),
        sa.Column("detection_type", sa.String(64), nullable=False),
        sa.Column("input_data", JSONB, nullable=False),
        sa.Column("expected_detected", sa.Boolean, nullable=False),
        sa.Column("expected_confidence_min", sa.Float, server_default="0.0"),
        sa.Column("expected_confidence_max", sa.Float, server_default="1.0"),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("source", sa.String(64), server_default="manual"),
        sa.Column("tags", JSONB, server_default="[]"),
        sa.Column("difficulty", sa.String(16), server_default="easy"),
        sa.Column("split", sa.String(16), server_default="train"),
        sa.Column("source_trace_id", sa.String(255), nullable=True),
        sa.Column("source_workflow_id", sa.String(255), nullable=True),
        sa.Column("augmentation_method", sa.String(128), nullable=True),
        sa.Column("human_verified", sa.Boolean, server_default="false"),
        sa.Column("entry_metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Indexes for common query patterns
    op.create_index("idx_gde_tenant", "golden_dataset_entries", ["tenant_id"])
    op.create_index("idx_gde_detection_type", "golden_dataset_entries", ["detection_type"])
    op.create_index("idx_gde_split", "golden_dataset_entries", ["split"])
    op.create_index("idx_gde_source", "golden_dataset_entries", ["source"])
    op.create_index("idx_gde_difficulty", "golden_dataset_entries", ["difficulty"])
    op.create_index("idx_gde_type_split", "golden_dataset_entries",
                     ["detection_type", "split"])
    op.create_index("idx_gde_type_detected", "golden_dataset_entries",
                     ["detection_type", "expected_detected"])
    op.create_index("idx_gde_tenant_type", "golden_dataset_entries",
                     ["tenant_id", "detection_type"])
    op.create_index("idx_gde_tags", "golden_dataset_entries", ["tags"],
                     postgresql_using="gin")
    op.create_index("idx_gde_created", "golden_dataset_entries", ["created_at"])


def downgrade() -> None:
    op.drop_table("golden_dataset_entries")
