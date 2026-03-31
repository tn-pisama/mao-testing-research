"""Critic quality detector for identifying rubber-stamping critics in reflection loops."""

import re
from typing import Any

from pisama_core.detection.base import BaseDetector
from pisama_core.detection.result import DetectionResult, FixType
from pisama_core.traces.models import Trace, Span
from pisama_core.traces.enums import SpanKind


# Keywords that indicate a critic/evaluator role
_CRITIC_KEYWORDS = frozenset({
    "review", "evaluate", "critic", "feedback", "judge", "assess",
    "validate", "check", "verify", "approve", "score", "rate", "grade",
    "qa", "quality", "audit",
})

# Keywords that indicate a producer role
_PRODUCER_KEYWORDS = frozenset({
    "write", "generate", "create", "draft", "compose", "produce",
    "build", "implement", "code", "design", "author", "synthesize",
})

# Approval indicators in critic output
_APPROVAL_PATTERNS = [
    re.compile(r"\bapprov(?:ed|es|al)\b", re.IGNORECASE),
    re.compile(r"\blooks?\s+good\b", re.IGNORECASE),
    re.compile(r"\bno\s+(?:issues?|problems?|concerns?)\b", re.IGNORECASE),
    re.compile(r"\blgtm\b", re.IGNORECASE),
    re.compile(r"\bwell\s+done\b", re.IGNORECASE),
    re.compile(r"\baccept(?:ed|able)?\b", re.IGNORECASE),
    re.compile(r"\bpass(?:es|ed)?\b", re.IGNORECASE),
    re.compile(r"\bsatisf(?:ied|actory|ies)\b", re.IGNORECASE),
    re.compile(r"\bready\s+(?:for|to)\b", re.IGNORECASE),
]

# Incomplete/placeholder markers in producer output
_INCOMPLETE_MARKERS = [
    re.compile(r"\bTODO\b"),
    re.compile(r"\bFIXME\b"),
    re.compile(r"\bHACK\b"),
    re.compile(r"\bXXX\b"),
    re.compile(r"\bplaceholder\b", re.IGNORECASE),
    re.compile(r"\bTBD\b"),
    re.compile(r"\blorem\s+ipsum\b", re.IGNORECASE),
    re.compile(r"\b\[.*?insert.*?\]", re.IGNORECASE),
    re.compile(r"\b\[.*?fill.*?\]", re.IGNORECASE),
    re.compile(r"\.{3,}"),  # Ellipsis as placeholder
]


def _is_critic_span(span: Span) -> bool:
    """Check whether a span represents a critic/evaluator role."""
    name_lower = span.name.lower()
    return any(kw in name_lower for kw in _CRITIC_KEYWORDS)


def _is_producer_span(span: Span) -> bool:
    """Check whether a span represents a producer role."""
    name_lower = span.name.lower()
    if any(kw in name_lower for kw in _PRODUCER_KEYWORDS):
        return True
    # If not explicitly a critic, treat agent spans as potential producers
    return not _is_critic_span(span)


def _get_output_text(span: Span) -> str:
    """Extract output text from a span."""
    parts: list[str] = []
    if span.output_data:
        for key in ("output", "result", "response", "text", "content",
                     "feedback", "review", "evaluation"):
            val = span.output_data.get(key)
            if isinstance(val, str):
                parts.append(val)
        if not parts:
            parts.append(str(span.output_data))
    return " ".join(parts)


def _has_approval(text: str) -> bool:
    """Check if text contains approval language."""
    return any(pat.search(text) for pat in _APPROVAL_PATTERNS)


def _has_incomplete_markers(text: str) -> list[str]:
    """Find incomplete/placeholder markers in text."""
    found: list[str] = []
    for pat in _INCOMPLETE_MARKERS:
        match = pat.search(text)
        if match:
            found.append(match.group())
    return found


def _word_level_diff_ratio(text_a: str, text_b: str) -> float:
    """Compute word-level difference ratio between two texts.

    Returns 0.0 for identical texts, 1.0 for completely different texts.
    """
    if not text_a and not text_b:
        return 0.0
    if not text_a or not text_b:
        return 1.0

    words_a = text_a.lower().split()
    words_b = text_b.lower().split()

    if not words_a and not words_b:
        return 0.0

    # Use set-based Jaccard distance for efficiency
    set_a = set(words_a)
    set_b = set(words_b)
    union = set_a | set_b
    if not union:
        return 0.0

    intersection = set_a & set_b
    return 1.0 - (len(intersection) / len(union))


class CriticQualityDetector(BaseDetector):
    """Detects rubber-stamping critics in reflection loops.

    This detector identifies:
    - Critics that approve without requesting meaningful changes
    - Critics that approve when producer output barely changed between iterations
    - Critics that approve output containing TODO/FIXME/placeholder markers
    """

    name = "critic_quality"
    description = "Detects rubber-stamping critics in reflection loops"
    version = "1.0.0"
    platforms = []  # All platforms
    severity_range = (20, 60)
    realtime_capable = False

    # A diff ratio below this means the producer barely changed their output
    min_meaningful_change = 0.10
    # Minimum number of reflection iterations to analyze
    min_iterations = 2

    async def detect(self, trace: Trace) -> DetectionResult:
        """Detect rubber-stamping critics in reflection loops."""
        agent_spans = trace.get_spans_by_kind(SpanKind.AGENT)
        turn_spans = trace.get_spans_by_kind(SpanKind.AGENT_TURN)
        all_candidates = agent_spans + turn_spans

        if len(all_candidates) < 3:
            return DetectionResult.no_issue(self.name)

        sorted_spans = sorted(all_candidates, key=lambda s: s.start_time)

        issues: list[str] = []
        severity = 0
        evidence_data: dict[str, Any] = {}

        # --- Identify critic-producer pairs ---
        reflection_pairs = self._find_reflection_pairs(sorted_spans)
        if not reflection_pairs:
            return DetectionResult.no_issue(self.name)

        # --- Check 1: Rubber-stamping (approve with minimal change) ---
        rubber_stamp = self._check_rubber_stamping(reflection_pairs)
        if rubber_stamp:
            severity += rubber_stamp["severity"]
            issues.append(rubber_stamp["summary"])
            evidence_data["rubber_stamping"] = rubber_stamp["details"]

        # --- Check 2: Weak critic (approve despite incomplete markers) ---
        weak_critic = self._check_weak_critic(reflection_pairs)
        if weak_critic:
            severity += weak_critic["severity"]
            issues.append(weak_critic["summary"])
            evidence_data["weak_critic"] = weak_critic["details"]

        if not issues:
            return DetectionResult.no_issue(self.name)

        severity = max(self.severity_range[0], min(self.severity_range[1], severity))

        result = DetectionResult.issue_found(
            detector_name=self.name,
            severity=severity,
            summary=issues[0],
            fix_type=FixType.ESCALATE,
            fix_instruction=(
                "The critic/evaluator appears to be rubber-stamping. "
                "Review the evaluation criteria and ensure the critic provides "
                "substantive feedback before approving."
            ),
        )

        span_ids = []
        for pair in reflection_pairs[:5]:
            span_ids.append(pair["critic"].span_id)
            if pair.get("producer"):
                span_ids.append(pair["producer"].span_id)

        for issue in issues:
            result.add_evidence(
                description=issue,
                span_ids=span_ids,
                data=evidence_data,
            )

        return result

    def _find_reflection_pairs(
        self, spans: list[Span]
    ) -> list[dict[str, Any]]:
        """Find producer-critic pairs in the span sequence.

        A reflection pair is a critic span that follows a producer span
        (possibly with some spans in between).
        """
        pairs: list[dict[str, Any]] = []
        last_producer: Span | None = None
        last_producer_output: str = ""

        for span in spans:
            if _is_critic_span(span):
                critic_output = _get_output_text(span)
                pair: dict[str, Any] = {
                    "critic": span,
                    "critic_output": critic_output,
                    "producer": last_producer,
                    "producer_output": last_producer_output,
                }
                pairs.append(pair)
            elif _is_producer_span(span):
                output = _get_output_text(span)
                if output:
                    last_producer = span
                    last_producer_output = output

        return pairs

    def _check_rubber_stamping(
        self, pairs: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Check if critic approves when producer output barely changed."""
        if len(pairs) < self.min_iterations:
            return None

        rubber_stamp_count = 0
        details: list[dict[str, Any]] = []

        # Compare consecutive producer outputs across reflection iterations
        previous_producer_output = ""
        for pair in pairs:
            critic_output = pair["critic_output"]
            producer_output = pair["producer_output"]

            if not critic_output:
                continue

            approved = _has_approval(critic_output)
            if not approved:
                previous_producer_output = producer_output
                continue

            # If we have a previous producer output, check if it changed
            if previous_producer_output and producer_output:
                diff = _word_level_diff_ratio(previous_producer_output, producer_output)
                if diff < self.min_meaningful_change:
                    rubber_stamp_count += 1
                    details.append({
                        "critic_span_id": pair["critic"].span_id,
                        "diff_ratio": round(diff, 3),
                        "approved": True,
                    })

            previous_producer_output = producer_output

        if rubber_stamp_count == 0:
            return None

        sev = 20 + rubber_stamp_count * 15

        return {
            "severity": min(sev, 45),
            "summary": (
                f"Critic rubber-stamped {rubber_stamp_count} time(s) "
                f"(approved with <{self.min_meaningful_change:.0%} producer change)"
            ),
            "details": details,
        }

    def _check_weak_critic(
        self, pairs: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Check if critic approves output with incomplete markers."""
        weak_approvals: list[dict[str, Any]] = []

        for pair in pairs:
            critic_output = pair["critic_output"]
            producer_output = pair["producer_output"]

            if not critic_output or not producer_output:
                continue

            approved = _has_approval(critic_output)
            if not approved:
                continue

            markers = _has_incomplete_markers(producer_output)
            if markers:
                weak_approvals.append({
                    "critic_span_id": pair["critic"].span_id,
                    "markers_found": markers,
                })

        if not weak_approvals:
            return None

        total_markers = sum(len(w["markers_found"]) for w in weak_approvals)
        sev = 20 + min(total_markers * 5, 30)

        return {
            "severity": min(sev, 40),
            "summary": (
                f"Critic approved output with {total_markers} incomplete marker(s) "
                f"({', '.join(weak_approvals[0]['markers_found'][:3])})"
            ),
            "details": weak_approvals,
        }
