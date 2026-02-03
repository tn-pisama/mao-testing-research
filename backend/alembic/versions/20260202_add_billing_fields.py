"""Add billing fields to tenants

Revision ID: 20260202_add_billing
Revises: 20250124_add_google_oauth
Create Date: 2026-02-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260202_add_billing'
down_revision = '20250124_add_google_oauth'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add billing fields to tenants table."""
    # Add billing columns
    op.add_column('tenants', sa.Column('plan', sa.String(20), nullable=False, server_default='free'))
    op.add_column('tenants', sa.Column('stripe_customer_id', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('stripe_subscription_id', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('subscription_status', sa.String(50), nullable=True))
    op.add_column('tenants', sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tenants', sa.Column('span_limit', sa.Integer(), nullable=False, server_default='10000'))

    # Add unique constraint on stripe_customer_id
    op.create_unique_constraint('uq_tenants_stripe_customer_id', 'tenants', ['stripe_customer_id'])

    # Add index for faster billing queries
    op.create_index('idx_tenants_plan', 'tenants', ['plan'])
    op.create_index('idx_tenants_subscription_status', 'tenants', ['subscription_status'])


def downgrade() -> None:
    """Remove billing fields from tenants table."""
    # Drop indexes
    op.drop_index('idx_tenants_subscription_status', table_name='tenants')
    op.drop_index('idx_tenants_plan', table_name='tenants')

    # Drop unique constraint
    op.drop_constraint('uq_tenants_stripe_customer_id', 'tenants', type_='unique')

    # Drop columns
    op.drop_column('tenants', 'span_limit')
    op.drop_column('tenants', 'current_period_end')
    op.drop_column('tenants', 'subscription_status')
    op.drop_column('tenants', 'stripe_subscription_id')
    op.drop_column('tenants', 'stripe_customer_id')
    op.drop_column('tenants', 'plan')
