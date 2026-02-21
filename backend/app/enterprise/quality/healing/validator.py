"""Validator that re-runs quality assessment to verify fixes improved scores."""

from typing import Dict, Any, List, Optional

from ..models import QualityReport, DimensionScore
from .models import QualityAppliedFix, QualityValidationResult


class QualityFixValidator:
    """Validates quality fixes by re-running the quality assessor."""

    def __init__(self):
        # Import here to avoid circular imports
        from .. import QualityAssessor
        self._assessor = QualityAssessor(use_llm_judge=False)

    def validate(
        self,
        applied_fix: QualityAppliedFix,
        original_report: QualityReport,
    ) -> QualityValidationResult:
        """Re-assess the modified workflow and compare dimension scores."""
        # Re-run quality assessment on modified config
        new_report = self._assessor.assess_workflow(applied_fix.modified_state)

        # Find the specific dimension score
        dimension = applied_fix.dimension
        before_score = self._find_dimension_score(original_report, dimension)
        after_score = self._find_dimension_score(new_report, dimension)
        improvement = after_score - before_score

        return QualityValidationResult(
            success=after_score > before_score,
            dimension=dimension,
            before_score=before_score,
            after_score=after_score,
            improvement=improvement,
            details={
                "overall_before": original_report.overall_score,
                "overall_after": new_report.overall_score,
                "overall_improvement": new_report.overall_score - original_report.overall_score,
            },
        )

    def validate_all(
        self,
        applied_fixes: List[QualityAppliedFix],
        original_report: QualityReport,
        final_config: Dict[str, Any],
    ) -> List[QualityValidationResult]:
        """Validate all applied fixes by re-assessing the final config."""
        new_report = self._assessor.assess_workflow(final_config)
        results: List[QualityValidationResult] = []
        for fix in applied_fixes:
            dimension = fix.dimension
            before_score = self._find_dimension_score(original_report, dimension)
            after_score = self._find_dimension_score(new_report, dimension)
            results.append(QualityValidationResult(
                success=after_score > before_score,
                dimension=dimension,
                before_score=before_score,
                after_score=after_score,
                improvement=after_score - before_score,
                details={
                    "overall_before": original_report.overall_score,
                    "overall_after": new_report.overall_score,
                },
            ))
        return results

    @staticmethod
    def _find_dimension_score(report: QualityReport, dimension: str) -> float:
        """Find score for a dimension in a quality report."""
        # Check agent dimensions
        for agent in report.agent_scores:
            for dim in agent.dimensions:
                if dim.dimension == dimension:
                    return dim.score
        # Check orchestration dimensions
        for dim in report.orchestration_score.dimensions:
            if dim.dimension == dimension:
                return dim.score
        return 0.0
