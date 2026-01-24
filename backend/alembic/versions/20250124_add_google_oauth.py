"""add google oauth support

Revision ID: 20250124_add_google_oauth
Revises: 20250116_staged_deployment
Create Date: 2025-01-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250124_add_google_oauth'
down_revision = '20250116_staged_deployment'
branch_labels = None
depends_on = None


def upgrade():
    # Add google_user_id column to users table
    op.add_column('users', sa.Column('google_user_id', sa.String(length=255), nullable=True))

    # Create unique constraint and index for google_user_id
    op.create_unique_constraint('uq_users_google_id', 'users', ['google_user_id'])
    op.create_index('idx_users_google_id', 'users', ['google_user_id'])

    # Make clerk_user_id nullable (for users who authenticate with Google only)
    op.alter_column('users', 'clerk_user_id',
                    existing_type=sa.String(length=255),
                    nullable=True)


def downgrade():
    # Remove google_user_id column and related constraints
    op.drop_index('idx_users_google_id', table_name='users')
    op.drop_constraint('uq_users_google_id', 'users', type_='unique')
    op.drop_column('users', 'google_user_id')

    # Restore clerk_user_id as non-nullable (this may fail if there are Google-only users)
    op.alter_column('users', 'clerk_user_id',
                    existing_type=sa.String(length=255),
                    nullable=False)
