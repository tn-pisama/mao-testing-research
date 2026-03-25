from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TenantResponse(BaseModel):
    id: UUID
    name: str
    api_key: str
    created_at: datetime


class TokenRequest(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=500)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    created_at: datetime
    revoked_at: Optional[datetime] = None


class ApiKeyCreateResponse(BaseModel):
    id: UUID
    name: str
    key: str
    key_prefix: str
    created_at: datetime


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str]
    role: str
    tenant_id: Optional[UUID] = None
    created_at: datetime


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
    # Plain-English explanation fields
    explanation: Optional[str] = None  # Human-readable explanation
    business_impact: Optional[str] = None  # Impact on users/business
    suggested_action: Optional[str] = None  # What to do next
    # Sprint 4: Detection transparency fields
    confidence_tier: Optional[str] = None  # HIGH/LIKELY/POSSIBLE/LOW
    detector_method: Optional[str] = None  # Detection method used
    # Continuous quality scoring (0.0 = total failure, 1.0 = perfect)
    quality_score: Optional[float] = None
    quality_dimensions: Optional[Dict[str, float]] = None  # correctness, completeness, safety, efficiency


class PaginatedDetectionResponse(BaseModel):
    """Paginated detection list response with total count."""
    items: List[DetectionResponse]
    total: int
    page: int
    per_page: int


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


class ApplyFixResponse(BaseModel):
    """Response when applying a fix."""
    success: bool
    fix_id: str
    detection_id: str
    applied_at: datetime
    message: str
    rollback_available: bool = False


# Agent Forensics Diagnosis Schemas

class DiagnoseRequest(BaseModel):
    """Request to diagnose a pasted trace."""
    content: str = Field(..., description="Raw trace content (JSON, JSONL, or structured text)")
    format: str = Field(default="auto", description="Format hint: auto, langsmith, otel, raw")
    include_fixes: bool = Field(default=True, description="Include suggested fixes in response")
    run_all_detections: bool = Field(default=True, description="Run all detection modules")


class DiagnoseDetectionResult(BaseModel):
    """Single detection result in diagnosis."""
    category: str
    detected: bool
    confidence: float
    severity: str
    title: str
    description: str
    evidence: List[Dict[str, Any]] = []
    affected_spans: List[str] = []
    suggested_fix: Optional[str] = None


class DiagnoseAutoFixPreview(BaseModel):
    """Preview of available auto-fix."""
    description: str
    confidence: float
    action: str


class DiagnoseResponse(BaseModel):
    """Response from trace diagnosis endpoint."""
    trace_id: str
    analyzed_at: datetime

    # Status
    has_failures: bool
    failure_count: int

    # Primary issue
    primary_failure: Optional[DiagnoseDetectionResult] = None

    # All issues
    all_detections: List[DiagnoseDetectionResult] = []

    # Trace stats
    total_spans: int
    error_spans: int
    total_tokens: int
    duration_ms: int

    # Root cause explanation
    root_cause_explanation: Optional[str] = None

    # Self-healing
    self_healing_available: bool = False
    auto_fix_preview: Optional[DiagnoseAutoFixPreview] = None

    # Performance
    detection_time_ms: int
    detectors_run: List[str] = []


class DiagnoseQuickCheckResponse(BaseModel):
    """Quick check response - lightweight failure detection."""
    has_failures: bool
    failure_count: int
    primary_category: Optional[str] = None
    primary_severity: Optional[str] = None
    message: str


# Conversation Trace Schemas

class ConversationIngestRequest(BaseModel):
    """Request to ingest a conversation trace."""
    content: str = Field(..., description="Raw conversation content (JSON or trajectory text)")
    format: str = Field(default="auto", description="Format: auto, mast, openai, claude, generic")


class ConversationTurnResponse(BaseModel):
    """Single turn in a conversation."""
    id: UUID
    turn_number: int
    participant_type: str
    participant_id: str
    content: str
    content_hash: Optional[str] = None
    accumulated_tokens: int = 0
    created_at: datetime


class ConversationResponse(BaseModel):
    """Response after ingesting a conversation."""
    trace_id: UUID
    conversation_id: str
    framework: str
    total_turns: int
    total_tokens: int
    participants: List[str]
    is_conversation: bool = True
    failure_modes: List[str] = []


class ConversationListResponse(BaseModel):
    """List of conversations."""
    conversations: List[ConversationResponse]
    total: int
    page: int
    per_page: int


class ConversationDetailResponse(BaseModel):
    """Detailed conversation with all turns."""
    trace_id: UUID
    conversation_id: str
    framework: str
    total_turns: int
    total_tokens: int
    participants: List[str]
    turns: List[ConversationTurnResponse]
    failure_modes: List[str] = []
    mast_annotations: Optional[Dict[str, Any]] = None
    created_at: datetime


class ConversationAnalyzeResponse(BaseModel):
    """Response from analyzing a conversation."""
    trace_id: UUID
    analyzed_turns: int
    detections: List[Dict[str, Any]]
    failure_modes_detected: List[str]
    turn_issues: List[Dict[str, Any]] = []


class DailyScore(BaseModel):
    """Daily average quality score."""
    date: str
    avg_score: float
    count: int


class IssueCount(BaseModel):
    """Quality issue count."""
    issue: str
    count: int
    severity: str


class QualityAnalyticsResponse(BaseModel):
    """Response for quality analytics."""
    score_distribution: Dict[str, int]
    grade_breakdown: Dict[str, int]
    category_breakdown: Dict[str, float]
    trend: List[DailyScore]
    top_issues: List[IssueCount]
    total_assessments: int
    page: int
    page_size: int
    has_more: bool
