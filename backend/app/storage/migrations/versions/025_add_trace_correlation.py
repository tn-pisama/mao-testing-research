"""Add correlation_id to traces and index parent_trace_id.

Supports multi-chain trace linking for cross-chain failure detection."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "025_add_trace_correlation"
down_revision: Union[str, None] = "024_add_user_password"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("traces", sa.Column("correlation_id", sa.String(128), nullable=True))
    op.create_index("idx_traces_parent", "traces", ["parent_trace_id"])
    op.create_index("idx_traces_correlation", "traces", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("idx_traces_correlation", table_name="traces")
    op.drop_index("idx_traces_parent", table_name="traces")
    op.drop_column("traces", "correlation_id")
