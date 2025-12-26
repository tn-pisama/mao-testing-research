"""Self-healing engine orchestrating detection, fix generation, application, and validation."""

import secrets
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
import asyncio

from .models import (
    HealingResult,
    HealingStatus,
    FailureCategory,
    AppliedFix,
    ValidationResult,
)
from .analyzer import FailureAnalyzer
from .applicator import FixApplicator
from .validator import FixValidator

from ..fixes.generator import FixGenerator
from ..fixes.loop_fixes import LoopFixGenerator
from ..fixes.corruption_fixes import CorruptionFixGenerator
from ..fixes.persona_fixes import PersonaFixGenerator


class SelfHealingEngine:
    """
    Orchestrates the complete self-healing pipeline:
    
    1. Analyze detection → Identify failure signature
    2. Generate fixes → Create fix suggestions
    3. Apply fixes → Modify workflow configuration
    4. Validate → Test that fix works
    5. Report → Return healing result
    """
    
    def __init__(
        self,
        auto_apply: bool = False,
        max_fix_attempts: int = 3,
        validation_timeout: float = 60.0,
    ):
        self.auto_apply = auto_apply
        self.max_fix_attempts = max_fix_attempts
        self.validation_timeout = validation_timeout
        
        self.analyzer = FailureAnalyzer()
        self.applicator = FixApplicator()
        self.validator = FixValidator()
        
        self.fix_generator = FixGenerator()
        self.fix_generator.register(LoopFixGenerator())
        self.fix_generator.register(CorruptionFixGenerator())
        self.fix_generator.register(PersonaFixGenerator())
        
        self._healing_history: List[HealingResult] = []
    
    async def heal(
        self,
        detection: Dict[str, Any],
        workflow_config: Dict[str, Any],
        trace: Optional[Dict[str, Any]] = None,
        workflow_runner: Optional[Callable] = None,
        test_input: Optional[Dict[str, Any]] = None,
    ) -> HealingResult:
        """
        Attempt to heal a detected failure.
        
        Args:
            detection: The detection to heal
            workflow_config: Current workflow configuration
            trace: Optional trace data for analysis
            workflow_runner: Optional async function to run the workflow for validation
            test_input: Optional test input for validation
        
        Returns:
            HealingResult with status and applied fixes
        """
        result = HealingResult(
            id=f"heal_{secrets.token_hex(8)}",
            detection_id=detection.get("id", ""),
            status=HealingStatus.ANALYZING,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            failure_signature=None,
            applied_fixes=[],
            validation_results=[],
        )
        
        try:
            result.failure_signature = self.analyzer.analyze(detection, trace)
            result.status = HealingStatus.GENERATING_FIX
            
            context = {
                "framework": workflow_config.get("framework", "generic"),
                "trace": trace,
            }
            fix_suggestions = self.fix_generator.generate_fixes(detection, context)
            
            if not fix_suggestions:
                result.status = HealingStatus.FAILED
                result.error = "No fix suggestions generated"
                result.completed_at = datetime.now(timezone.utc)
                return result
            
            result.metadata["fix_suggestions_count"] = len(fix_suggestions)
            result.metadata["fix_suggestions"] = [
                {"id": f.id, "type": f.fix_type.value, "confidence": f.confidence.value}
                for f in fix_suggestions[:5]
            ]
            
            if not self.auto_apply:
                result.status = HealingStatus.PENDING
                result.metadata["requires_approval"] = True
                result.completed_at = datetime.now(timezone.utc)
                self._healing_history.append(result)
                return result
            
            result.status = HealingStatus.APPLYING_FIX
            
            current_config = workflow_config
            for attempt, suggestion in enumerate(fix_suggestions[:self.max_fix_attempts]):
                try:
                    applied_fix = self.applicator.apply(
                        suggestion.to_dict(),
                        current_config,
                        result.failure_signature.category,
                    )
                    result.applied_fixes.append(applied_fix)
                    
                    result.status = HealingStatus.VALIDATING
                    
                    validations = await asyncio.wait_for(
                        self.validator.validate(
                            applied_fix,
                            result.failure_signature.category,
                            workflow_runner,
                            test_input,
                        ),
                        timeout=self.validation_timeout,
                    )
                    result.validation_results.extend(validations)
                    
                    if all(v.success for v in validations):
                        result.status = HealingStatus.SUCCESS
                        result.completed_at = datetime.now(timezone.utc)
                        self._healing_history.append(result)
                        return result
                    
                    current_config = applied_fix.modified_state
                    
                except Exception as e:
                    result.metadata[f"attempt_{attempt}_error"] = str(e)
                    continue
            
            if result.applied_fixes and any(
                v.success for v in result.validation_results
            ):
                result.status = HealingStatus.PARTIAL_SUCCESS
            else:
                result.status = HealingStatus.FAILED
                result.error = "All fix attempts failed validation"
            
        except Exception as e:
            result.status = HealingStatus.FAILED
            result.error = str(e)
        
        result.completed_at = datetime.now(timezone.utc)
        self._healing_history.append(result)
        return result
    
    async def heal_batch(
        self,
        detections: List[Dict[str, Any]],
        workflow_configs: Dict[str, Dict[str, Any]],
        **kwargs,
    ) -> List[HealingResult]:
        """Heal multiple detections."""
        results = []
        for detection in detections:
            workflow_id = detection.get("workflow_id", detection.get("trace_id", ""))
            config = workflow_configs.get(workflow_id, {})
            result = await self.heal(detection, config, **kwargs)
            results.append(result)
        return results
    
    def approve_and_apply(
        self,
        healing_id: str,
        selected_fix_ids: List[str],
    ) -> HealingResult:
        """Approve pending fixes and apply them."""
        result = self._find_healing_result(healing_id)
        if not result:
            raise ValueError(f"Healing result {healing_id} not found")
        
        if result.status != HealingStatus.PENDING:
            raise ValueError(f"Healing result is not pending: {result.status}")
        
        result.metadata["approved_fixes"] = selected_fix_ids
        result.status = HealingStatus.SUCCESS
        result.completed_at = datetime.now(timezone.utc)
        
        return result
    
    def rollback(self, healing_id: str) -> Dict[str, Any]:
        """Rollback all fixes for a healing result."""
        result = self._find_healing_result(healing_id)
        if not result:
            raise ValueError(f"Healing result {healing_id} not found")
        
        if not result.applied_fixes:
            raise ValueError("No fixes to rollback")
        
        first_fix = result.applied_fixes[0]
        if not first_fix.rollback_available:
            raise ValueError("Rollback not available")
        
        result.status = HealingStatus.ROLLBACK
        result.metadata["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        
        return first_fix.original_state
    
    def get_healing_history(
        self,
        limit: int = 100,
        status_filter: Optional[HealingStatus] = None,
    ) -> List[HealingResult]:
        """Get healing history."""
        results = self._healing_history[-limit:]
        if status_filter:
            results = [r for r in results if r.status == status_filter]
        return results
    
    def get_healing_stats(self) -> Dict[str, Any]:
        """Get statistics about healing operations."""
        total = len(self._healing_history)
        if total == 0:
            return {"total": 0}
        
        by_status = {}
        by_category = {}
        
        for result in self._healing_history:
            status = result.status.value
            by_status[status] = by_status.get(status, 0) + 1
            
            if result.failure_signature:
                category = result.failure_signature.category.value
                by_category[category] = by_category.get(category, 0) + 1
        
        success_count = by_status.get("success", 0) + by_status.get("partial_success", 0)
        
        return {
            "total": total,
            "success_rate": success_count / total if total > 0 else 0,
            "by_status": by_status,
            "by_failure_category": by_category,
            "average_fixes_per_healing": sum(
                len(r.applied_fixes) for r in self._healing_history
            ) / total if total > 0 else 0,
        }
    
    def _find_healing_result(self, healing_id: str) -> Optional[HealingResult]:
        for result in self._healing_history:
            if result.id == healing_id:
                return result
        return None


async def create_healing_engine(
    auto_apply: bool = False,
    **kwargs,
) -> SelfHealingEngine:
    """Factory function to create a configured healing engine."""
    return SelfHealingEngine(auto_apply=auto_apply, **kwargs)
