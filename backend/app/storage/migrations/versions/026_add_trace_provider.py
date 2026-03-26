"""Add provider column to traces and change framework default.

Supports auto-detection of source platform (Bedrock, Vertex, CrewAI, etc.)."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "026_add_trace_provider"
down_revision: Union[str, None] = "025_add_trace_correlation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("traces", sa.Column("provider", sa.String(32), nullable=True))
    op.create_index("idx_traces_provider", "traces", ["provider"])


def downgrade() -> None:
    op.drop_index("idx_traces_provider", table_name="traces")
    op.drop_column("traces", "provider")
