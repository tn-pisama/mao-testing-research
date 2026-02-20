"""Add n8n deployment fields to healing_records and create workflow_versions table.

Revision ID: 014_add_healing_n8n_fields
Revises: 013_add_agent_quality_assessments
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "014_add_healing_n8n_fields"
down_revision = "013_add_agent_quality_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add n8n deployment columns to healing_records
    op.add_column("healing_records", sa.Column("workflow_id", sa.String(255), nullable=True))
    op.add_column("healing_records", sa.Column("n8n_connection_id", UUID(as_uuid=True), nullable=True))
    op.add_column("healing_records", sa.Column("deployment_stage", sa.String(32), nullable=True))
    op.add_column("healing_records", sa.Column("staged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("healing_records", sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True))

    # Foreign key to n8n_connections
    op.create_foreign_key(
        "fk_healing_n8n_connection",
        "healing_records",
        "n8n_connections",
        ["n8n_connection_id"],
        ["id"],
    )

    # Indexes for common query patterns
    op.create_index("idx_healing_workflow", "healing_records", ["workflow_id"])
    op.create_index("idx_healing_connection", "healing_records", ["n8n_connection_id"])
    op.create_index("idx_healing_stage", "healing_records", ["deployment_stage"])

    # Status enum check constraint
    op.create_check_constraint(
        "ck_healing_status",
        "healing_records",
        "status IN ('pending', 'in_progress', 'applied', 'staged', 'failed', 'rolled_back', 'rejected')",
    )

    # Create workflow_versions table
    op.create_table(
        "workflow_versions",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.String(255), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("workflow_snapshot", JSONB(), nullable=False),
        sa.Column("healing_id", UUID(as_uuid=True), nullable=True),
        sa.Column("change_type", sa.String(32), nullable=False),
        sa.Column("change_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["connection_id"], ["n8n_connections.id"]),
        sa.ForeignKeyConstraint(["healing_id"], ["healing_records.id"]),
        sa.UniqueConstraint("tenant_id", "workflow_id", "version_number", name="uq_workflow_version_number"),
    )

    op.create_index("idx_wv_tenant", "workflow_versions", ["tenant_id"])
    op.create_index("idx_wv_workflow", "workflow_versions", ["workflow_id"])
    op.create_index("idx_wv_connection", "workflow_versions", ["connection_id"])
    op.create_index("idx_wv_healing", "workflow_versions", ["healing_id"])


def downgrade() -> None:
    # Drop workflow_versions
    op.drop_index("idx_wv_healing", table_name="workflow_versions")
    op.drop_index("idx_wv_connection", table_name="workflow_versions")
    op.drop_index("idx_wv_workflow", table_name="workflow_versions")
    op.drop_index("idx_wv_tenant", table_name="workflow_versions")
    op.drop_table("workflow_versions")

    # Drop healing_records n8n columns
    op.drop_constraint("ck_healing_status", "healing_records", type_="check")
    op.drop_index("idx_healing_stage", table_name="healing_records")
    op.drop_index("idx_healing_connection", table_name="healing_records")
    op.drop_index("idx_healing_workflow", table_name="healing_records")
    op.drop_constraint("fk_healing_n8n_connection", "healing_records", type_="foreignkey")
    op.drop_column("healing_records", "promoted_at")
    op.drop_column("healing_records", "staged_at")
    op.drop_column("healing_records", "deployment_stage")
    op.drop_column("healing_records", "n8n_connection_id")
    op.drop_column("healing_records", "workflow_id")
