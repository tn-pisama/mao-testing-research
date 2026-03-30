"""Add project_limit column to tenants.

The model defines project_limit (Integer, default=1) but the column
was never added to the database, causing n8n auto-sync to fail every
5 minutes with 'column tenants.project_limit does not exist'."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "030_add_project_limit"
down_revision: Union[str, None] = "029_tenant_provisioning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("project_limit", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "project_limit")
