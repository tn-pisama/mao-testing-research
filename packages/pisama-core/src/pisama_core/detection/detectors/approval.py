"""Approval bypass detector for high-risk actions without human approval."""

import re
from typing import Any

from pisama_core.detection.base import BaseDetector
from pisama_core.detection.result import DetectionResult, FixRecommendation, FixType
from pisama_core.traces.models import Trace, Span
from pisama_core.traces.enums import SpanKind, SpanStatus


class ApprovalBypassDetector(BaseDetector):
    """Detects high-risk actions taken without human approval.

    This detector identifies:
    - Dangerous tool calls (delete, deploy, transfer, etc.) without preceding approval
    - Multiple high-risk actions in rapid succession (batch danger)
    - Missing human-in-the-loop for destructive operations
    """

    name = "approval_bypass"
    description = "Detects high-risk actions taken without human approval"
    version = "1.0.0"
    platforms = []  # All platforms
    severity_range = (40, 90)
    realtime_capable = True

    # Number of preceding spans to search for approval
    approval_lookback = 5

    # Seconds threshold for "rapid succession" batch danger
    batch_window_seconds = 30.0

    # Default high-risk patterns
    HIGH_RISK_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"\bdelete\b", re.IGNORECASE),
        re.compile(r"\bdrop\b", re.IGNORECASE),
        re.compile(r"\brm\b", re.IGNORECASE),
        re.compile(r"\bremove\b", re.IGNORECASE),
        re.compile(r"\btransfer\b", re.IGNORECASE),
        re.compile(r"\bdeploy\b", re.IGNORECASE),
        re.compile(r"push\s+--force", re.IGNORECASE),
        re.compile(r"\bforce[\s-]push\b", re.IGNORECASE),
        re.compile(r"\bsend\s+email\b", re.IGNORECASE),
        re.compile(r"\bexecute\s+payment\b", re.IGNORECASE),
        re.compile(r"\bshutdown\b", re.IGNORECASE),
        re.compile(r"\bkill\b", re.IGNORECASE),
        re.compile(r"\btruncate\b", re.IGNORECASE),
        re.compile(r"\bformat\b", re.IGNORECASE),
        re.compile(r"\bpurge\b", re.IGNORECASE),
        re.compile(r"\brollback\b", re.IGNORECASE),
        re.compile(r"\brevoke\b", re.IGNORECASE),
    ]

    # Patterns that indicate approval was given
    APPROVAL_INDICATORS = [
        "approved", "confirmed", "yes, proceed", "go ahead",
        "authorize", "i confirm", "permission granted", "do it",
        "yes please", "affirmative", "acknowledged", "accept",
        "lgtm", "looks good", "ship it",
    ]

    async def detect(self, trace: Trace) -> DetectionResult:
        """Detect high-risk actions without approval."""
        tool_spans = trace.get_spans_by_kind(SpanKind.TOOL)
        if not tool_spans:
            return DetectionResult.no_issue(self.name)

        sorted_spans = sorted(trace.spans, key=lambda s: s.start_time)
        sorted_tools = sorted(tool_spans, key=lambda s: s.start_time)

        issues: list[str] = []
        severity = 0
        evidence_spans: list[str] = []
        unapproved_dangerous: list[Span] = []

        for tool_span in sorted_tools:
            risk = self._assess_risk(tool_span)
            if not risk:
                continue

            # Check if there's an approval before this span
            span_index = self._find_span_index(sorted_spans, tool_span)
            has_approval = self._check_approval_before(sorted_spans, span_index)

            if not has_approval:
                unapproved_dangerous.append(tool_span)
                issues.append(
                    f"High-risk action '{risk['matched_text']}' in tool "
                    f"'{tool_span.name}' without preceding approval"
                )
                evidence_spans.append(tool_span.span_id)
                severity += risk["severity_contribution"]

        # Check for batch danger: multiple high-risk actions in rapid succession
        batch_issues = self._check_batch_danger(unapproved_dangerous)
        if batch_issues:
            issues.append(batch_issues["description"])
            severity += batch_issues["severity_contribution"]

        if not issues:
            return DetectionResult.no_issue(self.name)

        severity = max(self.severity_range[0], min(self.severity_range[1], severity))

        result = DetectionResult.issue_found(
            detector_name=self.name,
            severity=severity,
            summary=issues[0] if len(issues) == 1 else f"{len(issues)} high-risk actions without approval",
            fix_type=FixType.ESCALATE,
            fix_instruction=(
                "High-risk actions were performed without human approval. "
                "Add an approval gate before destructive or irreversible operations. "
                "Consider requiring explicit user confirmation for delete, deploy, "
                "transfer, and similar actions."
            ),
        )

        for issue in issues:
            result.add_evidence(
                description=issue,
                span_ids=evidence_spans,
            )

        return result

    def _assess_risk(self, tool_span: Span) -> dict[str, Any] | None:
        """Assess whether a tool span contains a high-risk action."""
        texts_to_check: list[str] = [tool_span.name]

        if tool_span.input_data:
            for val in tool_span.input_data.values():
                if isinstance(val, str):
                    texts_to_check.append(val)

        combined_text = " ".join(texts_to_check)

        for pattern in self.HIGH_RISK_PATTERNS:
            match = pattern.search(combined_text)
            if match:
                return {
                    "matched_text": match.group(0),
                    "severity_contribution": 20,
                }

        return None

    def _find_span_index(self, sorted_spans: list[Span], target: Span) -> int:
        """Find the index of a span in a sorted list."""
        for i, span in enumerate(sorted_spans):
            if span.span_id == target.span_id:
                return i
        return -1

    def _check_approval_before(
        self, sorted_spans: list[Span], span_index: int
    ) -> bool:
        """Check if any preceding span contains approval context."""
        if span_index < 0:
            return False

        start = max(0, span_index - self.approval_lookback)
        for i in range(start, span_index):
            span = sorted_spans[i]

            # USER_INPUT spans are the primary approval source
            if span.kind == SpanKind.USER_INPUT:
                text = self._get_span_text(span).lower()
                for indicator in self.APPROVAL_INDICATORS:
                    if indicator in text:
                        return True
                # Even a plain user input near a dangerous action counts
                # as the user being in the loop
                return True

            # Check for approval-indicating span names
            name_lower = span.name.lower()
            if any(word in name_lower for word in ("approval", "confirm", "authorize", "consent")):
                return True

        return False

    def _check_batch_danger(
        self, unapproved_spans: list[Span]
    ) -> dict[str, Any] | None:
        """Check for multiple high-risk actions in rapid succession."""
        if len(unapproved_spans) < 2:
            return None

        sorted_spans = sorted(unapproved_spans, key=lambda s: s.start_time)

        # Check if multiple dangerous actions happen within the batch window
        batch_count = 1
        max_batch = 1

        for i in range(1, len(sorted_spans)):
            delta = (sorted_spans[i].start_time - sorted_spans[i - 1].start_time)
            if delta.total_seconds() <= self.batch_window_seconds:
                batch_count += 1
                max_batch = max(max_batch, batch_count)
            else:
                batch_count = 1

        if max_batch >= 2:
            return {
                "description": (
                    f"{max_batch} high-risk actions executed in rapid succession "
                    f"(within {self.batch_window_seconds}s) without approval"
                ),
                "severity_contribution": 15 + (max_batch - 2) * 5,
            }

        return None

    def _get_span_text(self, span: Span) -> str:
        """Extract text content from a span."""
        parts: list[str] = []

        for data in (span.input_data, span.output_data):
            if not data:
                continue
            for key in ("text", "content", "message", "query", "input", "command"):
                val = data.get(key)
                if isinstance(val, str):
                    parts.append(val)

        return " ".join(parts)
