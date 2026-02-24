"""Agent Forensics Diagnose API endpoints.

This module provides the "Why did this fail?" entry point for Agent Forensics.
It accepts raw trace content, detects failures, and returns root cause analysis.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
import logging

from app.api.v1.schemas import (
    DiagnoseRequest,
    DiagnoseResponse,
    DiagnoseDetectionResult,
    DiagnoseAutoFixPreview,
    DiagnoseQuickCheckResponse,
)
from app.ingestion.importers import import_trace, detect_format
from app.detection_enterprise.orchestrator import DetectionOrchestrator, DiagnosisResult


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnose", tags=["diagnose"])


def _convert_to_response(result: DiagnosisResult) -> DiagnoseResponse:
    """Convert internal DiagnosisResult to API response schema."""
    primary = None
    if result.primary_failure:
        primary = DiagnoseDetectionResult(
            category=result.primary_failure.category.value,
            detected=result.primary_failure.detected,
            confidence=result.primary_failure.confidence,
            severity=result.primary_failure.severity.value,
            title=result.primary_failure.title,
            description=result.primary_failure.description,
            evidence=result.primary_failure.evidence,
            affected_spans=result.primary_failure.affected_spans,
            suggested_fix=result.primary_failure.suggested_fix,
        )

    all_detections = [
        DiagnoseDetectionResult(
            category=d.category.value,
            detected=d.detected,
            confidence=d.confidence,
            severity=d.severity.value,
            title=d.title,
            description=d.description,
            evidence=d.evidence,
            affected_spans=d.affected_spans,
            suggested_fix=d.suggested_fix,
        )
        for d in result.all_detections
    ]

    auto_fix = None
    if result.auto_fix_preview:
        auto_fix = DiagnoseAutoFixPreview(
            description=result.auto_fix_preview.get("description", ""),
            confidence=result.auto_fix_preview.get("confidence", 0.0),
            action=result.auto_fix_preview.get("action", ""),
        )

    return DiagnoseResponse(
        trace_id=result.trace_id,
        analyzed_at=result.analyzed_at,
        has_failures=result.has_failures,
        failure_count=result.failure_count,
        primary_failure=primary,
        all_detections=all_detections,
        total_spans=result.total_spans,
        error_spans=result.error_spans,
        total_tokens=result.total_tokens,
        duration_ms=result.duration_ms,
        root_cause_explanation=result.root_cause_explanation,
        self_healing_available=result.self_healing_available,
        auto_fix_preview=auto_fix,
        detection_time_ms=result.detection_time_ms,
        detectors_run=result.detectors_run,
    )


@router.post("/why-failed", response_model=DiagnoseResponse)
async def why_did_this_fail(
    request: DiagnoseRequest,
) -> DiagnoseResponse:
    """Main Agent Forensics entry point: "Why did this fail?"

    Accepts a pasted trace in various formats, runs comprehensive detection,
    and returns root cause analysis with suggested fixes.

    This endpoint is designed for:
    - Low-friction debugging (paste and get answers)
    - Framework-agnostic trace analysis
    - Self-healing capability preview

    **Supported Formats:**
    - `auto` (default): Auto-detect format from content
    - `langsmith`: LangSmith/LangChain trace export
    - `otel`: OpenTelemetry spans
    - `raw`: Generic JSON with agent/tool information

    **Example Request:**
    ```json
    {
        "content": "[{\"run_type\": \"llm\", \"name\": \"ChatOpenAI\", ...}]",
        "format": "auto",
        "include_fixes": true
    }
    ```
    """
    try:
        # Detect format if auto
        format_name = request.format
        if format_name == "auto":
            format_name = detect_format(request.content)
            logger.info(f"Auto-detected format: {format_name}")

        # Import trace
        trace = import_trace(request.content, format_name)
        logger.info(f"Imported trace {trace.trace_id} with {len(trace.spans)} spans")

        # Run detection
        orchestrator = DetectionOrchestrator(
            enable_llm_explanation=request.include_fixes,
        )
        result = await orchestrator.analyze_trace_async(trace)

        logger.info(
            f"Diagnosis complete: {result.failure_count} issues found in {result.detection_time_ms}ms"
        )

        return _convert_to_response(result)

    except ValueError as e:
        logger.warning(f"Invalid trace content: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trace content: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Diagnosis failed: {str(e)}"
        )


@router.post("/quick-check", response_model=DiagnoseQuickCheckResponse)
async def quick_check(
    request: DiagnoseRequest,
) -> DiagnoseQuickCheckResponse:
    """Lightweight failure check without full analysis.

    Returns a quick yes/no on whether failures exist, without
    running full detection or generating explanations.
    Useful for CI/CD pipelines or quick validation.
    """
    try:
        # Detect format if auto
        format_name = request.format
        if format_name == "auto":
            format_name = detect_format(request.content)

        # Import trace
        trace = import_trace(request.content, format_name)

        # Quick checks only
        has_errors = trace.has_errors
        error_count = trace.error_count

        # Basic pattern detection (fast)
        tool_calls = trace.get_tool_calls()
        repeated_tools = 0
        if len(tool_calls) >= 2:
            tool_names = [t.tool_name for t in tool_calls if t.tool_name]
            for i in range(1, len(tool_names)):
                if tool_names[i] == tool_names[i-1]:
                    repeated_tools += 1

        # Determine primary issue
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
    return {
        "formats": [
            {
                "name": "auto",
                "description": "Auto-detect format from content",
                "default": True,
            },
            {
                "name": "langsmith",
                "description": "LangSmith/LangChain trace export (JSONL or JSON array)",
                "example_marker": "run_type field present",
            },
            {
                "name": "otel",
                "description": "OpenTelemetry spans (resourceSpans format)",
                "example_marker": "resourceSpans or traceId field present",
            },
            {
                "name": "raw",
                "description": "Generic JSON with agent/tool information",
                "example_marker": "Any valid JSON with span-like structure",
            },
        ]
    }


@router.get("/health")
async def diagnose_health():
    """Health check for diagnose service."""
    return {
        "status": "healthy",
        "service": "agent-forensics",
        "version": "0.1.0",
        "capabilities": [
            "loop_detection",
            "context_overflow",
            "tool_error_detection",
            "self_healing_preview",
        ],
    }
