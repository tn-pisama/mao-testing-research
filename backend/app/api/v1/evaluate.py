"""Real-time evaluation endpoint — Pisama as the evaluator.

Replaces hand-built Playwright-based QA agents in multi-agent harnesses.
Receives a specification + generator output, runs relevant detectors,
returns pass/fail with specific failures and suggestions.

Reference: Anthropic "Harness Design for Long-Running Apps" (2026)
"""

import time
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evaluate", tags=["evaluate"])


# --- Request / Response schemas ---

class EvaluateRequest(BaseModel):
    specification: Dict[str, Any] = Field(
        ..., description="Sprint contract or task spec the output should satisfy"
    )
    output: Dict[str, Any] = Field(
        ..., description="Generator output to evaluate"
    )
    agent_role: str = Field(
        default="generator",
        description="Role of the agent that produced this output (generator/evaluator/planner)",
    )
    detectors: Optional[List[str]] = Field(
        default=None,
        description="Specific detectors to run (default: auto-select based on role)",
    )
    context_limit: Optional[int] = Field(
        default=None,
        description="Model context window size for pressure detection",
    )
    agent_judge: bool = Field(
        default=False,
        description="Use Agent-as-Judge for ambiguous detections (multi-step reasoning with tools)",
    )


class FailureDetail(BaseModel):
    detector: str
    confidence: float
    severity: str
    title: str
    description: str
    suggested_fix: Optional[str] = None


class EvaluateResponse(BaseModel):
    passed: bool
    score: float  # 0.0-1.0 (1.0 = no issues)
    failures: List[FailureDetail]
    suggestions: List[str]
    detectors_run: List[str]
    evaluation_time_ms: int


# --- Detector selection by role ---

ROLE_DETECTORS = {
    "generator": ["specification", "completion", "hallucination", "corruption", "derailment", "context_pressure"],
    "evaluator": ["persona_drift", "hallucination"],
    "planner": ["decomposition", "specification"],
    "default": ["specification", "completion", "hallucination", "derailment"],
}


@router.post("", response_model=EvaluateResponse)
async def evaluate(
    request: EvaluateRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Evaluate generator output against a specification.

    Runs relevant Pisama detectors and returns a pass/fail verdict with
    specific failures and suggestions. Designed to be called from
    multi-agent harnesses as a drop-in evaluator.
    """
    start_ms = time.monotonic_ns() // 1_000_000

    # Select detectors
    if request.detectors:
        detector_names = request.detectors
    else:
        detector_names = ROLE_DETECTORS.get(request.agent_role, ROLE_DETECTORS["default"])

    # Build trace-like input for detectors
    spec = request.specification
    output = request.output

    # Extract text content for text-based detectors
    output_text = output.get("text", "") or output.get("content", "") or str(output)
    spec_text = spec.get("text", "") or spec.get("description", "") or str(spec)

    failures: List[FailureDetail] = []
    detectors_run: List[str] = []

    for det_name in detector_names:
        try:
            result = _run_single_detector(
                det_name, spec, output, output_text, spec_text,
                context_limit=request.context_limit,
            )
            if result:
                detectors_run.append(det_name)
                if result.get("detected"):
                    failures.append(FailureDetail(
                        detector=det_name,
                        confidence=result.get("confidence", 0.0),
                        severity=result.get("severity", "medium"),
                        title=result.get("title", f"{det_name} issue"),
                        description=result.get("description", ""),
                        suggested_fix=result.get("suggested_fix"),
                    ))
            else:
                detectors_run.append(det_name)
        except Exception as exc:
            logger.warning("Evaluator detector %s failed: %s", det_name, exc)
            detectors_run.append(det_name)

    # Agent-as-Judge: re-evaluate ambiguous detections with tiered LLM
    if request.agent_judge and failures:
        ambiguous = [f for f in failures if 0.30 <= f.confidence <= 0.75]
        if ambiguous:
            try:
                from app.detection.llm_judge.lightweight_judge import tiered_judge
                for failure in ambiguous:
                    verdict = tiered_judge(
                        detection_type=failure.detector,
                        input_data={"specification": spec, "output": output},
                        rule_confidence=failure.confidence,
                        max_tier="sonnet",  # Cap at Sonnet for evaluate API (cost control)
                    )
                    failure.confidence = verdict.confidence
                    if verdict.reasoning:
                        failure.description = f"{failure.description} [{verdict.tier_used}: {verdict.reasoning[:150]}]"
                # Remove failures that the judge downgraded below 0.2
                failures = [f for f in failures if f.confidence >= 0.2]
            except Exception as exc:
                logger.warning("Tiered judge failed: %s", exc)

    # Compute score
    if not failures:
        score = 1.0
    else:
        max_confidence = max(f.confidence for f in failures)
        score = max(0.0, 1.0 - max_confidence)

    elapsed_ms = (time.monotonic_ns() // 1_000_000) - start_ms

    return EvaluateResponse(
        passed=len(failures) == 0,
        score=round(score, 3),
        failures=failures,
        suggestions=[f.suggested_fix for f in failures if f.suggested_fix],
        detectors_run=detectors_run,
        evaluation_time_ms=elapsed_ms,
    )


def _run_single_detector(
    det_name: str,
    spec: Dict[str, Any],
    output: Dict[str, Any],
    output_text: str,
    spec_text: str,
    context_limit: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Run a single detector on the evaluate input. Returns a result dict."""

    if det_name == "specification":
        from app.detection.specification import SpecificationMismatchDetector
        detector = SpecificationMismatchDetector()
        result = detector.detect(
            task_specification=spec_text,
            user_intent=spec.get("user_intent", spec_text),
        )
        return {
            "detected": result.detected,
            "confidence": result.confidence,
            "severity": result.severity.value if hasattr(result.severity, 'value') else str(result.severity),
            "title": "Specification Mismatch",
            "description": "; ".join(result.missing_requirements[:3]) if result.missing_requirements else "Output doesn't match specification",
            "suggested_fix": "Review output against specification requirements",
        }

    elif det_name == "completion":
        from app.detection.completion import CompletionMisjudgmentDetector
        detector = CompletionMisjudgmentDetector()
        result = detector.detect(
            task=spec_text,
            subtasks=spec.get("subtasks", []),
            agent_output=output_text,
            success_criteria=spec.get("success_criteria", []),
        )
        return {
            "detected": result.detected,
            "confidence": result.confidence,
            "severity": result.severity.value if hasattr(result.severity, 'value') else str(result.severity),
            "title": "Completion Misjudgment",
            "description": "; ".join(i.description for i in result.issues) if result.issues else "Task completion assessment issue",
            "suggested_fix": "Verify all subtasks and success criteria are met",
        }

    elif det_name == "hallucination":
        from app.detection.hallucination import HallucinationDetector, SourceDocument
        detector = HallucinationDetector()
        sources = []
        if spec.get("sources"):
            sources = [SourceDocument(content=s) for s in spec["sources"]]
        elif spec_text:
            # Use spec text as implicit grounding source — but only when the output
            # is natural language (not code). Code outputs have many tokens that
            # legitimately don't appear in the spec.
            has_code = any(p in output_text for p in ["```", "def ", "import ", "print(", "return ", "function ", "class "])
            # Only use spec as source when:
            # 1. Output isn't code (code tokens legitimately differ from spec)
            # 2. Spec is substantial (>100 chars — short specs are poor sources)
            # 3. Output doesn't heavily overlap with spec (>40% overlap = grounded)
            import re as _re
            spec_words = set(w.lower() for w in _re.findall(r'[a-zA-Z]{3,}', spec_text))
            out_words = set(w.lower() for w in _re.findall(r'[a-zA-Z]{3,}', output_text))
            word_overlap = len(spec_words & out_words) / max(len(spec_words), 1)
            if not has_code and len(spec_text) > 100 and word_overlap < 0.4:
                sources = [SourceDocument(content=spec_text)]
        result = detector.detect_hallucination(
            output=output_text,
            sources=sources if sources else None,
        )
        return {
            "detected": result.detected,
            "confidence": result.confidence,
            "severity": "high" if result.confidence > 0.7 else "medium",
            "title": f"Hallucination: {result.hallucination_type}" if result.hallucination_type else "Hallucination",
            "description": "; ".join(result.evidence[:3]) if result.evidence else "Output contains ungrounded claims",
            "suggested_fix": "Verify claims against source material",
        }

    elif det_name == "derailment":
        from app.detection.derailment import TaskDerailmentDetector
        detector = TaskDerailmentDetector()
        result = detector.detect(
            task=spec_text,
            output=output_text,
        )
        return {
            "detected": result.detected,
            "confidence": result.confidence,
            "severity": result.severity.value if hasattr(result.severity, 'value') else str(result.severity),
            "title": "Task Derailment",
            "description": "; ".join(result.issues) if hasattr(result, 'issues') and result.issues else "Output drifts from task",
            "suggested_fix": "Refocus on the original task specification",
        }

    elif det_name == "corruption":
        from app.detection.corruption import SemanticCorruptionDetector
        detector = SemanticCorruptionDetector()
        prev_state = spec.get("previous_state", {})
        current_state = output
        if prev_state and current_state:
            result = detector.detect_corruption_with_confidence(prev_state, current_state)
            return {
                "detected": result.detected,
                "confidence": result.confidence,
                "severity": "high" if result.confidence > 0.7 else "medium",
                "title": "State Corruption",
                "description": f"{result.issue_count} corruption issues" if hasattr(result, 'issue_count') else "State corruption detected",
                "suggested_fix": "Restore from last known good state",
            }
        return None

    elif det_name == "persona_drift":
        from app.detection.persona import PersonaConsistencyScorer, Agent
        scorer = PersonaConsistencyScorer()
        persona_desc = spec.get("persona_description", "evaluator agent that rigorously reviews work")
        agent = Agent(
            id=spec.get("agent_id", "evaluator"),
            persona_description=persona_desc,
            allowed_actions=spec.get("allowed_actions", []),
        )
        result = scorer.score_consistency(agent=agent, output=output_text)
        return {
            "detected": result.drift_detected,
            "confidence": result.confidence,
            "severity": "high" if result.confidence > 0.7 else "medium",
            "title": "Persona Drift",
            "description": "; ".join(result.issues) if result.issues else "Agent drifted from expected behavior",
            "suggested_fix": "Reinforce agent role and evaluation criteria",
        }

    elif det_name == "context_pressure":
        from app.detection.context_pressure import ContextPressureDetector
        detector = ContextPressureDetector()
        states = output.get("states", [])
        if not states:
            # Build minimal states from output
            states = [{"sequence_num": 0, "token_count": len(output_text) // 4, "state_delta": output}]
        result = detector.detect(
            states=states,
            context_limit=context_limit,
        )
        return {
            "detected": result.detected,
            "confidence": result.confidence,
            "severity": result.severity.value,
            "title": "Context Pressure Degradation",
            "description": f"Context utilization: {result.context_utilization:.0%}; " + "; ".join(s.description for s in result.signals[:2]),
            "suggested_fix": "Implement context resets or summarization between sprints",
        }

    elif det_name == "decomposition":
        from app.detection.decomposition import TaskDecompositionDetector
        detector = TaskDecompositionDetector()
        result = detector.detect(
            task_description=spec_text,
            decomposition=output.get("decomposition", output_text),
        )
        return {
            "detected": result.detected,
            "confidence": result.confidence,
            "severity": "medium",
            "title": "Task Decomposition Issue",
            "description": "; ".join(i.value if hasattr(i, 'value') else str(i) for i in result.issues) if result.issues else "Decomposition issues found",
            "suggested_fix": "Review task breakdown for completeness and logical ordering",
        }

    return None
