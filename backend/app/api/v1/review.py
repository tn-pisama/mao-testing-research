"""Review Queue API — Hand-review detections, batch verdicts, golden dataset promotion.

Based on:
- GoodEye Labs: "Evaluation is the load-bearing part" — few-shot calibration from expert reviews
- LangChain: "20-50 hand-reviewed examples beat hundreds of unverified synthetic ones"

Review process:
1. GET /review/queue — list unreviewed detections (filterable, sortable)
2. POST /review/batch — submit batch verdicts (correct/false_positive/disputed)
3. POST /review/promote/{id} — promote reviewed detection to golden dataset
4. GET /review/stats — review progress metrics
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_verified_tenant
from app.storage.database import get_db, set_tenant_context
from app.storage.models import Detection, Trace, State

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/review", tags=["review"])


# ── Schemas ──────────────────────────────────────────────────────────

class ReviewVerdict(BaseModel):
    detection_id: str
    verdict: str  # "confirmed", "false_positive", "disputed"
    notes: Optional[str] = None
    promote_to_golden: bool = False


class BatchReviewRequest(BaseModel):
    reviews: List[ReviewVerdict]
    reviewer_id: Optional[str] = None


class BatchReviewResponse(BaseModel):
    reviewed: int
    promoted: int
    errors: List[str]


class ReviewQueueItem(BaseModel):
    id: str
    trace_id: str
    detection_type: str
    confidence: int
    method: str
    review_status: str
    created_at: str
    # Failure mode descriptions
    failure_mode_name: str = ""
    failure_mode_summary: str = ""
    failure_mode_technical: str = ""
    example_positive: str = ""
    example_negative: str = ""
    # Evidence fields for inline review (no click-away needed)
    explanation: Optional[str] = None
    business_impact: Optional[str] = None
    evidence: dict = {}
    agent_id: Optional[str] = None
    agent_role: Optional[str] = None
    state_snippet: Optional[str] = None


class ReviewQueueResponse(BaseModel):
    items: List[ReviewQueueItem]
    total: int
    pending: int
    page: int
    per_page: int


class ReviewStatsResponse(BaseModel):
    total_detections: int
    pending_review: int
    confirmed: int
    false_positives: int
    disputed: int
    promoted_to_golden: int
    agreement_rate: float  # How often reviewer confirms the detector
    by_type: dict


class PromoteResponse(BaseModel):
    detection_id: str
    golden_entry_created: bool
    message: str


# ── Endpoints ────────────────────────────────────────────────────────

def _truncate(val: str, max_len: int = 200) -> str:
    """Truncate a string for display."""
    s = str(val)
    return s[:max_len] + "..." if len(s) > max_len else s


def _extract_evidence(detection_type: str, details: dict) -> dict:
    """Extract the 2-3 most relevant evidence fields per detection type.

    Returns a dict of human-readable key-value pairs a reviewer needs
    to judge the detection without clicking into the trace.
    """
    evidence = {}

    if detection_type == "persona_drift":
        if "persona_description" in details:
            evidence["Assigned Persona"] = _truncate(details["persona_description"])
        if "output" in details:
            evidence["Agent Output"] = _truncate(details["output"])
        if "consistency_score" in details:
            evidence["Consistency Score"] = f"{details['consistency_score']:.2f}"

    elif detection_type == "hallucination":
        if "output" in details:
            evidence["Agent Claim"] = _truncate(details["output"])
        if "sources" in details:
            src = details["sources"]
            evidence["Sources"] = _truncate(str(src[0]) if isinstance(src, list) and src else str(src))

    elif detection_type == "coordination":
        if "agent_ids" in details:
            evidence["Agents"] = ", ".join(details["agent_ids"][:5])
        if "issues" in details and isinstance(details["issues"], list):
            evidence["Issues"] = "; ".join(str(i.get("message", i)) for i in details["issues"][:3])

    elif detection_type == "loop":
        if "iterations" in details:
            evidence["Iterations"] = str(details["iterations"])
        if "repeated_hash" in details:
            evidence["Repeated Pattern"] = _truncate(details["repeated_hash"])

    elif detection_type == "injection":
        if "text" in details:
            evidence["Suspicious Input"] = _truncate(details["text"])

    elif detection_type == "derailment":
        if "task" in details:
            evidence["Original Task"] = _truncate(details["task"])
        if "output" in details:
            evidence["Agent Output"] = _truncate(details["output"])

    elif detection_type == "agent_teams":
        if "task_list" in details:
            tasks = details["task_list"]
            if isinstance(tasks, list):
                done = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") in ("done", "completed"))
                evidence["Tasks"] = f"{done}/{len(tasks)} completed"
        if "messages" in details:
            evidence["Messages"] = f"{len(details['messages'])} exchanged"

    elif detection_type == "adaptive_thinking":
        if "cost_usd" in details:
            evidence["Cost"] = f"${details['cost_usd']:.3f}"
        if "thinking_tokens" in details:
            evidence["Thinking Tokens"] = f"{details['thinking_tokens']:,}"
        if "output_tokens" in details:
            evidence["Output Tokens"] = f"{details['output_tokens']:,}"

    elif detection_type == "cowork_safety":
        if "executed_actions" in details and isinstance(details["executed_actions"], list):
            destructive = [a for a in details["executed_actions"]
                          if isinstance(a, dict) and any(kw in str(a.get("action", "")).lower()
                          for kw in ("delete", "rm", "overwrite", "drop"))]
            if destructive:
                evidence["Destructive Actions"] = "; ".join(
                    f"{a.get('action')} → {a.get('target', '?')}" for a in destructive[:3]
                )
        if "files_modified" in details:
            evidence["Files Modified"] = str(details["files_modified"])

    # Default fallback: first 3 keys from details
    if not evidence:
        for key in list(details.keys())[:3]:
            if key not in ("explanation", "business_impact", "suggested_action"):
                evidence[key] = _truncate(str(details[key]))

    return evidence


def _get_business_impact(detection_type: str, confidence: int) -> str:
    """Generate a brief business impact statement."""
    severity = "High" if confidence >= 80 else "Medium" if confidence >= 50 else "Low"
    impacts = {
        "persona_drift": "Agent may confuse users by acting outside its designated role",
        "hallucination": "Agent output may contain fabricated information not supported by sources",
        "coordination": "Agents may fail to communicate, causing dropped tasks or duplicate work",
        "loop": "Agent is stuck repeating the same actions, wasting compute and time",
        "injection": "User input may be attempting to override agent safety instructions",
        "derailment": "Agent deviated from the assigned task, producing irrelevant output",
        "agent_teams": "Team coordination failure — tasks may be dropped, duplicated, or deadlocked",
        "adaptive_thinking": "Reasoning cost disproportionate to output value",
        "cowork_safety": "Agent performed potentially destructive actions on user files",
        "subagent_boundary": "Subagent used tools outside its authorized scope",
    }
    impact = impacts.get(detection_type, f"Potential {detection_type.replace('_', ' ')} issue detected")
    return f"[{severity}] {impact}"


def _summarize_state(delta: dict) -> str:
    """Extract a brief summary from a state_delta dict."""
    if not delta:
        return ""
    # Pick the most informative field
    for key in ("output", "text", "result", "response", "content", "message", "action"):
        if key in delta:
            return _truncate(str(delta[key]))
    # Fallback: first value
    first_val = next(iter(delta.values()), "")
    return _truncate(str(first_val))


@router.get("/queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str = Query("pending", description="pending|confirmed|false_positive|disputed|all"),
    detection_type: Optional[str] = Query(None),
    confidence_min: Optional[int] = Query(None, ge=0, le=100),
    confidence_max: Optional[int] = Query(None, ge=0, le=100),
    sort: str = Query("confidence_asc", description="confidence_asc|confidence_desc|newest|oldest"),
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List detections for hand-review. Default: unreviewed, sorted by confidence ascending (most ambiguous first)."""
    await set_tenant_context(db, tenant_id)

    query = select(Detection).where(Detection.tenant_id == UUID(tenant_id))

    if status != "all":
        query = query.where(Detection.review_status == status)
    if detection_type:
        query = query.where(Detection.detection_type == detection_type)
    if confidence_min is not None:
        query = query.where(Detection.confidence >= confidence_min)
    if confidence_max is not None:
        query = query.where(Detection.confidence <= confidence_max)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    pending_count = (await db.execute(
        select(func.count()).where(
            Detection.tenant_id == UUID(tenant_id),
            Detection.review_status == "pending",
        )
    )).scalar() or 0

    # Sort
    if sort == "confidence_asc":
        query = query.order_by(Detection.confidence.asc())
    elif sort == "confidence_desc":
        query = query.order_by(Detection.confidence.desc())
    elif sort == "newest":
        query = query.order_by(Detection.created_at.desc())
    else:
        query = query.order_by(Detection.created_at.asc())

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    detections = result.scalars().all()

    items = []
    for d in detections:
        details = d.details or {}

        # Extract explanation
        explanation = details.get("explanation", "")

        # Extract type-specific evidence for inline review
        evidence = _extract_evidence(d.detection_type, details)

        # Generate business impact from detection type
        business_impact = _get_business_impact(d.detection_type, d.confidence)

        # Load trace context (agent_id, state snippet) via state_id
        agent_id = None
        agent_role = None
        state_snippet = None
        if d.state_id:
            state_result = await db.execute(
                select(State).where(State.id == d.state_id)
            )
            state = state_result.scalar_one_or_none()
            if state:
                agent_id = state.agent_id
                agent_role = getattr(state, "agent_role", None)
                delta = state.state_delta or {}
                # Get the most relevant field from state_delta
                state_snippet = _summarize_state(delta)

        # Load failure mode description
        from app.detection.failure_modes import get_failure_mode
        fm = get_failure_mode(d.detection_type)

        items.append(ReviewQueueItem(
            id=str(d.id),
            trace_id=str(d.trace_id),
            detection_type=d.detection_type,
            confidence=d.confidence,
            method=d.method,
            review_status=d.review_status or "pending",
            created_at=d.created_at.isoformat() if d.created_at else "",
            failure_mode_name=fm.get("name", d.detection_type),
            failure_mode_summary=fm.get("summary", ""),
            failure_mode_technical=fm.get("technical", ""),
            example_positive=fm.get("example_positive", ""),
            example_negative=fm.get("example_negative", ""),
            explanation=explanation,
            business_impact=business_impact,
            evidence=evidence,
            agent_id=agent_id,
            agent_role=agent_role,
            state_snippet=state_snippet,
        ))

    return ReviewQueueResponse(
        items=items, total=total, pending=pending_count,
        page=page, per_page=per_page,
    )


@router.post("/batch", response_model=BatchReviewResponse)
async def submit_batch_review(
    request: BatchReviewRequest,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Submit hand-review verdicts for multiple detections at once."""
    await set_tenant_context(db, tenant_id)

    reviewed = 0
    promoted = 0
    errors = []
    now = datetime.now(timezone.utc)
    reviewer = request.reviewer_id or tenant_id

    for rv in request.reviews:
        try:
            det_result = await db.execute(
                select(Detection).where(
                    Detection.id == UUID(rv.detection_id),
                    Detection.tenant_id == UUID(tenant_id),
                )
            )
            det = det_result.scalar_one_or_none()
            if not det:
                errors.append(f"{rv.detection_id}: not found")
                continue

            # Map verdict to review fields
            if rv.verdict == "confirmed":
                det.review_status = "confirmed"
                det.validated = True
                det.false_positive = False
            elif rv.verdict == "false_positive":
                det.review_status = "false_positive"
                det.validated = True
                det.false_positive = True
            elif rv.verdict == "disputed":
                det.review_status = "disputed"
            else:
                errors.append(f"{rv.detection_id}: invalid verdict '{rv.verdict}'")
                continue

            det.reviewed_by = reviewer
            det.reviewed_at = now
            det.review_notes = rv.notes

            if rv.promote_to_golden:
                det.promoted_to_golden = True
                promoted += 1

            reviewed += 1

        except Exception as e:
            errors.append(f"{rv.detection_id}: {str(e)[:100]}")

    await db.commit()

    logger.info("Batch review: %d reviewed, %d promoted, %d errors by %s",
                reviewed, promoted, len(errors), reviewer)

    return BatchReviewResponse(reviewed=reviewed, promoted=promoted, errors=errors)


@router.post("/promote/{detection_id}", response_model=PromoteResponse)
async def promote_to_golden(
    detection_id: UUID,
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Promote a reviewed detection to the golden dataset for recalibration."""
    await set_tenant_context(db, tenant_id)

    det_result = await db.execute(
        select(Detection).where(
            Detection.id == detection_id,
            Detection.tenant_id == UUID(tenant_id),
        )
    )
    det = det_result.scalar_one_or_none()
    if not det:
        raise HTTPException(status_code=404, detail="Detection not found")

    if det.review_status not in ("confirmed", "false_positive"):
        raise HTTPException(status_code=400, detail="Only confirmed or false_positive detections can be promoted")

    det.promoted_to_golden = True
    await db.commit()

    return PromoteResponse(
        detection_id=str(detection_id),
        golden_entry_created=True,
        message=f"Detection promoted to golden dataset as {'positive' if det.review_status == 'confirmed' else 'negative'} example",
    )


@router.get("/stats", response_model=ReviewStatsResponse)
async def get_review_stats(
    tenant_id: str = Depends(get_verified_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get review progress metrics."""
    await set_tenant_context(db, tenant_id)

    base = select(Detection).where(Detection.tenant_id == UUID(tenant_id))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    status_counts = await db.execute(
        select(
            Detection.review_status,
            func.count().label("count"),
        ).where(Detection.tenant_id == UUID(tenant_id))
        .group_by(Detection.review_status)
    )

    counts = {row.review_status or "pending": row.count for row in status_counts}
    pending = counts.get("pending", 0)
    confirmed = counts.get("confirmed", 0)
    false_positives = counts.get("false_positive", 0)
    disputed = counts.get("disputed", 0)

    promoted = (await db.execute(
        select(func.count()).where(
            Detection.tenant_id == UUID(tenant_id),
            Detection.promoted_to_golden == True,
        )
    )).scalar() or 0

    reviewed_total = confirmed + false_positives
    agreement_rate = confirmed / reviewed_total if reviewed_total > 0 else 0.0

    # By type
    type_counts = await db.execute(
        select(
            Detection.detection_type,
            Detection.review_status,
            func.count().label("count"),
        ).where(Detection.tenant_id == UUID(tenant_id))
        .group_by(Detection.detection_type, Detection.review_status)
    )

    by_type = {}
    for row in type_counts:
        dt = row.detection_type
        if dt not in by_type:
            by_type[dt] = {"pending": 0, "confirmed": 0, "false_positive": 0, "disputed": 0}
        status_key = row.review_status or "pending"
        if status_key in by_type[dt]:
            by_type[dt][status_key] = row.count

    return ReviewStatsResponse(
        total_detections=total,
        pending_review=pending,
        confirmed=confirmed,
        false_positives=false_positives,
        disputed=disputed,
        promoted_to_golden=promoted,
        agreement_rate=round(agreement_rate, 3),
        by_type=by_type,
    )
