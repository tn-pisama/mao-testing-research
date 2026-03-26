from sqlalchemy import Column, String, Integer, Boolean, DateTime, Float, ForeignKey, Text, Index, UniqueConstraint
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

    # Billing fields
    plan = Column(String(20), default="free", nullable=False)
    stripe_customer_id = Column(String(255), unique=True, nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_status = Column(String(50), nullable=True)  # active, canceled, past_due, etc.
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    project_limit = Column(Integer, default=1, nullable=False)  # Free tier default

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
    clerk_user_id = Column(String(255), unique=True, nullable=True)  # Made nullable for migration
    google_user_id = Column(String(255), unique=True, nullable=True)  # New Google OAuth ID
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(128), nullable=True)
    name = Column(String(255), nullable=True)
    role = Column(String(50), default="member")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="users")

    __table_args__ = (
        Index("idx_users_clerk_id", "clerk_user_id"),
        Index("idx_users_google_id", "google_user_id"),
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


class ApiAudit(Base):
    __tablename__ = "api_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    status_code = Column(Integer, nullable=False)
    correlation_id = Column(String(64), nullable=True)
    ip_address = Column(String(45), nullable=True)
    duration_ms = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_api_audit_tenant", "tenant_id"),
        Index("idx_api_audit_created", "created_at"),
        Index("idx_api_audit_method", "method"),
    )


class Trace(Base):
    __tablename__ = "traces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    session_id = Column(String(64), nullable=False)
    parent_trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id"), nullable=True)
    framework = Column(String(32), default="unknown")
    provider = Column(String(32), nullable=True)  # bedrock, vertex_ai, crewai, openai, anthropic
    status = Column(String(32), default="running")
    detection_status = Column(String(32), default="pending")  # pending/running/partial/complete/failed
    detection_metadata = Column(JSONB, default=dict)  # {failed_detectors: [...], detectors_run: N, ...}
    total_tokens = Column(Integer, default=0)
    total_cost_cents = Column(Integer, default=0)
    is_conversation = Column(Boolean, default=False)
    harness_type = Column(String(32), nullable=True)  # single_agent/pipeline/gan_evaluator/hierarchical/sprint_based
    correlation_id = Column(String(128), nullable=True)  # Groups related traces across chains
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
        Index("idx_traces_parent", "parent_trace_id"),
        Index("idx_traces_correlation", "correlation_id"),
    )


class State(Base):
    __tablename__ = "states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    sequence_num = Column(Integer, nullable=False)
    agent_id = Column(String(128), nullable=False)
    agent_role = Column(String(32), nullable=True)  # planner/generator/evaluator/orchestrator/tool
    sprint_id = Column(String(64), nullable=True)  # Groups states into sprint boundaries
    context_reset = Column(Boolean, default=False)  # True if context was cleared before this state
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
    recall_context = Column(JSONB, nullable=True)  # {memories_recalled: [...ids], confidence_adjustment: float}
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


class GoldenDatasetEntryModel(Base):
    """Standalone golden dataset entries for detection calibration and training.

    Unlike GoldenTrace (which annotates real traces), these are synthetic
    calibration samples with ground-truth labels. tenant_id=NULL means global.
    """
    __tablename__ = "golden_dataset_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    entry_key = Column(String(255), nullable=False, unique=True)
    detection_type = Column(String(64), nullable=False)
    input_data = Column(JSONB, nullable=False)
    expected_detected = Column(Boolean, nullable=False)
    expected_confidence_min = Column(Float, default=0.0)
    expected_confidence_max = Column(Float, default=1.0)
    description = Column(Text, server_default="")
    source = Column(String(64), server_default="manual")
    tags = Column(JSONB, server_default="[]")
    difficulty = Column(String(16), server_default="easy")
    split = Column(String(16), server_default="train")
    source_trace_id = Column(String(255), nullable=True)
    source_workflow_id = Column(String(255), nullable=True)
    augmentation_method = Column(String(128), nullable=True)
    human_verified = Column(Boolean, server_default="false")
    entry_metadata = Column(JSONB, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_gde_tenant", "tenant_id"),
        Index("idx_gde_detection_type", "detection_type"),
        Index("idx_gde_split", "split"),
        Index("idx_gde_source", "source"),
        Index("idx_gde_difficulty", "difficulty"),
        Index("idx_gde_type_split", "detection_type", "split"),
        Index("idx_gde_type_detected", "detection_type", "expected_detected"),
        Index("idx_gde_tenant_type", "tenant_id", "detection_type"),
        Index("idx_gde_tags", "tags", postgresql_using="gin"),
        Index("idx_gde_created", "created_at"),
    )


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
    ingestion_mode = Column(String(20), nullable=True)  # NULL = use instance default
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "workflow_id", name="uq_n8n_workflow_tenant"),
        Index("idx_n8n_workflows_tenant", "tenant_id"),
    )


class N8nConnection(Base):
    """
    Stores n8n instance connection credentials per tenant.

    Each tenant can have multiple n8n connections (e.g., dev, staging, prod).
    API keys are stored encrypted for security.
    """
    __tablename__ = "n8n_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    # Connection details
    name = Column(String(255), nullable=False)  # e.g., "Production n8n", "Dev n8n"
    instance_url = Column(String(512), nullable=False)  # e.g., "https://my-n8n.example.com"
    api_key_encrypted = Column(Text, nullable=False)  # Encrypted API key

    # Status
    is_active = Column(Boolean, default=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    # Ingestion mode
    ingestion_mode = Column(String(20), default="full", server_default="full", nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_n8n_connections_tenant", "tenant_id"),
        UniqueConstraint("tenant_id", "name", name="uq_n8n_connection_name"),
    )


class OpenClawInstance(Base):
    """
    Stores OpenClaw instance connection credentials per tenant.

    Each tenant can have multiple OpenClaw instances (e.g., dev, prod).
    API keys are stored encrypted for security.
    """
    __tablename__ = "openclaw_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    # Connection details
    name = Column(String(255), nullable=False)  # e.g., "Production OpenClaw"
    gateway_url = Column(String(512), nullable=False)  # e.g., "ws://openclaw.example.com:18789"
    api_key_encrypted = Column(Text, nullable=False)  # Encrypted API key

    # Instance metadata
    openclaw_version = Column(String(32), nullable=True)
    channels_configured = Column(JSONB, default=list)  # ["whatsapp", "telegram", "slack"]
    agents_mapping = Column(JSONB, default=dict)  # Cached agents.mapping config

    # OTEL configuration
    otel_endpoint = Column(String(512), nullable=True)
    otel_enabled = Column(Boolean, default=False)

    # Status
    is_active = Column(Boolean, default=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    # Ingestion mode
    ingestion_mode = Column(String(20), default="full", server_default="full", nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    agents = relationship("OpenClawAgent", back_populates="instance", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_openclaw_instances_tenant", "tenant_id"),
        UniqueConstraint("tenant_id", "name", name="uq_openclaw_instance_name"),
    )


class OpenClawAgent(Base):
    """Registered OpenClaw agents for monitoring."""
    __tablename__ = "openclaw_agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    instance_id = Column(UUID(as_uuid=True), ForeignKey("openclaw_instances.id"), nullable=False)

    # Agent identity (from agents.mapping)
    agent_key = Column(String(255), nullable=False)  # Key in agents.mapping
    agent_name = Column(String(255), nullable=True)  # Display name
    model = Column(String(128), nullable=True)  # Configured model
    workspace = Column(String(512), nullable=True)  # Agent workspace path

    # Monitoring config
    webhook_secret = Column(String(255), nullable=True)
    monitoring_enabled = Column(Boolean, default=True)
    detection_overrides = Column(JSONB, default=dict)  # Per-agent threshold overrides
    ingestion_mode = Column(String(20), nullable=True)  # NULL = use instance default

    # Statistics
    total_sessions = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    last_active_at = Column(DateTime(timezone=True), nullable=True)

    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    instance = relationship("OpenClawInstance", back_populates="agents")

    __table_args__ = (
        UniqueConstraint("tenant_id", "instance_id", "agent_key", name="uq_openclaw_agent"),
        Index("idx_openclaw_agents_tenant", "tenant_id"),
        Index("idx_openclaw_agents_instance", "instance_id"),
    )


class DifyInstance(Base):
    """
    Stores Dify instance connection credentials per tenant.

    Each tenant can have multiple Dify instances (e.g., dev, prod).
    API keys are stored encrypted for security.
    """
    __tablename__ = "dify_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    # Connection details
    name = Column(String(255), nullable=False)  # e.g., "Production Dify"
    base_url = Column(String(512), nullable=False)  # e.g., "https://dify.example.com"
    api_key_encrypted = Column(Text, nullable=False)  # Encrypted API key

    # Instance metadata
    dify_version = Column(String(32), nullable=True)
    app_types_configured = Column(JSONB, default=list)  # ["chatbot", "agent", "workflow", "chatflow"]

    # Status
    is_active = Column(Boolean, default=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    # Ingestion mode
    ingestion_mode = Column(String(20), default="full", server_default="full", nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    apps = relationship("DifyApp", back_populates="instance", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_dify_instances_tenant", "tenant_id"),
        UniqueConstraint("tenant_id", "name", name="uq_dify_instance_name"),
    )


class DifyApp(Base):
    """Registered Dify apps for monitoring."""
    __tablename__ = "dify_apps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    instance_id = Column(UUID(as_uuid=True), ForeignKey("dify_instances.id"), nullable=False)

    # App identity
    app_id = Column(String(255), nullable=False)  # Dify's app UUID
    app_name = Column(String(255), nullable=True)  # Display name
    app_type = Column(String(64), nullable=False)  # chatbot, agent, workflow, chatflow

    # Monitoring config
    webhook_secret = Column(String(255), nullable=True)
    monitoring_enabled = Column(Boolean, default=True)
    detection_overrides = Column(JSONB, default=dict)  # Per-app threshold overrides
    ingestion_mode = Column(String(20), nullable=True)  # NULL = use instance default

    # Statistics
    total_runs = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    last_active_at = Column(DateTime(timezone=True), nullable=True)

    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    instance = relationship("DifyInstance", back_populates="apps")

    __table_args__ = (
        UniqueConstraint("tenant_id", "instance_id", "app_id", name="uq_dify_app"),
        Index("idx_dify_apps_tenant", "tenant_id"),
        Index("idx_dify_apps_instance", "instance_id"),
    )


class LangGraphDeployment(Base):
    """Registered LangGraph Platform deployments per tenant."""
    __tablename__ = "langgraph_deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    # Connection details
    name = Column(String(255), nullable=False)
    api_url = Column(String(512), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)

    # Deployment metadata
    deployment_id = Column(String(255), nullable=True)
    graph_name = Column(String(255), nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    # Ingestion mode
    ingestion_mode = Column(String(20), default="full", server_default="full", nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    assistants = relationship("LangGraphAssistant", back_populates="deployment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_lg_deployments_tenant", "tenant_id"),
        UniqueConstraint("tenant_id", "name", name="uq_lg_deployment_name"),
    )


class LangGraphAssistant(Base):
    """Registered LangGraph assistants (graphs) for monitoring."""
    __tablename__ = "langgraph_assistants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("langgraph_deployments.id"), nullable=False)

    # Assistant identity
    assistant_id = Column(String(255), nullable=False)
    graph_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)

    # Monitoring config
    webhook_secret = Column(String(255), nullable=True)
    monitoring_enabled = Column(Boolean, default=True)
    detection_overrides = Column(JSONB, default=dict)
    ingestion_mode = Column(String(20), nullable=True)

    # Statistics
    total_runs = Column(Integer, default=0)
    last_active_at = Column(DateTime(timezone=True), nullable=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    deployment = relationship("LangGraphDeployment", back_populates="assistants")

    __table_args__ = (
        UniqueConstraint("tenant_id", "deployment_id", "assistant_id", name="uq_lg_assistant"),
        Index("idx_lg_assistants_tenant", "tenant_id"),
        Index("idx_lg_assistants_deployment", "deployment_id"),
    )


class WorkflowGroup(Base):
    """
    Tenant-wide workflow groups for organizing and filtering workflows.

    Supports both manual assignment and auto-detection based on rules.
    Users can customize group names and visibility through UserGroupPreference.
    """
    __tablename__ = "workflow_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # Hex color (e.g., "#3b82f6")
    icon = Column(String(50), nullable=True)  # Icon name (e.g., "briefcase", "users")
    is_default = Column(Boolean, default=False, server_default="false")
    auto_detect_rules = Column(JSONB, nullable=True)  # Auto-detection configuration
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    assignments = relationship("WorkflowGroupAssignment", back_populates="group", cascade="all, delete-orphan")
    user_preferences = relationship("UserGroupPreference", back_populates="group", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_workflow_groups_tenant", "tenant_id"),
        UniqueConstraint("tenant_id", "name", name="uq_workflow_group_name"),
    )


class UserGroupPreference(Base):
    """
    User customizations for workflow groups.

    Allows users to rename groups, hide them, or reorder them
    without affecting the shared tenant-wide group configuration.
    """
    __tablename__ = "user_group_preferences"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(UUID(as_uuid=True), ForeignKey("workflow_groups.id", ondelete="CASCADE"), primary_key=True)
    custom_name = Column(String(255), nullable=True)  # User's custom name for this group
    is_hidden = Column(Boolean, default=False, server_default="false")  # Hide from filter dropdown
    sort_order = Column(Integer, nullable=True)  # Custom sort order

    # Relationships
    group = relationship("WorkflowGroup", back_populates="user_preferences")

    __table_args__ = (
        Index("idx_user_group_prefs_user", "user_id"),
        Index("idx_user_group_prefs_group", "group_id"),
    )


class WorkflowGroupAssignment(Base):
    """
    Workflow-to-group assignment mapping.

    Tracks both manual and auto-detected assignments.
    A workflow can belong to multiple groups.
    """
    __tablename__ = "workflow_group_assignments"

    workflow_id = Column(String(255), primary_key=True)
    group_id = Column(UUID(as_uuid=True), ForeignKey("workflow_groups.id", ondelete="CASCADE"), primary_key=True)
    assignment_type = Column(String(10), nullable=False)  # 'auto' or 'manual'
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # NULL for auto-assignments
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    group = relationship("WorkflowGroup", back_populates="assignments")

    __table_args__ = (
        Index("idx_workflow_assignments_workflow", "workflow_id"),
        Index("idx_workflow_assignments_group", "group_id"),
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

    # Per-detector progress tracking
    # {"loop": {"before": 0.85, "after": 0.1, "status": "fixed"}, ...}
    detector_progress = Column(JSONB, default=dict)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Framework entity tracking (for staged deployment and rollback)
    workflow_id = Column(String(255), nullable=True)  # Entity ID (workflow, app, agent, assistant)
    n8n_connection_id = Column(UUID(as_uuid=True), ForeignKey("n8n_connections.id"), nullable=True)
    dify_instance_id = Column(UUID(as_uuid=True), ForeignKey("dify_instances.id"), nullable=True)
    openclaw_instance_id = Column(UUID(as_uuid=True), ForeignKey("openclaw_instances.id"), nullable=True)
    langgraph_deployment_id = Column(UUID(as_uuid=True), ForeignKey("langgraph_deployments.id"), nullable=True)
    deployment_stage = Column(String(32), nullable=True)  # staged, promoted, rejected
    staged_at = Column(DateTime(timezone=True), nullable=True)
    promoted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_healing_tenant", "tenant_id"),
        Index("idx_healing_detection", "detection_id"),
        Index("idx_healing_status", "status"),
        Index("idx_healing_created", "created_at"),
        Index("idx_healing_workflow", "workflow_id"),
        Index("idx_healing_connection", "n8n_connection_id"),
        Index("idx_healing_stage", "deployment_stage"),
    )


class WorkflowVersion(Base):
    """Version history for n8n workflows modified by self-healing."""
    __tablename__ = "workflow_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    workflow_id = Column(String(255), nullable=False)  # n8n workflow ID
    connection_id = Column(UUID(as_uuid=True), ForeignKey("n8n_connections.id"), nullable=False)
    version_number = Column(Integer, nullable=False)  # Incrementing per workflow
    workflow_snapshot = Column(JSONB, nullable=False)  # Full workflow JSON
    healing_id = Column(UUID(as_uuid=True), ForeignKey("healing_records.id"), nullable=True)
    change_type = Column(String(32), nullable=False)  # fix_applied, rollback, promoted, rejected, restored
    change_description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_wv_tenant", "tenant_id"),
        Index("idx_wv_workflow", "workflow_id"),
        Index("idx_wv_connection", "connection_id"),
        Index("idx_wv_healing", "healing_id"),
        UniqueConstraint("tenant_id", "workflow_id", "version_number", name="uq_workflow_version_number"),
    )


class WorkflowQualityAssessment(Base):
    """
    Stores quality assessments for n8n workflows.

    Tracks agent quality scores, orchestration quality, and improvement suggestions
    for workflows analyzed by the quality assessment system.
    """
    __tablename__ = "workflow_quality_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id"), nullable=True)

    # Workflow identification
    workflow_id = Column(String(255), nullable=True, index=True)
    workflow_name = Column(String(255), nullable=True)

    # Overall scores
    overall_score = Column(Integer, nullable=False)  # 0-100
    overall_grade = Column(String(10), nullable=False)  # Healthy, Degraded, At Risk, Critical

    # Detailed scores (JSONB)
    agent_scores = Column(JSONB, nullable=False)  # List of agent quality scores
    orchestration_score = Column(JSONB, nullable=False)  # Orchestration quality details
    improvements = Column(JSONB, nullable=False)  # List of improvement suggestions

    # Metrics
    complexity_metrics = Column(JSONB, default=dict)  # node_count, agent_count, etc.
    total_issues = Column(Integer, default=0)
    critical_issues_count = Column(Integer, default=0)

    # Source and timing
    source = Column(String(50), nullable=False, default="api")  # api, webhook, manual
    assessment_time_ms = Column(Integer, nullable=True)

    # Summary
    summary = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_quality_tenant", "tenant_id"),
        Index("idx_quality_workflow", "workflow_id"),
        Index("idx_quality_trace", "trace_id"),
        Index("idx_quality_tenant_created", "tenant_id", "created_at"),
        Index("idx_quality_grade", "overall_grade"),
    )


class AgentQualityAssessment(Base):
    """
    Stores quality assessments for individual agents within a workflow.

    Each agent assessment is linked to a parent workflow assessment and tracks
    per-agent quality scores, dimension breakdowns, and optional reasoning.
    """
    __tablename__ = "agent_quality_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    workflow_assessment_id = Column(UUID(as_uuid=True), ForeignKey("workflow_quality_assessments.id"), nullable=False)
    trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id"), nullable=True)

    # Agent identification
    agent_id = Column(String(255), nullable=False, index=True)
    agent_name = Column(String(255), nullable=True)
    agent_type = Column(String(100), nullable=False)

    # Scores
    overall_score = Column(Integer, nullable=False)  # 0-100
    grade = Column(String(10), nullable=False)  # Healthy, Degraded, At Risk, Critical

    # Detailed scores (JSONB)
    dimensions = Column(JSONB, nullable=False)  # List of dimension scores

    # Issues
    issues_count = Column(Integer, default=0)
    critical_issues = Column(JSONB, default=list)

    # Reasoning
    reasoning = Column(Text, nullable=True)

    # Extra metadata
    extra_metadata = Column("metadata", JSONB, server_default="{}")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_agent_quality_tenant", "tenant_id"),
        Index("idx_agent_quality_workflow_assessment", "workflow_assessment_id"),
        Index("idx_agent_quality_agent_id", "agent_id"),
        Index("idx_agent_quality_tenant_created", "tenant_id", "created_at"),
    )


class QualityHealingRecord(Base):
    """
    Tracks quality healing fix applications and outcomes.

    Records the full lifecycle of a quality healing operation: the assessment
    that triggered it, fixes generated and applied, before/after scores,
    and rollback state.
    """
    __tablename__ = "quality_healing_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("workflow_quality_assessments.id"), nullable=True)

    # Status
    status = Column(String(32), nullable=False, default="pending")

    # Scores
    before_score = Column(Float, nullable=False)
    after_score = Column(Float, nullable=True)

    # Fix details
    dimensions_targeted = Column(JSONB, nullable=False, server_default="[]")
    fix_suggestions = Column(JSONB, nullable=False, server_default="[]")
    applied_fixes = Column(JSONB, server_default="[]")

    # State for rollback
    original_state = Column(JSONB, server_default="{}")
    modified_state = Column(JSONB, server_default="{}")
    rollback_available = Column(Boolean, default=True)

    # Validation
    validation_results = Column(JSONB, server_default="[]")

    # Approval workflow
    approval_required = Column(Boolean, default=False)
    approved_by = Column(String(128), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    rolled_back_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Workflow reference
    workflow_id = Column(String(255), nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_qh_tenant", "tenant_id"),
        Index("idx_qh_assessment", "assessment_id"),
        Index("idx_qh_status", "status"),
        Index("idx_qh_created", "created_at"),
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

    # Metadata from MAST dataset (renamed from 'metadata' to avoid SQLAlchemy reserved name)
    trace_metadata = Column(JSONB, default=dict)

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
            import numpy as np
            filtered_results = []
            for result in results:
                # Calculate cosine similarity
                vec1 = np.array(query_embedding)
                vec2 = np.array(result.task_embedding)
                similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
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


class ReplayBundle(Base):
    __tablename__ = "replay_bundles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    trace_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(32), default="ready")  # ready, replaying
    event_count = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    models_used = Column(JSONB, default=list)
    tools_used = Column(JSONB, default=list)
    agents_involved = Column(JSONB, default=list)
    bundle_data = Column(JSONB, nullable=True)  # serialized state snapshots
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    results = relationship("ReplayResult", back_populates="bundle", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_replay_bundles_tenant", "tenant_id"),
        Index("idx_replay_bundles_trace", "trace_id"),
    )


class ReplayResult(Base):
    __tablename__ = "replay_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bundle_id = Column(UUID(as_uuid=True), ForeignKey("replay_bundles.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    status = Column(String(32), default="pending")  # pending, running, completed, failed, stopped
    mode = Column(String(32), default="deterministic")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    events_replayed = Column(Integer, default=0)
    events_total = Column(Integer, default=0)
    matches = Column(Integer, default=0)
    mismatches = Column(Integer, default=0)
    similarity_score = Column(Integer, default=0)  # stored as 0-100 integer
    diffs = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bundle = relationship("ReplayBundle", back_populates="results")

    __table_args__ = (
        Index("idx_replay_results_bundle", "bundle_id"),
        Index("idx_replay_results_tenant", "tenant_id"),
    )


class CustomScorer(Base):
    __tablename__ = "custom_scorers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    prompt_template = Column(Text, nullable=False)
    scoring_criteria = Column(JSONB, default=list)
    scoring_rubric = Column(Text, nullable=True)
    model_key = Column(String(64), default="sonnet-4")
    score_range_min = Column(Integer, default=1)
    score_range_max = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    results = relationship("ScorerResult", back_populates="scorer", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_custom_scorers_tenant", "tenant_id"),
        Index("idx_custom_scorers_active", "tenant_id", "is_active"),
    )


class ScorerResult(Base):
    __tablename__ = "scorer_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scorer_id = Column(UUID(as_uuid=True), ForeignKey("custom_scorers.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, nullable=False)  # 1-5
    confidence = Column(Integer, default=50)  # 0-100
    verdict = Column(String(16), nullable=False)  # PASS, WARN, FAIL, UNCERTAIN
    reasoning = Column(Text, nullable=True)
    evidence = Column(JSONB, default=list)
    suggestions = Column(JSONB, default=list)
    model_used = Column(String(128), nullable=True)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Integer, default=0)  # stored as microdollars (x100000)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scorer = relationship("CustomScorer", back_populates="results")

    __table_args__ = (
        Index("idx_scorer_results_scorer", "scorer_id"),
        Index("idx_scorer_results_tenant", "tenant_id"),
        Index("idx_scorer_results_trace", "trace_id"),
        Index("idx_scorer_results_verdict", "verdict"),
    )


class ConversationEvaluation(Base):
    __tablename__ = "conversation_evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id", ondelete="CASCADE"), nullable=False)
    overall_score = Column(Float, nullable=False)  # 0.0 - 1.0
    overall_grade = Column(String(2), nullable=False)  # A, B, C, D, F
    dimension_scores = Column(JSONB, nullable=False)
    scoring_method = Column(String(32), nullable=False)  # heuristic, llm_judge, blended
    summary = Column(Text, nullable=True)
    turn_annotations = Column(JSONB, default=list)
    total_turns = Column(Integer, default=0)
    total_participants = Column(Integer, default=0)
    conversation_duration_ms = Column(Integer, nullable=True)
    eval_cost_usd = Column(Float, default=0.0)
    eval_tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_conv_eval_tenant", "tenant_id"),
        Index("idx_conv_eval_trace", "trace_id"),
        Index("idx_conv_eval_grade", "overall_grade"),
        Index("idx_conv_eval_tenant_created", "tenant_id", "created_at"),
    )


class SourceFix(Base):
    __tablename__ = "source_fixes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    detection_id = Column(UUID(as_uuid=True), ForeignKey("detections.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(512), nullable=False)
    language = Column(String(32), nullable=False)
    original_code = Column(Text, nullable=False)
    fixed_code = Column(Text, nullable=False)
    unified_diff = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False)
    root_cause = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False)  # 0.0 - 1.0
    breaking_risk = Column(String(16), default="low")  # low, medium, high
    requires_testing = Column(Boolean, default=True)
    framework_specific = Column(Boolean, default=False)
    model_used = Column(String(128), nullable=True)
    generation_cost_usd = Column(Float, default=0.0)
    generation_tokens = Column(Integer, default=0)
    status = Column(String(32), default="generated")  # generated, applied, rejected
    applied_at = Column(DateTime(timezone=True), nullable=True)
    applied_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_source_fix_tenant", "tenant_id"),
        Index("idx_source_fix_detection", "detection_id"),
        Index("idx_source_fix_status", "status"),
        Index("idx_source_fix_language", "language"),
        Index("idx_source_fix_created", "created_at"),
    )


# ---------------------------------------------------------------------------
# Cognitive Memory
# ---------------------------------------------------------------------------

class CognitiveMemory(Base):
    """Atomic memory unit for PISAMA's cognitive memory system.

    Each memory is a single fact/pattern/insight with composite scoring
    for intelligent recall. Encodes selectively, recalls with confidence,
    forgets deliberately.
    """
    __tablename__ = "cognitive_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    # Classification
    memory_type = Column(String(32), nullable=False)
    domain = Column(String(64), nullable=False)

    # Content
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    structured_data = Column(JSONB, default=dict)

    # Source provenance
    source_type = Column(String(32), nullable=False)
    source_id = Column(UUID(as_uuid=True), nullable=True)
    source_trace_id = Column(UUID(as_uuid=True), nullable=True)

    # Composite scoring
    importance = Column(Float, nullable=False, default=0.5)
    confidence = Column(Float, nullable=False, default=0.5)
    access_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)

    # Contradiction chain
    supersedes_id = Column(UUID(as_uuid=True), ForeignKey("cognitive_memories.id"), nullable=True)
    superseded_by_id = Column(UUID(as_uuid=True), ForeignKey("cognitive_memories.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    # Vector embedding (1024-dim e5-large-v2)
    embedding = Column(Vector(1024), nullable=True)

    # Filtering
    tags = Column(JSONB, server_default="[]")
    framework = Column(String(32), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_cm_tenant", "tenant_id"),
        Index("idx_cm_type", "memory_type"),
        Index("idx_cm_domain", "domain"),
        Index("idx_cm_active", "is_active"),
        Index("idx_cm_tenant_domain", "tenant_id", "domain"),
        Index("idx_cm_tenant_type", "tenant_id", "memory_type"),
        Index("idx_cm_importance", "importance"),
        Index("idx_cm_created", "created_at"),
        Index("idx_cm_tags", "tags", postgresql_using="gin"),
        Index("idx_cm_framework", "framework"),
        Index("idx_cm_content_hash", "tenant_id", "content_hash"),
    )


class MemoryRecallLog(Base):
    """Audit log of memory recall operations."""
    __tablename__ = "memory_recall_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    recall_context = Column(String(64), nullable=False)
    recall_query = Column(Text, nullable=False)
    domain_filter = Column(String(64), nullable=True)

    memories_returned = Column(Integer, nullable=False, default=0)
    top_memory_id = Column(UUID(as_uuid=True), ForeignKey("cognitive_memories.id"), nullable=True)
    composite_scores = Column(JSONB, default=list)

    was_useful = Column(Boolean, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_mrl_tenant", "tenant_id"),
        Index("idx_mrl_context", "recall_context"),
        Index("idx_mrl_created", "created_at"),
    )


class MemoryExtractionJob(Base):
    """Tracks atomic memory extraction from large analyses."""
    __tablename__ = "memory_extraction_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    source_type = Column(String(32), nullable=False)
    source_id = Column(String(255), nullable=False)
    source_text_length = Column(Integer, nullable=False)

    status = Column(String(20), nullable=False, default="pending")
    memories_extracted = Column(Integer, default=0)
    memories_deduplicated = Column(Integer, default=0)
    contradictions_found = Column(Integer, default=0)

    llm_cost_usd = Column(Float, default=0.0)
    llm_tokens_used = Column(Integer, default=0)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_mej_tenant", "tenant_id"),
        Index("idx_mej_status", "status"),
    )


class ShadowEvalResult(Base):
    """Shadow evaluation results for runtime judge drift detection."""
    __tablename__ = "shadow_eval_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    detector_type = Column(String(64), nullable=False)
    golden_entry_id = Column(String(255), nullable=False)
    expected_detected = Column(Boolean, nullable=False)
    actual_detected = Column(Boolean, nullable=False)
    expected_confidence_min = Column(Float, default=0.0)
    expected_confidence_max = Column(Float, default=1.0)
    actual_confidence = Column(Float, nullable=False)
    match = Column(Boolean, nullable=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_shadow_eval_detector", "detector_type"),
        Index("idx_shadow_eval_created", "created_at"),
        Index("idx_shadow_eval_match", "detector_type", "match"),
    )
