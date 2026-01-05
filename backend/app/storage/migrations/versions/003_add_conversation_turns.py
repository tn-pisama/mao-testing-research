"""Add conversation turns for multi-turn trace support

Revision ID: 003_conversation_turns
Revises: 002_upgrade_embeddings
Create Date: 2026-01-05

Adds ConversationTurn and TurnState tables to support multi-turn
conversation traces from MAST-Data and other conversation-based
agent frameworks.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '003_conversation_turns'
down_revision = '002_upgrade_embeddings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_conversation flag to traces table
    op.add_column('traces', sa.Column('is_conversation', sa.Boolean(), nullable=True, server_default='false'))

    # Create conversation_turns table
    op.create_table(
        'conversation_turns',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('trace_id', UUID(as_uuid=True), sa.ForeignKey('traces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('conversation_id', sa.String(64), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('participant_type', sa.String(32), nullable=False),
        sa.Column('participant_id', sa.String(128), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('accumulated_context', sa.Text(), nullable=True),
        sa.Column('accumulated_tokens', sa.Integer(), server_default='0'),
        sa.Column('turn_metadata', JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('trace_id', 'conversation_id', 'turn_number', name='uq_turn_sequence'),
    )

    # Add embedding column separately (pgvector type)
    op.execute("""
        ALTER TABLE conversation_turns
        ADD COLUMN embedding vector(1024);
    """)

    # Create indexes for conversation_turns
    op.create_index('idx_turns_trace', 'conversation_turns', ['trace_id'])
    op.create_index('idx_turns_tenant', 'conversation_turns', ['tenant_id'])
    op.create_index('idx_turns_conversation', 'conversation_turns', ['conversation_id'])
    op.create_index('idx_turns_participant', 'conversation_turns', ['participant_id'])
    op.create_index('idx_turns_created', 'conversation_turns', ['created_at'])

    # Create vector index for semantic search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_turns_embedding_vector
        ON conversation_turns
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)

    # Create turn_states junction table
    op.create_table(
        'turn_states',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('turn_id', UUID(as_uuid=True), sa.ForeignKey('conversation_turns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('state_id', UUID(as_uuid=True), sa.ForeignKey('states.id', ondelete='CASCADE'), nullable=False),
        sa.Column('state_order', sa.Integer(), nullable=False),
        sa.UniqueConstraint('turn_id', 'state_id', name='uq_turn_state'),
    )

    # Create indexes for turn_states
    op.create_index('idx_turn_states_turn', 'turn_states', ['turn_id'])
    op.create_index('idx_turn_states_state', 'turn_states', ['state_id'])


def downgrade() -> None:
    # Drop turn_states table
    op.drop_index('idx_turn_states_state', table_name='turn_states')
    op.drop_index('idx_turn_states_turn', table_name='turn_states')
    op.drop_table('turn_states')

    # Drop conversation_turns table
    op.execute("DROP INDEX IF EXISTS idx_turns_embedding_vector;")
    op.drop_index('idx_turns_created', table_name='conversation_turns')
    op.drop_index('idx_turns_participant', table_name='conversation_turns')
    op.drop_index('idx_turns_conversation', table_name='conversation_turns')
    op.drop_index('idx_turns_tenant', table_name='conversation_turns')
    op.drop_index('idx_turns_trace', table_name='conversation_turns')
    op.drop_table('conversation_turns')

    # Remove is_conversation column from traces
    op.drop_column('traces', 'is_conversation')
