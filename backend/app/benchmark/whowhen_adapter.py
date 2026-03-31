"""Who&When Adapter for Pisama detectors.

Converts Who&When multi-agent conversation logs into the input
format expected by Pisama detection algorithms.

Each Who&When case is a conversation between agents (WebSurfer, Coder,
FileSurfer, Orchestrator, human). The adapter extracts detector-specific
inputs from each case, then attributes detections back to specific agents
and step indices for the Who&When evaluation protocol.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.benchmark.whowhen_loader import WhoWhenCase, WhoWhenMessage

logger = logging.getLogger(__name__)


@dataclass
class AgentEvidence:
    """Evidence pointing to a specific agent at a specific step."""

    agent: str
    step_index: int
    detector: str
    confidence: float
    explanation: str = ""


@dataclass
class CaseDetectionResult:
    """All detection results for a single Who&When case."""

    case_id: str
    evidence: List[AgentEvidence] = field(default_factory=list)

    @property
    def best_evidence(self) -> Optional[AgentEvidence]:
        """Return the best evidence for attribution.

        Strategy: among high-confidence evidence (>= 0.7), prefer the
        earliest step (root cause). Among equal steps, prefer highest
        confidence. This favors root cause over downstream effects.
        """
        if not self.evidence:
            return None

        # Filter to high-confidence evidence
        high_conf = [e for e in self.evidence if e.confidence >= 0.7]
        if not high_conf:
            high_conf = self.evidence

        # Sort by step (ascending) then confidence (descending)
        high_conf.sort(key=lambda e: (e.step_index, -e.confidence))
        return high_conf[0]


class WhoWhenAdapter:
    """Converts Who&When cases to Pisama detector inputs and attributes results.

    For each case, runs all applicable detectors and collects evidence
    about which agent caused the failure and when.
    """

    def __init__(self):
        self._detector_runners = self._build_detector_runners()

    def _build_detector_runners(self) -> Dict[str, Any]:
        """Build mapping of detector types to runner callables.

        Each runner has signature:
            (case: WhoWhenCase) -> List[AgentEvidence]
        """
        runners: Dict[str, Any] = {}

        # --- COORDINATION ---
        try:
            from app.detection.coordination import CoordinationAnalyzer, Message

            analyzer = CoordinationAnalyzer()

            def _run_coordination(case: WhoWhenCase) -> List[AgentEvidence]:
                messages, agent_ids = _build_coordination_input(case)
                if len(messages) < 2:
                    return []

                coord_msgs = []
                for i, m in enumerate(messages):
                    receiver = "unknown"
                    for j in range(i + 1, min(i + 3, len(messages))):
                        if messages[j]["sender"] != m["sender"]:
                            receiver = messages[j]["sender"]
                            break
                    coord_msgs.append(Message(
                        from_agent=m["sender"],
                        to_agent=receiver,
                        content=m["content"],
                        timestamp=float(i),
                    ))

                result = analyzer.analyze_coordination(coord_msgs, agent_ids)
                evidence = []
                for issue in result.issues:
                    if issue.severity in ("high", "critical"):
                        # Find the earliest agent involved
                        agent = issue.agents_involved[0] if issue.agents_involved else "unknown"
                        step = _find_agent_step(case, agent)
                        evidence.append(AgentEvidence(
                            agent=agent,
                            step_index=step,
                            detector="coordination",
                            confidence=0.7 if issue.severity == "critical" else 0.5,
                            explanation=issue.message,
                        ))
                return evidence

            runners["coordination"] = _run_coordination
        except Exception as exc:
            logger.warning("Could not import coordination detector: %s", exc)

        # --- COMMUNICATION ---
        try:
            from app.detection.communication import CommunicationBreakdownDetector

            comm_det = CommunicationBreakdownDetector()

            def _run_communication(case: WhoWhenCase) -> List[AgentEvidence]:
                evidence = []
                # Check consecutive message pairs between different agents
                for i in range(len(case.history) - 1):
                    sender = case.history[i]
                    receiver = case.history[i + 1]
                    if sender.role == receiver.role:
                        continue
                    if sender.role == "human" or receiver.role == "human":
                        continue
                    if not sender.content.strip() or not receiver.content.strip():
                        continue

                    result = comm_det.detect(
                        sender_message=sender.content[:4000],
                        receiver_response=receiver.content[:4000],
                        sender_name=sender.role,
                        receiver_name=receiver.role,
                    )
                    if result.detected:
                        evidence.append(AgentEvidence(
                            agent=receiver.role,
                            step_index=receiver.step_index,
                            detector="communication",
                            confidence=result.confidence,
                            explanation=result.explanation,
                        ))
                return evidence

            runners["communication"] = _run_communication
        except Exception as exc:
            logger.warning("Could not import communication detector: %s", exc)

        # --- DERAILMENT ---
        try:
            from app.detection.derailment import TaskDerailmentDetector

            derail_det = TaskDerailmentDetector()

            def _run_derailment(case: WhoWhenCase) -> List[AgentEvidence]:
                evidence = []
                task = case.question
                if not task:
                    return evidence

                for msg in case.history:
                    if msg.role == "human":
                        continue
                    if not msg.content.strip() or len(msg.content) < 20:
                        continue

                    result = derail_det.detect(
                        task=task[:4000],
                        output=msg.content[:4000],
                        agent_name=msg.role,
                    )
                    if result.detected:
                        evidence.append(AgentEvidence(
                            agent=msg.role,
                            step_index=msg.step_index,
                            detector="derailment",
                            confidence=result.confidence,
                            explanation=result.explanation,
                        ))
                return evidence

            runners["derailment"] = _run_derailment
        except Exception as exc:
            logger.warning("Could not import derailment detector: %s", exc)

        # --- LOOP ---
        try:
            from app.detection.loop import loop_detector, StateSnapshot

            def _run_loop(case: WhoWhenCase) -> List[AgentEvidence]:
                evidence = []
                states = []
                for msg in case.history:
                    if msg.role == "human":
                        continue
                    states.append(StateSnapshot(
                        agent_id=msg.role,
                        content=msg.content[:2000],
                        state_delta={},
                        sequence_num=msg.step_index,
                    ))

                if len(states) < 3:
                    return evidence

                result = loop_detector.detect_loop(states)
                if result.detected:
                    # Attribute to the agent with most repeated content
                    agent_counts: Dict[str, int] = {}
                    for s in states:
                        agent_counts[s.agent_id] = agent_counts.get(s.agent_id, 0) + 1
                    top_agent = max(agent_counts, key=agent_counts.get)  # type: ignore[arg-type]
                    step = _find_agent_step(case, top_agent)
                    evidence.append(AgentEvidence(
                        agent=top_agent,
                        step_index=step,
                        detector="loop",
                        confidence=result.confidence,
                        explanation="Repetitive pattern detected",
                    ))
                return evidence

            runners["loop"] = _run_loop
        except Exception as exc:
            logger.warning("Could not import loop detector: %s", exc)

        # --- CONTEXT ---
        try:
            from app.detection.context import ContextNeglectDetector

            ctx_det = ContextNeglectDetector()

            def _run_context(case: WhoWhenCase) -> List[AgentEvidence]:
                evidence = []
                # Build accumulated context from conversation
                context_parts: List[str] = []
                for msg in case.history:
                    if msg.role == "human":
                        context_parts.append(msg.content[:2000])
                        continue

                    if not msg.content.strip() or len(msg.content) < 20:
                        context_parts.append(msg.content[:2000])
                        continue

                    # Context is everything before this message
                    context = "\n".join(context_parts[-5:])  # Last 5 messages
                    if len(context) < 50:
                        context_parts.append(msg.content[:2000])
                        continue

                    result = ctx_det.detect(
                        context=context[:4000],
                        output=msg.content[:4000],
                        agent_name=msg.role,
                    )
                    if result.detected:
                        evidence.append(AgentEvidence(
                            agent=msg.role,
                            step_index=msg.step_index,
                            detector="context",
                            confidence=result.confidence,
                            explanation=result.explanation,
                        ))

                    context_parts.append(msg.content[:2000])
                return evidence

            runners["context"] = _run_context
        except Exception as exc:
            logger.warning("Could not import context detector: %s", exc)

        # --- HALLUCINATION ---
        try:
            from app.detection.hallucination import (
                hallucination_detector,
                SourceDocument,
            )

            def _run_hallucination(case: WhoWhenCase) -> List[AgentEvidence]:
                evidence = []
                # Build sources from prior messages and the question
                source_texts: List[str] = [case.question]
                if case.ground_truth:
                    source_texts.append(case.ground_truth)

                for msg in case.history:
                    if msg.role == "human":
                        source_texts.append(msg.content[:2000])
                        continue

                    if not msg.content.strip() or len(msg.content) < 30:
                        source_texts.append(msg.content[:2000])
                        continue

                    sources = [
                        SourceDocument(content=s, metadata={})
                        for s in source_texts[-5:]  # Last 5 sources
                        if s.strip()
                    ]
                    if not sources:
                        source_texts.append(msg.content[:2000])
                        continue

                    result = hallucination_detector.detect_hallucination(
                        msg.content[:4000], sources
                    )
                    if result.detected:
                        evidence.append(AgentEvidence(
                            agent=msg.role,
                            step_index=msg.step_index,
                            detector="hallucination",
                            confidence=result.confidence,
                            explanation="Hallucination detected in agent output",
                        ))

                    source_texts.append(msg.content[:2000])
                return evidence

            runners["hallucination"] = _run_hallucination
        except Exception as exc:
            logger.warning("Could not import hallucination detector: %s", exc)

        logger.info(
            "Loaded %d Who&When detector runners: %s",
            len(runners), ", ".join(sorted(runners.keys())),
        )
        return runners

    @property
    def available_detectors(self) -> List[str]:
        return sorted(self._detector_runners.keys())

    def detect_case(self, case: WhoWhenCase) -> CaseDetectionResult:
        """Run all available detectors on a single Who&When case.

        Returns CaseDetectionResult with all evidence collected.
        """
        result = CaseDetectionResult(case_id=case.case_id)

        for det_name, runner in self._detector_runners.items():
            try:
                evidence_list = runner(case)
                result.evidence.extend(evidence_list)
            except Exception as exc:
                logger.debug(
                    "Detector %s failed on case %s: %s",
                    det_name, case.case_id, exc,
                )

        return result


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _build_coordination_input(
    case: WhoWhenCase,
) -> Tuple[List[Dict[str, str]], List[str]]:
    """Build coordination detector input from a Who&When case."""
    messages = []
    agent_ids_set: Dict[str, bool] = {}

    for msg in case.history:
        if msg.role == "human":
            continue
        messages.append({
            "sender": msg.role,
            "content": msg.content[:2000],
            "step_index": str(msg.step_index),
        })
        agent_ids_set[msg.role] = True

    return messages, list(agent_ids_set.keys())


def _find_agent_step(case: WhoWhenCase, agent: str) -> int:
    """Find the first step index where an agent appears in the history."""
    for msg in case.history:
        if msg.role == agent:
            return msg.step_index
    return 0
