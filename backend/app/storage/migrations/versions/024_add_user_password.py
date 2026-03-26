"""Add password_hash column to users table.

Supports email/password sign-in as an alternative to Google OAuth.
No self-registration — admin sets passwords for invited users."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "024_add_user_password"
down_revision: Union[str, None] = "023_add_healing_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
