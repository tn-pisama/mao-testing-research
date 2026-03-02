"""Background detection for webhook-ingested traces.

Webhook handlers store traces to the DB but don't run detection inline.
This module builds a UniversalTrace from stored states and runs the
orchestrator, storing results in the detections table.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.ingestion.universal_trace import UniversalTrace, UniversalSpan, SpanType, SpanStatus

logger = logging.getLogger(__name__)


def build_universal_trace(
    trace_id: str,
    framework: str,
    states: list,
    metadata: Optional[Dict[str, Any]] = None,
) -> UniversalTrace:
    """Build a UniversalTrace from parsed state records.

    Args:
        trace_id: The trace UUID string.
        framework: Provider name ("n8n", "dify", "openclaw", "langgraph").
        states: List of parsed state dataclass instances (with sequence_num,
                agent_id, state_delta, state_hash, token_count, latency_ms).
        metadata: Optional framework-specific metadata dict.

    Returns:
        UniversalTrace with source_format set to the framework name.
    """
    now = datetime.utcnow()
    spans: List[UniversalSpan] = []

    for state in states:
        seq = getattr(state, "sequence_num", 0)
        agent_id = getattr(state, "agent_id", "unknown")
        latency_ms = getattr(state, "latency_ms", 0)
        token_count = getattr(state, "token_count", 0)
        state_delta = getattr(state, "state_delta", {})

        start = now + timedelta(milliseconds=seq * 100)
        end = start + timedelta(milliseconds=max(latency_ms, 1))

        # Determine span type from state content
        span_type = SpanType.LLM_CALL
        if isinstance(state_delta, dict):
            if state_delta.get("tool_name") or state_delta.get("tool_call"):
                span_type = SpanType.TOOL_CALL

        span = UniversalSpan(
            id=f"{trace_id}-{seq}",
            trace_id=trace_id,
            name=agent_id,
            span_type=span_type,
            status=SpanStatus.OK,
            start_time=start,
            end_time=end,
            duration_ms=latency_ms,
            agent_id=agent_id,
            tokens_total=token_count,
            source_format=framework,
            metadata=state_delta if isinstance(state_delta, dict) else {},
        )
        spans.append(span)

    return UniversalTrace(
        trace_id=trace_id,
        spans=spans,
        source_format=framework,
        metadata=metadata or {},
    )


async def run_background_detection(
    trace_id: str,
    tenant_id: str,
    framework: str,
    states: list,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Background task: build UniversalTrace and run detection.

    Called from webhook handlers after trace ingestion. Runs the orchestrator
    and stores any detected issues in the detections table.

    Args:
        trace_id: The trace UUID string.
        tenant_id: The tenant UUID string.
        framework: Provider name.
        states: List of parsed state dataclass instances.
        metadata: Optional framework-specific metadata dict.
    """
    try:
        from app.detection_enterprise.orchestrator import DetectionOrchestrator
        from app.storage.database import async_session_maker
        from app.storage.models import Detection

        trace = build_universal_trace(trace_id, framework, states, metadata)

        orchestrator = DetectionOrchestrator(enable_llm_explanation=False)
        result = orchestrator.analyze_trace(trace)

        if not result.all_detections:
            return

        async with async_session_maker() as session:
            for detection in result.all_detections:
                db_detection = Detection(
                    tenant_id=UUID(tenant_id),
                    trace_id=UUID(trace_id),
                    detection_type=detection.category.value,
                    confidence=int(detection.confidence * 100),
                    method=f"background:{framework}",
                    details={
                        "title": detection.title,
                        "description": detection.description,
                        "severity": detection.severity.value,
                        "evidence": detection.evidence,
                        "suggested_fix": detection.suggested_fix,
                    },
                )
                session.add(db_detection)

            await session.commit()
            logger.info(
                "Background detection found %d issues for %s trace %s",
                len(result.all_detections), framework, trace_id,
            )
    except Exception as exc:
        logger.warning("Background detection failed for trace %s: %s", trace_id, exc)
