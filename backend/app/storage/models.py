from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    api_key_hash = Column(String(255), nullable=False)
    clerk_org_id = Column(String(255), nullable=True, unique=True)
    settings = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    traces = relationship("Trace", back_populates="tenant")
    detections = relationship("Detection", back_populates="tenant")
    users = relationship("User", back_populates="tenant")
    api_keys = relationship("ApiKey", back_populates="tenant")
    
    __table_args__ = (
        Index("idx_tenants_clerk_org", "clerk_org_id"),
    )


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_user_id = Column(String(255), unique=True, nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    role = Column(String(50), default="member")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    tenant = relationship("Tenant", back_populates="users")
    
    __table_args__ = (
        Index("idx_users_clerk_id", "clerk_user_id"),
        Index("idx_users_tenant", "tenant_id"),
    )


class ApiKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False)
    key_prefix = Column(String(12), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    tenant = relationship("Tenant", back_populates="api_keys")
    
    __table_args__ = (
        Index("idx_api_keys_tenant", "tenant_id"),
        Index("idx_api_keys_prefix", "key_prefix"),
    )


class AuthAudit(Base):
    __tablename__ = "auth_audit"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    success = Column(Boolean, nullable=False)
    error_code = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index("idx_auth_audit_tenant", "tenant_id"),
        Index("idx_auth_audit_created", "created_at"),
    )


class Trace(Base):
    __tablename__ = "traces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    session_id = Column(String(64), nullable=False)
    parent_trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id"), nullable=True)
    framework = Column(String(32), default="langgraph")
    status = Column(String(32), default="running")
    total_tokens = Column(Integer, default=0)
    total_cost_cents = Column(Integer, default=0)
    is_conversation = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant", back_populates="traces")
    states = relationship("State", back_populates="trace")
    detections = relationship("Detection", back_populates="trace")
    conversation_turns = relationship("ConversationTurn", back_populates="trace", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_traces_tenant", "tenant_id"),
        Index("idx_traces_session", "session_id"),
        Index("idx_traces_tenant_created", "tenant_id", "created_at"),
        Index("idx_traces_tenant_status", "tenant_id", "status"),
    )


class State(Base):
    __tablename__ = "states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    sequence_num = Column(Integer, nullable=False)
    agent_id = Column(String(128), nullable=False)
    state_delta = Column(JSONB, nullable=False)
    state_hash = Column(String(64), nullable=False)
    prompt_hash = Column(String(64), nullable=True)
    response_redacted = Column(Text, nullable=True)
    tool_calls = Column(JSONB, nullable=True)
    embedding = Column(Vector(1024), nullable=True)
    token_count = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trace = relationship("Trace", back_populates="states")
    turn_states = relationship("TurnState", back_populates="state", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("trace_id", "sequence_num"),
        Index("idx_states_trace", "trace_id"),
        Index("idx_states_tenant", "tenant_id"),
        Index("idx_states_agent", "agent_id"),
        Index("idx_states_created", "created_at"),
    )


class Transition(Base):
    __tablename__ = "transitions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    from_state_id = Column(UUID(as_uuid=True), ForeignKey("states.id"), nullable=False)
    to_state_id = Column(UUID(as_uuid=True), ForeignKey("states.id"), nullable=False)
    transition_type = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index("idx_transitions_tenant", "tenant_id"),
    )


class Detection(Base):
    __tablename__ = "detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id"), nullable=False)
    state_id = Column(UUID(as_uuid=True), ForeignKey("states.id"), nullable=True)
    detection_type = Column(String(32), nullable=False)
    confidence = Column(Integer, nullable=False)
    method = Column(String(32), nullable=False)
    details = Column(JSONB, default=dict)
    validated = Column(Boolean, default=False)
    validated_by = Column(String(128), nullable=True)
    false_positive = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="detections")
    trace = relationship("Trace", back_populates="detections")
    feedback = relationship("DetectionFeedback", back_populates="detection", uselist=False)

    __table_args__ = (
        Index("idx_detections_tenant", "tenant_id"),
        Index("idx_detections_trace", "trace_id"),
        Index("idx_detections_type", "detection_type"),
        Index("idx_detections_tenant_created", "tenant_id", "created_at"),
        Index("idx_detections_tenant_type", "tenant_id", "detection_type"),
    )


class DetectionFeedback(Base):
    """User feedback on detection accuracy for threshold tuning."""
    __tablename__ = "detection_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    detection_id = Column(UUID(as_uuid=True), ForeignKey("detections.id", ondelete="CASCADE"), nullable=False, unique=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    # Feedback classification
    is_correct = Column(Boolean, nullable=False)  # Was the detection correct?
    feedback_type = Column(String(32), nullable=False)  # true_positive, false_positive, false_negative, true_negative

    # Context captured at feedback time
    detection_confidence = Column(Integer, nullable=False)  # Original confidence
    detection_method = Column(String(32), nullable=False)   # Original method
    framework = Column(String(32), nullable=True)           # Framework used

    # User-provided context
    reason = Column(Text, nullable=True)                    # Why user thinks it's wrong/right
    severity_rating = Column(Integer, nullable=True)        # 1-5 user severity rating

    # Metadata
    submitted_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    detection = relationship("Detection", back_populates="feedback")

    __table_args__ = (
        Index("idx_feedback_tenant", "tenant_id"),
        Index("idx_feedback_type", "feedback_type"),
        Index("idx_feedback_framework", "framework"),
        Index("idx_feedback_created", "created_at"),
    )


class GoldenTrace(Base):
    __tablename__ = "golden_traces"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id"), nullable=False)
    source = Column(String(32), nullable=False)
    failure_type = Column(String(32), nullable=True)
    failure_confirmed = Column(Boolean, default=False)
    annotated_by = Column(String(128), nullable=True)
    annotation_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ImportJob(Base):
    __tablename__ = "import_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    format = Column(String(50), nullable=True)
    file_name = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False)
    records_total = Column(Integer, default=0)
    records_processed = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    traces_created = Column(Integer, default=0)
    detections_found = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    errors = relationship("ImportError", back_populates="import_job", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_import_jobs_tenant", "tenant_id"),
        Index("idx_import_jobs_status", "status"),
        UniqueConstraint("tenant_id", "file_hash", name="uq_import_jobs_file_hash"),
    )


class ImportError(Base):
    __tablename__ = "import_errors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    import_job_id = Column(UUID(as_uuid=True), ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False)
    record_index = Column(Integer, nullable=False)
    error_message = Column(Text, nullable=False)
    raw_record = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    import_job = relationship("ImportJob", back_populates="errors")
    
    __table_args__ = (
        Index("idx_import_errors_job", "import_job_id"),
    )


class WebhookNonce(Base):
    __tablename__ = "webhook_nonces"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nonce = Column(String(64), unique=True, nullable=False)
    timestamp = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index("idx_webhook_nonces_nonce", "nonce"),
        Index("idx_webhook_nonces_created", "created_at"),
    )


class N8nWorkflow(Base):
    __tablename__ = "n8n_workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    workflow_id = Column(String(255), nullable=False)
    workflow_name = Column(String(255), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "workflow_id", name="uq_n8n_workflow_tenant"),
        Index("idx_n8n_workflows_tenant", "tenant_id"),
    )


class ConversationTurn(Base):
    """Represents a single turn in a multi-turn conversation trace."""
    __tablename__ = "conversation_turns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    # Turn identification
    conversation_id = Column(String(64), nullable=False)
    turn_number = Column(Integer, nullable=False)

    # Participant info
    participant_type = Column(String(32), nullable=False)  # user, agent, system, tool
    participant_id = Column(String(128), nullable=False)

    # Content
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=True)
    accumulated_context = Column(Text, nullable=True)
    accumulated_tokens = Column(Integer, default=0)

    # Semantic embedding for similarity search
    embedding = Column(Vector(1024), nullable=True)

    # Extra data
    turn_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    trace = relationship("Trace", back_populates="conversation_turns")
    turn_states = relationship("TurnState", back_populates="turn", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("trace_id", "conversation_id", "turn_number", name="uq_turn_sequence"),
        Index("idx_turns_trace", "trace_id"),
        Index("idx_turns_tenant", "tenant_id"),
        Index("idx_turns_conversation", "conversation_id"),
        Index("idx_turns_participant", "participant_id"),
        Index("idx_turns_created", "created_at"),
    )


class TurnState(Base):
    """Junction table linking conversation turns to their constituent states."""
    __tablename__ = "turn_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turn_id = Column(UUID(as_uuid=True), ForeignKey("conversation_turns.id", ondelete="CASCADE"), nullable=False)
    state_id = Column(UUID(as_uuid=True), ForeignKey("states.id", ondelete="CASCADE"), nullable=False)
    state_order = Column(Integer, nullable=False)

    # Relationships
    turn = relationship("ConversationTurn", back_populates="turn_states")
    state = relationship("State", back_populates="turn_states")

    __table_args__ = (
        UniqueConstraint("turn_id", "state_id", name="uq_turn_state"),
        Index("idx_turn_states_turn", "turn_id"),
        Index("idx_turn_states_state", "state_id"),
    )


class FailureExample(Base):
    """
    Labeled failure examples for RAG-based detection improvement.

    Stores MAST benchmark traces with their known failure modes for
    dynamic few-shot retrieval during LLM-based detection.
    """
    __tablename__ = "failure_examples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source identification
    dataset = Column(String(64), nullable=False, default="mast")  # mast, internal, user_feedback
    framework = Column(String(64), nullable=True)  # ag2, chatdev, metagpt, etc.
    trace_id = Column(String(128), nullable=True)  # Original trace ID if available

    # Failure classification
    failure_mode = Column(String(16), nullable=False)  # F1-F14
    is_failure = Column(Boolean, nullable=False)  # True if this IS a failure, False for healthy example

    # Content for retrieval
    task_description = Column(Text, nullable=False)  # The original task/goal
    conversation_summary = Column(Text, nullable=False)  # Summary of agent behavior
    key_events = Column(JSONB, default=list)  # List of key events

    # Vector embedding for similarity search (1024 dim for e5-large-v2)
    embedding = Column(Vector(1024), nullable=True)

    # Quality metadata
    confidence = Column(Integer, default=100)  # 0-100, how confident is the label
    source = Column(String(64), nullable=True)  # ground_truth, llm_labeled, user_feedback
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_failure_examples_mode", "failure_mode"),
        Index("idx_failure_examples_dataset", "dataset"),
        Index("idx_failure_examples_framework", "framework"),
        Index("idx_failure_examples_is_failure", "is_failure"),
        # IVFFlat index for vector similarity search will be created separately
    )


class HealingRecord(Base):
    """Tracks self-healing fix applications and their outcomes."""
    __tablename__ = "healing_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    detection_id = Column(UUID(as_uuid=True), ForeignKey("detections.id"), nullable=False)

    # Healing status
    status = Column(String(32), nullable=False, default="pending")  # pending, in_progress, applied, rolled_back, failed

    # Fix details
    fix_type = Column(String(64), nullable=False)  # From FixType enum
    fix_id = Column(String(64), nullable=False)  # Unique ID of the fix suggestion
    fix_suggestions = Column(JSONB, nullable=False)  # List of fix suggestions considered
    applied_fixes = Column(JSONB, default=dict)  # Details of fixes that were applied

    # State for rollback
    original_state = Column(JSONB, default=dict)  # Snapshot of state before fix
    rollback_available = Column(Boolean, default=True)

    # Validation
    validation_status = Column(String(32), nullable=True)  # passed, failed, skipped
    validation_results = Column(JSONB, default=dict)

    # Approval workflow
    approval_required = Column(Boolean, default=False)
    approved_by = Column(String(128), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    rolled_back_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Error tracking
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_healing_tenant", "tenant_id"),
        Index("idx_healing_detection", "detection_id"),
        Index("idx_healing_status", "status"),
        Index("idx_healing_created", "created_at"),
    )


class MASTTraceEmbedding(Base):
    """
    MAST benchmark trace embeddings for few-shot learning.

    Phase 4 Enhancement: Stores embeddings of MAST traces to enable
    similarity search for few-shot example selection in LLM prompts.

    Used by hybrid_pipeline.py to find similar traces for improving
    LLM verification accuracy through in-context examples.
    """
    __tablename__ = "mast_trace_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # MAST trace identifier (from original dataset)
    trace_id = Column(String(128), unique=True, nullable=False, index=True)

    # Task description embedding (1024 dimensions, e5-large-v2)
    task_embedding = Column(Vector(1024), nullable=False)

    # Ground truth failure annotations from MAST dataset
    # Format: {"F1": true, "F3": false, "F6": true, ...}
    ground_truth_failures = Column(JSONB, nullable=False)

    # Framework for filtering (ChatDev, MetaGPT, AG2, etc.)
    framework = Column(String(64), nullable=False, index=True)

    # Original task description (for display in few-shot examples)
    task_description = Column(Text, nullable=False)

    # Conversation summary (for few-shot context)
    conversation_summary = Column(Text, nullable=True)

    # Metadata from MAST dataset
    metadata = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_mast_trace_id", "trace_id"),
        Index("idx_mast_framework", "framework"),
        Index("idx_mast_created", "created_at"),
        # Cosine similarity index for fast vector search
        Index("idx_mast_task_embedding", "task_embedding", postgresql_using="ivfflat", postgresql_with={"lists": 100}),
    )

    @classmethod
    def find_similar_traces(
        cls,
        session,
        query_task: str,
        failure_mode: str,
        framework: str = None,
        k: int = 3,
        min_similarity: float = 0.70
    ):
        """
        Find k most similar MAST traces for few-shot examples.

        Args:
            session: SQLAlchemy session
            query_task: Task description to match against
            failure_mode: MAST failure mode (F1-F14) to filter by
            framework: Optional framework filter (ChatDev, MetaGPT, etc.)
            k: Number of similar traces to return (default: 3)
            min_similarity: Minimum cosine similarity threshold (default: 0.70)

        Returns:
            List of MASTTraceEmbedding objects ordered by similarity

        Usage:
            similar = MASTTraceEmbedding.find_similar_traces(
                session,
                query_task="Build a chat application",
                failure_mode="F1",
                framework="ChatDev",
                k=2
            )
        """
        from app.core.embeddings import get_embedder

        # Generate embedding for query task
        embedder = get_embedder()
        query_embedding = embedder.encode(query_task, is_query=True)

        # Build query with filters
        query = session.query(cls)

        # Filter by failure mode (ground truth must have this failure)
        query = query.filter(
            cls.ground_truth_failures[failure_mode].astext.cast(Boolean) == True
        )

        # Optional framework filter
        if framework:
            query = query.filter(cls.framework == framework)

        # Order by cosine similarity (lower distance = higher similarity)
        query = query.order_by(
            cls.task_embedding.cosine_distance(query_embedding)
        )

        # Limit to k results
        query = query.limit(k)

        # Execute and filter by min_similarity if needed
        results = query.all()

        # Calculate actual similarities and filter
        if min_similarity > 0:
            from app.core.embeddings import cosine_similarity
            filtered_results = []
            for result in results:
                similarity = cosine_similarity(query_embedding, result.task_embedding)
                if similarity >= min_similarity:
                    filtered_results.append(result)
            return filtered_results

        return results

    def formatted_example(self) -> str:
        """
        Format this trace as a few-shot example for LLM prompts.

        Returns:
            Formatted string with task, summary, and ground truth failures
        """
        failures = [mode for mode, value in self.ground_truth_failures.items() if value]

        return f"""
**Task:** {self.task_description[:200]}
**Framework:** {self.framework}
**Ground Truth Failures:** {', '.join(failures)}
**Summary:** {self.conversation_summary[:300] if self.conversation_summary else 'N/A'}
""".strip()
