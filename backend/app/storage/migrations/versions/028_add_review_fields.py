"""Add hand-review workflow fields to detections.

Supports queue-based review, batch verdicts, and golden dataset promotion."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "028_add_review_fields"
down_revision: Union[str, None] = "027_add_performance_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("detections", sa.Column("review_status", sa.String(32), server_default="pending"))
    op.add_column("detections", sa.Column("reviewed_by", sa.String(128), nullable=True))
    op.add_column("detections", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("detections", sa.Column("review_notes", sa.String(1024), nullable=True))
    op.add_column("detections", sa.Column("promoted_to_golden", sa.Boolean(), server_default="false"))
    op.create_index("idx_detections_review_status", "detections", ["review_status"])


def downgrade() -> None:
    op.drop_index("idx_detections_review_status", table_name="detections")
    op.drop_column("detections", "promoted_to_golden")
    op.drop_column("detections", "review_notes")
    op.drop_column("detections", "reviewed_at")
    op.drop_column("detections", "reviewed_by")
    op.drop_column("detections", "review_status")
