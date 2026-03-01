"""Agent Forensics Diagnose API endpoint (ICP tier).

Provides the "Why did this fail?" entry point using ICP-tier detection
(no enterprise features required). Accepts raw trace content in various
formats, runs all available detectors, and returns root cause analysis.

This is the free-tier equivalent of the enterprise diagnose endpoint,
using pattern-based and turn-aware detectors instead of ML/LLM-based ones.
"""

import logging
import time
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas import (
    DiagnoseRequest,
    DiagnoseResponse,
    DiagnoseDetectionResult,
    DiagnoseQuickCheckResponse,
)
from app.ingestion.importers import import_trace, detect_format
from app.ingestion.universal_trace import UniversalTrace, SpanType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnose", tags=["diagnose"])


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

_FAILURE_MODE_TITLES = {
    "F1": "Specification Mismatch",
    "F2": "Poor Task Decomposition",
    "F3": "Resource Misallocation",
    "F4": "Tool Provision Failure",
    "F5": "Flawed Workflow",
    "F6": "Task Derailment",
    "F7": "Context Neglect",
    "F8": "Information Withholding",
    "F9": "Role Usurpation",
    "F10": "Communication Breakdown",
    "F11": "Coordination Failure",
    "F12": "Output Validation Failure",
    "F13": "Quality Gate Bypass",
    "F14": "Completion Misjudgment",
    "F15": "Termination Awareness",
    "F16": "Reasoning-Action Mismatch",
    "F17": "Clarification Request Failure",
}


def _spans_to_turn_snapshots(trace: UniversalTrace):
    """Convert UniversalTrace spans into TurnSnapshots for turn-aware detection."""
    from app.detection.turn_aware import TurnSnapshot

    snapshots: list = []
    for i, span in enumerate(trace.spans):
        # Determine participant type from span metadata
        if span.span_type == SpanType.TOOL_CALL:
            participant_type = "tool"
        elif span.span_type == SpanType.LLM_CALL:
            participant_type = "agent"
        elif span.span_type == SpanType.AGENT:
            participant_type = "agent"
        elif span.span_type == SpanType.HANDOFF:
            participant_type = "system"
        else:
            participant_type = "agent"

        # Build content from available fields
        parts = []
        if span.prompt:
            parts.append(span.prompt)
        if span.response:
            parts.append(span.response)
        if span.tool_name:
            parts.append(f"Tool: {span.tool_name}")
        if span.error:
            parts.append(f"Error: {span.error}")
        if not parts:
            # Fall back to input/output data
            if span.input_data:
                parts.append(str(span.input_data))
            if span.output_data:
                parts.append(str(span.output_data))

        content = "\n".join(parts) if parts else span.name

        snapshots.append(TurnSnapshot(
            turn_number=i,
            participant_type=participant_type,
            participant_id=span.agent_id or span.agent_name or f"span_{i}",
            content=content,
        ))

    return snapshots


def _run_span_detectors(trace: UniversalTrace) -> list:
    """Run span-based detectors (loop, corruption) on the trace."""
    results = []

    # Convert to StateSnapshots for loop detection
    try:
        state_snapshots = trace.to_state_snapshots()
        if len(state_snapshots) >= 2:
            from app.detection.loop import detect_loops
            loop_result = detect_loops(state_snapshots)
            if loop_result and loop_result.get("detected"):
                results.append({
                    "category": "loop",
                    "detected": True,
                    "confidence": loop_result.get("confidence", 0.7),
                    "severity": loop_result.get("severity", "moderate"),
                    "title": "Infinite Loop Detected",
                    "description": loop_result.get("explanation", "Repetitive pattern detected in agent behavior"),
                    "evidence": [{"type": "loop", "details": loop_result.get("evidence", {})}],
                    "affected_spans": [str(s.id) for s in trace.spans[:5]],
                    "suggested_fix": "Add loop detection guards or exit conditions to prevent repetitive behavior.",
                })
    except Exception as e:
        logger.debug(f"Span-based loop detection skipped: {e}")

    return results


def _run_turn_aware_detectors(trace: UniversalTrace) -> list:
    """Run all turn-aware detectors on the trace."""
    from app.detection.turn_aware import analyze_conversation_turns

    snapshots = _spans_to_turn_snapshots(trace)
    if len(snapshots) < 2:
        return []

    try:
        detection_results = analyze_conversation_turns(snapshots)
    except Exception as e:
        logger.warning(f"Turn-aware detection failed: {e}")
        return []

    results = []
    for det in detection_results:
        if not det.detected:
            continue

        fm = det.failure_mode or "unknown"
        results.append({
            "category": fm,
            "detected": True,
            "confidence": det.confidence,
            "severity": det.severity.value if hasattr(det.severity, "value") else str(det.severity),
            "title": _FAILURE_MODE_TITLES.get(fm, det.detector_name),
            "description": det.explanation,
            "evidence": [det.evidence] if det.evidence else [],
            "affected_spans": [str(t) for t in det.affected_turns],
            "suggested_fix": det.suggested_fix,
        })

    return results


def _build_error_detections(trace: UniversalTrace) -> list:
    """Detect explicit errors in spans."""
    results = []
    error_spans = trace.get_errors()

    if error_spans:
        error_details = []
        for span in error_spans[:10]:  # Limit to first 10 errors
            error_details.append({
                "span_id": span.id,
                "span_name": span.name,
                "error": span.error,
                "error_type": span.error_type,
            })

        results.append({
            "category": "error",
            "detected": True,
            "confidence": 0.95,
            "severity": "severe" if len(error_spans) > 2 else "moderate",
            "title": f"Span Errors ({len(error_spans)} spans)",
            "description": f"{len(error_spans)} span(s) have explicit errors: {error_spans[0].error or 'unknown error'}",
            "evidence": error_details,
            "affected_spans": [s.id for s in error_spans],
            "suggested_fix": "Review error messages and fix the root cause. Check tool configurations and API responses.",
        })

    return results


def _pick_primary(detections: list) -> Optional[dict]:
    """Select the primary (most important) detection result."""
    if not detections:
        return None

    severity_order = {"severe": 4, "moderate": 3, "minor": 2, "none": 1}

    return max(
        detections,
        key=lambda d: (
            severity_order.get(d["severity"], 0),
            d["confidence"],
        ),
    )


def _generate_root_cause(primary: Optional[dict], all_detections: list) -> Optional[str]:
    """Generate a root cause explanation from detection results."""
    if not primary:
        return None

    parts = [f"Primary issue: {primary['title']}"]
    parts.append(primary["description"])

    if len(all_detections) > 1:
        other = [d for d in all_detections if d is not primary]
        other_names = [d["title"] for d in other[:3]]
        parts.append(f"Additional issues: {', '.join(other_names)}")

    if primary.get("suggested_fix"):
        parts.append(f"Suggested fix: {primary['suggested_fix']}")

    return " | ".join(parts)


# --------------------------------------------------------------------------- #
#  Endpoints
# --------------------------------------------------------------------------- #

@router.post("/why-failed", response_model=DiagnoseResponse)
async def why_did_this_fail(request: DiagnoseRequest) -> DiagnoseResponse:
    """Main Agent Forensics entry point: "Why did this fail?"

    Accepts a pasted trace in various formats, runs ICP-tier detection
    (pattern + turn-aware), and returns root cause analysis.

    **Supported Formats:**
    - `auto` (default): Auto-detect format from content
    - `raw` / `json` / `generic`: Generic JSON traces
    - `mast`: MAST-Data conversation traces
    - `conversation`: Turn-based conversation traces
    - `otel` / `langsmith`: Available with enterprise feature flags

    **Example Request:**
    ```json
    {
        "content": "[{\"name\": \"agent.step\", \"type\": \"agent\", ...}]",
        "format": "auto",
        "include_fixes": true
    }
    ```
    """
    start_ms = time.monotonic()

    try:
        # 1. Detect format
        format_name = request.format
        if format_name == "auto":
            format_name = detect_format(request.content)
            logger.info(f"Auto-detected format: {format_name}")

        # 2. Import trace
        trace = import_trace(request.content, format_name)
        logger.info(f"Imported trace {trace.trace_id} with {len(trace.spans)} spans")

        if not trace.spans:
            raise ValueError("No spans found in trace content")

        # 3. Run all detection tiers
        all_detections: list = []
        detectors_run: list[str] = []

        # Tier A: Explicit error detection
        error_results = _build_error_detections(trace)
        all_detections.extend(error_results)
        detectors_run.append("error_scanner")

        # Tier B: Span-based pattern detection (loop, corruption)
        span_results = _run_span_detectors(trace)
        all_detections.extend(span_results)
        detectors_run.append("span_pattern_detector")

        # Tier C: Turn-aware detection (F1-F17)
        turn_results = _run_turn_aware_detectors(trace)
        all_detections.extend(turn_results)
        detectors_run.append("turn_aware_detector")

        # 4. Select primary failure and generate explanation
        primary = _pick_primary(all_detections)
        root_cause = _generate_root_cause(primary, all_detections)

        # 5. Build response
        elapsed_ms = int((time.monotonic() - start_ms) * 1000)

        primary_result = None
        if primary:
            primary_result = DiagnoseDetectionResult(
                category=primary["category"],
                detected=primary["detected"],
                confidence=primary["confidence"],
                severity=primary["severity"],
                title=primary["title"],
                description=primary["description"],
                evidence=primary["evidence"],
                affected_spans=primary["affected_spans"],
                suggested_fix=primary.get("suggested_fix"),
            )

        detection_models = [
            DiagnoseDetectionResult(
                category=d["category"],
                detected=d["detected"],
                confidence=d["confidence"],
                severity=d["severity"],
                title=d["title"],
                description=d["description"],
                evidence=d["evidence"],
                affected_spans=d["affected_spans"],
                suggested_fix=d.get("suggested_fix"),
            )
            for d in all_detections
        ]

        return DiagnoseResponse(
            trace_id=trace.trace_id,
            analyzed_at=datetime.now(timezone.utc),
            has_failures=len(all_detections) > 0,
            failure_count=len(all_detections),
            primary_failure=primary_result,
            all_detections=detection_models,
            total_spans=len(trace.spans),
            error_spans=trace.error_count,
            total_tokens=trace.total_tokens,
            duration_ms=trace.total_duration_ms,
            root_cause_explanation=root_cause,
            self_healing_available=False,
            auto_fix_preview=None,
            detection_time_ms=elapsed_ms,
            detectors_run=detectors_run,
        )

    except ValueError as e:
        logger.warning(f"Invalid trace content: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid trace content: {str(e)}")
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Diagnosis failed: {str(e)}")


@router.post("/quick-check", response_model=DiagnoseQuickCheckResponse)
async def quick_check(request: DiagnoseRequest) -> DiagnoseQuickCheckResponse:
    """Lightweight failure check without full analysis.

    Returns a quick yes/no on whether failures exist, without running
    the full detection pipeline. Useful for CI/CD or quick validation.
    """
    try:
        format_name = request.format
        if format_name == "auto":
            format_name = detect_format(request.content)

        trace = import_trace(request.content, format_name)

        # Quick checks
        has_errors = trace.has_errors
        error_count = trace.error_count

        # Basic loop check
        tool_calls = trace.get_tool_calls()
        repeated_tools = 0
        if len(tool_calls) >= 2:
            tool_names = [t.tool_name for t in tool_calls if t.tool_name]
            for i in range(1, len(tool_names)):
                if tool_names[i] == tool_names[i - 1]:
                    repeated_tools += 1

        primary_category = None
        primary_severity = None
        if has_errors:
            primary_category = "error"
            primary_severity = "high"
        elif repeated_tools >= 2:
            primary_category = "loop"
            primary_severity = "medium"

        failure_count = error_count + (1 if repeated_tools >= 2 else 0)

        if failure_count > 0:
            message = f"Found {failure_count} potential issue(s). Run full diagnosis for details."
        else:
            message = "No obvious issues detected. Trace appears healthy."

        return DiagnoseQuickCheckResponse(
            has_failures=failure_count > 0,
            failure_count=failure_count,
            primary_category=primary_category,
            primary_severity=primary_severity,
            message=message,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid trace: {str(e)}")
    except Exception as e:
        logger.error(f"Quick check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/formats")
async def list_supported_formats():
    """List supported trace formats for import."""
    from app.ingestion.importers import IMPORTERS

    formats = [
        {
            "name": "auto",
            "description": "Auto-detect format from content",
            "default": True,
        },
    ]

    # Add registered importers
    seen = set()
    for name, cls in IMPORTERS.items():
        if cls not in seen:
            seen.add(cls)
            formats.append({
                "name": name,
                "description": f"{cls.__doc__.split(chr(10))[0] if cls.__doc__ else name} importer",
                "aliases": [k for k, v in IMPORTERS.items() if v is cls and k != name],
            })

    return {"formats": formats}


@router.get("/health")
async def diagnose_health():
    """Health check for Agent Forensics diagnose service."""
    return {
        "status": "healthy",
        "service": "agent-forensics",
        "tier": "icp",
        "version": "1.0.0",
        "capabilities": [
            "error_detection",
            "loop_detection",
            "turn_aware_detection",
            "17_failure_modes",
            "auto_format_detection",
        ],
    }
