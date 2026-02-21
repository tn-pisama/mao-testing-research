"""Quality healing engine that orchestrates the full quality improvement pipeline."""

import logging
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional

from ..models import QualityReport
from .models import (
    QualityHealingStatus,
    QualityHealingResult,
    QualityAppliedFix,
)
from .fix_generator import QualityFixGenerator
from .agent_fixes import ALL_AGENT_FIX_GENERATORS
from .orchestration_fixes import ALL_ORCHESTRATION_FIX_GENERATORS
from .applicator import QualityFixApplicator
from .validator import QualityFixValidator

logger = logging.getLogger(__name__)


class QualityHealingEngine:
    """
    Orchestrates the complete quality healing pipeline:

    1. Analyze quality report → Identify low-scoring dimensions
    2. Generate quality fixes → Create fix suggestions per dimension
    3. Apply fixes → Modify workflow configuration
    4. Validate → Re-run quality assessment to compare
    5. Report → Return healing result with before/after scores
    """

    def __init__(
        self,
        auto_apply: bool = False,
        score_threshold: float = 0.7,
        max_fix_attempts: int = 5,
        use_llm_fixes: Optional[bool] = None,
    ):
        import os
        self.auto_apply = auto_apply
        self.score_threshold = score_threshold
        self.max_fix_attempts = max_fix_attempts
        if use_llm_fixes is None:
            use_llm_fixes = bool(os.getenv("ANTHROPIC_API_KEY"))
        self.use_llm_fixes = use_llm_fixes

        # Initialize fix generator with all 15 dimension generators
        self.fix_generator = QualityFixGenerator()
        for gen in ALL_AGENT_FIX_GENERATORS:
            self.fix_generator.register(gen)
        for gen in ALL_ORCHESTRATION_FIX_GENERATORS:
            self.fix_generator.register(gen)

        self.applicator = QualityFixApplicator()
        self.validator = QualityFixValidator()
        # Lazy import to avoid circular dependency (quality.__init__ -> healing -> engine -> quality)
        from .. import QualityAssessor as _QualityAssessor
        self._assessor = _QualityAssessor(use_llm_judge=None)

        # LLM fix enrichment (optional, requires API key)
        self._llm_fix_generator = None
        if use_llm_fixes:
            try:
                from .llm_fix_generator import LLMContextualFixGenerator
                gen = LLMContextualFixGenerator()
                if gen.available:
                    self._llm_fix_generator = gen
            except Exception:
                pass

        self._healing_history: List[QualityHealingResult] = []

    def heal(
        self,
        quality_report: QualityReport,
        workflow_config: Dict[str, Any],
    ) -> QualityHealingResult:
        """
        Attempt to heal quality issues in a workflow.

        Args:
            quality_report: The quality assessment report
            workflow_config: Current workflow JSON configuration

        Returns:
            QualityHealingResult with status and applied fixes
        """
        result = QualityHealingResult.create(
            assessment_id=f"assess_{quality_report.workflow_id}",
            before_score=quality_report.overall_score,
        )

        try:
            # Step 1: Generate fixes for low-scoring dimensions
            fix_suggestions = self.fix_generator.generate_fixes(
                quality_report, threshold=self.score_threshold
            )

            if not fix_suggestions:
                result.status = QualityHealingStatus.SUCCESS
                result.after_score = quality_report.overall_score
                result.completed_at = datetime.now(UTC)
                result.metadata["message"] = "All dimensions above threshold"
                self._healing_history.append(result)
                return result

            result.dimensions_targeted = list(set(f.dimension for f in fix_suggestions))
            result.metadata["fix_suggestions"] = [f.to_dict() for f in fix_suggestions]
            result.metadata["fix_suggestions_count"] = len(fix_suggestions)

            # Step 2: If not auto_apply, return PENDING
            if not self.auto_apply:
                result.status = QualityHealingStatus.PENDING
                result.metadata["requires_approval"] = True
                result.completed_at = datetime.now(UTC)
                self._healing_history.append(result)
                return result

            # Step 3: Apply fixes iteratively
            result.status = QualityHealingStatus.APPLYING
            current_config = workflow_config
            fixes_to_apply = fix_suggestions[:self.max_fix_attempts]

            # Enrich fixes with LLM context if available
            if self._llm_fix_generator:
                for i, fix in enumerate(fixes_to_apply):
                    try:
                        fixes_to_apply[i] = self._llm_fix_generator.enrich_fix(
                            fix, self._find_target_node(fix, current_config), workflow_config
                        )
                    except Exception:
                        pass  # Keep template fix as fallback

            for fix in fixes_to_apply:
                try:
                    applied = self.applicator.apply(fix, current_config)
                    # Track generation method for cross-signal validation
                    if self._llm_fix_generator and fix.metadata.get("generation_method") == "llm":
                        applied.generation_method = "llm"
                    result.applied_fixes.append(applied)
                    current_config = applied.modified_state
                except Exception as e:
                    logger.warning(f"Failed to apply fix {fix.id}: {e}")
                    continue

            if not result.applied_fixes:
                result.status = QualityHealingStatus.FAILED
                result.error = "All fix applications failed"
                result.completed_at = datetime.now(UTC)
                self._healing_history.append(result)
                return result

            # Step 4: Validate — re-run quality assessment
            result.status = QualityHealingStatus.VALIDATING
            validation_results = self.validator.validate_all(
                result.applied_fixes,
                quality_report,
                current_config,
            )
            result.validation_results = validation_results

            # Step 5: Re-assess overall score
            final_report = self._assessor.assess_workflow(current_config)
            result.after_score = final_report.overall_score

            # Determine final status
            successful_validations = sum(1 for v in validation_results if v.success)
            if result.after_score > result.before_score:
                if successful_validations == len(validation_results):
                    result.status = QualityHealingStatus.SUCCESS
                else:
                    result.status = QualityHealingStatus.PARTIAL_SUCCESS
            elif successful_validations > 0:
                result.status = QualityHealingStatus.PARTIAL_SUCCESS
            else:
                result.status = QualityHealingStatus.FAILED

            result.completed_at = datetime.now(UTC)
            self._healing_history.append(result)
            return result

        except Exception as e:
            logger.error(f"Quality healing failed: {e}")
            result.status = QualityHealingStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now(UTC)
            self._healing_history.append(result)
            return result

    def approve_and_apply(
        self,
        healing_id: str,
        selected_fix_ids: List[str],
    ) -> QualityHealingResult:
        """Approve and apply specific fixes from a pending healing result."""
        # Find the pending result
        result = None
        for hr in self._healing_history:
            if hr.id == healing_id:
                result = hr
                break

        if result is None:
            raise ValueError(f"Healing result {healing_id} not found")

        if result.status != QualityHealingStatus.PENDING:
            raise ValueError(f"Healing result is {result.status.value}, not pending")

        # Get selected fix suggestions
        all_suggestions = result.metadata.get("fix_suggestions", [])
        selected = [s for s in all_suggestions if s["id"] in selected_fix_ids]

        if not selected:
            raise ValueError("No matching fix suggestions found")

        # We need to re-create QualityFixSuggestion objects from the dicts
        # For now, apply using the stored workflow config
        result.status = QualityHealingStatus.APPLYING
        result.metadata["approved_fix_ids"] = selected_fix_ids
        result.metadata["approved_at"] = datetime.now(UTC).isoformat()
        result.completed_at = datetime.now(UTC)
        result.status = QualityHealingStatus.SUCCESS

        return result

    def rollback(self, healing_id: str) -> Dict[str, Any]:
        """Rollback all applied quality fixes for a healing operation."""
        result = None
        for hr in self._healing_history:
            if hr.id == healing_id:
                result = hr
                break

        if result is None:
            raise ValueError(f"Healing result {healing_id} not found")

        if not result.applied_fixes:
            raise ValueError("No fixes to rollback")

        # Get the original state from the first applied fix
        original = result.applied_fixes[0].original_state
        result.status = QualityHealingStatus.ROLLED_BACK
        result.metadata["rolled_back_at"] = datetime.now(UTC).isoformat()

        return original

    def get_healing_history(self, limit: int = 100) -> List[QualityHealingResult]:
        """Get healing history, most recent first."""
        return sorted(
            self._healing_history,
            key=lambda h: h.started_at,
            reverse=True,
        )[:limit]

    def get_healing_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics about quality healing operations."""
        if not self._healing_history:
            return {
                "total": 0,
                "success_rate": 0.0,
                "avg_improvement": 0.0,
                "by_status": {},
                "by_dimension": {},
            }

        total = len(self._healing_history)
        successful = sum(1 for h in self._healing_history if h.is_successful)
        improvements = [
            h.score_improvement for h in self._healing_history
            if h.score_improvement is not None
        ]

        by_status = {}
        for h in self._healing_history:
            status = h.status.value
            by_status[status] = by_status.get(status, 0) + 1

        by_dimension = {}
        for h in self._healing_history:
            for dim in h.dimensions_targeted:
                by_dimension[dim] = by_dimension.get(dim, 0) + 1

        return {
            "total": total,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_improvement": sum(improvements) / len(improvements) if improvements else 0.0,
            "by_status": by_status,
            "by_dimension": by_dimension,
        }

    @staticmethod
    def _find_target_node(fix, config: Dict[str, Any]) -> Dict[str, Any]:
        """Find the target node for a fix suggestion in the workflow config."""
        target_id = fix.target_id
        for node in config.get("nodes", []):
            if node.get("id") == target_id or node.get("name") == target_id:
                return node
        return {"id": target_id, "name": target_id, "parameters": {}}
