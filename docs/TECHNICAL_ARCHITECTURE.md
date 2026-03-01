# PISAMA Detection System — Technical Architecture

Complete technical reference for the PISAMA multi-agent failure detection platform. Covers every component from trace ingestion through detection, healing, and storage.

For the engineering onboarding guide, see [`docs/FAILURE_MODE_ONBOARDING.md`](./FAILURE_MODE_ONBOARDING.md).
For the customer-facing reference, see [`docs/failure-modes-reference.md`](./failure-modes-reference.md).

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Trace Ingestion Pipeline](#trace-ingestion-pipeline)
3. [Detection Pipeline](#detection-pipeline)
4. [Individual Detector Implementations](#individual-detector-implementations)
5. [Tiered Detection Architecture](#tiered-detection-architecture)
6. [Embedding System](#embedding-system)
7. [LLM Judge System](#llm-judge-system)
8. [Calibration System](#calibration-system)
9. [Self-Healing Pipeline](#self-healing-pipeline)
10. [Storage Layer](#storage-layer)
11. [API Layer](#api-layer)
12. [SDK & CLI](#sdk--cli)
13. [Testing Infrastructure](#testing-infrastructure)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              PISAMA Platform                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Frontend   │  │   Backend    │  │     SDK      │  │     CLI      │       │
│  │   (Next.js)  │  │  (FastAPI)   │  │   (Python)   │  │   (Python)   │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │                 │                │
│         └────────────────┼─────────────────┴─────────────────┘                │
│                          │                                                     │
│                          ▼                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                         Core Services                                    │  │
│  ├───────────────┬──────────────┬──────────────┬─────────────────────────── │  │
│  │  Detection    │   Ingestion  │   Storage    │   Self-Healing            │  │
│  │  Engine       │   Pipeline   │   Layer      │   Pipeline                │  │
│  │  - 21 MAST   │   - OTEL     │   - Postgres │   - Analyze              │  │
│  │  - 6 n8n     │   - n8n      │   - pgvector │   - Generate fixes       │  │
│  │  - Tiered    │   - Universal│   - SQLAlch  │   - Apply + validate     │  │
│  │  - LLM Judge │              │              │   - Rollback             │  │
│  └───────────────┴──────────────┴──────────────┴─────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy, PostgreSQL 15+, pgvector, Alembic |
| Frontend | Next.js 16, React 18, TailwindCSS 3.4, Zustand, TanStack Query 5 |
| ML/Embeddings | E5-large-instruct (1024d), nomic-embed-text-v1.5 (768d), sentence-transformers |
| LLM | Claude (Anthropic) — primary; Gemini — Tier 1 budget |
| SDK | Python with LangGraph/AutoGen/CrewAI/n8n adapters |
| CLI | Click-based with MCP server support |
| Infra | Docker, Terraform, AWS ECS |

---

## Trace Ingestion Pipeline

**Source**: `backend/app/ingestion/`

### OTEL Parser (`otel.py`)

Parses OpenTelemetry spans using `gen_ai.*` semantic conventions.

```python
@dataclass
class OTELSpan:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    kind: str                       # SPAN_KIND_INTERNAL, etc.
    start_time_unix_nano: int
    end_time_unix_nano: int
    attributes: Dict[str, Any]      # gen_ai.*, langgraph.*, crewai.*, etc.
    status: Dict[str, Any]
    events: List[Dict[str, Any]]

@dataclass
class ParsedState:
    trace_id: str
    sequence_num: int
    agent_id: str
    state_delta: dict
    state_hash: str                 # SHA256[:16]
    prompt: Optional[str]
    response: Optional[str]
    tool_calls: Optional[List[dict]]
    token_count: int
    latency_ms: int
    timestamp: datetime
```

**Agent identification** — the parser checks multiple framework-specific attributes to find the agent name:

```python
AGENT_ATTRIBUTES = [
    "gen_ai.agent.name",       # Standard OTEL GenAI
    "langgraph.node.name",     # LangGraph
    "crewai.agent.role",       # CrewAI
    "autogen.agent.name",      # AutoGen
    "openclaw.agent.name",     # OpenClaw
]

STATE_ATTRIBUTES = [
    "gen_ai.state",            # Standard
    "langgraph.state",         # LangGraph
    "crewai.state",            # CrewAI
    "openclaw.session.state",  # OpenClaw
]
```

**Key methods**: `parse_spans()`, `_extract_agent_id()`, `_extract_state_delta()`, `_extract_tool_calls()`, `_compute_hash()`.

### n8n Parser (`n8n_parser.py`)

Parses n8n workflow execution payloads received via webhook.

```python
@dataclass
class N8nNode:
    name: str
    type: str
    parameters: Dict[str, Any]
    execution_time_ms: int = 0
    output: Any = None
    error: Optional[str] = None

@dataclass
class N8nExecution:
    id: str
    workflow_id: str
    workflow_name: str
    mode: str                   # "manual", "trigger"
    started_at: datetime
    finished_at: Optional[datetime]
    status: str                 # "success", "error"
    nodes: List[N8nNode]
```

AI node types are detected for token tracking:
```python
AI_NODE_TYPES = [
    "n8n-nodes-base.openAi",
    "n8n-nodes-base.anthropic",
    "n8n-nodes-langchain.agent",
    # ...
]
```

### Normalization

All parsers normalize to `ParsedState` with consistent fields:
- `state_hash`: SHA256 of normalized `state_delta`, truncated to 16 chars
- `token_count`: Extracted from `gen_ai.tokens.input` + `gen_ai.tokens.output`
- `latency_ms`: Span duration from timestamps

---

## Detection Pipeline

### Orchestrator (`backend/app/detection_enterprise/orchestrator.py`)

The `DetectionOrchestrator` is the main entry point for trace analysis.

```python
class DetectionOrchestrator:
    def __init__(
        self,
        enable_llm_explanation: bool = True,
        max_parallel_detectors: int = 5,
        timeout_seconds: float = 30.0,
    )

    def analyze_trace(self, trace: UniversalTrace) -> DiagnosisResult
```

**Pipeline flow of `analyze_trace()`:**

1. Initialize `DiagnosisResult` with trace metadata (trace_id, total_spans, error_spans, total_tokens, duration_ms)
2. Convert spans to `StateSnapshot` objects
3. Execute detection chain sequentially:
   - `_detect_loops()` → Loop detection
   - `_detect_overflow()` → Context overflow
   - `_detect_tool_issues()` → Tool provision issues
   - `_detect_error_patterns()` → Error pattern analysis
   - `_detect_grounding_failure()` → Grounding failure (F15/OfficeQA)
   - `_detect_retrieval_quality()` → Retrieval quality (F16/OfficeQA)
4. Filter to `detected=True` results only
5. Sort by severity (CRITICAL→INFO) then confidence (descending)
6. Set `primary_failure` = first in sorted list
7. Generate root cause explanation via `_generate_explanation()`
8. Record `detection_time_ms`

**Lazy loading pattern** — detectors are instantiated on first use:
```python
@property
def loop_detector(self) -> MultiLevelLoopDetector:
    if self._loop_detector is None:
        self._loop_detector = MultiLevelLoopDetector()
    return self._loop_detector
```

### Detection Result Model

```python
@dataclass
class DetectionResult:
    category: DetectionCategory   # Enum: LOOP, CORRUPTION, etc.
    detected: bool
    confidence: float             # 0.0–1.0
    severity: Severity            # CRITICAL, HIGH, MEDIUM, LOW, INFO
    title: str
    description: str
    evidence: List[Dict[str, Any]]
    affected_spans: List[str]
    suggested_fix: Optional[str]
    raw_result: Optional[Any]     # Detector-specific result

@dataclass
class DiagnosisResult:
    trace_id: str
    analyzed_at: datetime
    has_failures: bool
    failure_count: int
    primary_failure: Optional[DetectionResult]
    all_detections: List[DetectionResult]
    total_spans: int
    error_spans: int
    total_tokens: int
    duration_ms: int
    root_cause_explanation: Optional[str]
    self_healing_available: bool
    auto_fix_preview: Optional[Dict[str, Any]]
    detection_time_ms: int
    detectors_run: List[str]
```

### DetectionType Enum

Full registry in `backend/app/detection/validation.py`:

```python
class DetectionType(Enum):
    # MAST behavioral
    LOOP = "loop"
    CORRUPTION = "corruption"
    PERSONA_DRIFT = "persona_drift"
    HALLUCINATION = "hallucination"
    DERAILMENT = "derailment"
    OVERFLOW = "overflow"
    COORDINATION = "coordination"
    INJECTION = "injection"
    COMMUNICATION = "communication"
    CONTEXT = "context"
    DECOMPOSITION = "decomposition"
    WORKFLOW = "workflow"
    GROUNDING = "grounding"
    RETRIEVAL_QUALITY = "retrieval_quality"
    # n8n structural
    N8N_SCHEMA = "n8n_schema"
    N8N_CYCLE = "n8n_cycle"
    N8N_COMPLEXITY = "n8n_complexity"
    N8N_ERROR = "n8n_error"
    N8N_RESOURCE = "n8n_resource"
    N8N_TIMEOUT = "n8n_timeout"
```

### Turn-Aware Detection (`backend/app/detection/turn_aware/_base.py`)

For conversation-level analysis across multiple turns:

```python
@dataclass
class TurnSnapshot:
    turn_number: int
    participant_type: str       # 'user', 'agent', 'system', 'tool'
    participant_id: str
    content: str
    content_hash: Optional[str] # SHA256[:16], auto-generated
    accumulated_context: Optional[str]
    accumulated_tokens: int
    turn_metadata: Dict[str, Any]

class TurnAwareDetector(ABC):
    name: str = "TurnAwareDetector"
    version: str = "1.1"
    supported_failure_modes: List[str] = []

    @abstractmethod
    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult
```

Constants:
- `MAX_TURNS_BEFORE_SUMMARIZATION = 50`
- `MAX_TOKENS_BEFORE_SUMMARIZATION = 8000`
- `EMBEDDING_SIMILARITY_THRESHOLD = 0.7`

---

## Individual Detector Implementations

### MAST Planning Failures (FC1)

#### F1: Specification Mismatch (`backend/app/detection/specification.py`)

**Version**: 2.1 | **Key**: `specification` | **Tier**: ICP | **F1**: 0.717

Detects when task output doesn't match user intent. Uses:
- **Keyword coverage**: Stem matching + domain synonyms (e.g., catalog↔category)
- **Semantic coverage** (v1.3): Sentence-level embedding comparison — `max(keyword, semantic)` floor ensures embeddings only improve, never regress
- **Reformulation detection**: Distinguishes task restatement from actual violation
- **Code quality checks**: Language mismatch (requested Python, got TypeScript), deprecated syntax
- **Numeric tolerance**: Approximate constraints (word counts)

Issue types: `SCOPE_DRIFT`, `MISSING_REQUIREMENT`, `AMBIGUOUS_SPEC`, `CONFLICTING_SPEC`, `OVERSPECIFIED`

Result structure:
```python
@dataclass
class SpecificationMismatchResult:
    detected: bool
    mismatch_type: Optional[MismatchType]
    severity: MismatchSeverity           # NONE, MINOR, MODERATE, SEVERE
    confidence: float
    requirement_coverage: float
    missing_requirements: list[str]
    ambiguous_elements: list[str]
    explanation: str
    suggested_fix: Optional[str]
```

#### F2: Poor Task Decomposition (`backend/app/detection/decomposition.py`)

**Version**: 1.7 | **Key**: `decomposition` | **Tier**: ICP | **F1**: 0.772

Detects flawed subtask breakdown. Checks:
- **Dependency validation**: Circular dependencies, missing dependencies
- **Granularity analysis**: Too-large subtasks (COMPLEXITY_INDICATORS), too-vague subtasks (VAGUE_INDICATORS)
- **Simple task bypass** (v1.2): `SIMPLE_TASK_INDICATORS` — simple tasks don't need decomposition
- **Direct implementation detection** (v1.2): Recognizes prose-style direct approaches
- **Weighted issue confidence**: Issue-specific weights for confidence calculation

#### F3: Resource Misallocation (`backend/app/detection_enterprise/resource_misallocation.py`)

**Tier**: Enterprise | Not yet calibrated

Detects inefficient resource allocation — token budgets, compute allocation, agent assignment.

#### F4: Inadequate Tool Provision (`backend/app/detection_enterprise/tool_provision.py`)

**Tier**: Enterprise | Not yet calibrated

Detects when required tools/APIs are missing or misconfigured for the task.

#### F5: Flawed Workflow Design (`backend/app/detection/workflow.py`)

**Version**: latest | **Key**: `workflow` | **Tier**: ICP | **F1**: 0.808

Analyzes workflow graph structure for:
- **Unreachable/dead-end nodes**: Graph traversal from start
- **Missing error handling**: Nodes without error handler paths
- **Infinite loop risk**: Cycles without termination conditions
- **Bottleneck nodes**: High in-degree/out-degree ratios
- **Orphan nodes**: No incoming or outgoing connections
- **Excessive depth** (v1.1): Long sequential chains

Issue types: `UNREACHABLE_NODE`, `DEAD_END`, `MISSING_ERROR_HANDLING`, `INFINITE_LOOP_RISK`, `BOTTLENECK`, `MISSING_TERMINATION`, `ORPHAN_NODE`, `EXCESSIVE_DEPTH`

Node model:
```python
@dataclass
class WorkflowNode:
    id: str
    name: str
    node_type: str
    incoming: list[str]
    outgoing: list[str]
    has_error_handler: bool = False
    is_terminal: bool = False
```

Confidence discrimination (v-latest): Issue-type-based confidence in 0.22–0.42 range for single-issue cases.

---

### MAST Execution Failures (FC2)

#### F6: Task Derailment (`backend/app/detection/derailment.py`)

**Version**: 1.5 | **Key**: `derailment` | **Tier**: ICP | **F1**: 0.820

Detects off-topic deviation via:
- **Semantic similarity**: Embedding distance between task and output
- **Topic drift**: Progressive drift measurement
- **Task substitution** (v1.2): Detects confused concepts using `TASK_CLUSTERS` and `SUBSTITUTION_PAIRS` (e.g., authentication vs authorization)
- **Focus mismatch** (v1.4): Research tasks delivering wrong focus area
- **Content-type matching**: Writing tasks delivering wrong format

Key data structures:
```python
TASK_CLUSTERS = {
    "authentication": ["authenticate", "login", "password", ...],
    "authorization": ["authorize", "permission", "access control", ...],
    ...
}
SUBSTITUTION_PAIRS = [
    ("authentication", "authorization"),
    ("encrypt", "decrypt"),
    ("upload", "download"),
    ...
]
```

#### F7: Context Neglect (`backend/app/detection/context.py`)

**Version**: 1.2 | **Key**: `context` | **Tier**: ICP | **F1**: 0.868

Detects when agents ignore upstream context:
- **Keyword element matching**: Checks if context keywords appear in output
- **Critical marker detection** (v1.2): Flags "CRITICAL:", "IMPORTANT:", "MUST HANDLE" markers
- **Adaptation recognition** (v1.1): `ADAPTATION_PHRASES` whitelist for legitimate reformulation
- **Conceptual overlap scoring**: Semantic matching for paraphrased context usage

Key constants: `CRITICAL_CONTEXT_MARKERS` (12 patterns), `CONTEXT_REFERENCE_PHRASES` (26 patterns), `ADAPTATION_PHRASES`.

Task completion threshold raised from 0.15 to 0.25 in v1.2.

#### F8: Information Withholding (`backend/app/detection/withholding.py`)

**Version**: 1.2 | **Key**: `withholding` | **Tier**: ICP | **F1**: 0.874

Detects when agents don't share critical information:
- **Critical omission**: Important info discovered but not passed on
- **Detail loss**: Summaries that remove critical details
- **Negative suppression**: Selectively omitting negative findings
- **Selective reporting**: Cherry-picking favorable data

Issue types: `CRITICAL_OMISSION`, `DETAIL_LOSS`, `NEGATIVE_SUPPRESSION`, `SELECTIVE_REPORTING`, `CONTEXT_STRIPPING`

FPR reduction (v1.2): Expanded condensed output patterns, importance weighting, semantic retention check, role-based thresholds.

#### F9: Role Usurpation (`backend/app/detection_enterprise/role_usurpation.py`)

**Tier**: Enterprise | Not yet calibrated

Detects agents exceeding their designated authority boundaries.

#### F10: Communication Breakdown (`backend/app/detection/communication.py`)

**Key**: `communication` | **Tier**: ICP | **F1**: 0.818

Detects inter-agent message misunderstanding:

Issue types: `INTENT_MISMATCH`, `FORMAT_MISMATCH`, `SEMANTIC_AMBIGUITY`, `INCOMPLETE_INFORMATION`, `CONFLICTING_INSTRUCTIONS`

```python
@dataclass
class CommunicationBreakdownResult:
    detected: bool
    breakdown_type: Optional[BreakdownType]
    severity: BreakdownSeverity     # NONE, MINOR, MODERATE, SEVERE
    confidence: float
    intent_alignment: float
    format_match: bool
    explanation: str
    suggested_fix: Optional[str]
```

#### F11: Coordination Failure (`backend/app/detection/coordination.py`)

**Key**: `coordination` | **Tier**: ICP | **F1**: 0.786

Analyzes multi-agent coordination patterns. The `CoordinationAnalyzer` checks 12 issue types:

```python
class CoordinationAnalyzer:
    message_timeout_seconds = 30.0
    max_back_forth_count = 5    # v1.3: raised from 3

    def analyze_coordination(self, messages, agent_ids) -> CoordinationAnalysisResult:
        issues = []
        issues.extend(self._detect_ignored_messages(messages))
        issues.extend(self._detect_information_withholding(messages, agent_ids))
        issues.extend(self._detect_excessive_back_forth(messages))
        issues.extend(self._detect_circular_delegation(messages))
        issues.extend(self._detect_conflicting_instructions(messages))
        issues.extend(self._detect_duplicate_dispatch(messages))
        issues.extend(self._detect_data_corruption_relay(messages))
        issues.extend(self._detect_ordering_violations(messages))
        issues.extend(self._detect_excessive_delegation(messages))
        issues.extend(self._detect_resource_contention(messages))
        issues.extend(self._detect_rapid_instruction_change(messages))
        issues.extend(self._detect_response_delay(messages))
        ...
```

Message model:
```python
@dataclass
class Message:
    from_agent: str
    to_agent: str
    content: str
    timestamp: float
    acknowledged: bool = False
```

---

### MAST Verification Failures (FC3)

#### F12: Output Validation Failure (`backend/app/detection_enterprise/output_validation.py`)

**Tier**: Enterprise | Not yet calibrated

Detects missing or failed output validation checks — format/schema compliance.

#### F13: Quality Gate Bypass (`backend/app/detection_enterprise/quality_gate.py`)

**Tier**: Enterprise | Not yet calibrated

Detects when quality thresholds are skipped or ignored.

#### F14: Completion Misjudgment (`backend/app/detection/completion.py`)

**Version**: 1.7 | **Key**: `completion` | **Tier**: ICP | **F1**: 0.733

Detects incorrect task completion assessment:
- **Explicit completion markers**: "task complete", "finished", "done"
- **Implicit completion** (v1.1): "comprehensive", "fully covered"
- **Quantitative requirement check** (v1.1): "all", "every", "complete" + partial hedges ("most", "90%")
- **JSON completion detection** (v1.3): `"status": "complete"`, `"documented": false`
- **Numeric ratio detection** (v1.3): "8/10", `documentedEndpoints: 8, total: 10`
- **Structural incompleteness** (v1.5): List item count, missing sections
- **Planned/future work**: Indicates task is NOT complete

Issue types: `PREMATURE_COMPLETION`, `PARTIAL_DELIVERY`, `IGNORED_SUBTASKS`, `MISSED_CRITERIA`, `FALSE_COMPLETION`

---

### Extended Detectors

#### Loop Detection (`backend/app/detection/loop.py`)

**Version**: 1.2 | **Key**: `loop` | **Tier**: ICP | **F1**: 0.846

The `MultiLevelLoopDetector` implements 4 detection methods, cheapest-first:

**1. Structural matching** (cost: $0, base confidence: 0.96):
```python
def _structural_match(a, b) -> bool:
    return a.agent_id == b.agent_id and set(a.state_delta.keys()) == set(b.state_delta.keys())
```

**2. Hash collision** (cost: $0, base confidence: 0.80):
```python
def _compute_state_hash(state) -> str:
    return hashlib.sha256(json.dumps(state.state_delta, sort_keys=True).encode()).hexdigest()[:16]
```

**3. Semantic similarity** (cost: ~$0.001, base confidence: 0.70):
Uses embeddings to detect semantically similar but textually different loops.

**4. Semantic clustering** (cost: ~$0.002, base confidence: 0.75):
KMeans on embeddings — detects cluster dominance (≥60% ratio) or cyclic patterns. Requires ≥6 states.

**Confidence calibration formula**:
```
confidence = base * 0.5 + raw_score * 0.25 + length_factor * 0.15 + evidence_factor * 0.10
```
Capped at 0.99, scaled by `confidence_scaling`.

**Anti-false-positive measures**:
- `SUMMARY_WHITELIST_PATTERNS`: "to summarize", "step N of M", "what we've done"
- `PROGRESS_WHITELIST_PATTERNS`: "phase N", "iteration N"
- `_has_meaningful_progress()`: New keys or >2 value changes = not a loop

**Framework-specific thresholds**: `for_framework(framework)` factory method adjusts thresholds.

#### State Corruption (`backend/app/detection/corruption.py`)

**Version**: 1.1 | **Key**: `corruption` | **Tier**: ICP | **F1**: 0.906

The `SemanticCorruptionDetector` checks state transitions for anomalies:

**Detection methods** (called in sequence):
1. `_validate_schema()` — hallucinated keys, type drift, missing fields
2. `_validate_cross_field_consistency()` — start_date > end_date, min > max
3. `_validate_domain_constraints()` — age 0–150, price ≥ 0, email/URL format
4. `_detect_hallucinated_references()` — _id fields with unknown values
5. `_detect_value_copying()` — identical strings in different fields
6. `_detect_suspicious_rapid_changes()` — >20 changes/sec AND >5 fields

**Domain validators**:
```python
domain_validators = {
    "age": lambda v: isinstance(v, (int, float)) and 0 <= v <= 150,
    "price": lambda v: isinstance(v, (int, float)) and v >= 0,
    "percentage": lambda v: isinstance(v, (int, float)) and 0 <= v <= 100,
    "email": lambda v: isinstance(v, str) and bool(email_pattern.match(v)),
    "url": lambda v: isinstance(v, str) and bool(url_pattern.match(v)),
    "phone": lambda v: isinstance(v, str) and len(re.sub(r'\D', '', v)) >= 10,
    "uuid": lambda v: isinstance(v, str) and len(v) == 36 and v.count('-') == 4,
}
```

**Velocity filtering** — high-frequency fields are excluded from anomaly detection:
```python
@dataclass
class VelocityConfig:
    window_seconds: float = 5.0
    max_changes_per_window: int = 10
    high_velocity_fields: List[str] = [
        "counter", "count", "iteration", "step", "progress",
        "timestamp", "updated_at", "last_seen", "version",
    ]
    ignore_velocity_for_types: List[type] = [bool]
```

**Critical fixes from Sprint 9b** (F1 0.362→0.906):
- `_VELOCITY_IMMUNE_ISSUES`: Exempts issue types (e.g., `monotonic_regression`) from velocity suppression — fixed "version" field blocking
- `_flatten_nested_dicts()`: n8n wraps data in `{"json": {...}}` — must flatten before comparison
- Boolean exclusion: `True→False` is not `extreme_magnitude_change` (True=1, False=0 in Python)
- `field_disappeared` threshold: Only flag when 3+ fields vanish simultaneously

**Text-based corruption** (`detect_from_text()`):
Uses `RELATED_TOPICS`, `NARROW_FOCUS_PATTERNS`, and `COMPREHENSIVE_PATTERNS` to detect context corruption in agent outputs.

**Confidence calculation**:
```
raw_score = low*0.1 + medium*0.25 + high*0.4 + critical*0.6
confidence = severity_weight*0.4 + raw_score*0.3 + diversity_factor*0.15 + issue_factor*0.15
```

#### Persona Drift (`backend/app/detection/persona.py`)

**Key**: `persona_drift` | **Tier**: ICP | **F1**: 0.932

Detects deviation from assigned role/personality:
- **Role embedding comparison**: Compares behavior vectors against role definition
- **Role-type thresholds**: Different thresholds per role type

```python
class RoleType(Enum):
    CREATIVE = "creative"       # consistency: 0.55, drift: 0.25
    ANALYTICAL = "analytical"   # consistency: 0.75, drift: 0.12
    ASSISTANT = "assistant"     # consistency: 0.65, drift: 0.18
    SPECIALIST = "specialist"   # consistency: 0.72, drift: 0.14
    CONVERSATIONAL = "conversational"  # consistency: 0.58, drift: 0.22
```

Each role type has `consistency_threshold`, `drift_threshold`, and `flexibility_bonus`.

**Role keyword detection**: Automatic role classification from persona description via `ROLE_KEYWORDS`.

#### Context Overflow (`backend/app/detection/overflow.py`)

**Key**: `overflow` | **Tier**: ICP | **F1**: 0.823

Tracks token usage against context window limits.

```python
class ContextOverflowDetector:
    def __init__(
        self,
        warning_threshold: float = 0.70,   # 70% of context window
        critical_threshold: float = 0.85,   # 85%
        overflow_threshold: float = 0.95,   # 95%
    )
```

Uses `tiktoken` for token counting. Supports all major model context windows.

Severity levels: `SAFE`, `WARNING`, `CRITICAL`, `OVERFLOW`

Result includes:
```python
@dataclass
class OverflowResult:
    severity: OverflowSeverity
    current_tokens: int
    context_window: int
    usage_percent: float
    remaining_tokens: int
    estimated_overflow_in: Optional[int]  # Turns until overflow
    warnings: List[str]
```

#### Prompt Injection (`backend/app/detection/injection.py`)

**Key**: `injection` | **Tier**: ICP | **F1**: 0.927

Pattern-based + embedding-based injection detection.

**Pattern categories** (65+ regex patterns):
- `direct_override` (high): "ignore previous instructions", "disregard all rules"
- `instruction_injection` (high): "new instructions:", "from now on"
- `role_hijack` (medium/high): "you are now a", "pretend to be"
- `constraint_manipulation` (medium): "you can do anything", "no restrictions"
- `safety_bypass` (critical): "override safety", "bypass filters"
- `jailbreak` (critical): "DAN mode", "developer mode", "unlock capabilities"

Result:
```python
@dataclass
class InjectionResult:
    detected: bool
    confidence: float
    attack_type: Optional[str]      # Category from above
    severity: str
    matched_patterns: List[str]     # Which patterns matched
```

Uses SentenceTransformer embeddings for semantic injection detection beyond pattern matching.

#### Hallucination (`backend/app/detection/hallucination.py`)

**Key**: `hallucination` | **Tier**: ICP | **F1**: 0.791

Detects factual inaccuracies using:
- **Grounding score**: Embedding similarity between output and source documents
- **Citation analysis**: Checks `[1]`, `(source: ...)`, `{{cite:...}}` patterns
- **Confidence phrase detection**: "I'm not sure", "I believe" = appropriately uncertain
- **Definitive phrase detection**: "definitely", "100%", "proven fact" = inappropriately confident

```python
class HallucinationDetector:
    grounding_threshold: float = 0.65
    confidence_phrases = ["I'm not sure", "I believe", ...]
    definitive_phrases = ["definitely", "certainly", ...]
```

#### Grounding Failure (`backend/app/detection_enterprise/grounding.py`)

**Key**: `grounding` | **Tier**: ICP | **F1**: 0.704

Source attribution and factual consistency checking.

#### Retrieval Quality (`backend/app/detection_enterprise/retrieval_quality.py`)

**Key**: `retrieval_quality` | **Tier**: Enterprise | **F1**: 0.832

Relevance scoring and coverage analysis for RAG-based agents.

#### Cost Tracking (`backend/app/detection/cost.py`)

**Key**: `cost` | **Tier**: ICP | **F1**: N/A (monitoring, not failure detection)

Token usage and API cost tracking across 25+ models:

```python
LLM_PRICING_2025: Dict[str, ModelPricing] = {
    "claude-sonnet-4-20250514": ModelPricing(3.00, 15.00, 200000, "anthropic"),
    "claude-opus-4-20250514": ModelPricing(15.00, 75.00, 200000, "anthropic"),
    "gpt-4o": ModelPricing(2.50, 10.00, 128000, "openai"),
    "gemini-2.5-pro": ModelPricing(1.25, 10.00, 1000000, "google"),
    # ... 20+ more models
}
```

`CostCalculator` resolves model aliases, calculates per-call cost, and aggregates.

### Framework-Specific Detectors

Six n8n-specific detection types:

| Type | Key | Purpose |
|------|-----|---------|
| Schema Mismatch | `n8n_schema` | Type mismatches between connected node outputs/inputs |
| Cycle Detection | `n8n_cycle` | Graph cycles in workflow connections |
| Complexity | `n8n_complexity` | Excessive nodes, branching, cyclomatic complexity |
| Error Handling | `n8n_error` | Missing error handlers, unprotected AI nodes |
| Resource | `n8n_resource` | Missing maxTokens, unbounded loops, no timeout on HTTP |
| Timeout | `n8n_timeout` | Missing workflow/webhook/AI node timeout |

The n8n workflow validator (`backend/app/detection_enterprise/n8n_workflow_validator.py`) validates against 70+ known n8n node types.

---

## Tiered Detection Architecture

**Source**: `backend/app/detection_enterprise/tiered.py`

### Configuration

```python
@dataclass
class TierConfig:
    rule_confidence_threshold: float = 0.7
    cheap_ai_confidence_threshold: float = 0.8
    expensive_ai_confidence_threshold: float = 0.85
    gray_zone_lower: float = 0.35
    gray_zone_upper: float = 0.65
    enable_cheap_ai: bool = True
    enable_expensive_ai: bool = True
    enable_human_escalation: bool = True
    track_costs: bool = True
```

### Escalation Flow

```
                    ┌─────────────┐
                    │  Tier 1     │ Rule-Based ($0)
                    │  Patterns   │
                    └──────┬──────┘
                           │
               confidence >= 0.7 AND not in gray zone?
              ╱                          ╲
         YES (return)              NO (escalate)
                                         │
                    ┌─────────────┐       │
                    │  Tier 2     │◄──────┘
                    │  Cheap AI   │ ($0.01)
                    └──────┬──────┘
                           │
               confidence >= 0.8 AND not in gray zone?
              ╱                          ╲
         YES (return)              NO (escalate)
                                         │
                    ┌─────────────┐       │
                    │  Tier 3     │◄──────┘
                    │  Expensive  │ ($0.50)
                    │  AI (LLM)  │
                    └──────┬──────┘
                           │
               confidence >= 0.85?
              ╱                    ╲
         YES (return)        NO (escalate)
                                   │
                    ┌─────────────┐│
                    │  Tier 4     │◄┘
                    │  Human      │ ($50)
                    │  Review     │
                    └─────────────┘
```

### Gray Zone

Confidence in [0.35, 0.65] is "uncertain" — always escalates regardless of threshold.

### Cost Model

```python
tier_costs = {
    DetectionTier.RULE_BASED: 0.0,
    DetectionTier.CHEAP_AI: 0.01,
    DetectionTier.EXPENSIVE_AI: 0.50,
    DetectionTier.HUMAN_REVIEW: 50.0,
}
```

### `_no_downgrade` Set

Detectors with high rule-based precision must not have confidence lowered by LLM judge:

```python
_no_downgrade = {"coordination", "grounding", ...}
```

For these detectors, LLM judge can only boost confidence.

### TieredResult

```python
@dataclass
class TieredResult:
    detected: bool
    confidence: float
    severity: str
    final_tier: DetectionTier
    tiers_used: List[DetectionTier]
    escalation_reasons: List[EscalationReason]
    detection_type: str
    tier_results: Dict[str, Any]
    estimated_cost: float
    needs_human_review: bool
    explanation: str
```

---

## Embedding System

**Source**: `backend/app/core/embeddings.py`

### EmbeddingService (Primary)

Thread-safe singleton for E5-large-instruct embeddings.

| Property | Value |
|----------|-------|
| Model | `intfloat/e5-large-instruct` |
| Dimensions | 1024 |
| Device | CUDA if available, else CPU |
| Prefixes | "query:" (search), "passage:" (documents) |
| Cache | LRU in-memory (5000 entries) + disk (2GB) |
| Cache key | MD5(text + is_query + normalize + model_name) |

```python
class EmbeddingService:
    def encode(texts, is_query=False, batch_size=32, normalize=True) -> np.ndarray
    def encode_query(query, normalize=True) -> np.ndarray
    def encode_passages(passages, batch_size=32) -> np.ndarray
    def similarity(embedding1, embedding2) -> float
    def batch_similarity(query_embedding, passage_embeddings) -> np.ndarray
    def compute_contrastive_score(anchor, positive, negative, margin=0.2) -> Dict
    def batch_encode_chunked(texts, max_chars_per_text=8000, batch_size=16) -> np.ndarray
    def encode_cached(text, is_query=False) -> np.ndarray
    def encode_batch_cached(texts, batch_size=32) -> np.ndarray
```

### FastEmbeddingService

Low-latency runtime similarity.

| Property | Value |
|----------|-------|
| Model | `nomic-ai/nomic-embed-text-v1.5` |
| Dimensions | 768 |
| Speed | ~2x faster than E5 |
| Prefixes | "search_query:", "search_document:" |
| Use case | Runtime comparisons only (incompatible with stored 1024d embeddings) |

```python
class FastEmbeddingService:
    def encode_query(query, normalize=True) -> np.ndarray
    def encode_document(document, normalize=True) -> np.ndarray
    def quick_similarity(text1, text2) -> float
    def batch_similarity(query, documents) -> np.ndarray
```

### EmbeddingEnsemble

Mode-specific routing to specialized providers:

```python
MODE_EMBEDDING_MAP = {
    "F6": "openai",    "F8": "openai",     # Semantic derailment → text-embedding-3-large (3072d)
    "F4": "cohere",    "F7": "cohere",     # Context/clarification → embed-english-v3 (1024d)
    "F1": "voyage",    "F11": "voyage",    # Code understanding → voyage-large-2 (1024d)
    "F12": "e5",       "F13": "e5",        # Verification → E5-large-instruct (1024d)
    "F14": "e5",                            # Default → E5
}
```

```python
class EmbeddingEnsemble:
    def encode(text, mode=None, provider=None) -> np.ndarray
    def encode_full_ensemble(text) -> np.ndarray     # Concatenated (up to 6144d)
    def get_provider_for_mode(mode) -> str
    def compute_contrastive_score(anchor, positive, negative, mode=None) -> Dict
```

---

## LLM Judge System

**Source**: `backend/app/detection/llm_judge/`

### Architecture

```
judge.py          — MASTLLMJudge main class (evaluate, cache, cost tracking)
_models.py        — Multi-provider model registry with tier routing
_prompts.py       — MAST failure mode definitions, CoT templates
_dataclasses.py   — JudgmentResult, JudgeCostTracker
_enums.py         — MASTFailureMode enum
detector.py       — FullLLMDetector wrapper
```

### Model Routing by Tier

```python
# Tier 1 — Low-stakes (F3, F7, F11, F12)
primary: gemini-flash-lite ($0.10/$0.40 per 1M)    # 87% cheaper
fallback: haiku-4.5 ($1.00/$5.00 per 1M)

# Tier 2 — Default moderate complexity (F1, F2, F4, F5, F10, F13)
primary: claude-sonnet-4 ($3/$15 per 1M)            # 97.1% accuracy
cost-opt: o3 ($2/$8 per 1M)                          # 33% cheaper

# Tier 3 — High-stakes complex reasoning (F6, F8, F9, F14)
primary: claude-sonnet-4-thinking ($3/$15 + $10/1M thinking)
thinking_budget: 32K tokens
```

### Judgment Flow

```python
class MASTLLMJudge:
    def evaluate(
        self,
        failure_mode: MASTFailureMode,
        task: str,
        trace_summary: str,
        key_events: Optional[List[str]] = None,
        full_conversation: str = "",
        agent_interactions: Optional[List[str]] = None,
        coordination_events: Optional[List[str]] = None,
        framework: str = "",
        timeout: float = 60.0,
    ) -> JudgmentResult
```

**Process:**
1. Check SHA256-based cache (LRU, max 1000 entries, evicts oldest 10% when full)
2. Retrieve RAG few-shot examples from pgvector (k=3, similarity ≥ 0.65)
3. Load domain knowledge for modes F3, F4, F9
4. Build prompt (framework context + failure definition + RAG examples + CoT for F6/F8 + conversation up to 150K chars)
5. Route to provider (Claude/OpenAI/Gemini based on model_key)
6. Parse response with 4 fallback strategies:
   - JSON in code block
   - JSON with verdict field
   - Regex extraction of verdict/confidence/reasoning
   - Keyword fallback ("VERDICT: YES")
7. Calculate cost (input + output + thinking tokens)
8. Cache result, record in cost tracker

### JudgmentResult

```python
@dataclass
class JudgmentResult:
    failure_mode: MASTFailureMode
    verdict: str                # "YES", "NO", "UNCERTAIN"
    confidence: float           # 0.0–1.0
    reasoning: str              # One-paragraph explanation
    raw_response: str
    model_used: str
    tokens_used: int
    cost_usd: float
    cached: bool = False
    latency_ms: int = 0
    provider: str = "anthropic"
```

### Cost Tracking

```python
@dataclass
class JudgeCostTracker:
    total_calls: int
    cached_calls: int
    total_tokens: int
    total_cost_usd: float
    # Per-tier
    tier1_calls: int; tier1_cost: float
    tier2_calls: int; tier2_cost: float
    tier3_calls: int; tier3_cost: float
    # Per-provider
    anthropic_calls: int; anthropic_cost: float
    google_calls: int; google_cost: float
    openai_calls: int; openai_cost: float
```

---

## Calibration System

**Source**: `backend/app/detection_enterprise/calibrate.py`

### Pipeline

```
Golden Dataset → Per-Detector Adapter → Run Detector → Grid Search Thresholds → Report
```

### Grid Search

Thresholds: `[0.10, 0.15, 0.20, 0.25, ..., 0.85, 0.90]` (17 values)

For each threshold, compute TP/TN/FP/FN → precision/recall/F1 → select threshold with max F1.

### Golden Dataset Format

```python
@dataclass
class GoldenDatasetEntry:
    id: str
    detection_type: DetectionType
    input_data: Dict[str, Any]
    expected_detected: bool
    expected_confidence_min: float = 0.0
    expected_confidence_max: float = 1.0
    description: str = ""
    source: str = "manual"          # "manual", "generated", "augmented"
    tags: List[str] = field(default_factory=list)
    difficulty: str = "medium"      # "easy", "medium", "hard"
```

OTEL-format golden traces are in `backend/fixtures/golden/golden_traces.jsonl` (1067 traces).

### CalibrationResult

```python
@dataclass
class CalibrationResult:
    detection_type: str
    optimal_threshold: float
    precision: float
    recall: float
    f1: float
    sample_count: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    ece: float                      # Expected Calibration Error
    f1_ci_lower: float              # Confidence interval
    f1_ci_upper: float
```

### Error Analysis

`SamplePrediction` classifies every sample:
```python
@dataclass
class SamplePrediction:
    entry_id: str
    detection_type: str
    expected: bool
    predicted: bool                 # After threshold
    raw_detected: bool              # Before threshold
    confidence: float
    threshold_used: float
    classification: str             # "TP", "TN", "FP", "FN"
    description: str
    tags: List[str]
    difficulty: str
    input_data_summary: str
```

### Validation Framework (`backend/app/detection/validation.py`)

```python
class DetectionValidator:
    def add_labeled_sample(sample: LabeledSample) -> None
    def add_prediction(prediction: DetectionPrediction) -> None
    def validate(detection_type=None) -> ValidationMetrics
    def validate_by_type() -> Dict[DetectionType, ValidationMetrics]
    def compute_calibration(num_bins=10) -> List[CalibrationResult]
    def compute_ece(num_bins=10) -> float
    def find_optimal_threshold(detection_type, metric='f1') -> Tuple[float, float]
    def get_misclassified(detection_type) -> Dict[str, Dict]
    def summary() -> Dict[str, Any]
```

---

## Self-Healing Pipeline

**Source**: `backend/app/healing/`

### 5-Stage Architecture

```
Detection → ANALYZING → GENERATING_FIX → APPLYING_FIX → VALIDATING → SUCCESS/FAILED
                                                              ↓
                                                         ROLLBACK (if failed)
```

### Stage 1: Analysis (`analyzer.py`)

```python
class FailureAnalyzer:
    def analyze(detection, trace=None) -> FailureSignature
```

Maps detection type to `FailureCategory` (20 categories) via pattern matching. Produces:

```python
@dataclass
class FailureSignature:
    category: FailureCategory
    pattern: str
    confidence: float
    indicators: List[str]
    root_cause: Optional[str]
    affected_components: List[str]
```

### Stage 2: Fix Generation (`fixes/`)

Plugin-based generator system:

```python
class BaseFixGenerator(ABC):
    @abstractmethod
    def can_handle(self, detection_type: str) -> bool
    @abstractmethod
    def generate_fixes(self, detection, context) -> List[FixSuggestion]

class FixGenerator:
    def register(generator: BaseFixGenerator) -> None
    def generate_fixes(detection, context=None) -> List[FixSuggestion]   # Sorted by confidence
```

**23 fix types** across categories:
- Loop: `RETRY_LIMIT`, `EXPONENTIAL_BACKOFF`, `CIRCUIT_BREAKER`
- Corruption: `STATE_VALIDATION`, `SCHEMA_ENFORCEMENT`, `INPUT_SANITIZATION`, `CHECKPOINT_RECOVERY`
- Persona: `PROMPT_REINFORCEMENT`, `ROLE_BOUNDARY`
- Deadlock: `TIMEOUT_ADDITION`, `PRIORITY_ADJUSTMENT`, `ASYNC_HANDOFF`
- Hallucination: `FACT_CHECKING`, `SOURCE_GROUNDING`, `CONFIDENCE_CALIBRATION`
- Injection: `INPUT_FILTERING`, `SAFETY_BOUNDARY`, `PERMISSION_GATE`
- Overflow: `CONTEXT_PRUNING`, `SUMMARIZATION`, `WINDOW_MANAGEMENT`

Fix confidence levels with effectiveness metrics:
```python
class ReinforcementLevel:
    LIGHT       # 65% effectiveness, 2% regression risk
    MODERATE    # 80% effectiveness, 4% regression risk
    AGGRESSIVE  # 92% effectiveness, 8% regression risk
```

```python
@dataclass
class FixSuggestion:
    id: str
    detection_id: str
    detection_type: str
    fix_type: FixType
    confidence: FixConfidence       # HIGH, MEDIUM, LOW
    title: str
    description: str
    rationale: str
    code_changes: List[CodeChange]
    estimated_impact: str
    breaking_changes: bool
    requires_testing: bool
```

### Stage 3: Application (`applicator.py`)

17 `ApplicatorStrategy` implementations, one per failure category:

```python
class FixApplicator:
    def apply(fix_suggestion, workflow_config, failure_category) -> AppliedFix
    def rollback(applied_fix, current_config) -> Dict[str, Any]
```

```python
@dataclass
class AppliedFix:
    fix_id: str
    fix_type: str
    applied_at: datetime
    target_component: str
    original_state: Dict[str, Any]    # For rollback
    modified_state: Dict[str, Any]
    rollback_available: bool = True
```

### Stage 4: Validation (`validator.py`)

18 `ValidationStrategy` implementations:

```python
class FixValidator:
    async def validate(applied_fix, failure_category, workflow_runner=None, test_input=None) -> List[ValidationResult]
```

### Stage 5: Verification (`verification.py`)

Two verification levels:

```python
class VerificationOrchestrator:
    async def verify_level1(detection_type, original_confidence, original_state, applied_fixes) -> VerificationResult
    # Level 1: Config-based checks (no execution)

    async def verify_level2(detection_type, original_confidence, original_state, applied_fixes, n8n_client, workflow_id) -> VerificationResult
    # Level 2: Execution-based (real n8n run + re-detection)
```

### Engine (`engine.py`)

```python
class SelfHealingEngine:
    def __init__(
        self,
        auto_apply: bool = False,
        max_fix_attempts: int = 3,
        validation_timeout: float = 60.0,
        healing_config: Optional[HealingConfig] = None,
    )

    async def heal(detection, workflow_config, trace=None, ...) -> HealingResult
    async def heal_n8n_workflow(detection, workflow_id, n8n_client, ...) -> HealingResult
    def approve_and_apply(healing_id, selected_fix_ids) -> HealingResult
    def rollback(healing_id) -> Dict[str, Any]
```

### Safety Mechanisms

```python
@dataclass
class HealingConfig:
    verification_timeout: float = 60.0
    confidence_fail_factor: float = 0.5
    partial_improvement_factor: float = 0.7
    improvement_threshold: float = 0.5
    default_confidence_threshold: float = 0.7
    max_fixes_per_hour: int = 5
    cooldown_after_rollback_seconds: int = 300
    max_consecutive_failures: int = 3
    healing_loop_threshold: int = 5
    healing_loop_window_minutes: int = 60
```

Safety features:
1. **Per-workflow locking**: `_get_workflow_lock(workflow_id)` prevents concurrent healing
2. **Checkpoint/rollback**: Every `AppliedFix` stores `original_state` for rollback
3. **Rate limiting**: `AutoApplyService.check_rate_limit()` enforces `max_fixes_per_hour`
4. **Approval policies**: Non-auto-apply returns `HealingStatus.PENDING`
5. **Git backup**: `GitBackupService` stores workflow versions before modification
6. **Fix risk levels**: `SAFE` (config-only), `MEDIUM` (adds guardrails), `DANGEROUS` (alters logic)

---

## Storage Layer

**Source**: `backend/app/storage/models.py`

### Core Models

**Tenant** (Multi-tenancy root):
```python
class Tenant(Base):
    id: UUID (pk)
    name: String(255)
    api_key_hash: String(255)
    clerk_org_id: String(255)       # SSO integration
    settings: JSONB
    plan: String(20)                # "free", "pro", "enterprise"
    stripe_customer_id: String(255)
    span_limit: Integer             # Default 10,000
    # relationships: traces, detections, users, api_keys
```

**User**:
```python
class User(Base):
    id: UUID (pk)
    clerk_user_id: String(255)
    google_user_id: String(255)     # Google OAuth
    tenant_id: UUID (fk → Tenant)
    email: String(255)
    role: String(50)                # "member", "admin"
```

**Trace**:
```python
class Trace(Base):
    id: UUID (pk)
    tenant_id: UUID (fk → Tenant)
    session_id: String(64)
    parent_trace_id: UUID           # Nested traces
    framework: String(32)           # "langgraph", "crewai", "autogen", "n8n"
    status: String(32)              # "running", "completed", "failed"
    total_tokens: Integer
    total_cost_cents: Integer
    is_conversation: Boolean
    # relationships: states, detections, conversation_turns
```

**State** (Agent execution snapshot):
```python
class State(Base):
    id: UUID (pk)
    trace_id: UUID (fk → Trace)
    tenant_id: UUID (fk → Tenant)
    sequence_num: Integer           # Order in trace
    agent_id: String(128)           # Node/agent name
    state_delta: JSONB              # Full state diff
    state_hash: String(64)          # SHA256[:16]
    prompt_hash: String(64)
    response_redacted: Text         # Redacted LLM output
    tool_calls: JSONB               # Tool invocations
    embedding: Vector(1024)         # pgvector for semantic search
    token_count: Integer
    latency_ms: Integer
    # unique constraint: (trace_id, sequence_num)
    # indexes: trace_id, tenant_id, agent_id, created_at
```

**Detection**:
```python
class Detection(Base):
    id: UUID (pk)
    tenant_id: UUID (fk → Tenant)
    trace_id: UUID (fk → Trace)
    state_id: UUID (fk → State)
    detection_type: String(32)      # "infinite_loop", "state_corruption", etc.
    confidence: Integer             # 0-100
    method: String(32)              # "hash", "state_delta", "embedding", "llm"
    details: JSONB                  # Detection-specific metadata
    validated: Boolean
    false_positive: Boolean         # User feedback
    # relationship: feedback
```

**DetectionFeedback** (for calibration):
```python
class DetectionFeedback(Base):
    detection_id: UUID (fk → Detection, unique)
    is_correct: Boolean
    feedback_type: String(32)       # "true_positive", "false_positive", etc.
    severity_rating: Integer        # 1-5
```

**GoldenDatasetEntryModel** (synthetic calibration samples):
```python
class GoldenDatasetEntryModel(Base):
    entry_key: String(255) (unique)
    detection_type: String(64)
    input_data: JSONB
    expected_detected: Boolean
    source: String(64)              # "manual", "generated", "augmented"
    difficulty: String(16)          # "easy", "medium", "hard"
    split: String(16)               # "train", "val", "test"
    human_verified: Boolean
```

**ImportJob** (batch ingestion tracking):
```python
class ImportJob(Base):
    status: String(20)              # "pending", "processing", "completed", "failed"
    format: String(50)              # "json", "jsonl", "otel", "n8n"
    records_total: Integer
    records_processed: Integer
    traces_created: Integer
    detections_found: Integer
```

### pgvector Integration

The `State.embedding` column uses `Vector(1024)` from pgvector for semantic search:
- Embeddings stored with each state snapshot
- Enables similarity search for loop detection and RAG retrieval
- Indexed for efficient nearest-neighbor queries

---

## API Layer

**Source**: `backend/app/api/v1/`

### Detection Endpoints (`detections.py`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/detections` | List detections with filtering (type, confidence, date range) |
| GET | `/detections/{id}` | Get single detection with full details |
| POST | `/detections/{id}/validate` | Submit human validation (true/false positive) |

Pagination: `page`, `per_page` (max 100). Filtering: `detection_type`, `validated`, `confidence_min/max`, `trace_id`, `date_from/to`.

Response includes computed fields: `explanation`, `business_impact`, `suggested_action`, `confidence_tier` ("HIGH"/"LIKELY"/"POSSIBLE"/"LOW").

### Trace Endpoints (`traces.py`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/traces/ingest` | Ingest a new trace |
| GET | `/traces/{id}` | Get trace details |
| GET | `/traces/{id}/states` | Get all states for a trace |

### Healing Endpoints (`healing.py`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/healing/trigger` | Start healing for a detection |
| GET | `/healing/{id}/status` | Check healing progress |
| POST | `/healing/{id}/approve` | Approve pending fixes |
| POST | `/healing/{id}/rollback` | Rollback applied fixes |
| GET | `/healing/records` | List healing history |
| POST | `/healing/n8n/connect` | Connect n8n instance |
| POST | `/healing/n8n/{workflow_id}/fix` | Apply n8n fix |
| POST | `/healing/n8n/{workflow_id}/promote` | Promote staged fix |
| POST | `/healing/n8n/{workflow_id}/reject` | Reject staged fix |
| POST | `/healing/{id}/verify` | Verify fix success |

### Auth

All endpoints use dependency injection:
- `tenant_id = Depends(get_current_tenant)` — extracted from JWT or API key
- `db = Depends(get_db)` — async database session
- Row-level security via `set_tenant_context(db, tenant_id)`

---

## SDK & CLI

### Python SDK (`packages/pisama-core`, `packages/agent-sdk`)

Framework adapters for instrumenting agent systems:

| Framework | Adapter | OTEL Attributes |
|-----------|---------|-----------------|
| LangGraph | `LangGraphAdapter` | `langgraph.node.name`, `langgraph.state` |
| AutoGen | `AutoGenAdapter` | `autogen.agent.name` |
| CrewAI | `CrewAIAdapter` | `crewai.agent.role`, `crewai.state` |
| n8n | `N8nAdapter` | Via webhook ingestion |

Core SDK provides:
- Trace instrumentation API
- Detection result types
- Automatic OTEL span generation with `gen_ai.*` semantic conventions

### CLI (`cli/`)

Click-based CLI with MCP server support:
- Trace ingestion commands
- Detection querying
- Healing trigger/status
- Configuration management

---

## Testing Infrastructure

### Organization

```
backend/tests/
├── unit/                      # Individual component tests
├── integration/               # Multi-component tests
├── detection_enterprise/      # Enterprise-tier detector tests
├── e2e/                       # End-to-end pipeline tests
└── fixtures/
    └── golden/                # Golden dataset files
        ├── manifest.json      # Dataset metadata
        └── golden_traces.jsonl # 1067 OTEL traces
```

### Golden Dataset Testing

Each detector has a golden dataset adapter that maps `GoldenDatasetEntry` to detector-specific inputs. The calibration pipeline (`calibrate.py`) runs all detectors against their golden entries and reports F1/P/R.

### Test Commands

```bash
cd backend
pytest tests/                          # All tests
pytest tests/ -k "test_loop"           # Specific detector
pytest tests/detection_enterprise/     # Enterprise tests
pytest tests/ -v --tb=short            # Verbose
```

### E2E Testing

See `docs/E2E_TESTING_STRATEGY.md` for the full end-to-end testing approach.

Frontend E2E: Playwright 1.41 in `frontend/tests/e2e/`.

---

## Appendix: Sprint 9c Accuracy Summary

| Detector | F1 | Precision | Recall | Status |
|----------|-----|-----------|--------|--------|
| persona_drift | 0.932 | 0.921 | 0.944 | Production |
| injection | 0.927 | 0.983 | 0.877 | Production |
| corruption | 0.906 | 0.955 | 0.863 | Production |
| withholding | 0.874 | 0.857 | 0.891 | Production |
| context | 0.868 | 0.842 | 0.896 | Production |
| loop | 0.846 | 0.829 | 0.863 | Production |
| retrieval_quality | 0.832 | 0.721 | 0.984 | Production |
| overflow | 0.823 | 1.000 | 0.699 | Production |
| derailment | 0.820 | 0.702 | 0.985 | Production |
| communication | 0.818 | 0.795 | 0.842 | Production |
| workflow | 0.808 | 0.843 | 0.776 | Production |
| hallucination | 0.791 | 0.762 | 0.822 | Beta |
| coordination | 0.786 | 0.768 | 0.805 | Beta |
| decomposition | 0.772 | 0.753 | 0.791 | Beta |
| completion | 0.733 | 0.718 | 0.749 | Beta |
| specification | 0.717 | 0.701 | 0.734 | Beta |
| grounding | 0.704 | 0.689 | 0.720 | Beta |
