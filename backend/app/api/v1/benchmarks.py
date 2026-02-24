"""Benchmark results API endpoints.

Provides transparent detection accuracy metrics for the MAST failure taxonomy.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


class FailureMode(BaseModel):
    """Individual failure mode benchmark result."""
    code: str
    name: str
    category: str  # content, structural, rag
    tier: int  # 1, 2, or 3
    detection_rate: Optional[float]  # percentage, None if TBD
    detected: int
    total: int
    description: str
    improvement_before: Optional[float] = None
    improvement_after: Optional[float] = None


class BenchmarkSummary(BaseModel):
    """Overall benchmark summary."""
    overall_detection_rate: float
    total_traces: int
    detected_traces: int
    failure_modes_count: int
    high_confidence_modes: int  # >95% detection
    improvement_from_baseline: float
    baseline_rate: float
    last_updated: str


class MethodologyInfo(BaseModel):
    """Benchmark methodology information."""
    dataset_size: str
    trace_count: int
    sources: list[str]
    frameworks: list[str]
    detection_approaches: list[str]


class BenchmarkResponse(BaseModel):
    """Complete benchmark response."""
    summary: BenchmarkSummary
    failure_modes: list[FailureMode]
    methodology: MethodologyInfo


# Benchmark data from DETECTION_REPORT.md
BENCHMARK_FAILURE_MODES = [
    # Tier 1: High Detection (>95%)
    FailureMode(code="F1", name="Specification Mismatch", category="content", tier=1, detection_rate=98.0, detected=49, total=50, description="Output doesn't match what was requested", improvement_before=0, improvement_after=98),
    FailureMode(code="F2", name="Poor Task Decomposition", category="structural", tier=1, detection_rate=100.0, detected=50, total=50, description="Tasks broken down incorrectly", improvement_before=10, improvement_after=100),
    FailureMode(code="F5", name="Flawed Workflow Design", category="structural", tier=1, detection_rate=100.0, detected=150, total=150, description="Workflow has structural issues"),
    FailureMode(code="F6", name="Task Derailment", category="content", tier=1, detection_rate=100.0, detected=50, total=50, description="Agent goes off-topic"),
    FailureMode(code="F7", name="Context Neglect", category="content", tier=1, detection_rate=100.0, detected=50, total=50, description="Agent ignores provided context", improvement_before=10, improvement_after=100),
    FailureMode(code="F8", name="Information Withholding", category="content", tier=1, detection_rate=100.0, detected=50, total=50, description="Agent omits critical info"),
    FailureMode(code="F11", name="Coordination Failure", category="structural", tier=1, detection_rate=100.0, detected=150, total=150, description="Agents fail to coordinate"),
    FailureMode(code="F13", name="Quality Gate Bypass", category="content", tier=1, detection_rate=96.0, detected=48, total=50, description="Skips quality checks"),

    # Tier 2: Good Detection (60-95%)
    FailureMode(code="F14", name="Completion Misjudgment", category="content", tier=2, detection_rate=84.0, detected=42, total=50, description="Declares done when incomplete", improvement_before=6, improvement_after=84),
    FailureMode(code="F3", name="Resource Misallocation", category="structural", tier=2, detection_rate=66.7, detected=100, total=150, description="Compute/time allocated poorly"),
    FailureMode(code="F4", name="Inadequate Tool Provision", category="structural", tier=2, detection_rate=66.7, detected=100, total=150, description="Wrong tools used for task"),
    FailureMode(code="F9", name="Role Usurpation", category="structural", tier=2, detection_rate=66.7, detected=100, total=150, description="Agent exceeds its role boundaries"),
    FailureMode(code="F12", name="Output Validation Failure", category="structural", tier=2, detection_rate=66.7, detected=100, total=150, description="Output not validated properly"),
    FailureMode(code="F10", name="Communication Breakdown", category="content", tier=2, detection_rate=64.0, detected=32, total=50, description="Inter-agent comms fail"),

    # Tier 3: RAG/Grounding (New)
    FailureMode(code="F15", name="Grounding Failure", category="rag", tier=3, detection_rate=None, detected=0, total=0, description="Claims not supported by sources"),
    FailureMode(code="F16", name="Retrieval Quality Failure", category="rag", tier=3, detection_rate=None, detected=0, total=0, description="Retrieves wrong/irrelevant docs"),
]

METHODOLOGY = MethodologyInfo(
    dataset_size="207MB",
    trace_count=20575,
    sources=["HuggingFace", "GitHub", "Anthropic", "Research Papers"],
    frameworks=["LangChain", "LangGraph", "AutoGen", "CrewAI", "OpenAI", "Anthropic"],
    detection_approaches=[
        "Pattern matching for structural failures",
        "Semantic analysis using sentence embeddings",
        "Intent parsing for specification alignment",
        "Marker detection for completion tracking",
    ],
)


@router.get("", response_model=BenchmarkResponse)
async def get_benchmarks():
    """Get complete benchmark results.

    Returns detection accuracy metrics for all 16 MAST failure modes,
    including methodology transparency and improvement history.
    """
    # Calculate summary stats
    f1_f14 = [m for m in BENCHMARK_FAILURE_MODES if m.tier in (1, 2)]
    total_detected = sum(m.detected for m in f1_f14)
    total_traces = sum(m.total for m in f1_f14)
    high_confidence = len([m for m in BENCHMARK_FAILURE_MODES if m.detection_rate and m.detection_rate >= 95])

    summary = BenchmarkSummary(
        overall_detection_rate=82.4,
        total_traces=total_traces,
        detected_traces=total_detected,
        failure_modes_count=len(BENCHMARK_FAILURE_MODES),
        high_confidence_modes=high_confidence,
        improvement_from_baseline=13.7,
        baseline_rate=68.7,
        last_updated=datetime.now().strftime("%Y-%m-%d"),
    )

    return BenchmarkResponse(
        summary=summary,
        failure_modes=BENCHMARK_FAILURE_MODES,
        methodology=METHODOLOGY,
    )


@router.get("/summary", response_model=BenchmarkSummary)
async def get_benchmark_summary():
    """Get benchmark summary only (lighter endpoint)."""
    f1_f14 = [m for m in BENCHMARK_FAILURE_MODES if m.tier in (1, 2)]
    total_detected = sum(m.detected for m in f1_f14)
    total_traces = sum(m.total for m in f1_f14)
    high_confidence = len([m for m in BENCHMARK_FAILURE_MODES if m.detection_rate and m.detection_rate >= 95])

    return BenchmarkSummary(
        overall_detection_rate=82.4,
        total_traces=total_traces,
        detected_traces=total_detected,
        failure_modes_count=len(BENCHMARK_FAILURE_MODES),
        high_confidence_modes=high_confidence,
        improvement_from_baseline=13.7,
        baseline_rate=68.7,
        last_updated=datetime.now().strftime("%Y-%m-%d"),
    )


@router.get("/modes", response_model=list[FailureMode])
async def get_failure_modes(
    tier: Optional[int] = None,
    category: Optional[str] = None,
):
    """Get failure modes, optionally filtered by tier or category."""
    modes = BENCHMARK_FAILURE_MODES

    if tier is not None:
        modes = [m for m in modes if m.tier == tier]

    if category is not None:
        modes = [m for m in modes if m.category == category]

    return modes


@router.get("/methodology", response_model=MethodologyInfo)
async def get_methodology():
    """Get benchmark methodology information."""
    return METHODOLOGY
