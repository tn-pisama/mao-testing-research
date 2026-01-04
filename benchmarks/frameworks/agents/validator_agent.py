"""Validator agent that validates outputs against specifications and requirements."""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler
from dataclasses import dataclass
from enum import Enum


class ValidationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    status: ValidationStatus
    checks_passed: int
    checks_failed: int
    total_checks: int
    failures: list[str]
    warnings: list[str]
    details: str


def create_validator_agent(
    callbacks: list[BaseCallbackHandler] | None = None,
) -> ChatAnthropic:
    """Create a validator agent using Claude.

    Args:
        callbacks: Optional list of callback handlers for tracing

    Returns:
        Configured ChatAnthropic instance for validation tasks
    """
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        callbacks=callbacks,
    )


VALIDATOR_SYSTEM_PROMPT = """You are a validation agent. Your role is to verify that outputs meet specified requirements and constraints.

When validating:
1. Check each requirement systematically
2. Verify data formats and structures
3. Validate completeness and accuracy
4. Check for constraint violations
5. Document all findings

Output format (use exactly this structure):
## Validation Status
[PASSED / FAILED / PARTIAL]

## Check Summary
- Passed: [N]
- Failed: [N]
- Total: [N]

## Failed Checks
- [Check 1]: [Reason for failure]
- [Check 2]: [Reason for failure]
...

## Warnings
- [Warning 1]
- [Warning 2]
...

## Detailed Report
[Comprehensive validation report]

Be thorough and precise. A single critical failure should result in FAILED status."""


async def run_validator(
    content: str,
    specification: str,
    agent: ChatAnthropic | None = None,
) -> str:
    """Validate content against a specification.

    Args:
        content: The content to validate
        specification: The specification/requirements to validate against
        agent: The validator agent instance

    Returns:
        Validation report with status and details
    """
    if agent is None:
        agent = create_validator_agent()

    messages = [
        SystemMessage(content=VALIDATOR_SYSTEM_PROMPT),
        HumanMessage(content=f"Validate the following content against the specification.\n\nSpecification:\n{specification}\n\nContent to validate:\n{content}"),
    ]

    response = await agent.ainvoke(messages)
    return response.content


def parse_validation_result(validation_text: str) -> ValidationResult:
    """Parse validation text into structured ValidationResult.

    Args:
        validation_text: Raw validation output from validator agent

    Returns:
        Structured ValidationResult
    """
    import re

    # Default values
    status = ValidationStatus.PARTIAL
    checks_passed = 0
    checks_failed = 0
    failures = []
    warnings = []

    # Parse status
    status_match = re.search(r"Validation Status[:\s]*\n?\s*(PASSED|FAILED|PARTIAL|SKIPPED)", validation_text, re.IGNORECASE)
    if status_match:
        status_str = status_match.group(1).upper()
        status = ValidationStatus(status_str.lower())

    # Parse check counts
    passed_match = re.search(r"Passed[:\s]*(\d+)", validation_text, re.IGNORECASE)
    if passed_match:
        checks_passed = int(passed_match.group(1))

    failed_match = re.search(r"Failed[:\s]*(\d+)", validation_text, re.IGNORECASE)
    if failed_match:
        checks_failed = int(failed_match.group(1))

    # Parse failures
    failures_section = re.search(r"Failed Checks[:\s]*\n((?:[-*]\s+.+\n?)+)", validation_text, re.IGNORECASE)
    if failures_section:
        failures = [line.strip().lstrip("-* ") for line in failures_section.group(1).strip().split("\n") if line.strip()]

    # Parse warnings
    warnings_section = re.search(r"Warnings[:\s]*\n((?:[-*]\s+.+\n?)+)", validation_text, re.IGNORECASE)
    if warnings_section:
        warnings = [line.strip().lstrip("-* ") for line in warnings_section.group(1).strip().split("\n") if line.strip()]

    return ValidationResult(
        status=status,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        total_checks=checks_passed + checks_failed,
        failures=failures,
        warnings=warnings,
        details=validation_text,
    )
