"""Add cognitive memory tables.

Revision ID: 019_add_cognitive_memory
Revises: 018_add_scorers_evals_source_fixes
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "019_add_cognitive_memory"
down_revision = "018_add_scorers_evals_source_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- cognitive_memories ---
    op.create_table(
        "cognitive_memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_type", sa.String(32), nullable=False),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("structured_data", JSONB, server_default="{}"),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_trace_id", UUID(as_uuid=True), nullable=True),
        sa.Column("importance", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("access_count", sa.Integer, server_default="0"),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_id", UUID(as_uuid=True), sa.ForeignKey("cognitive_memories.id"), nullable=True),
        sa.Column("superseded_by_id", UUID(as_uuid=True), sa.ForeignKey("cognitive_memories.id"), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("embedding", sa.LargeBinary, nullable=True),  # pgvector added via raw SQL
        sa.Column("tags", JSONB, server_default="[]"),
        sa.Column("framework", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Replace the LargeBinary column with proper vector type
    op.execute("ALTER TABLE cognitive_memories DROP COLUMN embedding")
    op.execute("ALTER TABLE cognitive_memories ADD COLUMN embedding vector(1024)")

    # Indexes
    op.create_index("idx_cm_tenant", "cognitive_memories", ["tenant_id"])
    op.create_index("idx_cm_type", "cognitive_memories", ["memory_type"])
    op.create_index("idx_cm_domain", "cognitive_memories", ["domain"])
    op.create_index("idx_cm_active", "cognitive_memories", ["is_active"])
    op.create_index("idx_cm_tenant_domain", "cognitive_memories", ["tenant_id", "domain"])
    op.create_index("idx_cm_tenant_type", "cognitive_memories", ["tenant_id", "memory_type"])
    op.create_index("idx_cm_importance", "cognitive_memories", ["importance"])
    op.create_index("idx_cm_created", "cognitive_memories", ["created_at"])
    op.create_index("idx_cm_tags", "cognitive_memories", ["tags"], postgresql_using="gin")
    op.create_index("idx_cm_framework", "cognitive_memories", ["framework"])
    op.create_index("idx_cm_content_hash", "cognitive_memories", ["tenant_id", "content_hash"])

    # IVFFlat vector index (cosine similarity)
    op.execute("""
        CREATE INDEX idx_cm_embedding ON cognitive_memories
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
    """)

    # --- memory_recall_logs ---
    op.create_table(
        "memory_recall_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recall_context", sa.String(64), nullable=False),
        sa.Column("recall_query", sa.Text, nullable=False),
        sa.Column("domain_filter", sa.String(64), nullable=True),
        sa.Column("memories_returned", sa.Integer, nullable=False, server_default="0"),
        sa.Column("top_memory_id", UUID(as_uuid=True), sa.ForeignKey("cognitive_memories.id"), nullable=True),
        sa.Column("composite_scores", JSONB, server_default="[]"),
        sa.Column("was_useful", sa.Boolean, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_mrl_tenant", "memory_recall_logs", ["tenant_id"])
    op.create_index("idx_mrl_context", "memory_recall_logs", ["recall_context"])
    op.create_index("idx_mrl_created", "memory_recall_logs", ["created_at"])

    # --- memory_extraction_jobs ---
    op.create_table(
        "memory_extraction_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("source_text_length", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("memories_extracted", sa.Integer, server_default="0"),
        sa.Column("memories_deduplicated", sa.Integer, server_default="0"),
        sa.Column("contradictions_found", sa.Integer, server_default="0"),
        sa.Column("llm_cost_usd", sa.Float, server_default="0.0"),
        sa.Column("llm_tokens_used", sa.Integer, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("idx_mej_tenant", "memory_extraction_jobs", ["tenant_id"])
    op.create_index("idx_mej_status", "memory_extraction_jobs", ["status"])

    # --- Add recall_context to detections ---
    op.add_column("detections", sa.Column("recall_context", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("detections", "recall_context")
    op.drop_table("memory_extraction_jobs")
    op.drop_table("memory_recall_logs")
    op.execute("DROP INDEX IF EXISTS idx_cm_embedding")
    op.drop_table("cognitive_memories")
