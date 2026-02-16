"""Add workflow groups and assignments

Revision ID: 007_add_workflow_groups
Revises: 006_add_n8n_connections
Create Date: 2026-02-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = "007_add_workflow_groups"
down_revision = "006_add_n8n_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create workflow_groups table
    op.create_table(
        "workflow_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("is_default", sa.Boolean, default=False, server_default=sa.text("false")),
        sa.Column("auto_detect_rules", JSONB, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_workflow_groups_tenant", "workflow_groups", ["tenant_id"])
    op.create_unique_constraint("uq_workflow_group_name", "workflow_groups", ["tenant_id", "name"])

    # Create user_group_preferences table
    op.create_table(
        "user_group_preferences",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("workflow_groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("custom_name", sa.String(255), nullable=True),
        sa.Column("is_hidden", sa.Boolean, default=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer, nullable=True),
    )
    op.create_index("idx_user_group_prefs_user", "user_group_preferences", ["user_id"])
    op.create_index("idx_user_group_prefs_group", "user_group_preferences", ["group_id"])

    # Create workflow_group_assignments table
    op.create_table(
        "workflow_group_assignments",
        sa.Column("workflow_id", sa.String(255), primary_key=True),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("workflow_groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assignment_type", sa.String(10), nullable=False),  # 'auto' or 'manual'
        sa.Column("assigned_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_workflow_assignments_workflow", "workflow_group_assignments", ["workflow_id"])
    op.create_index("idx_workflow_assignments_group", "workflow_group_assignments", ["group_id"])


def downgrade() -> None:
    # Drop workflow_group_assignments
    op.drop_index("idx_workflow_assignments_group", table_name="workflow_group_assignments")
    op.drop_index("idx_workflow_assignments_workflow", table_name="workflow_group_assignments")
    op.drop_table("workflow_group_assignments")

    # Drop user_group_preferences
    op.drop_index("idx_user_group_prefs_group", table_name="user_group_preferences")
    op.drop_index("idx_user_group_prefs_user", table_name="user_group_preferences")
    op.drop_table("user_group_preferences")

    # Drop workflow_groups
    op.drop_constraint("uq_workflow_group_name", "workflow_groups", type_="unique")
    op.drop_index("idx_workflow_groups_tenant", table_name="workflow_groups")
    op.drop_table("workflow_groups")
