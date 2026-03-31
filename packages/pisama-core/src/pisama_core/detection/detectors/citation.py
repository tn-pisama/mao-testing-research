"""Citation detector for identifying fabricated citations and source misattribution."""

import re
from typing import Any

from pisama_core.detection.base import BaseDetector
from pisama_core.detection.result import DetectionResult, FixType
from pisama_core.traces.models import Trace, Span
from pisama_core.traces.enums import SpanKind


# Patterns that introduce a citation (claim attributed to a source)
_CITATION_PATTERNS = [
    # "according to [source], [claim]"
    re.compile(
        r"according\s+to\s+(?P<source>[^,\.\n]{3,80})\s*[,:]?\s*(?P<claim>[^\.!\n]{10,})",
        re.IGNORECASE,
    ),
    # "source states/says/reports/indicates that [claim]"
    re.compile(
        r"(?P<source>[A-Z][^\.,]{2,60})\s+(?:states?|says?|reports?|indicates?|mentions?|notes?|confirms?|shows?)\s+(?:that\s+)?(?P<claim>[^\.!\n]{10,})",
        re.IGNORECASE,
    ),
    # "from [source]: [claim]" or "from [source], [claim]"
    re.compile(
        r"from\s+(?P<source>[^:,\n]{3,80})\s*[:,]\s*(?P<claim>[^\.!\n]{10,})",
        re.IGNORECASE,
    ),
    # "[source]: \"[claim]\""
    re.compile(
        r"(?P<source>[A-Z][^\:]{2,60}):\s*[\"'](?P<claim>[^\"']{10,})[\"']",
    ),
    # "as stated in [source]"
    re.compile(
        r"as\s+(?:stated|mentioned|described|noted|documented)\s+in\s+(?P<source>[^,\.\n]{3,80})\s*[,:]?\s*(?P<claim>[^\.!\n]{10,})",
        re.IGNORECASE,
    ),
    # "per [source], [claim]"
    re.compile(
        r"per\s+(?P<source>[^,\.\n]{3,80})\s*,\s*(?P<claim>[^\.!\n]{10,})",
        re.IGNORECASE,
    ),
    # "[claim] (source: [source])"
    re.compile(
        r"(?P<claim>[^(]{10,})\s*\(\s*source:\s*(?P<source>[^)]{3,80})\s*\)",
        re.IGNORECASE,
    ),
]


def _extract_citations(text: str) -> list[dict[str, str]]:
    """Extract all citations from text, each with a source name and claimed content."""
    if not text:
        return []

    citations: list[dict[str, str]] = []
    seen_claims: set[str] = set()

    for pattern in _CITATION_PATTERNS:
        for match in pattern.finditer(text):
            source = match.group("source").strip()
            claim = match.group("claim").strip()

            # Deduplicate by claim content
            claim_key = claim[:50].lower()
            if claim_key in seen_claims:
                continue
            seen_claims.add(claim_key)

            citations.append({
                "source": source,
                "claim": claim,
                "match_start": match.start(),
            })

    return citations


def _extract_source_content(trace: Trace) -> dict[str, str]:
    """Collect source content from RETRIEVAL spans and tool outputs.

    Returns a mapping from source identifier to source text content.
    """
    sources: dict[str, str] = {}

    # Collect from RETRIEVAL spans
    retrieval_spans = trace.get_spans_by_kind(SpanKind.RETRIEVAL)
    for span in retrieval_spans:
        source_id = span.name or span.span_id
        content_parts: list[str] = []

        if span.output_data:
            for key in ("content", "text", "document", "result", "output",
                        "retrieved_text", "chunk", "passage"):
                val = span.output_data.get(key)
                if isinstance(val, str):
                    content_parts.append(val)
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, str):
                            content_parts.append(item)
                        elif isinstance(item, dict):
                            for sub_key in ("content", "text", "page_content"):
                                sub_val = item.get(sub_key)
                                if isinstance(sub_val, str):
                                    content_parts.append(sub_val)

            # Also check for source metadata
            source_meta = span.output_data.get("source", span.output_data.get("metadata", {}))
            if isinstance(source_meta, dict):
                for key in ("title", "name", "filename", "url"):
                    val = source_meta.get(key)
                    if isinstance(val, str):
                        source_id = val
                        break

        if content_parts:
            sources[source_id] = " ".join(content_parts)

    # Also collect from TOOL spans that might fetch external content
    tool_spans = trace.get_spans_by_kind(SpanKind.TOOL)
    for span in tool_spans:
        name_lower = span.name.lower()
        if not any(kw in name_lower for kw in ("search", "fetch", "read", "retrieve", "get", "query")):
            continue

        if span.output_data:
            content_parts = []
            for key in ("content", "text", "result", "output", "body", "data"):
                val = span.output_data.get(key)
                if isinstance(val, str) and len(val) > 20:
                    content_parts.append(val)
            if content_parts:
                sources[span.name] = " ".join(content_parts)

    return sources


def _claim_supported_by_source(claim: str, source_text: str) -> float:
    """Check if a claim is supported by source text using fuzzy word overlap.

    Returns the overlap ratio (0.0 to 1.0).
    """
    if not claim or not source_text:
        return 0.0

    # Extract meaningful words (3+ chars, lowercased)
    claim_words = {w.lower() for w in re.findall(r"[a-z0-9]+", claim.lower()) if len(w) >= 3}
    source_words = {w.lower() for w in re.findall(r"[a-z0-9]+", source_text.lower()) if len(w) >= 3}

    if not claim_words:
        return 1.0  # Nothing to verify

    overlap = len(claim_words & source_words)
    return overlap / len(claim_words)


class CitationDetector(BaseDetector):
    """Detects fabricated citations where claims are attributed to sources
    that don't contain the claimed information.

    This detector:
    - Extracts citation patterns from agent output text
    - Collects available source content from RETRIEVAL spans and tool outputs
    - Checks if cited claims appear in any available source content
    - Flags when overlap between claim and source is below threshold
    """

    name = "citation"
    description = "Detects fabricated citations and source misattribution"
    version = "1.0.0"
    platforms = []  # All platforms
    severity_range = (35, 85)
    realtime_capable = False

    # Minimum overlap for a citation to be considered supported
    min_support_overlap = 0.30

    async def detect(self, trace: Trace) -> DetectionResult:
        """Detect fabricated citations in a trace."""
        # Collect all available source content
        sources = _extract_source_content(trace)
        if not sources:
            # Without source content, we can't verify citations
            return DetectionResult.no_issue(self.name)

        # Extract citations from agent output spans
        output_spans = self._get_output_spans(trace)
        if not output_spans:
            return DetectionResult.no_issue(self.name)

        all_source_text = " ".join(sources.values())
        fabricated: list[dict[str, Any]] = []
        total_citations = 0

        for span in output_spans:
            output_text = self._get_output_text(span)
            citations = _extract_citations(output_text)

            for citation in citations:
                total_citations += 1
                claim = citation["claim"]
                cited_source = citation["source"]

                # First check: does the cited source name match any known source?
                best_overlap = 0.0
                best_source = ""

                for source_id, source_text in sources.items():
                    # Check if the citation references this specific source
                    source_name_match = (
                        source_id.lower() in cited_source.lower()
                        or cited_source.lower() in source_id.lower()
                    )

                    overlap = _claim_supported_by_source(claim, source_text)

                    if source_name_match:
                        # Specific source cited: use its overlap directly
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_source = source_id
                    elif overlap > best_overlap:
                        best_overlap = overlap
                        best_source = source_id

                if best_overlap < self.min_support_overlap:
                    fabricated.append({
                        "span_id": span.span_id,
                        "cited_source": cited_source,
                        "claim": claim[:200],
                        "best_matching_source": best_source,
                        "best_overlap": round(best_overlap, 3),
                    })

        if not fabricated:
            return DetectionResult.no_issue(self.name)

        # Score severity based on count and overlap
        severity = self._score_fabrications(fabricated, total_citations)
        severity = max(self.severity_range[0], min(self.severity_range[1], severity))

        worst = min(fabricated, key=lambda f: f["best_overlap"])

        result = DetectionResult.issue_found(
            detector_name=self.name,
            severity=severity,
            summary=(
                f"Fabricated citation: claim attributed to '{worst['cited_source']}' "
                f"not supported by source content (overlap {worst['best_overlap']:.0%})"
            ),
            fix_type=FixType.ROLLBACK,
            fix_instruction=(
                "Citation appears fabricated. The claimed information was not found "
                "in the cited source. Remove the unsupported citation or verify the "
                "claim against the actual source content."
            ),
        )

        result.add_evidence(
            description=f"{len(fabricated)} of {total_citations} citation(s) unsupported by sources",
            span_ids=[f["span_id"] for f in fabricated[:10]],
            data={
                "fabricated_citations": fabricated[:10],
                "total_citations": total_citations,
                "available_sources": list(sources.keys()),
            },
        )

        return result

    def _get_output_spans(self, trace: Trace) -> list[Span]:
        """Get spans that produce user-facing output (agent turns, agents, tasks)."""
        output_kinds = {
            SpanKind.AGENT, SpanKind.AGENT_TURN, SpanKind.TASK,
            SpanKind.USER_OUTPUT,
        }
        spans = [s for s in trace.spans if s.kind in output_kinds]
        return sorted(spans, key=lambda s: s.start_time)

    @staticmethod
    def _get_output_text(span: Span) -> str:
        """Extract output text from a span."""
        parts: list[str] = []
        if span.output_data:
            for key in ("output", "result", "response", "text", "content", "answer", "message"):
                val = span.output_data.get(key)
                if isinstance(val, str):
                    parts.append(val)
            if not parts:
                parts.append(str(span.output_data))
        return " ".join(parts)

    @staticmethod
    def _score_fabrications(
        fabricated: list[dict[str, Any]], total_citations: int
    ) -> int:
        """Score severity based on fabrication count and quality."""
        if total_citations == 0:
            return 0

        fabrication_ratio = len(fabricated) / total_citations
        # Base severity from ratio
        base = 35 + int(fabrication_ratio * 30)

        # Bonus for very low overlap (blatant fabrication)
        min_overlap = min(f["best_overlap"] for f in fabricated)
        if min_overlap < 0.10:
            base += 15
        elif min_overlap < 0.20:
            base += 8

        return min(base, 85)
