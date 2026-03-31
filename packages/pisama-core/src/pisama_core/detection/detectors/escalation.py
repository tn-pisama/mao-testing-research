"""Escalation loop detector for identifying unresolved escalation cycles."""

from collections import Counter
from typing import Any

from pisama_core.detection.base import BaseDetector
from pisama_core.detection.result import DetectionResult, FixType
from pisama_core.traces.models import Trace, Span
from pisama_core.traces.enums import SpanKind


def _get_output_text(span: Span) -> str:
    """Extract output text from a span."""
    parts: list[str] = []
    if span.output_data:
        for key in ("output", "result", "response", "text", "content"):
            val = span.output_data.get(key)
            if isinstance(val, str):
                parts.append(val)
    return " ".join(parts)


def _text_similarity(text_a: str, text_b: str) -> float:
    """Compute word-level Jaccard similarity between two texts.

    Returns 0.0 for no overlap, 1.0 for identical word sets.
    """
    if not text_a or not text_b:
        return 0.0
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    union = words_a | words_b
    if not union:
        return 0.0
    return len(words_a & words_b) / len(union)


def _extract_handoff_direction(span: Span) -> tuple[str, str]:
    """Extract source and target from a handoff span.

    Looks in attributes first, then falls back to parsing the span name.
    """
    source = span.attributes.get("source_agent", "")
    target = span.attributes.get("target_agent", "")

    if source and target:
        return (source, target)

    # Fallback: try to parse from span name (e.g., "handoff:agentA->agentB")
    name = span.name.lower()
    for sep in ("->", "→", " to ", "=>"):
        if sep in name:
            parts = name.split(sep, 1)
            return (parts[0].strip(), parts[1].strip())

    # Last resort: use input/output attributes
    source = span.attributes.get("from", span.attributes.get("sender", ""))
    target = span.attributes.get("to", span.attributes.get("receiver", ""))

    return (source or span.name, target or "unknown")


class EscalationLoopDetector(BaseDetector):
    """Detects escalation loops where agents escalate without resolution.

    This detector identifies:
    - Round-trip escalations: agent escalates to supervisor, gets sent back,
      escalates again without progress
    - Approval shopping: same issue escalated to 3+ different handlers
    """

    name = "escalation_loop"
    description = "Detects unresolved escalation loops between agents"
    version = "1.0.0"
    platforms = []  # All platforms
    severity_range = (30, 75)
    realtime_capable = False

    # Thresholds
    max_round_trips = 2
    max_unique_handlers = 3
    # Output similarity above this threshold means no progress was made
    stale_output_threshold = 0.70

    async def detect(self, trace: Trace) -> DetectionResult:
        """Detect escalation loops in a trace."""
        handoff_spans = trace.get_spans_by_kind(SpanKind.HANDOFF)

        if len(handoff_spans) < 3:
            return DetectionResult.no_issue(self.name)

        sorted_handoffs = sorted(handoff_spans, key=lambda s: s.start_time)

        issues: list[str] = []
        severity = 0
        evidence_data: dict[str, Any] = {}

        # --- Check 1: Round-trip escalation loops ---
        round_trip = self._check_round_trips(sorted_handoffs, trace)
        if round_trip:
            severity += round_trip["severity"]
            issues.append(round_trip["summary"])
            evidence_data["round_trips"] = round_trip["details"]

        # --- Check 2: Approval shopping ---
        shopping = self._check_approval_shopping(sorted_handoffs)
        if shopping:
            severity += shopping["severity"]
            issues.append(shopping["summary"])
            evidence_data["approval_shopping"] = shopping["details"]

        if not issues:
            return DetectionResult.no_issue(self.name)

        severity = max(self.severity_range[0], min(self.severity_range[1], severity))

        result = DetectionResult.issue_found(
            detector_name=self.name,
            severity=severity,
            summary=issues[0],
            fix_type=FixType.ESCALATE,
            fix_instruction=(
                "Escalation loop detected. The task is being passed back and forth "
                "without resolution. Intervene to clarify requirements or assign to "
                "a different handler with the right authority/capability."
            ),
        )

        for issue in issues:
            result.add_evidence(
                description=issue,
                span_ids=[s.span_id for s in sorted_handoffs[:10]],
                data=evidence_data,
            )

        return result

    def _check_round_trips(
        self,
        handoffs: list[Span],
        trace: Trace,
    ) -> dict[str, Any] | None:
        """Check for round-trip escalations between the same agent pair."""
        # Count directed edges between agent pairs
        pair_trips: dict[tuple[str, str], list[Span]] = {}
        for span in handoffs:
            source, target = _extract_handoff_direction(span)
            if not source or not target:
                continue
            pair = (source, target)
            pair_trips.setdefault(pair, []).append(span)

        # Find round-trips: A->B and B->A both exist with enough occurrences
        flagged_pairs: list[dict[str, Any]] = []
        seen_pairs: set[frozenset[str]] = set()

        for (source, target), forward_spans in pair_trips.items():
            pair_key = frozenset([source, target])
            if pair_key in seen_pairs:
                continue

            reverse_spans = pair_trips.get((target, source), [])
            round_trips = min(len(forward_spans), len(reverse_spans))

            if round_trips <= self.max_round_trips:
                continue

            seen_pairs.add(pair_key)

            # Check if task is progressing by comparing outputs around handoffs
            stale = self._check_staleness(forward_spans + reverse_spans, trace)

            if stale:
                flagged_pairs.append({
                    "source": source,
                    "target": target,
                    "round_trips": round_trips,
                    "stale": True,
                })

        if not flagged_pairs:
            return None

        worst = max(flagged_pairs, key=lambda p: p["round_trips"])
        sev = 30 + (worst["round_trips"] - self.max_round_trips) * 10

        return {
            "severity": min(sev, 55),
            "summary": (
                f"Escalation loop: {worst['source']} <-> {worst['target']} "
                f"({worst['round_trips']} round-trips without progress)"
            ),
            "details": flagged_pairs,
        }

    def _check_staleness(
        self,
        handoff_spans: list[Span],
        trace: Trace,
    ) -> bool:
        """Check if the outputs around handoff spans are stale (not progressing).

        Looks at agent/task spans that are siblings or children of the handoff
        spans' parents to check output similarity.
        """
        sorted_spans = sorted(handoff_spans, key=lambda s: s.start_time)
        outputs: list[str] = []

        for span in sorted_spans:
            # Get the handoff's own output or its parent's output
            text = _get_output_text(span)
            if not text and span.parent_id:
                parent = trace.get_span(span.parent_id)
                if parent:
                    text = _get_output_text(parent)
            if text:
                outputs.append(text)

        if len(outputs) < 2:
            # Not enough data to assess; assume stale to be cautious
            return True

        # Compare consecutive outputs
        stale_count = 0
        for i in range(1, len(outputs)):
            sim = _text_similarity(outputs[i - 1], outputs[i])
            if sim >= self.stale_output_threshold:
                stale_count += 1

        # If majority of transitions are stale, flag it
        return stale_count >= len(outputs) // 2

    def _check_approval_shopping(
        self,
        handoffs: list[Span],
    ) -> dict[str, Any] | None:
        """Check if the same source escalates to many different targets."""
        # Group by source agent
        source_targets: dict[str, list[str]] = {}
        for span in handoffs:
            source, target = _extract_handoff_direction(span)
            if not source or not target:
                continue
            source_targets.setdefault(source, []).append(target)

        flagged: list[dict[str, Any]] = []
        for source, targets in source_targets.items():
            unique_targets = set(targets)
            if len(unique_targets) >= self.max_unique_handlers:
                flagged.append({
                    "source": source,
                    "unique_targets": sorted(unique_targets),
                    "total_handoffs": len(targets),
                })

        if not flagged:
            return None

        worst = max(flagged, key=lambda f: len(f["unique_targets"]))
        sev = 25 + len(worst["unique_targets"]) * 8

        return {
            "severity": min(sev, 50),
            "summary": (
                f"Approval shopping: '{worst['source']}' escalated to "
                f"{len(worst['unique_targets'])} different handlers "
                f"({', '.join(worst['unique_targets'][:4])})"
            ),
            "details": flagged,
        }
