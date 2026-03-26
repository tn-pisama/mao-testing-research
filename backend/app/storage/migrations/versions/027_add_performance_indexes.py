"""Add performance indexes for frequently filtered columns.

Covers: agent_role, sprint_id, compound detection index, JSONB GIN."""

from typing import Sequence, Union
from alembic import op

revision: str = "027_add_performance_indexes"
down_revision: Union[str, None] = "026_add_trace_provider"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("idx_states_agent_role", "states", ["agent_role"])
    op.create_index("idx_states_sprint", "states", ["sprint_id"])
    op.execute("CREATE INDEX IF NOT EXISTS idx_traces_detection_meta ON traces USING GIN(detection_metadata)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_traces_detection_meta")
    op.drop_index("idx_states_sprint", table_name="states")
    op.drop_index("idx_states_agent_role", table_name="states")
