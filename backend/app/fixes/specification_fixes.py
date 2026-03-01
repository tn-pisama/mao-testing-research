"""Fix generators for specification mismatch detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class SpecificationFixGenerator(BaseFixGenerator):
    """Generates fixes for specification mismatch detections."""

    def can_handle(self, detection_type: str) -> bool:
        return "specification" in detection_type or "mismatch" in detection_type

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._spec_validation_fix(detection_id, details, context))
        fixes.append(self._output_constraint_fix(detection_id, details, context))
        fixes.append(self._schema_enforcement_fix(detection_id, details, context))

        return fixes

    def _spec_validation_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SpecViolationType(Enum):
    MISSING_FIELD = "missing_field"
    TYPE_MISMATCH = "type_mismatch"
    VALUE_OUT_OF_RANGE = "value_out_of_range"
    FORMAT_INVALID = "format_invalid"
    CONSTRAINT_VIOLATED = "constraint_violated"
    EXTRA_FIELD = "extra_field"


@dataclass
class SpecViolation:
    """A single specification violation found in agent output."""
    field_path: str
    violation_type: SpecViolationType
    expected: str
    actual: str
    severity: str = "error"  # error, warning, info


@dataclass
class SpecValidationResult:
    """Result of validating output against specification."""
    is_valid: bool
    violations: List[SpecViolation] = field(default_factory=list)
    score: float = 1.0  # 0.0 to 1.0 compliance score
    checked_fields: int = 0


@dataclass
class SpecRule:
    """A single specification rule to check."""
    field_path: str
    rule_type: str  # required, type, range, regex, custom
    params: Dict[str, Any] = field(default_factory=dict)
    severity: str = "error"


class PostOutputSpecValidator:
    """
    Validates agent output against a specification after generation.
    Catches mismatches before output is consumed downstream.
    """

    def __init__(self):
        self._rules: List[SpecRule] = []
        self._custom_checkers: Dict[str, Callable] = {}

    def add_rule(self, rule: SpecRule):
        """Add a validation rule."""
        self._rules.append(rule)

    def add_required_field(self, field_path: str, field_type: Optional[type] = None):
        """Convenience: add a required field rule."""
        params = {}
        if field_type:
            params["expected_type"] = field_type.__name__
        self._rules.append(SpecRule(field_path, "required", params))

    def add_range_check(self, field_path: str, min_val: Any = None, max_val: Any = None):
        """Convenience: add a numeric range rule."""
        self._rules.append(SpecRule(field_path, "range", {"min": min_val, "max": max_val}))

    def register_custom_checker(self, name: str, checker: Callable):
        """Register a custom validation function."""
        self._custom_checkers[name] = checker

    def _resolve_path(self, data: Dict[str, Any], path: str) -> tuple:
        """Resolve a dotted field path. Returns (found, value)."""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False, None
        return True, current

    def validate(self, output: Dict[str, Any]) -> SpecValidationResult:
        """Validate output against all registered rules."""
        violations = []
        checked = 0

        for rule in self._rules:
            checked += 1
            found, value = self._resolve_path(output, rule.field_path)

            if rule.rule_type == "required":
                if not found:
                    violations.append(SpecViolation(
                        field_path=rule.field_path,
                        violation_type=SpecViolationType.MISSING_FIELD,
                        expected="present",
                        actual="missing",
                        severity=rule.severity,
                    ))
                elif "expected_type" in rule.params:
                    expected_type = rule.params["expected_type"]
                    actual_type = type(value).__name__
                    if actual_type != expected_type:
                        violations.append(SpecViolation(
                            field_path=rule.field_path,
                            violation_type=SpecViolationType.TYPE_MISMATCH,
                            expected=expected_type,
                            actual=actual_type,
                            severity=rule.severity,
                        ))

            elif rule.rule_type == "range" and found and value is not None:
                min_val = rule.params.get("min")
                max_val = rule.params.get("max")
                if min_val is not None and value < min_val:
                    violations.append(SpecViolation(
                        field_path=rule.field_path,
                        violation_type=SpecViolationType.VALUE_OUT_OF_RANGE,
                        expected=f">= {min_val}",
                        actual=str(value),
                        severity=rule.severity,
                    ))
                if max_val is not None and value > max_val:
                    violations.append(SpecViolation(
                        field_path=rule.field_path,
                        violation_type=SpecViolationType.VALUE_OUT_OF_RANGE,
                        expected=f"<= {max_val}",
                        actual=str(value),
                        severity=rule.severity,
                    ))

            elif rule.rule_type == "custom":
                checker_name = rule.params.get("checker")
                if checker_name and checker_name in self._custom_checkers:
                    try:
                        is_ok = self._custom_checkers[checker_name](value, rule.params)
                        if not is_ok:
                            violations.append(SpecViolation(
                                field_path=rule.field_path,
                                violation_type=SpecViolationType.CONSTRAINT_VIOLATED,
                                expected=f"pass {checker_name}",
                                actual=str(value)[:100],
                                severity=rule.severity,
                            ))
                    except Exception as e:
                        logger.warning(f"Custom checker '{checker_name}' failed: {e}")

        error_violations = [v for v in violations if v.severity == "error"]
        score = 1.0 - (len(error_violations) / checked) if checked > 0 else 1.0

        if violations:
            logger.warning(f"Spec validation found {len(violations)} violations (score={score:.2f})")

        return SpecValidationResult(
            is_valid=len(error_violations) == 0,
            violations=violations,
            score=max(0.0, score),
            checked_fields=checked,
        )'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="specification_mismatch",
            fix_type=FixType.SPEC_VALIDATION,
            confidence=FixConfidence.HIGH,
            title="Add post-output specification validator",
            description="Validate agent outputs against a specification after generation, catching missing fields, type mismatches, range violations, and custom constraints before output is consumed downstream.",
            rationale="Specification mismatches go undetected when there is no validation layer between generation and consumption. A post-output validator with configurable rules provides a systematic safety net that catches deviations from the spec.",
            code_changes=[
                CodeChange(
                    file_path="utils/spec_validator.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Post-output specification validator with configurable rules and scoring",
                )
            ],
            estimated_impact="Catches specification mismatches immediately after generation, preventing downstream errors",
            tags=["specification", "validation", "output-quality", "compliance"],
        )

    def _output_constraint_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import json
import logging
from typing import Dict, Any, Optional, Type, TypeVar, get_type_hints
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ConstrainedOutputConfig:
    """Configuration for constrained output generation."""
    response_format: str = "json_object"  # json_object, json_schema
    strict_mode: bool = True
    max_retries_on_parse_fail: int = 2
    include_schema_in_prompt: bool = True


class StructuredOutputEnforcer:
    """
    Enforce structured JSON output from LLM agents by wrapping calls
    with JSON mode and schema instructions.
    """

    def __init__(self, config: Optional[ConstrainedOutputConfig] = None):
        self._config = config or ConstrainedOutputConfig()

    def build_schema_prompt(self, schema: Dict[str, Any]) -> str:
        """Build a prompt section describing the expected JSON schema."""
        lines = [
            "You MUST respond with valid JSON matching this exact schema:",
            "```json",
            json.dumps(schema, indent=2),
            "```",
            "",
            "IMPORTANT RULES:",
            "- Output ONLY valid JSON, no markdown, no explanation text",
            "- Include ALL required fields",
            "- Use correct types (string, number, boolean, array, object)",
            "- Do not add fields not in the schema",
        ]
        return "\\n".join(lines)

    def wrap_prompt_for_json(
        self,
        original_prompt: str,
        schema: Dict[str, Any],
    ) -> str:
        """Wrap a prompt to enforce JSON output."""
        schema_block = self.build_schema_prompt(schema)
        return f"{original_prompt}\\n\\n{schema_block}"

    def build_api_params(self, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build LLM API parameters for structured output."""
        params: Dict[str, Any] = {}

        if self._config.response_format == "json_object":
            params["response_format"] = {"type": "json_object"}
        elif self._config.response_format == "json_schema" and schema:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "agent_output",
                    "strict": self._config.strict_mode,
                    "schema": schema,
                },
            }

        return params

    def parse_and_validate(
        self,
        raw_output: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Parse LLM output as JSON with validation."""
        # Strip markdown code fences if present
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\\n")
            lines = lines[1:]  # remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\\n".join(lines)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output: {e}")
            raise OutputConstraintError(f"Output is not valid JSON: {e}")

        if schema and "required" in schema:
            missing = [f for f in schema["required"] if f not in parsed]
            if missing:
                raise OutputConstraintError(
                    f"Output missing required fields: {missing}"
                )

        return parsed

    async def call_with_structured_output(
        self,
        llm_call_fn,
        prompt: str,
        schema: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """Call an LLM with structured output enforcement and retry."""
        wrapped_prompt = self.wrap_prompt_for_json(prompt, schema)
        api_params = self.build_api_params(schema)

        last_error = None
        for attempt in range(self._config.max_retries_on_parse_fail + 1):
            try:
                raw = await llm_call_fn(wrapped_prompt, **api_params, **kwargs)
                result = self.parse_and_validate(raw, schema)
                if attempt > 0:
                    logger.info(f"Structured output succeeded on retry {attempt}")
                return result
            except (OutputConstraintError, json.JSONDecodeError) as e:
                last_error = e
                logger.warning(f"Structured output attempt {attempt + 1} failed: {e}")
                # Add stronger hint on retry
                wrapped_prompt = (
                    f"{wrapped_prompt}\\n\\n"
                    f"PREVIOUS ATTEMPT FAILED: {e}\\n"
                    f"You MUST output valid JSON matching the schema exactly."
                )

        raise OutputConstraintError(
            f"Failed to get valid structured output after "
            f"{self._config.max_retries_on_parse_fail + 1} attempts: {last_error}"
        )


class OutputConstraintError(Exception):
    pass'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="specification_mismatch",
            fix_type=FixType.OUTPUT_CONSTRAINT,
            confidence=FixConfidence.HIGH,
            title="Enforce structured JSON output with schema constraints",
            description="Use JSON mode and schema-in-prompt techniques to constrain LLM outputs to a defined structure, with automatic retry on parse failures.",
            rationale="Specification mismatches often occur because LLM outputs are free-form text. Constraining output to JSON with a defined schema eliminates structural mismatches and makes validation deterministic.",
            code_changes=[
                CodeChange(
                    file_path="utils/structured_output.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Structured output enforcer with JSON mode, schema prompting, and retry",
                )
            ],
            estimated_impact="Eliminates structural specification mismatches by constraining output format at generation time",
            tags=["specification", "structured-output", "json-mode", "constraint"],
        )

    def _schema_enforcement_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import logging
from typing import Dict, Any, Optional, Type, TypeVar, List
from pydantic import BaseModel, ValidationError, Field
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# Example Pydantic models for agent outputs
class AgentTaskResult(BaseModel):
    """Standard schema for agent task results."""
    task_id: str
    status: str = Field(pattern="^(success|partial|failed|skipped)$")
    result: Dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ResearchOutput(BaseModel):
    """Schema for research agent outputs."""
    query: str
    findings: List[Dict[str, Any]] = Field(min_length=1)
    sources: List[str] = Field(default_factory=list)
    summary: str = Field(min_length=10)
    confidence: float = Field(ge=0.0, le=1.0)


class PydanticSchemaEnforcer:
    """
    Validates agent outputs against Pydantic models with automatic
    retry on validation failure. Provides detailed error feedback
    to the LLM for self-correction.
    """

    def __init__(self, max_retries: int = 2):
        self._max_retries = max_retries
        self._validation_history: List[Dict[str, Any]] = []

    def validate(
        self,
        data: Dict[str, Any],
        model_class: Type[T],
    ) -> T:
        """Validate data against a Pydantic model. Raises on failure."""
        try:
            instance = model_class.model_validate(data)
            self._validation_history.append({
                "model": model_class.__name__,
                "success": True,
                "timestamp": datetime.utcnow().isoformat(),
            })
            return instance
        except ValidationError as e:
            self._validation_history.append({
                "model": model_class.__name__,
                "success": False,
                "errors": e.error_count(),
                "timestamp": datetime.utcnow().isoformat(),
            })
            raise

    def format_errors_for_llm(self, error: ValidationError) -> str:
        """Format Pydantic validation errors as LLM-friendly feedback."""
        lines = ["Your output had the following validation errors:", ""]
        for i, err in enumerate(error.errors(), 1):
            loc = " -> ".join(str(l) for l in err["loc"])
            lines.append(f"{i}. Field '{loc}': {err['msg']} (type: {err['type']})")
            if "input" in err:
                lines.append(f"   You provided: {str(err['input'])[:80]}")
        lines.append("")
        lines.append("Please fix these errors and try again.")
        return "\\n".join(lines)

    async def validate_with_retry(
        self,
        llm_call_fn,
        prompt: str,
        model_class: Type[T],
        parse_fn=None,
        **kwargs,
    ) -> T:
        """
        Call LLM and validate output with retry on validation failure.
        Sends error feedback to LLM for self-correction.
        """
        import json

        current_prompt = prompt
        last_error = None

        for attempt in range(self._max_retries + 1):
            raw_output = await llm_call_fn(current_prompt, **kwargs)

            # Parse raw output to dict
            if parse_fn:
                data = parse_fn(raw_output)
            else:
                try:
                    data = json.loads(raw_output)
                except json.JSONDecodeError:
                    # Try to extract JSON from mixed output
                    data = self._extract_json(raw_output)

            try:
                result = self.validate(data, model_class)
                if attempt > 0:
                    logger.info(
                        f"Pydantic validation passed on retry {attempt} "
                        f"for {model_class.__name__}"
                    )
                return result
            except ValidationError as e:
                last_error = e
                logger.warning(
                    f"Pydantic validation failed for {model_class.__name__} "
                    f"(attempt {attempt + 1}): {e.error_count()} errors"
                )
                if attempt < self._max_retries:
                    error_feedback = self.format_errors_for_llm(e)
                    schema_json = json.dumps(
                        model_class.model_json_schema(), indent=2
                    )
                    current_prompt = (
                        f"{prompt}\\n\\n"
                        f"Expected schema:\\n```json\\n{schema_json}\\n```\\n\\n"
                        f"{error_feedback}"
                    )

        raise SchemaEnforcementError(
            f"Output failed {model_class.__name__} validation after "
            f"{self._max_retries + 1} attempts",
            validation_error=last_error,
        )

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Try to extract JSON from text that may contain non-JSON content."""
        import json
        import re

        # Try to find JSON block in markdown
        match = re.search(r"```(?:json)?\\s*\\n(.*?)\\n```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # Try to find raw JSON object
        match = re.search(r"\\{.*\\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        raise ValueError("No JSON found in output")


class SchemaEnforcementError(Exception):
    def __init__(self, message: str, validation_error: Optional[ValidationError] = None):
        super().__init__(message)
        self.validation_error = validation_error'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="specification_mismatch",
            fix_type=FixType.SCHEMA_ENFORCEMENT,
            confidence=FixConfidence.MEDIUM,
            title="Enforce output schema with Pydantic validation and retry",
            description="Validate all agent outputs against Pydantic models with automatic retry. On validation failure, format errors as LLM-friendly feedback and re-prompt for self-correction.",
            rationale="Pydantic provides runtime type checking and constraint validation that catches specification mismatches with detailed, actionable error messages. Feeding these errors back to the LLM enables self-correction without human intervention.",
            code_changes=[
                CodeChange(
                    file_path="utils/schema_enforcer.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Pydantic schema enforcer with validation retry and LLM error feedback",
                )
            ],
            estimated_impact="Ensures type safety and constraint compliance in agent outputs with automatic correction",
            tags=["specification", "pydantic", "schema", "validation", "retry"],
        )
