"""Upgrade embeddings from 384 to 1024 dimensions (e5-large-v2)

Revision ID: 002_upgrade_embeddings
Revises: 001_performance_indexes
Create Date: 2024-12-29

Note: This migration invalidates existing embeddings. Run the re-embedding
script after migration to recompute embeddings with the new model.
"""
from alembic import op
import sqlalchemy as sa

revision = '002_upgrade_embeddings'
down_revision = '001_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_states_embedding_vector;")
    
    op.execute("""
        ALTER TABLE states 
        ALTER COLUMN embedding TYPE vector(1024)
        USING NULL;
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_states_embedding_vector 
        ON states 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_states_embedding_vector;")
    
    op.execute("""
        ALTER TABLE states 
        ALTER COLUMN embedding TYPE vector(384)
        USING NULL;
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_states_embedding_vector 
        ON states 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
