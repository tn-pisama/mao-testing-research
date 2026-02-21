"""Add quality healing records table.

Revision ID: 015_add_quality_healing_records
Revises: 014_add_healing_n8n_fields
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "015_add_quality_healing_records"
down_revision = "014_add_healing_n8n_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quality_healing_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("assessment_id", UUID(as_uuid=True), sa.ForeignKey("workflow_quality_assessments.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("before_score", sa.Float, nullable=False),
        sa.Column("after_score", sa.Float, nullable=True),
        sa.Column("dimensions_targeted", JSONB, nullable=False, server_default="[]"),
        sa.Column("fix_suggestions", JSONB, nullable=False, server_default="[]"),
        sa.Column("applied_fixes", JSONB, server_default="[]"),
        sa.Column("original_state", JSONB, server_default="{}"),
        sa.Column("modified_state", JSONB, server_default="{}"),
        sa.Column("rollback_available", sa.Boolean, server_default="true"),
        sa.Column("validation_results", JSONB, server_default="[]"),
        sa.Column("approval_required", sa.Boolean, server_default="false"),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("workflow_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )

    op.create_index("idx_qh_tenant", "quality_healing_records", ["tenant_id"])
    op.create_index("idx_qh_assessment", "quality_healing_records", ["assessment_id"])
    op.create_index("idx_qh_status", "quality_healing_records", ["status"])
    op.create_index("idx_qh_created", "quality_healing_records", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_qh_created", table_name="quality_healing_records")
    op.drop_index("idx_qh_status", table_name="quality_healing_records")
    op.drop_index("idx_qh_assessment", table_name="quality_healing_records")
    op.drop_index("idx_qh_tenant", table_name="quality_healing_records")
    op.drop_table("quality_healing_records")
