"""MCP protocol detector for tool communication failures."""

import re
from typing import Any

from pisama_core.detection.base import BaseDetector
from pisama_core.detection.result import DetectionResult, FixRecommendation, FixType
from pisama_core.traces.models import Trace, Span
from pisama_core.traces.enums import SpanKind, SpanStatus


class MCPProtocolDetector(BaseDetector):
    """Detects MCP-specific failures in tool communication.

    This detector identifies:
    - Tool discovery failures (tool not found, unknown tool)
    - Schema validation errors (invalid arguments, type mismatch)
    - Authentication failures (unauthorized, auth failed)
    - Connection failures (timeout, connection refused)
    """

    name = "mcp_protocol"
    description = "Detects MCP-specific failures in tool communication"
    version = "1.0.0"
    platforms = []  # All platforms
    severity_range = (25, 70)
    realtime_capable = True

    # Failure category patterns and their severity weights
    FAILURE_CATEGORIES: dict[str, dict[str, Any]] = {
        "discovery": {
            "patterns": [
                re.compile(r"tool\s+not\s+found", re.IGNORECASE),
                re.compile(r"unknown\s+tool", re.IGNORECASE),
                re.compile(r"no\s+such\s+tool", re.IGNORECASE),
                re.compile(r"tool\s+(?:does\s+not|doesn'?t)\s+exist", re.IGNORECASE),
                re.compile(r"unrecognized\s+tool", re.IGNORECASE),
                re.compile(r"method\s+not\s+found", re.IGNORECASE),
            ],
            "severity_weight": 20,
            "description": "Tool discovery failure",
        },
        "schema": {
            "patterns": [
                re.compile(r"schema\s+validation", re.IGNORECASE),
                re.compile(r"invalid\s+arguments?", re.IGNORECASE),
                re.compile(r"type\s+mismatch", re.IGNORECASE),
                re.compile(r"required\s+field", re.IGNORECASE),
                re.compile(r"missing\s+required", re.IGNORECASE),
                re.compile(r"validation\s+error", re.IGNORECASE),
                re.compile(r"invalid\s+param", re.IGNORECASE),
                re.compile(r"unexpected\s+(?:argument|field|property)", re.IGNORECASE),
                re.compile(r"wrong\s+type", re.IGNORECASE),
            ],
            "severity_weight": 30,
            "description": "Schema validation failure",
        },
        "auth": {
            "patterns": [
                re.compile(r"unauthori[sz]ed", re.IGNORECASE),
                re.compile(r"authentication\s+failed", re.IGNORECASE),
                re.compile(r"auth(?:entication)?\s+error", re.IGNORECASE),
                re.compile(r"permission\s+denied", re.IGNORECASE),
                re.compile(r"access\s+denied", re.IGNORECASE),
                re.compile(r"forbidden", re.IGNORECASE),
                re.compile(r"invalid\s+(?:token|credential|api[_\s]?key)", re.IGNORECASE),
                re.compile(r"expired\s+token", re.IGNORECASE),
            ],
            "severity_weight": 40,
            "description": "Authentication/authorization failure",
        },
        "connection": {
            "patterns": [
                re.compile(r"connection\s+refused", re.IGNORECASE),
                re.compile(r"timeout", re.IGNORECASE),
                re.compile(r"timed?\s*out", re.IGNORECASE),
                re.compile(r"connect(?:ion)?\s+(?:error|failed)", re.IGNORECASE),
                re.compile(r"ECONNREFUSED", re.IGNORECASE),
                re.compile(r"ETIMEDOUT", re.IGNORECASE),
                re.compile(r"host\s+(?:not\s+found|unreachable)", re.IGNORECASE),
                re.compile(r"network\s+(?:error|unreachable)", re.IGNORECASE),
                re.compile(r"server\s+(?:not\s+responding|unavailable)", re.IGNORECASE),
            ],
            "severity_weight": 25,
            "description": "Connection failure",
        },
    }

    async def detect(self, trace: Trace) -> DetectionResult:
        """Detect MCP protocol failures in tool spans."""
        tool_spans = trace.get_spans_by_kind(SpanKind.TOOL)
        if not tool_spans:
            return DetectionResult.no_issue(self.name)

        # Filter to error spans
        error_spans = [
            s for s in tool_spans
            if s.status.is_failure
        ]
        if not error_spans:
            return DetectionResult.no_issue(self.name)

        issues: list[str] = []
        severity = 0
        evidence_spans: list[str] = []
        failure_counts: dict[str, int] = {
            "discovery": 0, "schema": 0, "auth": 0, "connection": 0,
        }

        for span in error_spans:
            error_text = self._get_error_text(span)
            if not error_text:
                continue

            categories = self._classify_failure(error_text)
            if not categories:
                continue

            for category in categories:
                cat_info = self.FAILURE_CATEGORIES[category]
                failure_counts[category] += 1
                issues.append(
                    f"{cat_info['description']} in tool '{span.name}': "
                    f"{self._truncate(error_text, 100)}"
                )
                evidence_spans.append(span.span_id)
                severity += cat_info["severity_weight"]

        if not issues:
            return DetectionResult.no_issue(self.name)

        severity = max(self.severity_range[0], min(self.severity_range[1], severity))

        # Determine fix type based on dominant failure category
        dominant_category = max(failure_counts, key=failure_counts.get)  # type: ignore[arg-type]
        fix_type, fix_instruction = self._get_fix_for_category(dominant_category)

        result = DetectionResult.issue_found(
            detector_name=self.name,
            severity=severity,
            summary=(
                issues[0] if len(issues) == 1
                else f"{len(issues)} MCP protocol failures detected"
            ),
            fix_type=fix_type,
            fix_instruction=fix_instruction,
        )

        for issue in issues:
            result.add_evidence(
                description=issue,
                span_ids=evidence_spans,
                data={"failure_counts": failure_counts},
            )

        return result

    def _get_error_text(self, span: Span) -> str:
        """Extract error text from a span."""
        parts: list[str] = []

        if span.error_message:
            parts.append(span.error_message)

        # Check output_data for error details
        if span.output_data:
            for key in ("error", "message", "detail", "error_message", "reason"):
                val = span.output_data.get(key)
                if isinstance(val, str):
                    parts.append(val)
                elif isinstance(val, dict):
                    msg = val.get("message") or val.get("detail") or val.get("error")
                    if isinstance(msg, str):
                        parts.append(msg)

        # Check attributes
        for key in ("error.message", "error.type", "exception.message"):
            val = span.attributes.get(key)
            if isinstance(val, str):
                parts.append(val)

        return " ".join(parts)

    def _classify_failure(self, error_text: str) -> list[str]:
        """Classify an error into MCP failure categories."""
        matched_categories: list[str] = []

        for category, info in self.FAILURE_CATEGORIES.items():
            for pattern in info["patterns"]:
                if pattern.search(error_text):
                    if category not in matched_categories:
                        matched_categories.append(category)
                    break

        return matched_categories

    def _get_fix_for_category(
        self, category: str
    ) -> tuple[FixType, str]:
        """Get the appropriate fix type and instruction for a failure category."""
        if category == "auth":
            return (
                FixType.ESCALATE,
                "Authentication/authorization failure detected in MCP tool communication. "
                "Check API keys, tokens, or permissions. The tool server may require "
                "re-authentication or the credentials may have expired.",
            )
        elif category == "schema":
            return (
                FixType.SWITCH_STRATEGY,
                "Schema validation errors in MCP tool calls. "
                "The tool arguments do not match the expected schema. "
                "Re-read the tool's input schema and ensure all required fields "
                "are present with correct types.",
            )
        elif category == "discovery":
            return (
                FixType.SWITCH_STRATEGY,
                "Tool not found in MCP server. "
                "The requested tool may not be available on this server. "
                "List available tools and use an alternative, or check "
                "that the MCP server is configured correctly.",
            )
        else:  # connection
            return (
                FixType.ADD_DELAY,
                "Connection failure to MCP tool server. "
                "The server may be down, overloaded, or unreachable. "
                "Retry after a brief delay, or check network connectivity "
                "and server status.",
            )

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text to max length with ellipsis."""
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."
