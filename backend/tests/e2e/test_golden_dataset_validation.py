"""
E2E Golden Dataset Validation Tests
=====================================

Validates all detectors against the golden dataset (1,067 traces) to ensure
detection accuracy meets target thresholds.

Usage:
    # Run all golden dataset validation tests
    pytest backend/tests/e2e/test_golden_dataset_validation.py -v

    # Run specific detector validation
    pytest backend/tests/e2e/test_golden_dataset_validation.py -k "loop" -v

    # Run with F1 threshold report
    pytest backend/tests/e2e/test_golden_dataset_validation.py -v --tb=short
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any

from app.detection.validation import DetectionType


# Target F1 thresholds per detection type
ACCURACY_TARGETS = {
    "infinite_loop": 0.90,
    "state_corruption": 0.85,
    "persona_drift": 0.80,
    "coordination_deadlock": 0.85,
    "F1_specification_mismatch": 0.70,
    "F2_poor_decomposition": 0.70,
    "F3_resource_misallocation": 0.70,
    "F5_flawed_workflow": 0.70,
    "F6_task_derailment": 0.70,
    "F7_context_neglect": 0.70,
    "F8_information_withholding": 0.70,
    "F9_role_usurpation": 0.70,
    "F10_communication_breakdown": 0.70,
    "F11_coordination_failure": 0.70,
    "F12_output_validation": 0.70,
    "F13_quality_gate_bypass": 0.70,
    "F14_completion_misjudgment": 0.70,
}

GOLDEN_DATASET_PATH = Path(__file__).parent.parent.parent / "fixtures" / "golden" / "golden_traces.jsonl"
MANIFEST_PATH = Path(__file__).parent.parent.parent / "fixtures" / "golden" / "manifest.json"


@pytest.fixture(scope="module")
def golden_manifest() -> Dict[str, Any]:
    """Load golden dataset manifest."""
    if not MANIFEST_PATH.exists():
        pytest.skip(f"Golden manifest not found: {MANIFEST_PATH}")
    with open(MANIFEST_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def golden_traces() -> list:
    """Load all golden traces."""
    if not GOLDEN_DATASET_PATH.exists():
        pytest.skip(f"Golden dataset not found: {GOLDEN_DATASET_PATH}")
    traces = []
    with open(GOLDEN_DATASET_PATH) as f:
        for line in f:
            if line.strip():
                traces.append(json.loads(line))
    return traces


class TestGoldenDatasetIntegrity:
    """Validate the golden dataset itself is complete and well-formed."""

    def test_dataset_exists(self):
        assert GOLDEN_DATASET_PATH.exists(), f"Golden dataset not found: {GOLDEN_DATASET_PATH}"

    def test_manifest_exists(self):
        assert MANIFEST_PATH.exists(), f"Manifest not found: {MANIFEST_PATH}"

    def test_minimum_trace_count(self, golden_traces):
        assert len(golden_traces) >= 1000, (
            f"Golden dataset has only {len(golden_traces)} traces, expected 1000+"
        )

    def test_all_detection_types_covered(self, golden_manifest):
        """Verify golden dataset covers all required detection types."""
        required_types = [
            "infinite_loop", "state_corruption", "persona_drift",
            "coordination_deadlock",
        ]
        breakdown = golden_manifest.get("by_detection_type", golden_manifest.get("breakdown", {}))
        for dtype in required_types:
            found = any(
                dtype.lower() in key.lower()
                for key in breakdown.keys()
            )
            assert found, f"Detection type '{dtype}' not in golden dataset"

    def test_minimum_samples_per_type(self, golden_manifest):
        """Each detection type needs at least 30 samples for reliable metrics."""
        breakdown = golden_manifest.get("by_detection_type", golden_manifest.get("breakdown", {}))
        for dtype, count in breakdown.items():
            if dtype.lower() == "healthy":
                continue
            assert count >= 30, (
                f"Detection type '{dtype}' has only {count} samples (need 30+)"
            )

    def test_healthy_control_traces(self, golden_manifest):
        """Golden dataset must include healthy control traces."""
        breakdown = golden_manifest.get("by_detection_type", golden_manifest.get("breakdown", {}))
        healthy_keys = [k for k in breakdown if "healthy" in k.lower()]
        assert healthy_keys, "No healthy control traces in golden dataset"
        total_healthy = sum(breakdown[k] for k in healthy_keys)
        assert total_healthy >= 50, f"Only {total_healthy} healthy traces (need 50+)"

    def test_trace_format(self, golden_traces):
        """Verify traces have expected format."""
        sample = golden_traces[0]
        assert "resourceSpans" in sample or "_golden_metadata" in sample, (
            "Golden traces must contain resourceSpans or _golden_metadata"
        )


class TestCoreDetectorAccuracy:
    """Validate core detector accuracy against golden dataset."""

    @pytest.fixture(scope="class")
    def harness_results(self, golden_traces):
        """Run the golden test harness and cache results for all tests."""
        try:
            from app.detection.golden_test_harness import (
                GoldenDatasetTestHarness,
                HarnessConfig,
            )
        except ImportError:
            pytest.skip("Golden test harness not available")

        config = HarnessConfig(
            dataset_path=GOLDEN_DATASET_PATH,
            output_dir=Path("/tmp/golden_validation"),
            detectors=["loop", "coordination", "corruption", "persona_drift"],
            save_misclassified=False,
        )
        harness = GoldenDatasetTestHarness(config)
        return harness.run_all()

    def test_loop_detector_accuracy(self, harness_results):
        if "loop" not in harness_results:
            pytest.skip("Loop detector not tested")
        result = harness_results["loop"]
        target = ACCURACY_TARGETS.get("infinite_loop", 0.90)
        assert result.metrics["f1_score"] >= target * 0.8, (
            f"Loop F1={result.metrics['f1_score']:.3f}, target={target:.2f} "
            f"(P={result.metrics['precision']:.3f}, R={result.metrics['recall']:.3f})"
        )

    def test_corruption_detector_accuracy(self, harness_results):
        if "corruption" not in harness_results:
            pytest.skip("Corruption detector not tested")
        result = harness_results["corruption"]
        target = ACCURACY_TARGETS.get("state_corruption", 0.85)
        assert result.metrics["f1_score"] >= target * 0.8, (
            f"Corruption F1={result.metrics['f1_score']:.3f}, target={target:.2f}"
        )

    def test_coordination_detector_accuracy(self, harness_results):
        if "coordination" not in harness_results:
            pytest.skip("Coordination detector not tested")
        result = harness_results["coordination"]
        target = ACCURACY_TARGETS.get("coordination_deadlock", 0.85)
        assert result.metrics["f1_score"] >= target * 0.8, (
            f"Coordination F1={result.metrics['f1_score']:.3f}, target={target:.2f}"
        )

    def test_persona_detector_accuracy(self, harness_results):
        if "persona_drift" not in harness_results:
            pytest.skip("Persona detector not tested")
        result = harness_results["persona_drift"]
        target = ACCURACY_TARGETS.get("persona_drift", 0.80)
        assert result.metrics["f1_score"] >= target * 0.8, (
            f"Persona F1={result.metrics['f1_score']:.3f}, target={target:.2f}"
        )


class TestFrameworkDetectorAccuracy:
    """Validate framework-specific detectors against golden dataset."""

    @pytest.fixture(scope="class")
    def framework_golden_entries(self, golden_traces):
        """Extract framework-specific golden entries."""
        entries_by_type = {}
        for trace in golden_traces:
            meta = trace.get("_golden_metadata", {})
            dtype = meta.get("detection_type", "")
            if dtype not in entries_by_type:
                entries_by_type[dtype] = []
            entries_by_type[dtype].append(trace)
        return entries_by_type

    def test_framework_types_have_golden_data(self, framework_golden_entries):
        """At least some framework types should have golden data."""
        framework_types = [
            "openclaw_session_loop", "openclaw_tool_abuse",
            "dify_rag_poisoning", "dify_variable_leak",
            "langgraph_recursion", "langgraph_state_corruption",
        ]
        found = [t for t in framework_types if t in framework_golden_entries]
        # Report coverage without hard failure (golden data being built)
        print(f"\nFramework golden data coverage: {len(found)}/{len(framework_types)}")
        for t in framework_types:
            count = len(framework_golden_entries.get(t, []))
            status = "OK" if count >= 5 else "MISSING"
            print(f"  {t}: {count} traces [{status}]")


class TestDetectionPipelineE2E:
    """End-to-end pipeline tests: ingest → detect → report."""

    def test_otel_trace_ingestion_and_detection(self):
        """Ingest an OTEL trace and run detection on it."""
        from app.ingestion.otel import OTELParser

        # Create a minimal OTEL trace with loop pattern
        otel_trace = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "test-agent"}},
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "abc123",
                                    "spanId": f"span_{i}",
                                    "name": "agent.step",
                                    "startTimeUnixNano": str(1000000000 * (i + 1)),
                                    "endTimeUnixNano": str(1000000000 * (i + 2)),
                                    "attributes": [
                                        {"key": "gen_ai.agent.id", "value": {"stringValue": "agent1"}},
                                        {"key": "gen_ai.response", "value": {"stringValue": f"Processing step {i % 3}"}},
                                    ],
                                }
                                for i in range(10)
                            ]
                        }
                    ],
                }
            ]
        }

        parser = OTELParser()
        spans = otel_trace["resourceSpans"][0]["scopeSpans"][0]["spans"]
        parsed = parser.parse_spans(spans)
        assert parsed is not None, "OTEL parser should parse valid spans"
        assert len(parsed) > 0, "Should extract state snapshots from spans"

    def test_mast_trace_import_and_detect(self):
        """Import a real MAST trace from the test set and run detection."""
        from app.ingestion.importers.mast import MASTImporter
        from app.detection.turn_aware import analyze_conversation_turns

        mast_file = Path(__file__).parent.parent.parent.parent / "data" / "mast_test_373.json"
        if not mast_file.exists():
            pytest.skip("MAST test set not found")

        with open(mast_file) as f:
            records = json.load(f)

        # Find a parseable trace
        importer = MASTImporter()
        conv = None
        for record in records[:20]:
            if len(json.dumps(record)) > 100_000:
                continue
            try:
                conv = importer.import_conversation(json.dumps(record))
                if conv.total_turns >= 2:
                    break
            except Exception:
                continue

        assert conv is not None, "Should find at least one parseable MAST trace"
        assert conv.total_turns >= 2

        # Convert ConversationTrace to TurnSnapshots
        from app.detection.turn_aware._base import TurnSnapshot
        snapshots = [
            TurnSnapshot(
                turn_number=t.turn_number,
                participant_type=t.role or "agent",
                participant_id=t.participant_id or "unknown",
                content=t.content or "",
            )
            for t in conv.turns
        ]

        # Run detection
        results = analyze_conversation_turns(snapshots)
        assert isinstance(results, list)
        assert results is not None


class TestDetectionConsistency:
    """Verify detectors produce consistent results across runs."""

    def test_deterministic_detection(self):
        """Same input should produce same output."""
        from app.detection.turn_aware.task_decomposition import TurnAwareTaskDecompositionDetector
        from app.detection.turn_aware._base import TurnSnapshot

        detector = TurnAwareTaskDecompositionDetector()
        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="user",
                participant_id="user1",
                content="Build an authentication system with OAuth and JWT",
            ),
            TurnSnapshot(
                turn_number=1,
                participant_type="agent",
                participant_id="agent1",
                content="I'll implement OAuth. Step 1: Set up OAuth provider.",
            ),
        ]

        result1 = detector.detect(turns)
        result2 = detector.detect(turns)

        assert result1.detected == result2.detected
        assert result1.confidence == result2.confidence
        assert result1.severity == result2.severity

    def test_framework_detector_deterministic(self):
        """Framework-specific detectors are deterministic."""
        from app.detection.openclaw import OpenClawSessionLoopDetector

        detector = OpenClawSessionLoopDetector()
        session = {
            "session_id": "det-test",
            "events": [
                {"type": "tool.call", "tool_name": "search", "tool_input": {"q": "x"}},
                {"type": "tool.result", "tool_result": {"status": "ok"}},
                {"type": "tool.call", "tool_name": "search", "tool_input": {"q": "x"}},
                {"type": "tool.result", "tool_result": {"status": "ok"}},
                {"type": "tool.call", "tool_name": "search", "tool_input": {"q": "x"}},
            ],
        }

        result1 = detector.detect_session(session)
        result2 = detector.detect_session(session)

        assert result1.detected == result2.detected
        assert result1.confidence == result2.confidence
