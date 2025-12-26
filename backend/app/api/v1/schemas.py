from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID


class TenantCreate(BaseModel):
    name: str


class TenantResponse(BaseModel):
    id: UUID
    name: str
    api_key: str
    created_at: datetime


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TraceIngestRequest(BaseModel):
    resourceSpans: List[Dict[str, Any]]


class TraceResponse(BaseModel):
    id: UUID
    session_id: str
    framework: str
    status: str
    total_tokens: int
    total_cost_cents: int
    created_at: datetime
    completed_at: Optional[datetime]
    state_count: int = 0
    detection_count: int = 0


class TraceListResponse(BaseModel):
    traces: List[TraceResponse]
    total: int
    page: int
    per_page: int


class StateResponse(BaseModel):
    id: UUID
    sequence_num: int
    agent_id: str
    state_delta: Dict[str, Any]
    state_hash: str
    token_count: int
    latency_ms: int
    created_at: datetime


class DetectionResponse(BaseModel):
    id: UUID
    trace_id: UUID
    state_id: Optional[UUID]
    detection_type: str
    confidence: int
    method: str
    details: Dict[str, Any]
    validated: bool
    false_positive: Optional[bool]
    created_at: datetime


class DetectionValidateRequest(BaseModel):
    false_positive: bool
    notes: Optional[str] = None


class AnalyticsLoopResponse(BaseModel):
    total_loops_detected: int
    loops_by_method: Dict[str, int]
    avg_loop_length: float
    top_agents_in_loops: List[Dict[str, Any]]
    time_series: List[Dict[str, Any]]


class AnalyticsCostResponse(BaseModel):
    total_cost_cents: int
    total_tokens: int
    cost_by_framework: Dict[str, int]
    cost_by_day: List[Dict[str, Any]]
    top_expensive_traces: List[Dict[str, Any]]


class SettingsUpdate(BaseModel):
    loop_detection_enabled: Optional[bool] = None
    corruption_detection_enabled: Optional[bool] = None
    persona_detection_enabled: Optional[bool] = None
    coordination_analysis_enabled: Optional[bool] = None
    pii_redaction_enabled: Optional[bool] = None
    alert_webhook_url: Optional[str] = None


class SettingsResponse(BaseModel):
    loop_detection_enabled: bool = True
    corruption_detection_enabled: bool = True
    persona_detection_enabled: bool = True
    coordination_analysis_enabled: bool = True
    pii_redaction_enabled: bool = True
    alert_webhook_url: Optional[str] = None


class ChaosTestCreate(BaseModel):
    test_type: str = Field(..., pattern="^(loop|corruption|delay|failure)$")
    target_agent: Optional[str] = None
    parameters: Dict[str, Any] = {}


class ChaosTestResponse(BaseModel):
    id: UUID
    test_type: str
    target_agent: Optional[str]
    parameters: Dict[str, Any]
    status: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    version: str


class CodeChangeResponse(BaseModel):
    file_path: str
    language: str
    original_code: Optional[str]
    suggested_code: str
    start_line: Optional[int]
    end_line: Optional[int]
    description: str
    diff: str


class FixSuggestionResponse(BaseModel):
    id: str
    detection_id: str
    detection_type: str
    fix_type: str
    confidence: str
    title: str
    description: str
    rationale: str
    code_changes: List[CodeChangeResponse]
    estimated_impact: str
    breaking_changes: bool
    requires_testing: bool
    tags: List[str]
    metadata: Dict[str, Any]


class FixSuggestionsListResponse(BaseModel):
    detection_id: str
    suggestions: List[FixSuggestionResponse]
    total: int
