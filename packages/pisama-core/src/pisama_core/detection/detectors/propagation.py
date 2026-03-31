"""Error propagation detector for tracking silent fact corruption across pipeline steps."""

import re
from typing import Any

from pisama_core.detection.base import BaseDetector
from pisama_core.detection.result import DetectionResult, FixType
from pisama_core.traces.models import Trace, Span
from pisama_core.traces.enums import SpanKind


# Patterns for extracting structured facts from text
_NUMBER_PATTERN = re.compile(
    r"(?:(?:[$€£¥])\s?[\d,]+(?:\.\d+)?)|"     # Currency values
    r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|"       # Dates
    r"(?:\d+(?:\.\d+)?%)|"                        # Percentages
    r"(?:\b\d[\d,]*(?:\.\d+)?\b)"                 # Plain numbers
)

_URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+|www\.[^\s<>\"']+"
)

_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# Words that signal an intentional update rather than silent corruption
_UPDATE_SIGNALS = frozenset({
    "corrected", "correction", "updated", "revised", "amendment",
    "actually", "instead", "rather", "fixed", "recalculated",
    "adjustment", "adjusted", "modified", "changed to",
})


def _extract_facts(text: str) -> dict[str, list[str]]:
    """Extract verifiable facts from text.

    Returns a dict mapping fact category to list of fact values.
    """
    if not text:
        return {}

    facts: dict[str, list[str]] = {}

    numbers = _NUMBER_PATTERN.findall(text)
    if numbers:
        facts["numbers"] = [n.strip() for n in numbers]

    urls = _URL_PATTERN.findall(text)
    if urls:
        facts["urls"] = urls

    emails = _EMAIL_PATTERN.findall(text)
    if emails:
        facts["emails"] = emails

    # Extract named entities: capitalized multi-word sequences
    names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)
    if names:
        facts["names"] = names

    return facts


def _has_update_signal(text: str) -> bool:
    """Check whether text contains language signaling an intentional correction."""
    text_lower = text.lower()
    return any(signal in text_lower for signal in _UPDATE_SIGNALS)


def _normalize_number(raw: str) -> str:
    """Normalize a number string for comparison (strip currency, commas)."""
    return re.sub(r"[,$€£¥%\s]", "", raw)


class ErrorPropagationDetector(BaseDetector):
    """Detects silent error propagation across pipeline steps.

    Tracks key facts (numbers, names, dates, URLs) through sequential spans
    and flags when a fact from step N is contradicted or silently dropped
    in step N+2 or later.

    Distinguishes from legitimate updates by checking for explicit
    correction language.
    """

    name = "propagation"
    description = "Detects silent error propagation and fact corruption across pipeline steps"
    version = "1.0.0"
    platforms = []  # All platforms
    severity_range = (30, 80)
    realtime_capable = False

    # A fact must survive at least this many steps before a contradiction counts
    min_propagation_gap = 2

    async def detect(self, trace: Trace) -> DetectionResult:
        """Detect error propagation in a trace."""
        # Work with sequential processing spans (agent turns, tasks, chains)
        processing_kinds = {SpanKind.AGENT_TURN, SpanKind.TASK, SpanKind.CHAIN, SpanKind.AGENT}
        processing_spans = [
            s for s in trace.spans if s.kind in processing_kinds
        ]

        if len(processing_spans) < 3:
            return DetectionResult.no_issue(self.name)

        sorted_spans = sorted(processing_spans, key=lambda s: s.start_time)

        issues: list[str] = []
        severity = 0
        evidence_data: dict[str, Any] = {}

        # --- Build fact registry through the pipeline ---
        contradictions = self._track_fact_propagation(sorted_spans)
        if contradictions:
            severity += self._score_contradictions(contradictions)
            worst = contradictions[0]
            issues.append(
                f"Fact contradiction: '{worst['original']}' became "
                f"'{worst['contradicted_by']}' (step {worst['original_step']} -> {worst['contradiction_step']})"
            )
            evidence_data["contradictions"] = contradictions[:10]

        # --- Check for silently dropped facts ---
        dropped = self._check_dropped_facts(sorted_spans)
        if dropped:
            severity += min(len(dropped) * 8, 30)
            issues.append(
                f"{len(dropped)} fact(s) silently dropped from pipeline output"
            )
            evidence_data["dropped_facts"] = dropped[:10]

        if not issues:
            return DetectionResult.no_issue(self.name)

        severity = max(self.severity_range[0], min(self.severity_range[1], severity))

        result = DetectionResult.issue_found(
            detector_name=self.name,
            severity=severity,
            summary=issues[0],
            fix_type=FixType.ROLLBACK,
            fix_instruction=(
                "A fact was silently corrupted or dropped during pipeline processing. "
                "Review the intermediate outputs and either correct the error or "
                "explicitly acknowledge the change."
            ),
        )

        for issue in issues:
            result.add_evidence(
                description=issue,
                span_ids=[s.span_id for s in sorted_spans[:10]],
                data=evidence_data,
            )

        return result

    def _get_span_output_text(self, span: Span) -> str:
        """Extract output text from a span."""
        parts: list[str] = []
        if span.output_data:
            for key in ("output", "result", "response", "text", "content", "answer"):
                val = span.output_data.get(key)
                if isinstance(val, str):
                    parts.append(val)
            # Fallback: stringify the entire output_data if no standard keys
            if not parts:
                parts.append(str(span.output_data))
        return " ".join(parts)

    def _track_fact_propagation(
        self, spans: list[Span]
    ) -> list[dict[str, Any]]:
        """Track facts across pipeline steps and find contradictions."""
        # fact_value -> (normalized_value, first_seen_step, category)
        fact_registry: dict[str, tuple[str, int, str]] = {}
        contradictions: list[dict[str, Any]] = []

        for step_idx, span in enumerate(spans):
            output_text = self._get_span_output_text(span)
            if not output_text:
                continue

            has_update = _has_update_signal(output_text)
            facts = _extract_facts(output_text)

            for category, values in facts.items():
                for value in values:
                    normalized = _normalize_number(value) if category == "numbers" else value.lower()

                    if category == "numbers":
                        # Check if any previously registered number is contradicted
                        for reg_val, (reg_norm, reg_step, reg_cat) in list(fact_registry.items()):
                            if reg_cat != "numbers":
                                continue
                            if step_idx - reg_step < self.min_propagation_gap:
                                continue
                            # Same magnitude range but different value suggests corruption
                            if (
                                reg_norm != normalized
                                and self._same_magnitude(reg_norm, normalized)
                                and not has_update
                            ):
                                contradictions.append({
                                    "category": category,
                                    "original": reg_val,
                                    "contradicted_by": value,
                                    "original_step": reg_step,
                                    "contradiction_step": step_idx,
                                    "span_id": span.span_id,
                                })

                    # Register the fact (first occurrence wins)
                    if normalized not in {
                        v[0] for v in fact_registry.values()
                    }:
                        fact_registry[value] = (normalized, step_idx, category)

        # Sort by severity: larger propagation gaps are worse
        contradictions.sort(
            key=lambda c: c["contradiction_step"] - c["original_step"],
            reverse=True,
        )
        return contradictions

    def _check_dropped_facts(
        self, spans: list[Span]
    ) -> list[dict[str, Any]]:
        """Check if facts from early steps are absent in the final output."""
        if len(spans) < 3:
            return []

        # Collect facts from the first third of the pipeline
        early_cutoff = max(1, len(spans) // 3)
        early_facts: dict[str, tuple[str, int]] = {}

        for step_idx in range(early_cutoff):
            text = self._get_span_output_text(spans[step_idx])
            facts = _extract_facts(text)
            for category, values in facts.items():
                for value in values:
                    key = f"{category}:{value}"
                    if key not in early_facts:
                        early_facts[key] = (value, step_idx)

        if not early_facts:
            return []

        # Check the last span's output for presence of early facts
        final_text = self._get_span_output_text(spans[-1])
        if not final_text:
            return []

        final_lower = final_text.lower()
        dropped: list[dict[str, Any]] = []

        for key, (value, step_idx) in early_facts.items():
            category = key.split(":")[0]
            search_val = value.lower() if category != "numbers" else _normalize_number(value)

            # For numbers, search the normalized form
            if category == "numbers":
                final_numbers = [_normalize_number(n) for n in _NUMBER_PATTERN.findall(final_text)]
                if search_val not in final_numbers:
                    dropped.append({
                        "category": category,
                        "value": value,
                        "first_seen_step": step_idx,
                    })
            else:
                if search_val not in final_lower:
                    dropped.append({
                        "category": category,
                        "value": value,
                        "first_seen_step": step_idx,
                    })

        return dropped

    @staticmethod
    def _same_magnitude(a: str, b: str) -> bool:
        """Check if two number strings are in the same order of magnitude.

        This helps distinguish a genuine contradiction (100 vs 150)
        from unrelated numbers (5 vs 50000).
        """
        try:
            fa, fb = float(a), float(b)
        except ValueError:
            return False
        if fa == 0 or fb == 0:
            return False
        ratio = max(fa, fb) / min(fa, fb)
        return ratio < 10  # Within one order of magnitude

    def _score_contradictions(self, contradictions: list[dict[str, Any]]) -> int:
        """Score the severity of contradictions."""
        if not contradictions:
            return 0
        # Base: 30 for first contradiction, +10 per additional, cap at 60
        return min(30 + (len(contradictions) - 1) * 10, 60)
