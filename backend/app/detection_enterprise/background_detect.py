"""Background detection for webhook-ingested traces.

Webhook handlers store traces to the DB but don't run detection inline.
This module builds a UniversalTrace from stored states and runs the
orchestrator, storing results in the detections table.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.ingestion.universal_trace import UniversalTrace, UniversalSpan, SpanType, SpanStatus

logger = logging.getLogger(__name__)

# Shadow eval: run a golden-dataset sample every N traces to detect judge drift.
_SHADOW_EVAL_INTERVAL = int(os.environ.get("SHADOW_EVAL_INTERVAL", "100"))
_shadow_eval_counter = 0

# Concurrency control: limits how many detection pipelines run simultaneously.
# Prevents cost blowup and LLM API rate-limit degradation under burst load.
_DETECTION_MAX_CONCURRENT = int(os.environ.get("DETECTION_MAX_CONCURRENT", "5"))
_detection_semaphore = asyncio.Semaphore(_DETECTION_MAX_CONCURRENT)


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


async def _maybe_run_shadow_eval() -> None:
    """Run a shadow evaluation every SHADOW_EVAL_INTERVAL traces."""
    global _shadow_eval_counter
    _shadow_eval_counter += 1

    if _shadow_eval_counter % _SHADOW_EVAL_INTERVAL != 0:
        return

    try:
        from app.detection_enterprise.shadow_eval import pick_shadow_sample, run_shadow_eval
        from app.detection_enterprise.golden_dataset import GoldenDataset
        from app.storage.database import async_session_maker
        from app.storage.models import ShadowEvalResult as ShadowEvalModel
        from pisama_detectors import DETECTOR_REGISTRY, _try_run_detector

        dataset = GoldenDataset()
        entries = [e.__dict__ if hasattr(e, '__dict__') else e for e in dataset.entries]

        sample = pick_shadow_sample(entries)
        if not sample:
            return

        det_type = sample.get("detection_type", "")
        if det_type not in DETECTOR_REGISTRY:
            return

        detector_fn = DETECTOR_REGISTRY[det_type].function

        def runner(input_data):
            result = _try_run_detector(detector_fn, input_data)
            if result is None:
                return False, 0.0
            return getattr(result, "detected", False), getattr(result, "confidence", 0.0)

        eval_result = run_shadow_eval(sample, runner)

        async with async_session_maker() as session:
            db_row = ShadowEvalModel(
                detector_type=eval_result.detector_type,
                golden_entry_id=eval_result.golden_entry_id,
                expected_detected=eval_result.expected_detected,
                actual_detected=eval_result.actual_detected,
                expected_confidence_min=eval_result.expected_confidence_min,
                expected_confidence_max=eval_result.expected_confidence_max,
                actual_confidence=eval_result.actual_confidence,
                match=eval_result.match,
                error=eval_result.error,
            )
            session.add(db_row)
            await session.commit()

        logger.debug(
            "Shadow eval [%s]: expected=%s, actual=%s, match=%s",
            eval_result.detector_type, eval_result.expected_detected,
            eval_result.actual_detected, eval_result.match,
        )
    except Exception as exc:
        logger.debug("Shadow eval skipped: %s", exc)


async def _update_trace_detection_status(
    session, trace_id: str, status: str, metadata_update: Optional[Dict[str, Any]] = None,
) -> None:
    """Update the detection_status and detection_metadata on a Trace."""
    from app.storage.models import Trace
    from sqlalchemy import update

    values: Dict[str, Any] = {"detection_status": status}
    if metadata_update is not None:
        values["detection_metadata"] = metadata_update
    await session.execute(
        update(Trace).where(Trace.id == UUID(trace_id)).values(**values)
    )
    await session.commit()


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

    Uses checkpoint-per-detector pattern: each detection result is committed
    individually so partial results survive if a later detector fails.

    Args:
        trace_id: The trace UUID string.
        tenant_id: The tenant UUID string.
        framework: Provider name.
        states: List of parsed state dataclass instances.
        metadata: Optional framework-specific metadata dict.
    """
    async with _detection_semaphore:
        logger.debug(
            "Detection pipeline started for trace %s (%d/%d slots)",
            trace_id,
            _DETECTION_MAX_CONCURRENT - _detection_semaphore._value,
            _DETECTION_MAX_CONCURRENT,
        )
        try:
            from app.detection_enterprise.orchestrator import DetectionOrchestrator
            from app.storage.database import async_session_maker
            from app.storage.models import Detection

            trace = build_universal_trace(trace_id, framework, states, metadata)
            orchestrator = DetectionOrchestrator(enable_llm_explanation=False)

            # Mark pipeline as running
            async with async_session_maker() as session:
                await _update_trace_detection_status(session, trace_id, "running")

            result = orchestrator.analyze_trace(trace)

            if not result.all_detections:
                async with async_session_maker() as session:
                    await _update_trace_detection_status(
                        session, trace_id, "complete",
                        {"detectors_run": len(result.detectors_run), "detections_found": 0},
                    )
                return

            # Checkpoint: save each detection individually
            saved_count = 0
            failed_detectors: List[str] = []

            async with async_session_maker() as session:
                for detection in result.all_detections:
                    try:
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
                        await session.flush()
                        saved_count += 1
                    except Exception as det_exc:
                        logger.warning(
                            "Failed to save detection %s for trace %s: %s",
                            detection.category.value, trace_id, det_exc,
                        )
                        failed_detectors.append(detection.category.value)
                        await session.rollback()

                await session.commit()

            # Determine final status
            final_status = "complete" if not failed_detectors else "partial"
            detection_meta = {
                "detectors_run": len(result.detectors_run),
                "detections_found": saved_count,
                "detection_time_ms": result.detection_time_ms,
            }
            if failed_detectors:
                detection_meta["failed_detectors"] = failed_detectors

            async with async_session_maker() as session:
                await _update_trace_detection_status(session, trace_id, final_status, detection_meta)

            logger.info(
                "Background detection found %d issues (%d saved) for %s trace %s [%s]",
                len(result.all_detections), saved_count, framework, trace_id, final_status,
            )

            # Shadow eval: periodically run a golden sample to detect drift
            await _maybe_run_shadow_eval()

        except Exception as exc:
            logger.warning("Background detection failed for trace %s: %s", trace_id, exc)
            try:
                from app.storage.database import async_session_maker
                async with async_session_maker() as session:
                    await _update_trace_detection_status(
                        session, trace_id, "failed",
                        {"error": str(exc)},
                    )
            except Exception:
                pass
