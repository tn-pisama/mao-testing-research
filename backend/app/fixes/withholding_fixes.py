"""Fix generators for information withholding detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class WithholdingFixGenerator(BaseFixGenerator):
    """Generates fixes for information withholding detections."""

    def can_handle(self, detection_type: str) -> bool:
        return detection_type in ("withholding", "information_withholding")

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._transparency_enforcer_fix(detection_id, details, context))
        fixes.append(self._information_completeness_fix(detection_id, details, context))
        fixes.append(self._source_grounding_fix(detection_id, details, context))

        return fixes

    def _transparency_enforcer_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import re
import logging

logger = logging.getLogger(__name__)

TRANSPARENCY_SYSTEM_PROMPT = """You MUST follow these transparency rules:
1. Never omit information that is relevant to the user's query.
2. If you are uncertain about a fact, explicitly say so.
3. If there are caveats, limitations, or risks, state them clearly.
4. Do not hedge or soften negative information beyond factual accuracy.
5. If the query has multiple parts, address every part in your response.
6. When summarizing, flag that details were omitted and offer to elaborate.
"""

WITHHOLDING_INDICATORS = [
    r"I cannot .* provide",
    r"I\'m not able to .* share",
    r"that information is (not available|restricted)",
    r"I don\'t have .* details on",
    r"I\'m unable to (disclose|reveal)",
    r"for (safety|security) reasons I",
]


@dataclass
class TransparencyViolation:
    rule: str
    evidence: str
    severity: str  # "high", "medium", "low"


class TransparencyEnforcer:
    """System-prompt injection and output validator for transparency."""

    def __init__(self, extra_rules: Optional[List[str]] = None):
        self._rules = list(WITHHOLDING_INDICATORS)
        self._custom_rules = extra_rules or []
        self._violation_history: List[TransparencyViolation] = []

    def inject_system_prompt(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Prepend the transparency system prompt to a message list."""
        transparency_msg = {"role": "system", "content": TRANSPARENCY_SYSTEM_PROMPT}
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = (
                TRANSPARENCY_SYSTEM_PROMPT + "\n\n" + messages[0]["content"]
            )
            return messages
        return [transparency_msg] + messages

    def validate_output(
        self,
        output: str,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[TransparencyViolation]:
        """Scan output for signs of information withholding."""
        violations: List[TransparencyViolation] = []

        # Check for withholding indicator phrases
        for pattern in self._rules:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                violation = TransparencyViolation(
                    rule=pattern,
                    evidence=match.group(0),
                    severity="high",
                )
                violations.append(violation)
                logger.warning(
                    "Withholding indicator detected: '%s'",
                    match.group(0),
                )

        # Check that response length is proportional to query complexity
        query_parts = [p.strip() for p in re.split(r"[?.!;]", query) if p.strip()]
        if len(query_parts) >= 3 and len(output.split()) < 50:
            violations.append(
                TransparencyViolation(
                    rule="response_length_check",
                    evidence=(
                        f"Query has {len(query_parts)} parts but response "
                        f"is only {len(output.split())} words"
                    ),
                    severity="medium",
                )
            )

        self._violation_history.extend(violations)
        return violations

    @property
    def violation_count(self) -> int:
        return len(self._violation_history)'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="withholding",
            fix_type=FixType.TRANSPARENCY_ENFORCER,
            confidence=FixConfidence.HIGH,
            title="Enforce transparency via system prompt and output validation",
            description=(
                "Inject a transparency-focused system prompt that explicitly forbids "
                "withholding relevant information, and validate the output for known "
                "withholding indicator phrases."
            ),
            rationale=(
                "LLMs sometimes omit important information due to over-cautious safety "
                "alignment or prompt ambiguity. A dedicated transparency prompt combined "
                "with regex-based output scanning catches the most common patterns."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/transparency_enforcer.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="System prompt injection and output validator for transparency",
                )
            ],
            estimated_impact="Reduces information withholding by making transparency requirements explicit",
            tags=["withholding", "transparency", "system-prompt", "validation"],
        )

    def _information_completeness_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueryPart:
    text: str
    addressed: bool = False
    evidence: str = ""


@dataclass
class CompletenessReport:
    total_parts: int
    addressed_parts: int
    missing_parts: List[str]
    coverage_ratio: float
    passed: bool


class InformationCompletenessChecker:
    """Check that all parts of a user query are addressed in the response."""

    def __init__(self, coverage_threshold: float = 0.8):
        self._threshold = coverage_threshold
        self._history: List[CompletenessReport] = []

    def decompose_query(self, query: str) -> List[QueryPart]:
        """Split a query into its constituent sub-questions / requirements."""
        parts: List[QueryPart] = []

        # Split on question marks for multi-question queries
        questions = [q.strip() + "?" for q in query.split("?") if q.strip()]
        if len(questions) > 1:
            for q in questions:
                parts.append(QueryPart(text=q))
            return parts

        # Split on conjunctions and enumerations
        segments = re.split(
            r"\b(and|also|additionally|plus|as well as|\d+[\.\)]\s)",
            query,
            flags=re.IGNORECASE,
        )
        segments = [s.strip() for s in segments if s.strip() and len(s.strip()) > 5]
        for seg in segments:
            parts.append(QueryPart(text=seg))

        return parts if parts else [QueryPart(text=query)]

    def check_completeness(
        self, query: str, response: str
    ) -> CompletenessReport:
        """Check whether the response addresses all parts of the query."""
        parts = self.decompose_query(query)

        for part in parts:
            # Extract key nouns / phrases from the query part
            keywords = self._extract_keywords(part.text)
            matches = sum(
                1 for kw in keywords
                if kw.lower() in response.lower()
            )
            if keywords and matches / len(keywords) >= 0.4:
                part.addressed = True
                part.evidence = f"Matched {matches}/{len(keywords)} keywords"

        addressed = sum(1 for p in parts if p.addressed)
        total = len(parts)
        ratio = addressed / total if total > 0 else 1.0

        report = CompletenessReport(
            total_parts=total,
            addressed_parts=addressed,
            missing_parts=[p.text for p in parts if not p.addressed],
            coverage_ratio=ratio,
            passed=ratio >= self._threshold,
        )
        self._history.append(report)

        if not report.passed:
            logger.warning(
                "Completeness check failed: %.0f%% coverage (%d/%d parts). "
                "Missing: %s",
                ratio * 100,
                addressed,
                total,
                report.missing_parts,
            )
        return report

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Extract significant words, ignoring stopwords."""
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "what", "how",
            "why", "when", "where", "which", "who", "do", "does", "did",
            "can", "could", "should", "would", "will", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "and", "or", "not",
            "it", "this", "that", "be", "have", "has", "had", "i", "you",
            "me", "my", "your",
        }
        words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        return [w for w in words if w not in stopwords]'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="withholding",
            fix_type=FixType.INFORMATION_COMPLETENESS,
            confidence=FixConfidence.MEDIUM,
            title="Check that all query parts are addressed in the response",
            description=(
                "Decompose the user query into sub-questions and verify that the "
                "response addresses each one, flagging incomplete answers that skip "
                "parts of the original request."
            ),
            rationale=(
                "A common form of information withholding is simply ignoring parts "
                "of a multi-part question. Keyword-based coverage analysis provides "
                "a lightweight, deterministic check without requiring an extra LLM call."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/completeness_checker.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Query decomposition and keyword coverage checker",
                )
            ],
            estimated_impact="Detects partial answers that skip sub-questions in multi-part queries",
            tags=["withholding", "completeness", "coverage", "query-decomposition"],
        )

    def _source_grounding_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import re
import logging

logger = logging.getLogger(__name__)

SOURCE_GROUNDING_PROMPT = """When answering, you MUST:
1. Cite the source of every factual claim (document name, URL, or section).
2. If no source is available for a claim, prefix it with "[Unsourced]".
3. At the end of your response, include a "Sources" section listing all references.
4. Never present speculation as established fact.
"""


@dataclass
class SourceReference:
    text: str
    source_type: str  # "url", "document", "section", "none"
    location: str


@dataclass
class GroundingReport:
    total_claims: int
    grounded_claims: int
    ungrounded_claims: int
    grounding_ratio: float
    references: List[SourceReference]
    passed: bool


class SourceGroundingEnforcer:
    """Require agents to disclose the source of every factual claim."""

    def __init__(self, grounding_threshold: float = 0.7):
        self._threshold = grounding_threshold
        self._reports: List[GroundingReport] = []

    def inject_grounding_prompt(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Add source-grounding instructions to the system prompt."""
        grounding_msg = {"role": "system", "content": SOURCE_GROUNDING_PROMPT}
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = (
                SOURCE_GROUNDING_PROMPT + "\n\n" + messages[0]["content"]
            )
            return messages
        return [grounding_msg] + messages

    def analyze_grounding(self, response: str) -> GroundingReport:
        """Analyze how well the response grounds its claims in sources."""
        sentences = [
            s.strip() for s in re.split(r"[.!?]\s+", response) if s.strip()
        ]
        references: List[SourceReference] = []
        grounded = 0
        total_claims = 0

        for sentence in sentences:
            # Skip very short or non-factual sentences
            if len(sentence.split()) < 5:
                continue
            if sentence.lower().startswith(("i think", "perhaps", "maybe")):
                continue

            total_claims += 1
            source_type, location = self._find_source(sentence)

            references.append(
                SourceReference(
                    text=sentence[:80],
                    source_type=source_type,
                    location=location,
                )
            )
            if source_type != "none":
                grounded += 1

        ratio = grounded / total_claims if total_claims > 0 else 1.0
        report = GroundingReport(
            total_claims=total_claims,
            grounded_claims=grounded,
            ungrounded_claims=total_claims - grounded,
            grounding_ratio=ratio,
            references=references,
            passed=ratio >= self._threshold,
        )
        self._reports.append(report)

        if not report.passed:
            logger.warning(
                "Source grounding check failed: %.0f%% grounded (%d/%d claims)",
                ratio * 100,
                grounded,
                total_claims,
            )
        return report

    @staticmethod
    def _find_source(text: str) -> tuple:
        """Detect whether a sentence cites a source."""
        # URL references
        if re.search(r"https?://\S+", text):
            url = re.search(r"(https?://\S+)", text).group(1)
            return ("url", url)
        # Document references
        doc_match = re.search(
            r"(?:according to|per|from|in)\s+[\"']?([A-Z][^\"',;]{3,})[\"']?",
            text,
        )
        if doc_match:
            return ("document", doc_match.group(1).strip())
        # Section / page references
        sec_match = re.search(
            r"(?:section|page|chapter|table|figure)\s+\d+",
            text,
            re.IGNORECASE,
        )
        if sec_match:
            return ("section", sec_match.group(0))
        # Explicit unsourced marker
        if "[Unsourced]" in text or "[unsourced]" in text:
            return ("none", "explicitly marked unsourced")
        return ("none", "")'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="withholding",
            fix_type=FixType.SOURCE_GROUNDING,
            confidence=FixConfidence.MEDIUM,
            title="Require source disclosure for all factual claims",
            description=(
                "Inject a system prompt requiring source citations and analyze the "
                "response to compute a grounding ratio, flagging answers where too many "
                "claims lack a source reference."
            ),
            rationale=(
                "Requiring source disclosure makes it harder for the model to silently "
                "withhold information or fabricate facts. The grounding ratio provides "
                "a quantitative measure of how well the output is backed by evidence."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/source_grounding.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Source grounding enforcer with citation analysis",
                )
            ],
            estimated_impact="Makes unsourced claims visible and measurable, reducing silent withholding",
            tags=["withholding", "source-grounding", "citation", "transparency"],
        )
