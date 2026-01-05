"""
F1: Specification Mismatch Detection (MAST Taxonomy)
====================================================

Detects when a task specification doesn't match the user's original intent.
This occurs at the system design level when:
- The task decomposition loses critical requirements
- The specification is ambiguous or incomplete
- The task scope drifts from original intent

Version History:
- v1.0: Initial implementation
- v1.1: Improved for adversarial accuracy:
  - Code quality checks for code-related tasks
  - Numeric tolerance for approximate constraints (word counts, etc.)
  - Language mismatch detection (requested Python, got TypeScript)
  - Deprecated syntax detection
- v1.2: Phase 2 adversarial fixes:
  - Python deprecated syntax detection (cmp=, has_key, print statement)
  - JavaScript deprecated patterns (var, arguments.callee)
  - General deprecated API patterns
  - Improved word count tolerance handling
"""

# Detector version for tracking
DETECTOR_VERSION = "1.2"
DETECTOR_NAME = "SpecificationMismatchDetector"

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re

logger = logging.getLogger(__name__)


class MismatchSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


class MismatchType(str, Enum):
    SCOPE_DRIFT = "scope_drift"
    MISSING_REQUIREMENT = "missing_requirement"
    AMBIGUOUS_SPEC = "ambiguous_spec"
    CONFLICTING_SPEC = "conflicting_spec"
    OVERSPECIFIED = "overspecified"


@dataclass
class SpecificationMismatchResult:
    detected: bool
    mismatch_type: Optional[MismatchType]
    severity: MismatchSeverity
    confidence: float
    requirement_coverage: float
    missing_requirements: list[str]
    ambiguous_elements: list[str]
    explanation: str
    suggested_fix: Optional[str] = None


class SpecificationMismatchDetector:
    """
    Detects F1: Specification Mismatch - task doesn't match user intent.

    Compares user intent with task specification to identify
    gaps, ambiguities, and scope drift.
    """

    # v1.1: Programming language patterns for language mismatch detection
    LANGUAGE_PATTERNS = {
        'python': (r'\bpython\b', [r'\bdef\s+\w+\s*\(', r'\bimport\s+\w+', r':\s*$', r'\bprint\s*\(']),
        'javascript': (r'\b(?:javascript|js)\b', [r'\bfunction\s+\w+', r'\bconst\s+\w+', r'\blet\s+\w+', r'=>']),
        'typescript': (r'\btypescript\b', [r':\s*\w+(?:\[\])?(?:\s*[,\)])', r'\binterface\s+\w+', r'<\w+>']),
        'java': (r'\bjava\b(?!script)', [r'\bpublic\s+class', r'\bprivate\s+\w+', r'\bvoid\s+\w+']),
        'sql': (r'\bsql\b', [r'\bSELECT\b', r'\bFROM\b', r'\bWHERE\b', r'\bINSERT\b']),
    }

    # v1.1: Code quality issues that indicate specification mismatch
    CODE_QUALITY_PATTERNS = [
        # Method reference without () - specifically common Python methods
        (r'\.(?:sort|append|extend|pop|remove|clear|reverse)\s*(?:\n|$|[^(])', "method_without_call"),
        (r'\bpass\s*$', "empty_implementation"),  # Python pass statement (placeholder)
        (r'//\s*TODO', "todo_marker"),
        (r'#\s*TODO', "todo_marker"),
        (r'raise\s+NotImplementedError', "not_implemented"),
        (r'throw\s+new\s+Error\(["\']not implemented', "not_implemented"),
        (r'\.\.\.\s*$', "ellipsis_placeholder"),  # ... as placeholder
    ]

    # v1.2: Deprecated syntax patterns by language
    DEPRECATED_SYNTAX_PATTERNS = {
        'python': [
            # Python 2 deprecated in Python 3
            (r'\bcmp\s*=', "deprecated_cmp_parameter"),  # sorted(..., cmp=func)
            (r'\.has_key\s*\(', "deprecated_has_key"),  # dict.has_key() -> use 'in'
            (r'\bprint\s+["\']', "deprecated_print_statement"),  # print "x" without parens
            (r'\braw_input\s*\(', "deprecated_raw_input"),  # raw_input() -> input()
            (r'\bexecfile\s*\(', "deprecated_execfile"),  # execfile() removed
            (r'\bxrange\s*\(', "deprecated_xrange"),  # xrange() -> range()
            (r'\.iteritems\s*\(', "deprecated_iteritems"),  # dict.iteritems() -> items()
            (r'\.iterkeys\s*\(', "deprecated_iterkeys"),  # dict.iterkeys() -> keys()
            (r'\.itervalues\s*\(', "deprecated_itervalues"),  # dict.itervalues() -> values()
            (r'\breduce\s*\((?![^)]*functools)', "deprecated_reduce"),  # reduce() needs functools
            (r'\bapply\s*\(', "deprecated_apply"),  # apply() removed
            (r'\bcoerce\s*\(', "deprecated_coerce"),  # coerce() removed
            (r'<>\s*', "deprecated_not_equal"),  # <> -> !=
            (r'\blong\s*\(', "deprecated_long"),  # long() -> int()
            (r'\bunicode\s*\(', "deprecated_unicode"),  # unicode() -> str()
        ],
        'javascript': [
            (r'\bvar\s+\w+', "deprecated_var"),  # var -> let/const (ES6+)
            (r'arguments\.callee', "deprecated_callee"),  # arguments.callee deprecated
            (r'with\s*\([^)]+\)\s*{', "deprecated_with"),  # with statement deprecated
            (r'\.substr\s*\(', "deprecated_substr"),  # substr -> substring/slice
            (r'escape\s*\(', "deprecated_escape"),  # escape() -> encodeURIComponent
            (r'unescape\s*\(', "deprecated_unescape"),  # unescape() -> decodeURIComponent
        ],
        'java': [
            (r'new\s+Date\s*\(\s*\d+\s*,', "deprecated_date_constructor"),  # Date(year,month,day) deprecated
            (r'\.getYear\s*\(', "deprecated_getYear"),  # getYear() -> getFullYear() - 1900
            (r'Thread\s*\.\s*stop\s*\(', "deprecated_thread_stop"),  # Thread.stop() deprecated
        ],
    }

    # v1.1: Numeric constraint patterns with tolerance
    NUMERIC_CONSTRAINT_PATTERNS = [
        (r'(\d+)[\s-]?word', "word_count"),
        (r'(\d+)[\s-]?character', "char_count"),
        (r'(\d+)[\s-]?line', "line_count"),
        (r'(\d+)[\s-]?item', "item_count"),
        (r'(\d+)[\s-]?point', "point_count"),
        (r'(\d+)[\s-]?step', "step_count"),
    ]

    # v1.1: Tolerance for approximate numeric constraints (percentage)
    NUMERIC_TOLERANCE = 0.10  # 10% tolerance

    def __init__(
        self,
        coverage_threshold: float = 0.7,
        ambiguity_threshold: int = 3,
    ):
        self.coverage_threshold = coverage_threshold
        self.ambiguity_threshold = ambiguity_threshold

    def _extract_requirements(self, text: str) -> list[str]:
        requirements = []
        
        must_patterns = [
            r'must\s+([^.!?]+)',
            r'should\s+([^.!?]+)',
            r'need(?:s)?\s+to\s+([^.!?]+)',
            r'require(?:s|d)?\s+([^.!?]+)',
            r'has\s+to\s+([^.!?]+)',
            r'ensure\s+(?:that\s+)?([^.!?]+)',
        ]
        
        for pattern in must_patterns:
            matches = re.findall(pattern, text.lower())
            requirements.extend(matches)
        
        action_patterns = [
            r'(?:create|build|make|generate)\s+(?:a\s+)?([^.!?,]+)',
            r'(?:find|search|get|fetch)\s+([^.!?,]+)',
            r'(?:analyze|evaluate|assess)\s+([^.!?,]+)',
            r'(?:send|deliver|transmit)\s+([^.!?,]+)',
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, text.lower())
            requirements.extend(matches)
        
        return [r.strip() for r in requirements if len(r.strip()) > 3]

    def _extract_constraints(self, text: str) -> list[str]:
        constraints = []
        
        constraint_patterns = [
            r'(?:no|not|never|without)\s+([^.!?,]+)',
            r'(?:only|exclusively)\s+([^.!?,]+)',
            r'(?:at\s+(?:most|least))\s+([^.!?,]+)',
            r'(?:within|under|below|above)\s+(\d+[^.!?,]*)',
            r'(?:before|after|by)\s+([^.!?,]+)',
            r'(?:limit(?:ed)?\s+to)\s+([^.!?,]+)',
        ]
        
        for pattern in constraint_patterns:
            matches = re.findall(pattern, text.lower())
            constraints.extend(matches)
        
        return [c.strip() for c in constraints if len(c.strip()) > 3]

    def _detect_requested_language(self, intent: str) -> Optional[str]:
        """v1.1: Detect which programming language was requested."""
        intent_lower = intent.lower()
        for lang, (pattern, _) in self.LANGUAGE_PATTERNS.items():
            if re.search(pattern, intent_lower):
                return lang
        return None

    def _detect_output_language(self, output: str) -> Optional[str]:
        """v1.1: Detect which programming language is in the output."""
        for lang, (_, code_patterns) in self.LANGUAGE_PATTERNS.items():
            matches = sum(1 for p in code_patterns if re.search(p, output, re.MULTILINE))
            if matches >= 2:  # At least 2 language markers
                return lang
        return None

    def _check_code_quality(self, output: str) -> list[tuple]:
        """v1.1: Check for code quality issues that indicate incomplete/buggy code."""
        issues = []
        for pattern, issue_type in self.CODE_QUALITY_PATTERNS:
            matches = re.finditer(pattern, output, re.MULTILINE)
            for match in matches:
                # Get context around the match
                start = max(0, match.start() - 20)
                end = min(len(output), match.end() + 20)
                context = output[start:end].strip()
                issues.append((issue_type, match.group(), context))
        return issues

    def _check_deprecated_syntax(self, output: str, language: Optional[str]) -> list[tuple]:
        """v1.2: Check for deprecated syntax patterns in code output."""
        issues = []
        if not language or language not in self.DEPRECATED_SYNTAX_PATTERNS:
            return issues

        for pattern, issue_type in self.DEPRECATED_SYNTAX_PATTERNS[language]:
            matches = re.finditer(pattern, output, re.MULTILINE)
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(output), match.end() + 30)
                context = output[start:end].strip()
                issues.append((issue_type, match.group(), context))
        return issues

    def _extract_numeric_constraint(self, intent: str) -> Optional[tuple]:
        """v1.1: Extract numeric constraint from intent (e.g., '100-word')."""
        for pattern, constraint_type in self.NUMERIC_CONSTRAINT_PATTERNS:
            match = re.search(pattern, intent.lower())
            if match:
                return (int(match.group(1)), constraint_type)
        return None

    def _check_numeric_constraint(self, output: str, target: int, constraint_type: str) -> bool:
        """v1.1: Check if output meets numeric constraint within tolerance."""
        if constraint_type == "word_count":
            # Count words in output
            words = len(output.split())
            tolerance = int(target * self.NUMERIC_TOLERANCE)
            return abs(words - target) <= tolerance
        elif constraint_type == "line_count":
            lines = len(output.strip().split('\n'))
            tolerance = max(1, int(target * self.NUMERIC_TOLERANCE))
            return abs(lines - target) <= tolerance
        # For other types, be lenient
        return True

    def _is_code_task(self, intent: str) -> bool:
        """v1.1: Check if the task is code-related."""
        code_keywords = [
            r'\bcode\b', r'\bfunction\b', r'\bprogram\b', r'\bscript\b',
            r'\bimplement\b', r'\bwrite\s+(?:a\s+)?(?:python|javascript|java|sql)',
            r'\bcreate\s+(?:a\s+)?(?:function|class|method)',
        ]
        intent_lower = intent.lower()
        return any(re.search(kw, intent_lower) for kw in code_keywords)

    def _detect_ambiguities(self, text: str) -> list[str]:
        ambiguities = []
        
        vague_patterns = [
            (r'\b(some|several|many|few|various)\s+\w+', "vague quantity"),
            (r'\b(soon|later|eventually|sometime)\b', "vague timing"),
            (r'\b(good|better|best|nice|appropriate)\b', "subjective quality"),
            (r'\b(etc|and so on|and more|among others)\b', "incomplete list"),
            (r'\b(it|this|that)\b(?!\s+(?:is|are|was|will))', "ambiguous reference"),
            (r'\b(usually|typically|generally|normally)\b', "uncertain qualifier"),
            (r'\b(might|may|could|possibly|perhaps)\b', "uncertain action"),
            (r'\b(simple|easy|quick|basic)\b', "undefined complexity"),
        ]
        
        for pattern, issue_type in vague_patterns:
            if re.search(pattern, text.lower()):
                ambiguities.append(issue_type)
        
        return ambiguities

    def _compute_coverage(
        self,
        intent_requirements: list[str],
        spec_text: str,
    ) -> tuple[float, list[str]]:
        if not intent_requirements:
            return 1.0, []
        
        spec_lower = spec_text.lower()
        covered = 0
        missing = []
        
        for req in intent_requirements:
            req_words = set(req.lower().split())
            req_words = {w for w in req_words if len(w) > 3}
            
            if not req_words:
                covered += 1
                continue
            
            overlap = sum(1 for w in req_words if w in spec_lower)
            coverage_ratio = overlap / len(req_words)
            
            if coverage_ratio >= 0.5:
                covered += 1
            else:
                missing.append(req)
        
        return covered / len(intent_requirements), missing

    def detect(
        self,
        user_intent: str,
        task_specification: str,
        original_request: Optional[str] = None,
    ) -> SpecificationMismatchResult:
        intent_requirements = self._extract_requirements(user_intent)
        intent_constraints = self._extract_constraints(user_intent)
        all_requirements = intent_requirements + intent_constraints

        coverage, missing = self._compute_coverage(all_requirements, task_specification)

        ambiguities = self._detect_ambiguities(task_specification)

        mismatch_type = None
        detected = False
        code_issues = []

        # v1.1: Check numeric constraints with tolerance
        numeric_constraint = self._extract_numeric_constraint(user_intent)
        numeric_constraint_met = False
        if numeric_constraint:
            target, constraint_type = numeric_constraint
            if self._check_numeric_constraint(task_specification, target, constraint_type):
                # Constraint met within tolerance - this is the primary requirement
                numeric_constraint_met = True
            else:
                detected = True
                mismatch_type = MismatchType.MISSING_REQUIREMENT
                missing.append(f"{target}-{constraint_type.replace('_', ' ')}")

        # v1.1: Check code quality for code tasks
        if self._is_code_task(user_intent):
            code_issues = self._check_code_quality(task_specification)
            if code_issues:
                detected = True
                mismatch_type = MismatchType.MISSING_REQUIREMENT
                for issue_type, match, context in code_issues[:3]:
                    missing.append(f"code issue: {issue_type}")

        # v1.1: Check language mismatch (only flag if wrong language, not supersets)
        # v1.2: Also check for deprecated syntax
        requested_lang = self._detect_requested_language(user_intent)
        if requested_lang:
            # v1.2: Check deprecated syntax
            deprecated_issues = self._check_deprecated_syntax(task_specification, requested_lang)
            if deprecated_issues:
                detected = True
                mismatch_type = MismatchType.MISSING_REQUIREMENT
                for issue_type, match, context in deprecated_issues[:3]:
                    missing.append(f"deprecated syntax: {issue_type}")

            # v1.1: Check language mismatch
            output_lang = self._detect_output_language(task_specification)
            # TypeScript is superset of JavaScript - don't flag
            # Other language mismatches should be flagged
            if output_lang and output_lang != requested_lang:
                if not (requested_lang == 'javascript' and output_lang == 'typescript'):
                    detected = True
                    mismatch_type = MismatchType.MISSING_REQUIREMENT
                    missing.append(f"language mismatch: requested {requested_lang}, got {output_lang}")

        # v1.1: If numeric constraint is met, don't flag based on coverage/ambiguity
        # (the primary requirement was satisfied)
        if not numeric_constraint_met:
            if coverage < self.coverage_threshold and not detected:
                detected = True
                mismatch_type = MismatchType.MISSING_REQUIREMENT
            elif len(ambiguities) >= self.ambiguity_threshold and not detected:
                detected = True
                mismatch_type = MismatchType.AMBIGUOUS_SPEC

        if original_request and user_intent != original_request:
            orig_reqs = self._extract_requirements(original_request)
            orig_coverage, orig_missing = self._compute_coverage(orig_reqs, task_specification)
            if orig_coverage < coverage - 0.2:
                detected = True
                mismatch_type = MismatchType.SCOPE_DRIFT
                missing.extend(orig_missing)

        if not detected:
            return SpecificationMismatchResult(
                detected=False,
                mismatch_type=None,
                severity=MismatchSeverity.NONE,
                confidence=coverage,
                requirement_coverage=coverage,
                missing_requirements=[],
                ambiguous_elements=[],
                explanation="Specification matches user intent",
            )

        if coverage < 0.3:
            severity = MismatchSeverity.SEVERE
        elif coverage < 0.5:
            severity = MismatchSeverity.MODERATE
        else:
            severity = MismatchSeverity.MINOR

        confidence = 1 - coverage

        if mismatch_type == MismatchType.MISSING_REQUIREMENT:
            explanation = (
                f"Task specification missing {len(missing)} requirements from user intent. "
                f"Coverage: {coverage:.1%}"
            )
            fix = f"Add missing requirements to specification: {', '.join(missing[:3])}"
        elif mismatch_type == MismatchType.AMBIGUOUS_SPEC:
            explanation = (
                f"Task specification contains {len(ambiguities)} ambiguous elements: "
                f"{', '.join(ambiguities[:5])}"
            )
            fix = "Replace vague language with specific, measurable criteria"
        else:
            explanation = "Task specification has drifted from original user request"
            fix = "Re-align specification with original user intent"

        return SpecificationMismatchResult(
            detected=True,
            mismatch_type=mismatch_type,
            severity=severity,
            confidence=confidence,
            requirement_coverage=coverage,
            missing_requirements=missing[:10],
            ambiguous_elements=ambiguities,
            explanation=explanation,
            suggested_fix=fix,
        )

    def detect_from_trace(
        self,
        trace: dict,
    ) -> list[SpecificationMismatchResult]:
        results = []
        
        root_input = trace.get("input", {}).get("user_request", "")
        if not root_input:
            return results
        
        spans = trace.get("spans", [])
        for span in spans:
            task_spec = span.get("input", {}).get("task", "")
            if task_spec and len(task_spec) > 20:
                result = self.detect(
                    user_intent=root_input,
                    task_specification=task_spec,
                )
                if result.detected:
                    results.append(result)
        
        return results
