"""Add harness-aware fields to traces and states.

Enables role-based detection by tracking agent roles (planner, generator,
evaluator), sprint boundaries, context resets, and harness architecture type.

Revision ID: 022_add_harness_aware_fields
Revises: 021_add_shadow_eval_results
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa

revision = "022_add_harness_aware_fields"
down_revision = "021_add_shadow_eval_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trace: harness type
    op.add_column(
        "traces",
        sa.Column("harness_type", sa.String(32), nullable=True),
    )

    # State: agent role, sprint grouping, context reset marker
    op.add_column(
        "states",
        sa.Column("agent_role", sa.String(32), nullable=True),
    )
    op.add_column(
        "states",
        sa.Column("sprint_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "states",
        sa.Column("context_reset", sa.Boolean, server_default="false", nullable=True),
    )

    # Indexes for role-based queries
    op.create_index("idx_states_agent_role", "states", ["agent_role"])
    op.create_index("idx_states_sprint", "states", ["sprint_id"])
    op.create_index("idx_traces_harness_type", "traces", ["harness_type"])


def downgrade() -> None:
    op.drop_index("idx_traces_harness_type", table_name="traces")
    op.drop_index("idx_states_sprint", table_name="states")
    op.drop_index("idx_states_agent_role", table_name="states")
    op.drop_column("states", "context_reset")
    op.drop_column("states", "sprint_id")
    op.drop_column("states", "agent_role")
    op.drop_column("traces", "harness_type")
