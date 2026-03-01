"""Fix generators for context neglect detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class ContextNeglectFixGenerator(BaseFixGenerator):
    """Generates fixes for context neglect detections."""

    def can_handle(self, detection_type: str) -> bool:
        return "context" in detection_type and "overflow" not in detection_type

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._checkpoint_recovery_fix(detection_id, details, context))
        fixes.append(self._prompt_reinforcement_fix(detection_id, details, context))
        fixes.append(self._state_validation_fix(detection_id, details, context))

        return fixes

    def _checkpoint_recovery_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import copy
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ContextCheckpoint:
    """Snapshot of context at a specific point in the pipeline."""
    step_name: str
    timestamp: datetime
    context_snapshot: Dict[str, Any]
    context_keys: List[str]
    checksum: str


class ContextCheckpointManager:
    """
    Manages context checkpoints throughout multi-agent pipelines.
    Detects when context items are dropped and enables rollback.
    """

    def __init__(self, max_checkpoints: int = 50):
        self._checkpoints: List[ContextCheckpoint] = []
        self._max_checkpoints = max_checkpoints

    def _compute_checksum(self, ctx: Dict[str, Any]) -> str:
        import hashlib
        import json
        serialized = json.dumps(sorted(ctx.keys()))
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def save_checkpoint(self, step_name: str, ctx: Dict[str, Any]) -> ContextCheckpoint:
        """Save a context checkpoint before a pipeline step."""
        checkpoint = ContextCheckpoint(
            step_name=step_name,
            timestamp=datetime.utcnow(),
            context_snapshot=copy.deepcopy(ctx),
            context_keys=list(ctx.keys()),
            checksum=self._compute_checksum(ctx),
        )
        self._checkpoints.append(checkpoint)
        if len(self._checkpoints) > self._max_checkpoints:
            self._checkpoints.pop(0)
        logger.debug(f"Checkpoint saved at step '{step_name}' with {len(ctx)} keys")
        return checkpoint

    def detect_context_loss(
        self, current_ctx: Dict[str, Any], required_keys: Optional[List[str]] = None
    ) -> List[str]:
        """Detect context keys that were present in the last checkpoint but are now missing."""
        if not self._checkpoints:
            return []
        last = self._checkpoints[-1]
        expected_keys = set(required_keys or last.context_keys)
        current_keys = set(current_ctx.keys())
        missing = list(expected_keys - current_keys)
        if missing:
            logger.warning(
                f"Context loss detected: {len(missing)} keys missing since "
                f"step '{last.step_name}': {missing}"
            )
        return missing

    def rollback(self, step_name: Optional[str] = None) -> Dict[str, Any]:
        """Rollback context to a previous checkpoint."""
        if not self._checkpoints:
            raise ValueError("No checkpoints available for rollback")
        if step_name:
            for cp in reversed(self._checkpoints):
                if cp.step_name == step_name:
                    logger.info(f"Rolling back context to step '{step_name}'")
                    return copy.deepcopy(cp.context_snapshot)
            raise ValueError(f"No checkpoint found for step '{step_name}'")
        last = self._checkpoints[-1]
        logger.info(f"Rolling back context to last checkpoint at '{last.step_name}'")
        return copy.deepcopy(last.context_snapshot)

    def restore_missing_keys(self, current_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Restore only the missing keys from the most recent checkpoint."""
        missing = self.detect_context_loss(current_ctx)
        if not missing or not self._checkpoints:
            return current_ctx
        last = self._checkpoints[-1]
        restored = dict(current_ctx)
        for key in missing:
            if key in last.context_snapshot:
                restored[key] = copy.deepcopy(last.context_snapshot[key])
                logger.info(f"Restored missing context key: '{key}'")
        return restored'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="context_neglect",
            fix_type=FixType.CHECKPOINT_RECOVERY,
            confidence=FixConfidence.HIGH,
            title="Add context checkpoints with rollback for context preservation",
            description="Save context snapshots before each pipeline step and detect when context items are dropped. Enables automatic rollback or selective restoration of missing keys.",
            rationale="Context neglect occurs when agents lose track of important context items across pipeline steps. Checkpointing the context state allows detection of lost keys and automatic recovery without restarting the entire pipeline.",
            code_changes=[
                CodeChange(
                    file_path="utils/context_checkpoint.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Context checkpoint manager with loss detection and rollback",
                )
            ],
            estimated_impact="Prevents silent context loss across pipeline steps, enables automatic recovery",
            tags=["context-neglect", "checkpoint", "rollback", "reliability"],
        )

    def _prompt_reinforcement_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """A single context item to be reinforced in prompts."""
    key: str
    value: Any
    priority: int = 1  # 1=highest priority
    category: str = "general"


class ContextReinforcer:
    """
    Re-injects key context items into agent prompts before each step.
    Ensures critical information is not lost across multi-step interactions.
    """

    def __init__(self, max_reinforcement_tokens: int = 500):
        self._critical_context: List[ContextItem] = []
        self._max_tokens = max_reinforcement_tokens

    def register_critical_context(
        self, key: str, value: Any, priority: int = 1, category: str = "general"
    ):
        """Register a context item as critical for reinforcement."""
        self._critical_context.append(
            ContextItem(key=key, value=value, priority=priority, category=category)
        )
        self._critical_context.sort(key=lambda x: x.priority)
        logger.debug(f"Registered critical context: '{key}' (priority={priority})")

    def build_reinforcement_block(
        self,
        step_name: str,
        relevant_categories: Optional[List[str]] = None,
    ) -> str:
        """Build a context reinforcement block to inject into the prompt."""
        items = self._critical_context
        if relevant_categories:
            items = [i for i in items if i.category in relevant_categories]

        if not items:
            return ""

        lines = [
            f"[CONTEXT REMINDER for step '{step_name}']",
            "The following context items are critical and MUST be considered:",
            "",
        ]
        for item in items:
            value_str = str(item.value)
            if len(value_str) > 200:
                value_str = value_str[:200] + "..."
            lines.append(f"- **{item.key}**: {value_str}")

        lines.append("")
        lines.append("[END CONTEXT REMINDER]")
        return "\\n".join(lines)

    def reinforce_prompt(
        self,
        original_prompt: str,
        step_name: str,
        relevant_categories: Optional[List[str]] = None,
        position: str = "prefix",
    ) -> str:
        """Inject context reinforcement into a prompt."""
        block = self.build_reinforcement_block(step_name, relevant_categories)
        if not block:
            return original_prompt

        if position == "prefix":
            reinforced = f"{block}\\n\\n{original_prompt}"
        elif position == "suffix":
            reinforced = f"{original_prompt}\\n\\n{block}"
        else:
            midpoint = len(original_prompt) // 2
            break_point = original_prompt.find("\\n", midpoint)
            if break_point == -1:
                break_point = midpoint
            reinforced = (
                f"{original_prompt[:break_point]}\\n\\n{block}\\n\\n"
                f"{original_prompt[break_point:]}"
            )

        logger.info(
            f"Reinforced prompt for step '{step_name}' with "
            f"{len(self._critical_context)} context items"
        )
        return reinforced

    def clear_context(self, category: Optional[str] = None):
        """Clear registered context items."""
        if category:
            self._critical_context = [
                i for i in self._critical_context if i.category != category
            ]
        else:
            self._critical_context.clear()'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="context_neglect",
            fix_type=FixType.PROMPT_REINFORCEMENT,
            confidence=FixConfidence.MEDIUM,
            title="Re-inject key context into prompts before each pipeline step",
            description="Automatically prepend or append critical context reminders to agent prompts before each step, ensuring important information is not lost mid-pipeline.",
            rationale="LLMs can lose track of context provided earlier in a conversation or pipeline. Explicitly re-injecting critical context items into each step's prompt significantly reduces context neglect without requiring architectural changes.",
            code_changes=[
                CodeChange(
                    file_path="utils/context_reinforcer.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Context reinforcer that injects critical context items into agent prompts",
                )
            ],
            estimated_impact="Reduces context neglect by keeping critical information visible to the LLM at each step",
            tags=["context-neglect", "prompt-reinforcement", "context-injection"],
        )

    def _state_validation_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import logging
from typing import Dict, Any, List, Set, Optional, Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class ContextUtilizationReport:
    """Report on how well the output utilized the provided context."""
    total_context_items: int
    utilized_items: List[str]
    neglected_items: List[str]
    utilization_ratio: float
    below_threshold: bool
    details: Dict[str, Any] = field(default_factory=dict)


class ContextUtilizationValidator:
    """
    Validates that agent outputs actually reference and use the
    context items that were provided as input. Catches context neglect
    post-generation.
    """

    def __init__(
        self,
        utilization_threshold: float = 0.6,
        similarity_threshold: float = 0.4,
    ):
        self._utilization_threshold = utilization_threshold
        self._similarity_threshold = similarity_threshold
        self._custom_validators: List[Callable] = []

    def add_validator(self, validator_fn: Callable[[str, Dict[str, Any]], bool]):
        """Add a custom validation function."""
        self._custom_validators.append(validator_fn)

    def validate(
        self,
        output: str,
        context_items: Dict[str, Any],
        required_keys: Optional[Set[str]] = None,
    ) -> ContextUtilizationReport:
        """
        Validate that the output references the provided context items.
        Uses string matching and similarity checks.
        """
        utilized = []
        neglected = []
        output_lower = output.lower()

        check_keys = required_keys or set(context_items.keys())

        for key in check_keys:
            if key not in context_items:
                continue
            value = str(context_items[key])

            # Direct mention check
            if key.lower() in output_lower or value.lower() in output_lower:
                utilized.append(key)
                continue

            # Fuzzy similarity check for paraphrased references
            value_words = value.lower().split()
            if len(value_words) >= 3:
                best_ratio = 0.0
                for i in range(len(output_lower) - len(value)):
                    window = output_lower[i:i + len(value) + 50]
                    ratio = SequenceMatcher(None, value.lower(), window).ratio()
                    best_ratio = max(best_ratio, ratio)
                    if best_ratio >= self._similarity_threshold:
                        break

                if best_ratio >= self._similarity_threshold:
                    utilized.append(key)
                    continue

            # Run custom validators
            custom_match = any(
                v(output, {key: context_items[key]}) for v in self._custom_validators
            )
            if custom_match:
                utilized.append(key)
                continue

            neglected.append(key)

        total = len(check_keys)
        ratio = len(utilized) / total if total > 0 else 1.0
        below = ratio < self._utilization_threshold

        if below:
            logger.warning(
                f"Context utilization below threshold: {ratio:.2%} "
                f"({len(neglected)} items neglected: {neglected})"
            )

        return ContextUtilizationReport(
            total_context_items=total,
            utilized_items=utilized,
            neglected_items=neglected,
            utilization_ratio=ratio,
            below_threshold=below,
            details={"threshold": self._utilization_threshold},
        )

    def validate_or_raise(
        self,
        output: str,
        context_items: Dict[str, Any],
        required_keys: Optional[Set[str]] = None,
    ) -> ContextUtilizationReport:
        """Validate and raise if utilization is below threshold."""
        report = self.validate(output, context_items, required_keys)
        if report.below_threshold:
            raise ContextNeglectError(
                f"Output used only {report.utilization_ratio:.0%} of context "
                f"(threshold: {self._utilization_threshold:.0%}). "
                f"Neglected: {report.neglected_items}"
            )
        return report


class ContextNeglectError(Exception):
    """Raised when output fails context utilization validation."""
    pass'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="context_neglect",
            fix_type=FixType.STATE_VALIDATION,
            confidence=FixConfidence.MEDIUM,
            title="Validate context utilization in agent outputs",
            description="Post-generation validator that checks whether agent outputs actually reference and use the context items provided as input, catching context neglect before results propagate downstream.",
            rationale="Context neglect often goes undetected because outputs may look reasonable even when ignoring key inputs. Explicit validation of context utilization provides a safety net that catches neglect at the source.",
            code_changes=[
                CodeChange(
                    file_path="utils/context_utilization_validator.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Post-generation context utilization validator with configurable thresholds",
                )
            ],
            estimated_impact="Catches context neglect immediately after generation, preventing downstream propagation of incomplete outputs",
            tags=["context-neglect", "validation", "output-quality"],
        )
