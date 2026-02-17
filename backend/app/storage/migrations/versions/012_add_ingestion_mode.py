"""Add ingestion_mode to platform instance and entity tables

Revision ID: 012_add_ingestion_mode
Revises: 011_add_dify_tables
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012_add_ingestion_mode'
down_revision = '011_add_dify_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Instance-level tables (NOT NULL, default "full")
    op.add_column('n8n_connections',
        sa.Column('ingestion_mode', sa.String(20), server_default='full', nullable=False))
    op.add_column('openclaw_instances',
        sa.Column('ingestion_mode', sa.String(20), server_default='full', nullable=False))
    op.add_column('dify_instances',
        sa.Column('ingestion_mode', sa.String(20), server_default='full', nullable=False))

    # Entity-level tables (nullable, NULL = inherit from instance)
    op.add_column('n8n_workflows',
        sa.Column('ingestion_mode', sa.String(20), nullable=True))
    op.add_column('openclaw_agents',
        sa.Column('ingestion_mode', sa.String(20), nullable=True))
    op.add_column('dify_apps',
        sa.Column('ingestion_mode', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('dify_apps', 'ingestion_mode')
    op.drop_column('openclaw_agents', 'ingestion_mode')
    op.drop_column('n8n_workflows', 'ingestion_mode')
    op.drop_column('dify_instances', 'ingestion_mode')
    op.drop_column('openclaw_instances', 'ingestion_mode')
    op.drop_column('n8n_connections', 'ingestion_mode')
