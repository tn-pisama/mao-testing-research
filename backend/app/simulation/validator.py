"""Pre-deployment validator.

Runs failure scenarios through detectors and reports coverage,
helping teams understand which failures their system can detect
before going to production.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .generator import FailureScenario, ScenarioGenerator
from .injector import FailureInjector, InjectionType

logger = logging.getLogger(__name__)


@dataclass
class DetectionAttempt:
    """Result of running a detector on a scenario."""
    scenario_name: str
    failure_type: str
    expected_detector: str
    detected: bool
    confidence: float
    actual_detector: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ValidationReport:
    """Summary of pre-deployment validation."""
    total_scenarios: int
    detected: int
    missed: int
    errors: int
    coverage_pct: float
    attempts: List[DetectionAttempt] = field(default_factory=list)
    per_type_coverage: Dict[str, float] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Check if validation passed (>= 70% coverage)."""
        return self.coverage_pct >= 0.70


class PreDeploymentValidator:
    """Run failure scenarios through detectors before production deployment.

    Usage:
        validator = PreDeploymentValidator()
        report = validator.validate(
            agent_config={"role": "coder", "tools": ["search", "write_file"]},
        )
        print(f"Coverage: {report.coverage_pct:.1%}")
        print(f"Passed: {report.passed}")
    """

    def __init__(self):
        self.generator = ScenarioGenerator()
        self.injector = FailureInjector()

    def validate(
        self,
        agent_config: Optional[Dict[str, Any]] = None,
        scenarios: Optional[List[FailureScenario]] = None,
        failure_types: Optional[List[str]] = None,
    ) -> ValidationReport:
        """Run validation scenarios and report detector coverage.

        Args:
            agent_config: Agent config for generating tailored scenarios
            scenarios: Pre-built scenarios (overrides agent_config generation)
            failure_types: Only test specific failure types

        Returns:
            ValidationReport with coverage metrics
        """
        # Generate or use provided scenarios
        if scenarios:
            test_scenarios = scenarios
        elif agent_config:
            test_scenarios = self.generator.from_agent_config(agent_config)
        else:
            test_scenarios = self.generator.from_templates(failure_types=failure_types)

        attempts = []

        for scenario in test_scenarios:
            attempt = self._run_scenario(scenario)
            attempts.append(attempt)

        # Calculate coverage
        detected = sum(1 for a in attempts if a.detected)
        errors = sum(1 for a in attempts if a.error)
        total = len(attempts)
        missed = total - detected - errors

        # Per-type coverage
        per_type: Dict[str, List[bool]] = {}
        for a in attempts:
            per_type.setdefault(a.failure_type, []).append(a.detected)

        per_type_coverage = {
            ftype: sum(results) / len(results) if results else 0.0
            for ftype, results in per_type.items()
        }

        return ValidationReport(
            total_scenarios=total,
            detected=detected,
            missed=missed,
            errors=errors,
            coverage_pct=detected / total if total > 0 else 0.0,
            attempts=attempts,
            per_type_coverage=per_type_coverage,
        )

    def validate_with_injection(
        self,
        clean_trace: Dict[str, Any],
        injection_types: Optional[List[InjectionType]] = None,
    ) -> ValidationReport:
        """Inject failures into a clean trace and validate detection.

        Args:
            clean_trace: A clean (non-failing) trace
            injection_types: Specific injection types to test (default: all)

        Returns:
            ValidationReport
        """
        types = injection_types or list(InjectionType)
        attempts = []

        for itype in types:
            try:
                injected = self.injector.inject(clean_trace, itype)
                scenario = FailureScenario(
                    name=f"Injected {itype.value}",
                    description=injected.injection_description,
                    failure_type=itype.value,
                    trace_data=injected.modified,
                    expected_detections=[injected.expected_detection],
                )
                attempt = self._run_scenario(scenario)
                attempts.append(attempt)
            except Exception as e:
                attempts.append(DetectionAttempt(
                    scenario_name=f"Injected {itype.value}",
                    failure_type=itype.value,
                    expected_detector=itype.value,
                    detected=False,
                    confidence=0.0,
                    error=str(e),
                ))

        detected = sum(1 for a in attempts if a.detected)
        errors = sum(1 for a in attempts if a.error)
        total = len(attempts)

        return ValidationReport(
            total_scenarios=total,
            detected=detected,
            missed=total - detected - errors,
            errors=errors,
            coverage_pct=detected / total if total > 0 else 0.0,
            attempts=attempts,
        )

    def _run_scenario(self, scenario: FailureScenario) -> DetectionAttempt:
        """Run a single scenario through the detection pipeline."""
        try:
            import sys
            import os
            backend_path = os.path.join(os.path.dirname(__file__), "..", "..")
            if backend_path not in sys.path:
                sys.path.insert(0, os.path.abspath(backend_path))

            from pisama_detectors import run_all_detectors
        except ImportError:
            try:
                # Fallback: import pisama_detectors from packages
                pkg_path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                       "packages", "pisama-detectors", "src")
                if pkg_path not in sys.path:
                    sys.path.insert(0, os.path.abspath(pkg_path))
                from pisama_detectors import run_all_detectors
            except ImportError:
                return DetectionAttempt(
                    scenario_name=scenario.name,
                    failure_type=scenario.failure_type,
                    expected_detector=scenario.expected_detections[0] if scenario.expected_detections else "unknown",
                    detected=False,
                    confidence=0.0,
                    error="pisama_detectors not importable",
                )

        try:
            results = run_all_detectors(scenario.trace_data)

            # Check if any expected detector fired
            for expected in scenario.expected_detections:
                result = results.get(expected)
                if result and not isinstance(result, dict):
                    detected = getattr(result, "detected", False)
                    confidence = getattr(result, "confidence", 0.0)
                    if detected:
                        return DetectionAttempt(
                            scenario_name=scenario.name,
                            failure_type=scenario.failure_type,
                            expected_detector=expected,
                            detected=True,
                            confidence=confidence,
                            actual_detector=expected,
                        )

            # Check if any OTHER detector caught it
            for det_name, result in results.items():
                if isinstance(result, dict):
                    continue
                if getattr(result, "detected", False):
                    return DetectionAttempt(
                        scenario_name=scenario.name,
                        failure_type=scenario.failure_type,
                        expected_detector=scenario.expected_detections[0] if scenario.expected_detections else "unknown",
                        detected=True,
                        confidence=getattr(result, "confidence", 0.0),
                        actual_detector=det_name,
                    )

            return DetectionAttempt(
                scenario_name=scenario.name,
                failure_type=scenario.failure_type,
                expected_detector=scenario.expected_detections[0] if scenario.expected_detections else "unknown",
                detected=False,
                confidence=0.0,
            )

        except Exception as e:
            return DetectionAttempt(
                scenario_name=scenario.name,
                failure_type=scenario.failure_type,
                expected_detector=scenario.expected_detections[0] if scenario.expected_detections else "unknown",
                detected=False,
                confidence=0.0,
                error=str(e),
            )
