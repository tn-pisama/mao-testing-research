"""CSV export for PISAMA quality reports.

Produces a flat CSV representation of a :class:`QualityReport` with one row
per quality dimension (both agent-level and orchestration-level dimensions).
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import QualityReport

from ..error_codes import get_codes_for_dimension
from ..models import _score_to_grade


class QualityCSVReporter:
    """Export a :class:`QualityReport` as a CSV string.

    Columns produced for every dimension row:

    * ``scope``       -- ``"agent"`` or ``"orchestration"``
    * ``target``      -- Agent name or workflow name
    * ``dimension``   -- Dimension identifier (e.g. ``role_clarity``)
    * ``score``       -- Numeric score 0.0-1.0
    * ``grade``       -- Health tier (Healthy / Degraded / At Risk / Critical)
    * ``issues``      -- Semicolon-separated issue descriptions
    * ``suggestions`` -- Semicolon-separated improvement suggestions
    * ``error_codes`` -- Semicolon-separated applicable error codes
    """

    COLUMNS = [
        "scope",
        "target",
        "dimension",
        "score",
        "grade",
        "issues",
        "suggestions",
        "error_codes",
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export_report(self, report: "QualityReport") -> str:
        """Render the quality report as a CSV string.

        Args:
            report: A fully populated :class:`QualityReport`.

        Returns:
            A UTF-8 CSV string with a header row followed by one row per
            dimension.
        """
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=self.COLUMNS)
        writer.writeheader()

        # Agent dimension rows
        for agent_score in report.agent_scores:
            for dim in agent_score.dimensions:
                writer.writerow(
                    self._dimension_row(
                        scope="agent",
                        target=agent_score.agent_name,
                        dim_name=dim.dimension,
                        score=dim.score,
                        issues=dim.issues,
                        suggestions=dim.suggestions,
                    )
                )

        # Orchestration dimension rows
        for dim in report.orchestration_score.dimensions:
            writer.writerow(
                self._dimension_row(
                    scope="orchestration",
                    target=report.workflow_name,
                    dim_name=dim.dimension,
                    score=dim.score,
                    issues=dim.issues,
                    suggestions=dim.suggestions,
                )
            )

        return buf.getvalue()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _dimension_row(
        scope: str,
        target: str,
        dim_name: str,
        score: float,
        issues: list[str],
        suggestions: list[str],
    ) -> dict:
        """Build a single CSV row dict."""
        applicable_codes = get_codes_for_dimension(dim_name)
        code_strs = [ec.code for ec in applicable_codes]

        return {
            "scope": scope,
            "target": target,
            "dimension": dim_name,
            "score": f"{score:.3f}",
            "grade": _score_to_grade(score),
            "issues": "; ".join(issues) if issues else "",
            "suggestions": "; ".join(suggestions) if suggestions else "",
            "error_codes": "; ".join(code_strs) if code_strs else "",
        }
