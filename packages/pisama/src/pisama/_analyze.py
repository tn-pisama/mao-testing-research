"""High-level analyze API wrapping the DetectionOrchestrator."""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from pisama_core.traces.models import Trace

from pisama._loader import load_trace


@dataclass
class Issue:
    """A single detected issue."""

    type: str
    summary: str
    severity: int
    confidence: float
    evidence: list[dict[str, Any]]
    recommendation: Optional[str]


@dataclass
class AnalyzeResult:
    """Result of running all detectors on a trace."""

    issues: list[Issue]
    trace_id: str
    detectors_run: int
    execution_time_ms: float

    @property
    def has_issues(self) -> bool:
        """Whether any issues were detected."""
        return len(self.issues) > 0

    @property
    def critical_issues(self) -> list[Issue]:
        """Issues with severity >= 60."""
        return [i for i in self.issues if i.severity >= 60]


def analyze(input_data: Union[str, dict[str, Any], Trace]) -> AnalyzeResult:
    """Analyze a trace for multi-agent failures.

    Synchronous wrapper around async_analyze(). Handles the case where an
    event loop is already running (e.g. Jupyter notebooks) by spawning a
    background thread.

    Args:
        input_data: A file path, JSON string, dict, or Trace object.

    Returns:
        AnalyzeResult with detected issues.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # Already inside an event loop (Jupyter, async REPL, etc.).
        # Run in a new thread with its own loop.
        result_container: list[Union[AnalyzeResult, BaseException]] = []

        def _run() -> None:
            try:
                result_container.append(asyncio.run(async_analyze(input_data)))
            except BaseException as exc:
                result_container.append(exc)

        thread = threading.Thread(target=_run)
        thread.start()
        thread.join()

        if isinstance(result_container[0], BaseException):
            raise result_container[0]
        return result_container[0]

    return asyncio.run(async_analyze(input_data))


async def async_analyze(
    input_data: Union[str, dict[str, Any], Trace],
) -> AnalyzeResult:
    """Analyze a trace for multi-agent failures (async).

    Args:
        input_data: A file path, JSON string, dict, or Trace object.

    Returns:
        AnalyzeResult with detected issues.
    """
    start = time.perf_counter()

    trace = load_trace(input_data)

    # Import here to trigger detector auto-registration on first use
    from pisama_core.detection.detectors import __all__ as _detectors_loaded  # noqa: F401
    from pisama_core.detection.orchestrator import DetectionOrchestrator

    orchestrator = DetectionOrchestrator()
    analysis = await orchestrator.analyze(trace)

    issues = _convert_issues(analysis)
    elapsed_ms = (time.perf_counter() - start) * 1000

    return AnalyzeResult(
        issues=issues,
        trace_id=trace.trace_id,
        detectors_run=analysis.total_detectors_run,
        execution_time_ms=elapsed_ms,
    )


def _convert_issues(
    analysis: Any,
) -> list[Issue]:
    """Convert DetectionResult objects into Issue dataclasses."""
    issues: list[Issue] = []
    for result in analysis.detection_results:
        if not result.detected:
            continue
        rec_text: Optional[str] = None
        if result.recommendation is not None:
            rec_text = result.recommendation.instruction
        issues.append(
            Issue(
                type=result.detector_name,
                summary=result.summary,
                severity=result.severity,
                confidence=result.confidence,
                evidence=[e.to_dict() for e in result.evidence],
                recommendation=rec_text,
            )
        )
    return issues
