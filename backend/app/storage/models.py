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
    api_key_hash = Column(String(64), nullable=False)
    settings = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    traces = relationship("Trace", back_populates="tenant")
    detections = relationship("Detection", back_populates="tenant")


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
