"""Add performance indexes for common query patterns

Revision ID: 001_performance_indexes
Revises: 
Create Date: 2024-12-28

"""
from alembic import op

revision = '001_performance_indexes'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('idx_traces_tenant_created', 'traces', ['tenant_id', 'created_at'])
    op.create_index('idx_traces_tenant_status', 'traces', ['tenant_id', 'status'])
    
    op.create_index('idx_states_agent', 'states', ['agent_id'])
    op.create_index('idx_states_created', 'states', ['created_at'])
    
    op.create_index('idx_detections_type', 'detections', ['detection_type'])
    op.create_index('idx_detections_tenant_created', 'detections', ['tenant_id', 'created_at'])
    op.create_index('idx_detections_tenant_type', 'detections', ['tenant_id', 'detection_type'])
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_states_embedding_vector 
        ON states 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)


def downgrade() -> None:
    op.drop_index('idx_traces_tenant_created', table_name='traces')
    op.drop_index('idx_traces_tenant_status', table_name='traces')
    
    op.drop_index('idx_states_agent', table_name='states')
    op.drop_index('idx_states_created', table_name='states')
    
    op.drop_index('idx_detections_type', table_name='detections')
    op.drop_index('idx_detections_tenant_created', table_name='detections')
    op.drop_index('idx_detections_tenant_type', table_name='detections')
    
    op.execute("DROP INDEX IF EXISTS idx_states_embedding_vector;")
