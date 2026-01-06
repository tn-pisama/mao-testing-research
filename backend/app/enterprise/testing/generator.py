"""
Handoff Test Generator - Auto-generate test cases from traces.

Generates:
- Context completeness tests
- Data integrity tests
- SLA compliance tests
- Failure recovery tests
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from .handoff import Handoff, HandoffExtractor, HandoffAnalysis
from .assertions import HandoffAssertions, AssertionResult, AssertionStatus

logger = logging.getLogger(__name__)


class TestPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestCategory(str, Enum):
    CONTEXT = "context"
    DATA_INTEGRITY = "data_integrity"
    LATENCY = "latency"
    ERROR_HANDLING = "error_handling"
    CIRCULAR = "circular"
    CONTINUITY = "continuity"


@dataclass
class TestCase:
    id: str
    name: str
    description: str
    category: TestCategory
    priority: TestPriority
    
    handoff_id: Optional[str] = None
    sender_agent: Optional[str] = None
    receiver_agent: Optional[str] = None
    
    assertions: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    
    expected_result: str = "pass"
    tags: list[str] = field(default_factory=list)


@dataclass
class TestResult:
    test_case: TestCase
    status: AssertionStatus
    duration_ms: int
    assertions: list[AssertionResult]
    error: Optional[str] = None


@dataclass
class TestSuite:
    id: str
    name: str
    description: str
    created_at: datetime
    
    test_cases: list[TestCase] = field(default_factory=list)
    
    trace_id: Optional[str] = None
    tenant_id: Optional[str] = None
    
    tags: list[str] = field(default_factory=list)


class HandoffTestGenerator:
    """
    Generates test cases from analyzed handoffs.
    
    Creates comprehensive test suites covering:
    - Context completeness for each handoff
    - Data integrity across agent boundaries
    - Latency SLA compliance
    - Circular handoff prevention
    """
    
    def __init__(
        self,
        default_sla_ms: int = 500,
        critical_fields: Optional[list[str]] = None,
    ):
        self.default_sla_ms = default_sla_ms
        self.critical_fields = critical_fields or []
        self.extractor = HandoffExtractor()

    def generate_from_trace(
        self,
        trace: dict,
        suite_name: Optional[str] = None,
    ) -> TestSuite:
        trace_id = trace.get("trace_id", str(uuid.uuid4()))
        tenant_id = trace.get("tenant_id", "unknown")
        
        handoffs = self.extractor.extract_from_trace(trace)
        analysis = self.extractor.analyze(handoffs)
        
        suite = TestSuite(
            id=str(uuid.uuid4()),
            name=suite_name or f"Handoff Tests - {trace_id[:8]}",
            description=f"Auto-generated handoff tests from trace {trace_id}",
            created_at=datetime.utcnow(),
            trace_id=trace_id,
            tenant_id=tenant_id,
        )
        
        for handoff in handoffs:
            suite.test_cases.extend(self._generate_handoff_tests(handoff))
        
        suite.test_cases.extend(self._generate_analysis_tests(analysis))
        
        return suite

    def _generate_handoff_tests(self, handoff: Handoff) -> list[TestCase]:
        tests = []
        
        tests.append(TestCase(
            id=f"ctx_{handoff.id}",
            name=f"Context Completeness: {handoff.sender_agent} -> {handoff.receiver_agent}",
            description=f"Verify all required context fields are passed from {handoff.sender_agent} to {handoff.receiver_agent}",
            category=TestCategory.CONTEXT,
            priority=TestPriority.HIGH,
            handoff_id=handoff.id,
            sender_agent=handoff.sender_agent,
            receiver_agent=handoff.receiver_agent,
            assertions=["assert_context_complete"],
            parameters={
                "required_fields": handoff.fields_expected,
            },
            tags=["context", "handoff"],
        ))
        
        tests.append(TestCase(
            id=f"data_{handoff.id}",
            name=f"Data Integrity: {handoff.sender_agent} -> {handoff.receiver_agent}",
            description=f"Verify no data is lost or corrupted during handoff from {handoff.sender_agent} to {handoff.receiver_agent}",
            category=TestCategory.DATA_INTEGRITY,
            priority=TestPriority.CRITICAL,
            handoff_id=handoff.id,
            sender_agent=handoff.sender_agent,
            receiver_agent=handoff.receiver_agent,
            assertions=["assert_no_data_loss"],
            parameters={
                "critical_fields": self.critical_fields or handoff.fields_expected,
            },
            tags=["data", "integrity", "handoff"],
        ))
        
        tests.append(TestCase(
            id=f"sla_{handoff.id}",
            name=f"SLA Compliance: {handoff.sender_agent} -> {handoff.receiver_agent}",
            description=f"Verify handoff completes within {self.default_sla_ms}ms SLA",
            category=TestCategory.LATENCY,
            priority=TestPriority.MEDIUM,
            handoff_id=handoff.id,
            sender_agent=handoff.sender_agent,
            receiver_agent=handoff.receiver_agent,
            assertions=["assert_handoff_sla"],
            parameters={
                "max_latency_ms": self.default_sla_ms,
            },
            tags=["sla", "latency", "handoff"],
        ))
        
        tests.append(TestCase(
            id=f"success_{handoff.id}",
            name=f"Handoff Success: {handoff.sender_agent} -> {handoff.receiver_agent}",
            description=f"Verify handoff completes successfully",
            category=TestCategory.ERROR_HANDLING,
            priority=TestPriority.CRITICAL,
            handoff_id=handoff.id,
            sender_agent=handoff.sender_agent,
            receiver_agent=handoff.receiver_agent,
            assertions=["assert_handoff_success"],
            parameters={},
            tags=["success", "handoff"],
        ))
        
        tests.append(TestCase(
            id=f"cont_{handoff.id}",
            name=f"Output Continuity: {handoff.sender_agent} -> {handoff.receiver_agent}",
            description=f"Verify output from {handoff.sender_agent} is reflected in {handoff.receiver_agent} input",
            category=TestCategory.CONTINUITY,
            priority=TestPriority.MEDIUM,
            handoff_id=handoff.id,
            sender_agent=handoff.sender_agent,
            receiver_agent=handoff.receiver_agent,
            assertions=["assert_output_continuity"],
            parameters={
                "min_similarity": 0.3,
            },
            tags=["continuity", "handoff"],
        ))
        
        return tests

    def _generate_analysis_tests(self, analysis: HandoffAnalysis) -> list[TestCase]:
        tests = []
        
        tests.append(TestCase(
            id="no_circular",
            name="No Circular Handoffs",
            description="Verify no circular dependencies exist in agent handoff graph",
            category=TestCategory.CIRCULAR,
            priority=TestPriority.CRITICAL,
            assertions=["assert_no_circular_handoff"],
            parameters={
                "max_depth": 3,
            },
            tags=["circular", "graph", "global"],
        ))
        
        if analysis.data_loss_detected:
            tests.append(TestCase(
                id="global_data_loss",
                name="Global Data Integrity Check",
                description="Flag: Data loss was detected in handoff analysis",
                category=TestCategory.DATA_INTEGRITY,
                priority=TestPriority.CRITICAL,
                assertions=[],
                parameters={},
                expected_result="fail",
                tags=["data", "global", "warning"],
            ))
        
        return tests

    def run_suite(
        self,
        suite: TestSuite,
        handoffs: list[Handoff],
        analysis: HandoffAnalysis,
    ) -> list[TestResult]:
        results = []
        handoff_map = {h.id: h for h in handoffs}
        
        for test_case in suite.test_cases:
            start = datetime.utcnow()
            assertions = HandoffAssertions()
            
            try:
                handoff = None
                if test_case.handoff_id:
                    handoff = handoff_map.get(test_case.handoff_id)
                
                for assertion_name in test_case.assertions:
                    if assertion_name == "assert_context_complete" and handoff:
                        assertions.assert_context_complete(
                            handoff,
                            test_case.parameters.get("required_fields"),
                        )
                    elif assertion_name == "assert_no_data_loss" and handoff:
                        assertions.assert_no_data_loss(
                            handoff,
                            test_case.parameters.get("critical_fields"),
                        )
                    elif assertion_name == "assert_handoff_sla" and handoff:
                        assertions.assert_handoff_sla(
                            handoff,
                            test_case.parameters.get("max_latency_ms", self.default_sla_ms),
                        )
                    elif assertion_name == "assert_handoff_success" and handoff:
                        assertions.assert_handoff_success(handoff)
                    elif assertion_name == "assert_output_continuity" and handoff:
                        assertions.assert_output_continuity(
                            handoff,
                            test_case.parameters.get("min_similarity", 0.3),
                        )
                    elif assertion_name == "assert_no_circular_handoff":
                        assertions.assert_no_circular_handoff(
                            analysis,
                            test_case.parameters.get("max_depth", 3),
                        )
                
                assertion_results = assertions.get_results()
                
                if not assertion_results:
                    status = AssertionStatus.PASSED if test_case.expected_result == "pass" else AssertionStatus.FAILED
                elif all(r.status == AssertionStatus.PASSED for r in assertion_results):
                    status = AssertionStatus.PASSED
                elif any(r.status == AssertionStatus.FAILED for r in assertion_results):
                    status = AssertionStatus.FAILED
                else:
                    status = AssertionStatus.WARNING
                
                duration = int((datetime.utcnow() - start).total_seconds() * 1000)
                
                results.append(TestResult(
                    test_case=test_case,
                    status=status,
                    duration_ms=duration,
                    assertions=assertion_results,
                ))
                
            except Exception as e:
                duration = int((datetime.utcnow() - start).total_seconds() * 1000)
                results.append(TestResult(
                    test_case=test_case,
                    status=AssertionStatus.FAILED,
                    duration_ms=duration,
                    assertions=[],
                    error=str(e),
                ))
        
        return results

    def generate_report(self, results: list[TestResult]) -> dict:
        passed = sum(1 for r in results if r.status == AssertionStatus.PASSED)
        failed = sum(1 for r in results if r.status == AssertionStatus.FAILED)
        
        by_category = {}
        for r in results:
            cat = r.test_case.category.value
            if cat not in by_category:
                by_category[cat] = {"passed": 0, "failed": 0}
            if r.status == AssertionStatus.PASSED:
                by_category[cat]["passed"] += 1
            else:
                by_category[cat]["failed"] += 1
        
        failures = [
            {
                "test": r.test_case.name,
                "category": r.test_case.category.value,
                "error": r.error or "; ".join(a.message for a in r.assertions if a.status == AssertionStatus.FAILED),
            }
            for r in results if r.status == AssertionStatus.FAILED
        ]
        
        return {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(results) if results else 0,
            "by_category": by_category,
            "failures": failures,
        }
