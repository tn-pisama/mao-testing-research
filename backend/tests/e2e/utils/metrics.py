"""Metrics collection for E2E testing."""

from typing import Dict, Any, List
from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class TestMetrics:
    """Metrics for a single test execution."""
    test_name: str
    framework: str
    failure_mode: str
    healing_duration_ms: float
    fixes_applied: int
    validations_passed: int
    validations_total: int
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MetricsCollector:
    """Collects and aggregates E2E test metrics."""
    
    def __init__(self):
        self.metrics: List[TestMetrics] = []
    
    def record(
        self,
        test_name: str,
        framework: str,
        failure_mode: str,
        healing_result,
    ):
        """Record metrics from a healing result."""
        duration_ms = 0
        if healing_result.completed_at and healing_result.started_at:
            duration_ms = (healing_result.completed_at - healing_result.started_at).total_seconds() * 1000
        
        self.metrics.append(TestMetrics(
            test_name=test_name,
            framework=framework,
            failure_mode=failure_mode,
            healing_duration_ms=duration_ms,
            fixes_applied=len(healing_result.applied_fixes),
            validations_passed=sum(1 for v in healing_result.validation_results if v.success),
            validations_total=len(healing_result.validation_results),
            success=healing_result.is_successful,
        ))
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all collected metrics."""
        if not self.metrics:
            return {"total_tests": 0}
        
        total = len(self.metrics)
        passed = sum(1 for m in self.metrics if m.success)
        
        by_framework = {}
        by_failure_mode = {}
        
        for m in self.metrics:
            if m.framework not in by_framework:
                by_framework[m.framework] = {"total": 0, "passed": 0}
            by_framework[m.framework]["total"] += 1
            if m.success:
                by_framework[m.framework]["passed"] += 1
            
            if m.failure_mode not in by_failure_mode:
                by_failure_mode[m.failure_mode] = {"total": 0, "passed": 0}
            by_failure_mode[m.failure_mode]["total"] += 1
            if m.success:
                by_failure_mode[m.failure_mode]["passed"] += 1
        
        durations = [m.healing_duration_ms for m in self.metrics]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0,
            "avg_healing_duration_ms": avg_duration,
            "by_framework": by_framework,
            "by_failure_mode": by_failure_mode,
        }
    
    def print_report(self):
        """Print a formatted test report."""
        summary = self.get_summary()
        
        print("\n" + "=" * 60)
        print("E2E TEST METRICS REPORT")
        print("=" * 60)
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Pass Rate: {summary['pass_rate']:.1%}")
        print(f"Avg Healing Duration: {summary['avg_healing_duration_ms']:.2f}ms")
        
        print("\nBy Framework:")
        for framework, stats in summary.get("by_framework", {}).items():
            rate = stats["passed"] / stats["total"] if stats["total"] > 0 else 0
            print(f"  {framework}: {stats['passed']}/{stats['total']} ({rate:.0%})")
        
        print("\nBy Failure Mode:")
        for mode, stats in summary.get("by_failure_mode", {}).items():
            rate = stats["passed"] / stats["total"] if stats["total"] > 0 else 0
            print(f"  {mode}: {stats['passed']}/{stats['total']} ({rate:.0%})")
        
        print("=" * 60)
