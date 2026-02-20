"""Fix generators for flawed workflow detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class WorkflowFixGenerator(BaseFixGenerator):
    """Generates fixes for flawed workflow detections."""

    def can_handle(self, detection_type: str) -> bool:
        return detection_type in ("flawed_workflow", "workflow")

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._workflow_guard_fix(detection_id, details, context))
        fixes.append(self._step_validator_fix(detection_id, details, context))
        fixes.append(self._circuit_breaker_fix(detection_id, details, context))

        return fixes

    def _workflow_guard_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class GuardResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


@dataclass
class Condition:
    """A single pre- or post-condition for a workflow step."""
    name: str
    check: Callable[[Dict[str, Any]], bool]
    severity: str = "error"  # "error" blocks, "warning" logs
    message: str = ""


@dataclass
class StepGuard:
    """Pre- and post-conditions for one workflow step."""
    step_name: str
    preconditions: List[Condition] = field(default_factory=list)
    postconditions: List[Condition] = field(default_factory=list)


class WorkflowGuardian:
    """Enforce pre/post-conditions at every workflow step."""

    def __init__(self):
        self._guards: Dict[str, StepGuard] = {}
        self._violation_log: List[Dict[str, Any]] = []

    def register_guard(self, guard: StepGuard) -> None:
        self._guards[guard.step_name] = guard

    def check_preconditions(
        self, step_name: str, state: Dict[str, Any]
    ) -> GuardResult:
        guard = self._guards.get(step_name)
        if not guard:
            return GuardResult.PASS

        for cond in guard.preconditions:
            if not cond.check(state):
                violation = {
                    "step": step_name,
                    "phase": "precondition",
                    "condition": cond.name,
                    "message": cond.message or f"Pre-condition '{cond.name}' failed",
                }
                self._violation_log.append(violation)
                logger.warning("Guard violation: %s", violation)
                if cond.severity == "error":
                    return GuardResult.FAIL
        return GuardResult.PASS

    def check_postconditions(
        self, step_name: str, state: Dict[str, Any]
    ) -> GuardResult:
        guard = self._guards.get(step_name)
        if not guard:
            return GuardResult.PASS

        for cond in guard.postconditions:
            if not cond.check(state):
                violation = {
                    "step": step_name,
                    "phase": "postcondition",
                    "condition": cond.name,
                    "message": cond.message or f"Post-condition '{cond.name}' failed",
                }
                self._violation_log.append(violation)
                logger.warning("Guard violation: %s", violation)
                if cond.severity == "error":
                    return GuardResult.FAIL
        return GuardResult.PASS

    async def run_step(
        self,
        step_name: str,
        step_fn: Callable,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        pre_result = self.check_preconditions(step_name, state)
        if pre_result == GuardResult.FAIL:
            raise WorkflowGuardError(
                f"Step '{step_name}' blocked by failed preconditions"
            )

        result = await step_fn(state)

        post_result = self.check_postconditions(step_name, result)
        if post_result == GuardResult.FAIL:
            raise WorkflowGuardError(
                f"Step '{step_name}' produced invalid output (postcondition failed)"
            )
        return result


class WorkflowGuardError(Exception):
    pass'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="flawed_workflow",
            fix_type=FixType.WORKFLOW_GUARD,
            confidence=FixConfidence.HIGH,
            title="Add pre/post-condition guards to workflow steps",
            description=(
                "Enforce explicit pre-conditions and post-conditions at every workflow "
                "step so that invalid state is caught immediately rather than propagating "
                "silently through downstream steps."
            ),
            rationale=(
                "Workflow failures often stem from one step producing unexpected output "
                "that the next step silently accepts. Guard conditions make each step's "
                "contract explicit and halt execution the moment invariants are violated."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/workflow_guard.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Workflow guardian with pre/post-condition enforcement",
                )
            ],
            estimated_impact="Catches invalid workflow state at the step boundary instead of downstream",
            tags=["workflow", "guard", "precondition", "postcondition"],
        )

    def _step_validator_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass, field
from pydantic import BaseModel, ValidationError
import logging

logger = logging.getLogger(__name__)


class StepOutput(BaseModel):
    """Base schema every step output must extend."""
    step_name: str
    status: str  # "success", "partial", "error"
    data: Dict[str, Any] = {}
    errors: List[str] = []


@dataclass
class ValidationRule:
    name: str
    field_path: str
    validator: Callable[[Any], bool]
    error_message: str = ""


class StepValidator:
    """Validate each workflow step's output against its declared schema."""

    def __init__(self):
        self._schemas: Dict[str, Type[BaseModel]] = {}
        self._rules: Dict[str, List[ValidationRule]] = {}
        self._history: List[Dict[str, Any]] = []

    def register_schema(
        self, step_name: str, schema: Type[BaseModel]
    ) -> None:
        self._schemas[step_name] = schema

    def add_rule(self, step_name: str, rule: ValidationRule) -> None:
        self._rules.setdefault(step_name, []).append(rule)

    def validate(
        self, step_name: str, output: Dict[str, Any]
    ) -> "ValidationResult":
        errors: List[str] = []

        # 1. Schema validation via pydantic
        schema = self._schemas.get(step_name)
        if schema:
            try:
                schema(**output)
            except ValidationError as exc:
                for err in exc.errors():
                    errors.append(
                        f"Schema: {' -> '.join(str(l) for l in err['loc'])}: "
                        f"{err['msg']}"
                    )

        # 2. Custom rule validation
        for rule in self._rules.get(step_name, []):
            value = _deep_get(output, rule.field_path)
            if not rule.validator(value):
                errors.append(
                    rule.error_message
                    or f"Rule '{rule.name}' failed for {rule.field_path}"
                )

        result = ValidationResult(
            step_name=step_name,
            valid=len(errors) == 0,
            errors=errors,
        )
        self._history.append(result.__dict__)
        if not result.valid:
            logger.warning(
                "Step '%s' output validation failed: %s",
                step_name,
                errors,
            )
        return result


@dataclass
class ValidationResult:
    step_name: str
    valid: bool
    errors: List[str] = field(default_factory=list)


def _deep_get(data: Dict, path: str, default: Any = None) -> Any:
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="flawed_workflow",
            fix_type=FixType.STEP_VALIDATOR,
            confidence=FixConfidence.HIGH,
            title="Validate each step's output with schema and custom rules",
            description=(
                "Attach a pydantic schema and optional custom validation rules to "
                "every workflow step. Outputs that do not conform are rejected before "
                "they reach the next step."
            ),
            rationale=(
                "Without output validation, a step can return malformed or incomplete "
                "data that silently corrupts downstream processing. Schema-based "
                "validation provides a cheap, deterministic safety net."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/step_validator.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Pydantic + custom rule validator for workflow step outputs",
                )
            ],
            estimated_impact="Prevents malformed step outputs from propagating through the workflow",
            tags=["workflow", "validation", "schema", "pydantic"],
        )

    def _circuit_breaker_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import time
from enum import Enum
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class BreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3
    recovery_timeout: float = 60.0  # seconds before trying again
    success_threshold: int = 2      # successes in half-open to close


class WorkflowCircuitBreaker:
    """Workflow-level circuit breaker that trips on repeated step failures."""

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self._config = config or CircuitBreakerConfig()
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._trip_history: list = []

    @property
    def state(self) -> BreakerState:
        if self._state == BreakerState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self._config.recovery_timeout:
                logger.info("Circuit breaker entering half-open state")
                self._state = BreakerState.HALF_OPEN
                self._success_count = 0
        return self._state

    def record_success(self) -> None:
        if self.state == BreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._config.success_threshold:
                logger.info("Circuit breaker closing after recovery")
                self._state = BreakerState.CLOSED
                self._failure_count = 0
        elif self.state == BreakerState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self.state == BreakerState.HALF_OPEN:
            logger.warning("Failure in half-open state, re-opening breaker")
            self._state = BreakerState.OPEN
        elif self._failure_count >= self._config.failure_threshold:
            logger.warning(
                "Circuit breaker tripped after %d failures",
                self._failure_count,
            )
            self._state = BreakerState.OPEN
            self._trip_history.append(
                {"time": self._last_failure_time, "failures": self._failure_count}
            )

    async def call(
        self,
        step_fn: Callable,
        state: Dict[str, Any],
        fallback: Optional[Callable] = None,
    ) -> Any:
        if self.state == BreakerState.OPEN:
            if fallback:
                logger.info("Circuit open, using fallback")
                return await fallback(state)
            raise CircuitOpenError(
                "Workflow circuit breaker is open; too many recent failures"
            )

        try:
            result = await step_fn(state)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            if self.state == BreakerState.OPEN and fallback:
                return await fallback(state)
            raise


class CircuitOpenError(Exception):
    pass'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="flawed_workflow",
            fix_type=FixType.CIRCUIT_BREAKER,
            confidence=FixConfidence.MEDIUM,
            title="Add workflow-level circuit breaker for repeated failures",
            description=(
                "Wrap the workflow execution path with a circuit breaker that "
                "opens after a configurable number of consecutive step failures, "
                "preventing further wasted computation until the issue is resolved."
            ),
            rationale=(
                "When a workflow step keeps failing, continuing to retry wastes "
                "tokens and compute. A circuit breaker stops the bleeding, gives "
                "the system time to recover, and optionally routes to a fallback path."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/workflow_circuit_breaker.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Circuit breaker with closed/open/half-open states for workflows",
                )
            ],
            estimated_impact="Prevents cascading failures and wasted compute on broken workflow paths",
            tags=["workflow", "circuit-breaker", "resilience", "fault-tolerance"],
        )
