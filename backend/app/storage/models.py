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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    tenant = relationship("Tenant", back_populates="traces")
    states = relationship("State", back_populates="trace")
    detections = relationship("Detection", back_populates="trace")
    
    __table_args__ = (
        Index("idx_traces_tenant", "tenant_id"),
        Index("idx_traces_session", "session_id"),
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
    embedding = Column(Vector(384), nullable=True)
    token_count = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    trace = relationship("Trace", back_populates="states")
    
    __table_args__ = (
        UniqueConstraint("trace_id", "sequence_num"),
        Index("idx_states_trace", "trace_id"),
        Index("idx_states_tenant", "tenant_id"),
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
    
    __table_args__ = (
        Index("idx_detections_tenant", "tenant_id"),
        Index("idx_detections_trace", "trace_id"),
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
