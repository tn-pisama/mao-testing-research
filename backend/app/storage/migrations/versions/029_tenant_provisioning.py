"""Add onboarding_completed_at to tenants for server-side onboarding enforcement.

Fixes self-serve signup flow: tracks when customer completes onboarding wizard."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "029_tenant_provisioning"
down_revision: Union[str, None] = "028_add_review_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "onboarding_completed_at")
