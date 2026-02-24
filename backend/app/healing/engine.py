"""Self-healing engine orchestrating detection, fix generation, application, and validation."""

import secrets
import logging
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
from .auto_apply import AutoApplyService, AutoApplyConfig, ApplyResult
from .git_backup import GitBackupService, GitBackupConfig

from ..fixes.generator import FixGenerator
from ..fixes.loop_fixes import LoopFixGenerator
from ..fixes.corruption_fixes import CorruptionFixGenerator
from ..fixes.persona_fixes import PersonaFixGenerator
from ..fixes.deadlock_fixes import DeadlockFixGenerator
from ..fixes.hallucination_fixes import HallucinationFixGenerator
from ..fixes.injection_fixes import InjectionFixGenerator
from ..fixes.overflow_fixes import OverflowFixGenerator
from ..fixes.derailment_fixes import DerailmentFixGenerator
from ..fixes.context_neglect_fixes import ContextNeglectFixGenerator
from ..fixes.communication_fixes import CommunicationFixGenerator
from ..fixes.specification_fixes import SpecificationFixGenerator
from ..fixes.decomposition_fixes import DecompositionFixGenerator
from ..fixes.workflow_fixes import WorkflowFixGenerator
from ..fixes.withholding_fixes import WithholdingFixGenerator
from ..fixes.completion_fixes import CompletionFixGenerator
from ..fixes.cost_fixes import CostFixGenerator

logger = logging.getLogger(__name__)


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
        auto_apply_service: Optional[AutoApplyService] = None,
        git_backup_service: Optional[GitBackupService] = None,
        auto_apply_config: Optional[AutoApplyConfig] = None,
        git_backup_config: Optional[GitBackupConfig] = None,
    ):
        self.auto_apply = auto_apply
        self.max_fix_attempts = max_fix_attempts
        self.validation_timeout = validation_timeout

        # Initialize auto-apply service (for n8n workflows)
        if auto_apply_service:
            self.auto_apply_service = auto_apply_service
        elif auto_apply_config:
            self.auto_apply_service = AutoApplyService(auto_apply_config)
        else:
            self.auto_apply_service = AutoApplyService() if auto_apply else None

        # Initialize git backup service
        if git_backup_service:
            self.git_backup_service = git_backup_service
        elif git_backup_config:
            self.git_backup_service = GitBackupService(git_backup_config)
        else:
            self.git_backup_service = None

        self.analyzer = FailureAnalyzer()
        self.applicator = FixApplicator()
        self.validator = FixValidator()

        # Per-workflow locks to prevent concurrent healing on the same workflow
        self._workflow_locks: Dict[str, asyncio.Lock] = {}

        self.fix_generator = FixGenerator()
        self.fix_generator.register(LoopFixGenerator())
        self.fix_generator.register(CorruptionFixGenerator())
        self.fix_generator.register(PersonaFixGenerator())
        self.fix_generator.register(DeadlockFixGenerator())
        self.fix_generator.register(HallucinationFixGenerator())
        self.fix_generator.register(InjectionFixGenerator())
        self.fix_generator.register(OverflowFixGenerator())
        self.fix_generator.register(DerailmentFixGenerator())
        self.fix_generator.register(ContextNeglectFixGenerator())
        self.fix_generator.register(CommunicationFixGenerator())
        self.fix_generator.register(SpecificationFixGenerator())
        self.fix_generator.register(DecompositionFixGenerator())
        self.fix_generator.register(WorkflowFixGenerator())
        self.fix_generator.register(WithholdingFixGenerator())
        self.fix_generator.register(CompletionFixGenerator())
        self.fix_generator.register(CostFixGenerator())

        self._healing_history: List[HealingResult] = []
        self._apply_results: List[ApplyResult] = []

    def _get_workflow_lock(self, workflow_id: str) -> asyncio.Lock:
        """Get or create an asyncio.Lock for a workflow to prevent concurrent healing."""
        if workflow_id not in self._workflow_locks:
            self._workflow_locks[workflow_id] = asyncio.Lock()
        return self._workflow_locks[workflow_id]

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

    async def heal_n8n_workflow(
        self,
        detection: Dict[str, Any],
        workflow_id: str,
        n8n_client: Any,
        trace: Optional[Dict[str, Any]] = None,
    ) -> HealingResult:
        """
        Heal an n8n workflow with auto-apply and git backup.

        This is the main entry point for solo developers using n8n.
        It combines detection, fix generation, git backup, and auto-apply.

        Acquires a per-workflow lock to prevent concurrent healing operations
        on the same workflow, which could corrupt state.

        Args:
            detection: The detection result to heal
            workflow_id: n8n workflow ID
            n8n_client: n8n API client
            trace: Optional trace data for analysis

        Returns:
            HealingResult with status and applied fixes
        """
        lock = self._get_workflow_lock(workflow_id)

        if lock.locked():
            # Another healing is already in progress for this workflow
            return HealingResult(
                id=f"heal_{secrets.token_hex(8)}",
                detection_id=detection.get("id", ""),
                status=HealingStatus.FAILED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                failure_signature=None,
                applied_fixes=[],
                validation_results=[],
                error=f"Concurrent healing blocked: another healing is in progress for workflow {workflow_id}",
            )

        async with lock:
            return await self._heal_n8n_workflow_locked(
                detection, workflow_id, n8n_client, trace,
            )

    async def _heal_n8n_workflow_locked(
        self,
        detection: Dict[str, Any],
        workflow_id: str,
        n8n_client: Any,
        trace: Optional[Dict[str, Any]] = None,
    ) -> HealingResult:
        """Internal: heal workflow while holding the workflow lock."""
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
            # Step 1: Analyze the detection
            result.failure_signature = self.analyzer.analyze(detection, trace)
            result.status = HealingStatus.GENERATING_FIX
            logger.info(f"Analyzed failure: {result.failure_signature.category.value}")

            # Step 2: Get workflow config from n8n
            workflow_config = await n8n_client.get_workflow(workflow_id)

            # Step 3: Generate fix suggestions
            context = {
                "framework": "n8n",
                "trace": trace,
                "workflow_id": workflow_id,
            }
            fix_suggestions = self.fix_generator.generate_fixes(detection, context)

            if not fix_suggestions:
                result.status = HealingStatus.FAILED
                result.error = "No fix suggestions generated"
                result.completed_at = datetime.now(timezone.utc)
                return result

            result.metadata["fix_suggestions_count"] = len(fix_suggestions)
            logger.info(f"Generated {len(fix_suggestions)} fix suggestions")

            # Step 4: Check if auto-apply is available
            if not self.auto_apply or not self.auto_apply_service:
                result.status = HealingStatus.PENDING
                result.metadata["requires_approval"] = True
                result.metadata["fix_suggestions"] = [
                    {"id": f.id, "type": f.fix_type.value, "confidence": f.confidence.value}
                    for f in fix_suggestions[:5]
                ]
                result.completed_at = datetime.now(timezone.utc)
                self._healing_history.append(result)
                return result

            # Step 5: Check rate limit
            if not self.auto_apply_service.check_rate_limit(workflow_id):
                result.status = HealingStatus.PENDING
                result.error = "Rate limited - too many fixes applied recently"
                result.completed_at = datetime.now(timezone.utc)
                self._healing_history.append(result)
                return result

            result.status = HealingStatus.APPLYING_FIX

            # Step 6: Apply fixes using auto-apply service
            for suggestion in fix_suggestions[:self.max_fix_attempts]:
                fix_dict = suggestion.to_dict()

                apply_result = await self.auto_apply_service.apply_fix(
                    fix=fix_dict,
                    workflow_id=workflow_id,
                    healing_id=result.id,
                    n8n_client=n8n_client,
                    git_backup=self.git_backup_service,
                )

                self._apply_results.append(apply_result)

                if apply_result.success:
                    # Record the applied fix
                    applied_fix = AppliedFix(
                        fix_id=suggestion.id,
                        fix_type=suggestion.fix_type.value,
                        applied_at=apply_result.applied_at or datetime.now(timezone.utc),
                        target_component=suggestion.target_component,
                        original_state=workflow_config,
                        modified_state=fix_dict.get("modified_state", {}),
                        rollback_available=apply_result.backup_commit_sha is not None,
                    )
                    result.applied_fixes.append(applied_fix)

                    result.status = HealingStatus.SUCCESS
                    result.metadata["backup_commit_sha"] = apply_result.backup_commit_sha
                    result.completed_at = datetime.now(timezone.utc)
                    self._healing_history.append(result)

                    logger.info(f"Successfully healed workflow {workflow_id}")
                    return result

                elif apply_result.rolled_back:
                    logger.warning(f"Fix rolled back for workflow {workflow_id}")
                    continue

                else:
                    logger.warning(f"Fix failed for workflow {workflow_id}: {apply_result.error}")
                    continue

            # All fixes failed
            result.status = HealingStatus.FAILED
            result.error = "All fix attempts failed"

        except Exception as e:
            result.status = HealingStatus.FAILED
            result.error = str(e)
            logger.error(f"Healing failed for workflow {workflow_id}: {e}")

        result.completed_at = datetime.now(timezone.utc)
        self._healing_history.append(result)
        return result

    def get_apply_results(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ApplyResult]:
        """Get auto-apply results."""
        results = self._apply_results[-limit:]
        if workflow_id:
            results = [r for r in results if r.workflow_id == workflow_id]
        return results


async def create_healing_engine(
    auto_apply: bool = False,
    git_backup_path: Optional[str] = None,
    auto_apply_config: Optional[AutoApplyConfig] = None,
    **kwargs,
) -> SelfHealingEngine:
    """Factory function to create a configured healing engine.

    Args:
        auto_apply: Enable automatic fix application
        git_backup_path: Path to git backup repository
        auto_apply_config: Configuration for auto-apply service
        **kwargs: Additional arguments for SelfHealingEngine

    Returns:
        Configured SelfHealingEngine instance
    """
    git_backup_service = None
    if git_backup_path:
        git_backup_config = GitBackupConfig(repo_path=git_backup_path)
        git_backup_service = GitBackupService(git_backup_config)
        await git_backup_service.initialize()

    return SelfHealingEngine(
        auto_apply=auto_apply,
        auto_apply_config=auto_apply_config,
        git_backup_service=git_backup_service,
        **kwargs,
    )
