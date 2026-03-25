"""Implementation Correctness Detection (DAB FM4).

Detects when an agent has the right plan and right data but implements
it incorrectly — wrong regex, wrong aggregation code, type errors,
off-by-one, wrong column references.

DAB found this accounts for 45% of data agent failures. The agent
selects the right tables and columns but the code/regex/SQL is wrong.

Key patterns:
- Regex extraction errors (extracting ISBN instead of year)
- Wrong column in aggregation (averaging wrong field)
- Type coercion failures (string vs number comparison)
- Off-by-one in filtering (>= vs >)
- Wrong sort direction (ASC vs DESC)
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ImplementationIssue:
    """A specific implementation error."""
    issue_type: str  # regex_error, type_mismatch, wrong_column, off_by_one, wrong_sort
    severity: str
    description: str
    code_snippet: str = ""
    suggested_fix: str = ""


@dataclass
class ImplementationResult:
    """Result of implementation correctness analysis."""
    detected: bool
    confidence: float
    issues: List[ImplementationIssue] = field(default_factory=list)
    code_analyzed: bool = False
    raw_score: Optional[float] = None


class ImplementationCorrectnessDetector:
    """Detects code/regex/SQL implementation errors in agent output.

    Analyzes agent-generated code for common mistakes:
    1. Regex patterns that match wrong data (ISBN instead of year)
    2. Type mismatches in comparisons
    3. Wrong column references in SQL/pandas
    4. Incorrect sort order
    5. Missing edge case handling
    """

    # Common regex anti-patterns
    REGEX_ANTI_PATTERNS = [
        # Overly greedy date extraction (matches ISBNs, phone numbers)
        (r"\\d{4}", "year_extraction", "4-digit pattern matches ISBNs, zip codes, not just years"),
        # Greedy number extraction
        (r"\\d+", "number_extraction", "Greedy \\d+ may match unintended numeric strings"),
    ]

    def detect(
        self,
        code: str,
        task: str,
        output: Optional[str] = None,
        expected_output: Optional[str] = None,
    ) -> ImplementationResult:
        """Analyze agent-generated code for implementation errors.

        Args:
            code: The agent's generated code (Python, SQL, or mixed)
            task: The original task description
            output: The actual output produced
            expected_output: The expected correct output (if known)
        """
        issues = []
        code_lower = code.lower()

        # Check 1: Regex pattern issues
        regex_issues = self._check_regex_patterns(code, task)
        issues.extend(regex_issues)

        # Check 2: Type mismatch risks
        type_issues = self._check_type_mismatches(code)
        issues.extend(type_issues)

        # Check 3: SQL-specific issues
        sql_issues = self._check_sql_issues(code, task)
        issues.extend(sql_issues)

        # Check 4: Pandas-specific issues
        pandas_issues = self._check_pandas_issues(code, task)
        issues.extend(pandas_issues)

        # Check 5: Output mismatch (if expected output provided)
        if output and expected_output:
            mismatch_issues = self._check_output_mismatch(output, expected_output)
            issues.extend(mismatch_issues)

        # Check 6: Common coding mistakes
        coding_issues = self._check_common_mistakes(code)
        issues.extend(coding_issues)

        if not issues:
            return ImplementationResult(detected=False, confidence=0.0, code_analyzed=True)

        severity_weights = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.2}
        max_sev = max(severity_weights.get(i.severity, 0.3) for i in issues)
        confidence = min(1.0, max_sev * (1 + 0.1 * (len(issues) - 1)))

        return ImplementationResult(
            detected=True,
            confidence=round(confidence, 4),
            issues=issues,
            code_analyzed=True,
            raw_score=confidence,
        )

    def _check_regex_patterns(self, code: str, task: str) -> List[ImplementationIssue]:
        """Check for regex patterns that may extract wrong data."""
        issues = []

        # Find all regex patterns in code
        regex_patterns = re.findall(r"re\.(?:search|findall|match|sub)\s*\(\s*['\"](.+?)['\"]", code)
        regex_patterns += re.findall(r"r['\"](.+?)['\"]", code)

        for pattern in regex_patterns:
            # Check if pattern is too greedy for the task
            if r"\d{4}" in pattern and "year" in task.lower():
                # 4-digit pattern for year — but could match ISBNs
                if "isbn" in code.lower() or "book" in task.lower():
                    issues.append(ImplementationIssue(
                        issue_type="regex_error",
                        severity="high",
                        description="Regex \\d{4} for year extraction may match ISBNs or other 4-digit numbers",
                        code_snippet=pattern,
                        suggested_fix="Add context anchoring: e.g., (?:19|20)\\d{2} for modern years",
                    ))

            if r"\d+" in pattern and not re.search(r"\\d\+.*\\d\+", pattern):
                # Greedy number extraction without bounds
                if any(w in task.lower() for w in ("price", "rating", "count", "number")):
                    issues.append(ImplementationIssue(
                        issue_type="regex_error",
                        severity="medium",
                        description="Greedy \\d+ may match unintended numeric strings in free text",
                        code_snippet=pattern,
                        suggested_fix="Add word boundaries: \\b\\d+\\b or more specific pattern",
                    ))

        return issues

    def _check_type_mismatches(self, code: str) -> List[ImplementationIssue]:
        """Check for type mismatch risks in comparisons."""
        issues = []

        # String vs number comparison
        if re.search(r"==\s*['\"]?\d+['\"]?", code) and re.search(r"==\s*\d+\b", code):
            # Both string and numeric comparisons present
            pass  # May be intentional

        # .astype() missing before numeric operations
        if "str.contains" in code and any(op in code for op in [".sum()", ".mean()", ".max()"]):
            issues.append(ImplementationIssue(
                issue_type="type_mismatch",
                severity="medium",
                description="String operation (str.contains) followed by numeric aggregation — may need type conversion",
                suggested_fix="Add .astype(float) or pd.to_numeric() before aggregation",
            ))

        return issues

    def _check_sql_issues(self, code: str, task: str) -> List[ImplementationIssue]:
        """Check for SQL-specific implementation errors."""
        issues = []

        # Find SQL queries in code
        sql_blocks = re.findall(r"(?:SELECT|INSERT|UPDATE|DELETE).*?(?:;|\"|'|\))", code, re.IGNORECASE | re.DOTALL)

        for sql in sql_blocks:
            sql_upper = sql.upper()

            # GROUP BY without aggregation
            if "GROUP BY" in sql_upper and not any(f in sql_upper for f in ("COUNT", "SUM", "AVG", "MAX", "MIN")):
                issues.append(ImplementationIssue(
                    issue_type="wrong_column",
                    severity="high",
                    description="GROUP BY without aggregation function — SELECT may return arbitrary values",
                    code_snippet=sql[:100],
                ))

            # HAVING without GROUP BY
            if "HAVING" in sql_upper and "GROUP BY" not in sql_upper:
                issues.append(ImplementationIssue(
                    issue_type="wrong_column",
                    severity="high",
                    description="HAVING clause without GROUP BY",
                    code_snippet=sql[:100],
                ))

            # SELECT * in production query (may return too much data)
            if "SELECT *" in sql_upper and "LIMIT" not in sql_upper:
                issues.append(ImplementationIssue(
                    issue_type="wrong_column",
                    severity="low",
                    description="SELECT * without LIMIT may return excessive data",
                    code_snippet=sql[:80],
                    suggested_fix="Add LIMIT clause or select specific columns",
                ))

        return issues

    def _check_pandas_issues(self, code: str, task: str) -> List[ImplementationIssue]:
        """Check for pandas-specific errors."""
        issues = []

        # .sort_values() direction check
        sort_matches = re.findall(r"sort_values\s*\(.*?ascending\s*=\s*(True|False)", code)
        if sort_matches:
            if "top" in task.lower() or "highest" in task.lower() or "best" in task.lower():
                if "True" in sort_matches:
                    issues.append(ImplementationIssue(
                        issue_type="wrong_sort",
                        severity="high",
                        description="Task asks for 'top/highest' but sort is ascending=True (should be False)",
                        suggested_fix="Change ascending=True to ascending=False",
                    ))
            elif "lowest" in task.lower() or "bottom" in task.lower() or "worst" in task.lower():
                if "False" in sort_matches:
                    issues.append(ImplementationIssue(
                        issue_type="wrong_sort",
                        severity="high",
                        description="Task asks for 'lowest/bottom' but sort is ascending=False (should be True)",
                    ))

        # .head() without sort (returns arbitrary rows)
        if ".head(" in code and "sort" not in code.lower() and "rank" in task.lower():
            issues.append(ImplementationIssue(
                issue_type="wrong_sort",
                severity="medium",
                description=".head() used without sorting — returns arbitrary rows, not ranked",
            ))

        return issues

    def _check_output_mismatch(self, output: str, expected: str) -> List[ImplementationIssue]:
        """Check if actual output matches expected output."""
        issues = []

        if output.strip() != expected.strip():
            # Check if it's a formatting issue vs wrong answer
            try:
                out_num = float(re.sub(r"[^\d.-]", "", output))
                exp_num = float(re.sub(r"[^\d.-]", "", expected))
                if abs(out_num - exp_num) / max(abs(exp_num), 1e-10) > 0.01:
                    issues.append(ImplementationIssue(
                        issue_type="wrong_answer",
                        severity="critical",
                        description=f"Output '{output[:50]}' differs from expected '{expected[:50]}' by more than 1%",
                    ))
            except (ValueError, ZeroDivisionError):
                if output.strip().lower() != expected.strip().lower():
                    issues.append(ImplementationIssue(
                        issue_type="wrong_answer",
                        severity="critical",
                        description=f"Output doesn't match expected answer",
                    ))

        return issues

    def _check_common_mistakes(self, code: str) -> List[ImplementationIssue]:
        """Check for common coding mistakes."""
        issues = []

        # Division by zero risk
        if re.search(r"/\s*(?:len|count|sum)\s*\(", code) and "if" not in code:
            issues.append(ImplementationIssue(
                issue_type="missing_guard",
                severity="low",
                description="Division by aggregate (len/count/sum) without zero-check",
            ))

        # .iloc[0] without checking if dataframe is empty
        if ".iloc[0]" in code and "len(" not in code and "empty" not in code:
            issues.append(ImplementationIssue(
                issue_type="missing_guard",
                severity="medium",
                description=".iloc[0] without checking if dataframe is empty — may raise IndexError",
            ))

        return issues


# Singleton
implementation_detector = ImplementationCorrectnessDetector()
