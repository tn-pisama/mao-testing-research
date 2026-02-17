"""Add agent quality assessments table and reasoning column.

Revision ID: 013_add_agent_quality_assessments
Revises: 012_add_ingestion_mode
Create Date: 2025-06-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "013_add_agent_quality_assessments"
down_revision = "012_add_ingestion_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create agent_quality_assessments table
    op.create_table(
        "agent_quality_assessments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workflow_assessment_id", UUID(as_uuid=True), sa.ForeignKey("workflow_quality_assessments.id"), nullable=False),
        sa.Column("trace_id", UUID(as_uuid=True), sa.ForeignKey("traces.id"), nullable=True),
        sa.Column("agent_id", sa.String(255), nullable=False),
        sa.Column("agent_name", sa.String(255), nullable=True),
        sa.Column("agent_type", sa.String(100), nullable=False),
        sa.Column("overall_score", sa.Integer, nullable=False),
        sa.Column("grade", sa.String(10), nullable=False),
        sa.Column("dimensions", JSONB, nullable=False),
        sa.Column("issues_count", sa.Integer, default=0),
        sa.Column("critical_issues", JSONB, default=list),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("idx_agent_quality_tenant", "agent_quality_assessments", ["tenant_id"])
    op.create_index("idx_agent_quality_workflow_assessment", "agent_quality_assessments", ["workflow_assessment_id"])
    op.create_index("idx_agent_quality_agent_id", "agent_quality_assessments", ["agent_id"])
    op.create_index("idx_agent_quality_tenant_created", "agent_quality_assessments", ["tenant_id", "created_at"])

    # Add reasoning column to workflow_quality_assessments
    op.add_column(
        "workflow_quality_assessments",
        sa.Column("reasoning", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_quality_assessments", "reasoning")
    op.drop_index("idx_agent_quality_tenant_created", table_name="agent_quality_assessments")
    op.drop_index("idx_agent_quality_agent_id", table_name="agent_quality_assessments")
    op.drop_index("idx_agent_quality_workflow_assessment", table_name="agent_quality_assessments")
    op.drop_index("idx_agent_quality_tenant", table_name="agent_quality_assessments")
    op.drop_table("agent_quality_assessments")
