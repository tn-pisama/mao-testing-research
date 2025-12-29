"""
Handoff Assertions - Test assertions for agent handoffs.

Provides assertion functions for:
- Context completeness
- Data integrity
- SLA compliance
- Circular handoff prevention
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from .handoff import Handoff, HandoffAnalysis

logger = logging.getLogger(__name__)


class AssertionStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class AssertionResult:
    name: str
    status: AssertionStatus
    message: str
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    details: Optional[dict] = None


class HandoffAssertions:
    """
    Collection of assertions for testing agent handoffs.
    """
    
    def __init__(self):
        self.results: list[AssertionResult] = []

    def assert_context_complete(
        self,
        handoff: Handoff,
        required_fields: Optional[list[str]] = None,
    ) -> AssertionResult:
        if required_fields is None:
            required_fields = handoff.fields_expected
        
        missing = [f for f in required_fields if f not in handoff.fields_received]
        
        if not missing:
            result = AssertionResult(
                name="context_complete",
                status=AssertionStatus.PASSED,
                message="All required context fields present",
                expected=required_fields,
                actual=handoff.fields_received,
            )
        else:
            result = AssertionResult(
                name="context_complete",
                status=AssertionStatus.FAILED,
                message=f"Missing context fields: {missing}",
                expected=required_fields,
                actual=handoff.fields_received,
                details={"missing": missing},
            )
        
        self.results.append(result)
        return result

    def assert_no_data_loss(
        self,
        handoff: Handoff,
        critical_fields: Optional[list[str]] = None,
    ) -> AssertionResult:
        context_passed = handoff.context_passed
        context_received = handoff.context_received
        
        if critical_fields:
            fields_to_check = critical_fields
        else:
            fields_to_check = list(context_passed.keys())
        
        lost_fields = []
        for field in fields_to_check:
            if field in context_passed:
                passed_value = context_passed[field]
                received_value = context_received.get(field)
                
                if received_value is None:
                    lost_fields.append(field)
                elif str(passed_value) != str(received_value):
                    lost_fields.append(f"{field} (modified)")
        
        if not lost_fields:
            result = AssertionResult(
                name="no_data_loss",
                status=AssertionStatus.PASSED,
                message="No data loss detected in handoff",
                expected="All fields preserved",
                actual="All fields preserved",
            )
        else:
            result = AssertionResult(
                name="no_data_loss",
                status=AssertionStatus.FAILED,
                message=f"Data loss detected: {lost_fields}",
                expected="All fields preserved",
                actual=f"Lost: {lost_fields}",
                details={"lost_fields": lost_fields},
            )
        
        self.results.append(result)
        return result

    def assert_handoff_sla(
        self,
        handoff: Handoff,
        max_latency_ms: int = 500,
    ) -> AssertionResult:
        if handoff.latency_ms <= max_latency_ms:
            result = AssertionResult(
                name="handoff_sla",
                status=AssertionStatus.PASSED,
                message=f"Handoff completed within SLA ({handoff.latency_ms}ms <= {max_latency_ms}ms)",
                expected=f"<= {max_latency_ms}ms",
                actual=f"{handoff.latency_ms}ms",
            )
        else:
            result = AssertionResult(
                name="handoff_sla",
                status=AssertionStatus.FAILED,
                message=f"Handoff exceeded SLA ({handoff.latency_ms}ms > {max_latency_ms}ms)",
                expected=f"<= {max_latency_ms}ms",
                actual=f"{handoff.latency_ms}ms",
                details={
                    "latency_ms": handoff.latency_ms,
                    "sla_ms": max_latency_ms,
                    "exceeded_by_ms": handoff.latency_ms - max_latency_ms,
                },
            )
        
        self.results.append(result)
        return result

    def assert_no_circular_handoff(
        self,
        analysis: HandoffAnalysis,
        max_depth: int = 3,
    ) -> AssertionResult:
        if not analysis.circular_handoffs:
            result = AssertionResult(
                name="no_circular_handoff",
                status=AssertionStatus.PASSED,
                message="No circular handoffs detected",
                expected="No cycles",
                actual="No cycles",
            )
        else:
            result = AssertionResult(
                name="no_circular_handoff",
                status=AssertionStatus.FAILED,
                message=f"Circular handoffs detected: {analysis.circular_handoffs}",
                expected="No cycles",
                actual=f"{len(analysis.circular_handoffs)} cycles",
                details={"cycles": analysis.circular_handoffs},
            )
        
        self.results.append(result)
        return result

    def assert_handoff_success(
        self,
        handoff: Handoff,
    ) -> AssertionResult:
        from .handoff import HandoffStatus
        
        if handoff.status == HandoffStatus.SUCCESS:
            result = AssertionResult(
                name="handoff_success",
                status=AssertionStatus.PASSED,
                message=f"Handoff {handoff.sender_agent} -> {handoff.receiver_agent} succeeded",
                expected="success",
                actual=handoff.status.value,
            )
        else:
            result = AssertionResult(
                name="handoff_success",
                status=AssertionStatus.FAILED,
                message=f"Handoff {handoff.sender_agent} -> {handoff.receiver_agent} failed: {handoff.status.value}",
                expected="success",
                actual=handoff.status.value,
                details={"error": handoff.error} if handoff.error else None,
            )
        
        self.results.append(result)
        return result

    def assert_output_continuity(
        self,
        handoff: Handoff,
        min_similarity: float = 0.3,
    ) -> AssertionResult:
        sender_output = handoff.sender_output.lower()
        receiver_input = handoff.receiver_input.lower()
        
        if not sender_output or not receiver_input:
            result = AssertionResult(
                name="output_continuity",
                status=AssertionStatus.SKIPPED,
                message="Cannot check continuity: missing output or input",
            )
            self.results.append(result)
            return result
        
        sender_words = set(sender_output.split())
        receiver_words = set(receiver_input.split())
        
        if not sender_words:
            similarity = 1.0 if not receiver_words else 0.0
        else:
            overlap = len(sender_words & receiver_words)
            similarity = overlap / len(sender_words)
        
        if similarity >= min_similarity:
            result = AssertionResult(
                name="output_continuity",
                status=AssertionStatus.PASSED,
                message=f"Output continuity maintained ({similarity:.1%} >= {min_similarity:.1%})",
                expected=f">= {min_similarity:.1%}",
                actual=f"{similarity:.1%}",
            )
        else:
            result = AssertionResult(
                name="output_continuity",
                status=AssertionStatus.FAILED,
                message=f"Output continuity broken ({similarity:.1%} < {min_similarity:.1%})",
                expected=f">= {min_similarity:.1%}",
                actual=f"{similarity:.1%}",
                details={"similarity": similarity},
            )
        
        self.results.append(result)
        return result

    def get_results(self) -> list[AssertionResult]:
        return self.results

    def get_summary(self) -> dict:
        passed = sum(1 for r in self.results if r.status == AssertionStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == AssertionStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == AssertionStatus.SKIPPED)
        
        return {
            "total": len(self.results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": passed / len(self.results) if self.results else 0,
        }

    def reset(self):
        self.results = []


def assert_context_complete(
    handoff: Handoff,
    required_fields: Optional[list[str]] = None,
) -> AssertionResult:
    assertions = HandoffAssertions()
    return assertions.assert_context_complete(handoff, required_fields)


def assert_no_data_loss(
    handoff: Handoff,
    critical_fields: Optional[list[str]] = None,
) -> AssertionResult:
    assertions = HandoffAssertions()
    return assertions.assert_no_data_loss(handoff, critical_fields)


def assert_handoff_sla(
    handoff: Handoff,
    max_latency_ms: int = 500,
) -> AssertionResult:
    assertions = HandoffAssertions()
    return assertions.assert_handoff_sla(handoff, max_latency_ms)


def assert_no_circular_handoff(
    analysis: HandoffAnalysis,
    max_depth: int = 3,
) -> AssertionResult:
    assertions = HandoffAssertions()
    return assertions.assert_no_circular_handoff(analysis, max_depth)
