"""Detection feedback API endpoints.

Allows users to submit feedback on detection accuracy for threshold tuning.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Detection, DetectionFeedback, Trace
from app.core.auth import get_current_tenant

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackSubmission(BaseModel):
    """Request model for submitting feedback."""
    detection_id: UUID
    is_correct: bool = Field(..., description="Was the detection correct?")
    reason: Optional[str] = Field(None, max_length=1000, description="Why you think it's correct/incorrect")
    severity_rating: Optional[int] = Field(None, ge=1, le=5, description="How severe was the actual issue? 1=minor, 5=critical")


class FeedbackResponse(BaseModel):
    """Response model for feedback."""
    id: UUID
    detection_id: UUID
    is_correct: bool
    feedback_type: str
    detection_confidence: int
    detection_method: str
    framework: Optional[str]
    reason: Optional[str]
    severity_rating: Optional[int]
    created_at: datetime


class FeedbackStats(BaseModel):
    """Aggregated feedback statistics."""
    total_feedback: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1_score: float
    by_framework: dict
    by_detection_type: dict
    by_method: dict


class ThresholdRecommendation(BaseModel):
    """Recommended threshold adjustments based on feedback."""
    framework: str
    current_structural_threshold: float
    current_semantic_threshold: float
    recommended_structural_threshold: float
    recommended_semantic_threshold: float
    confidence: float
    sample_size: int
    reasoning: str


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    feedback: FeedbackSubmission,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback on a detection.

    Feedback is used to improve detection accuracy through threshold tuning.
    """
    await set_tenant_context(db, tenant_id)

    # Get detection
    result = await db.execute(
        select(Detection).where(
            Detection.id == feedback.detection_id,
            Detection.tenant_id == UUID(tenant_id),
        )
    )
    detection = result.scalar_one_or_none()

    if not detection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection not found",
        )

    # Check for existing feedback
    existing = await db.execute(
        select(DetectionFeedback).where(
            DetectionFeedback.detection_id == feedback.detection_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feedback already submitted for this detection",
        )

    # Get framework from trace
    trace_result = await db.execute(
        select(Trace).where(Trace.id == detection.trace_id)
    )
    trace = trace_result.scalar_one_or_none()
    framework = trace.framework if trace else None

    # Determine feedback type
    # If detection was triggered (confidence > 0) and user says correct -> TP
    # If detection was triggered and user says incorrect -> FP
    # For FN/TN, we'd need a separate "report missed detection" endpoint
    if detection.confidence > 0:
        feedback_type = "true_positive" if feedback.is_correct else "false_positive"
    else:
        feedback_type = "true_negative" if feedback.is_correct else "false_negative"

    # Create feedback record
    fb = DetectionFeedback(
        detection_id=detection.id,
        tenant_id=UUID(tenant_id),
        is_correct=feedback.is_correct,
        feedback_type=feedback_type,
        detection_confidence=detection.confidence,
        detection_method=detection.method,
        framework=framework,
        reason=feedback.reason,
        severity_rating=feedback.severity_rating,
    )
    db.add(fb)

    # Update detection validation status
    detection.validated = True
    detection.false_positive = not feedback.is_correct

    # --- Episodic memory: record feedback for adaptive thresholds ---
    try:
        from app.detection_enterprise.episodic_memory import EpisodicMemoryService
        episodic = EpisodicMemoryService(session=db, tenant_id=UUID(tenant_id))
        await episodic.record_feedback(
            detection_id=detection.id,
            feedback_type=feedback_type,
            detection_type=detection.detection_type,
            confidence=detection.confidence / 100.0,  # stored as 0-100 int
            framework=framework,
            input_data=detection.details if isinstance(detection.details, dict) else None,
        )
    except Exception:
        # Episodic memory is best-effort; don't fail the feedback endpoint
        import logging
        logging.getLogger(__name__).debug(
            "Episodic memory feedback recording failed", exc_info=True,
        )

    await db.commit()
    await db.refresh(fb)

    return FeedbackResponse(
        id=fb.id,
        detection_id=fb.detection_id,
        is_correct=fb.is_correct,
        feedback_type=fb.feedback_type,
        detection_confidence=fb.detection_confidence,
        detection_method=fb.detection_method,
        framework=fb.framework,
        reason=fb.reason,
        severity_rating=fb.severity_rating,
        created_at=fb.created_at,
    )


@router.get("/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    framework: Optional[str] = Query(None, description="Filter by framework"),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated feedback statistics.

    Returns precision, recall, and F1 score based on user feedback.
    """
    await set_tenant_context(db, tenant_id)

    since = datetime.utcnow() - timedelta(days=days)

    query = select(DetectionFeedback).where(
        DetectionFeedback.tenant_id == UUID(tenant_id),
        DetectionFeedback.created_at >= since,
    )

    if framework:
        query = query.where(DetectionFeedback.framework == framework)

    result = await db.execute(query)
    feedback_list = result.scalars().all()

    # Aggregate stats
    tp = sum(1 for f in feedback_list if f.feedback_type == "true_positive")
    fp = sum(1 for f in feedback_list if f.feedback_type == "false_positive")
    fn = sum(1 for f in feedback_list if f.feedback_type == "false_negative")
    tn = sum(1 for f in feedback_list if f.feedback_type == "true_negative")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # By framework
    by_framework = {}
    for f in feedback_list:
        fw = f.framework or "unknown"
        if fw not in by_framework:
            by_framework[fw] = {"total": 0, "correct": 0, "incorrect": 0}
        by_framework[fw]["total"] += 1
        if f.is_correct:
            by_framework[fw]["correct"] += 1
        else:
            by_framework[fw]["incorrect"] += 1

    # By detection type
    by_detection_type = {}
    for f in feedback_list:
        detection_result = await db.execute(
            select(Detection).where(Detection.id == f.detection_id)
        )
        detection = detection_result.scalar_one_or_none()
        if detection:
            dt = detection.detection_type
            if dt not in by_detection_type:
                by_detection_type[dt] = {"total": 0, "correct": 0, "incorrect": 0}
            by_detection_type[dt]["total"] += 1
            if f.is_correct:
                by_detection_type[dt]["correct"] += 1
            else:
                by_detection_type[dt]["incorrect"] += 1

    # By method
    by_method = {}
    for f in feedback_list:
        method = f.detection_method
        if method not in by_method:
            by_method[method] = {"total": 0, "correct": 0, "incorrect": 0}
        by_method[method]["total"] += 1
        if f.is_correct:
            by_method[method]["correct"] += 1
        else:
            by_method[method]["incorrect"] += 1

    return FeedbackStats(
        total_feedback=len(feedback_list),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=precision,
        recall=recall,
        f1_score=f1,
        by_framework=by_framework,
        by_detection_type=by_detection_type,
        by_method=by_method,
    )


@router.get("/recommendations", response_model=List[ThresholdRecommendation])
async def get_threshold_recommendations(
    min_samples: int = Query(10, ge=5, description="Minimum feedback samples required"),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get recommended threshold adjustments based on feedback.

    Analyzes false positive rates and suggests threshold changes.
    """
    await set_tenant_context(db, tenant_id)

    from app.config import get_framework_thresholds

    result = await db.execute(
        select(DetectionFeedback).where(
            DetectionFeedback.tenant_id == UUID(tenant_id),
        )
    )
    feedback_list = result.scalars().all()

    # Group by framework
    by_framework = {}
    for f in feedback_list:
        fw = f.framework or "unknown"
        if fw not in by_framework:
            by_framework[fw] = []
        by_framework[fw].append(f)

    recommendations = []
    for framework, feedback in by_framework.items():
        if len(feedback) < min_samples:
            continue

        current = get_framework_thresholds(framework)

        # Calculate FP rate by confidence band
        fp_count = sum(1 for f in feedback if f.feedback_type == "false_positive")
        tp_count = sum(1 for f in feedback if f.feedback_type == "true_positive")
        total = fp_count + tp_count

        if total == 0:
            continue

        fp_rate = fp_count / total

        # Analyze FPs by confidence level
        fp_by_confidence = {}
        for f in feedback:
            if f.feedback_type == "false_positive":
                band = (f.detection_confidence // 10) * 10  # 0-10, 10-20, etc
                fp_by_confidence[band] = fp_by_confidence.get(band, 0) + 1

        # Calculate recommended adjustments
        # High FP rate -> increase thresholds
        # Low FP rate -> can decrease thresholds
        if fp_rate > 0.3:
            structural_adj = 0.03  # Increase by 3%
            semantic_adj = 0.03
            reasoning = f"High false positive rate ({fp_rate:.1%}). Recommend increasing thresholds."
        elif fp_rate > 0.15:
            structural_adj = 0.01
            semantic_adj = 0.01
            reasoning = f"Moderate false positive rate ({fp_rate:.1%}). Recommend slight threshold increase."
        elif fp_rate < 0.05 and tp_count > 10:
            structural_adj = -0.02
            semantic_adj = -0.02
            reasoning = f"Very low false positive rate ({fp_rate:.1%}). Could decrease thresholds to catch more issues."
        else:
            structural_adj = 0
            semantic_adj = 0
            reasoning = f"False positive rate ({fp_rate:.1%}) is acceptable. No changes recommended."

        recommendations.append(ThresholdRecommendation(
            framework=framework,
            current_structural_threshold=current.structural_threshold,
            current_semantic_threshold=current.semantic_threshold,
            recommended_structural_threshold=min(0.99, max(0.5, current.structural_threshold + structural_adj)),
            recommended_semantic_threshold=min(0.99, max(0.5, current.semantic_threshold + semantic_adj)),
            confidence=min(1.0, len(feedback) / 50),  # More samples = higher confidence
            sample_size=len(feedback),
            reasoning=reasoning,
        ))

    return recommendations


@router.get("", response_model=List[FeedbackResponse])
async def list_feedback(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    feedback_type: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List feedback submissions."""
    await set_tenant_context(db, tenant_id)

    query = select(DetectionFeedback).where(
        DetectionFeedback.tenant_id == UUID(tenant_id),
    )

    if feedback_type:
        query = query.where(DetectionFeedback.feedback_type == feedback_type)
    if framework:
        query = query.where(DetectionFeedback.framework == framework)

    query = query.order_by(DetectionFeedback.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    feedback_list = result.scalars().all()

    return [
        FeedbackResponse(
            id=f.id,
            detection_id=f.detection_id,
            is_correct=f.is_correct,
            feedback_type=f.feedback_type,
            detection_confidence=f.detection_confidence,
            detection_method=f.detection_method,
            framework=f.framework,
            reason=f.reason,
            severity_rating=f.severity_rating,
            created_at=f.created_at,
        )
        for f in feedback_list
    ]
