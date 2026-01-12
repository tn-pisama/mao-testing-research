"""Add mast_trace_embeddings table for few-shot learning.

Revision ID: 005_add_mast_trace_embeddings
Revises: 004_add_healing_records
Create Date: 2026-01-11

Phase 4: Stores MAST benchmark trace embeddings for similarity search
and few-shot example selection in LLM verification prompts.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '005_add_mast_trace_embeddings'
down_revision = '004_add_healing_records'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create mast_trace_embeddings table with vector index."""

    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Create table
    op.create_table(
        'mast_trace_embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trace_id', sa.String(128), nullable=False),
        sa.Column('task_embedding', Vector(1024), nullable=False),
        sa.Column('ground_truth_failures', postgresql.JSONB(), nullable=False),
        sa.Column('framework', sa.String(64), nullable=False),
        sa.Column('task_description', sa.Text(), nullable=False),
        sa.Column('conversation_summary', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trace_id'),
    )

    # Create indexes for common query patterns
    op.create_index('idx_mast_trace_id', 'mast_trace_embeddings', ['trace_id'])
    op.create_index('idx_mast_framework', 'mast_trace_embeddings', ['framework'])
    op.create_index('idx_mast_created', 'mast_trace_embeddings', ['created_at'])

    # Create ivfflat index for vector similarity search
    # Using cosine distance for similarity matching
    op.execute("""
        CREATE INDEX idx_mast_task_embedding
        ON mast_trace_embeddings
        USING ivfflat (task_embedding vector_cosine_ops)
        WITH (lists = 100);
    """)


def downgrade() -> None:
    """Drop mast_trace_embeddings table and indexes."""
    op.drop_index('idx_mast_task_embedding', table_name='mast_trace_embeddings')
    op.drop_index('idx_mast_created', table_name='mast_trace_embeddings')
    op.drop_index('idx_mast_framework', table_name='mast_trace_embeddings')
    op.drop_index('idx_mast_trace_id', table_name='mast_trace_embeddings')
    op.drop_table('mast_trace_embeddings')
