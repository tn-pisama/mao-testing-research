"""Smoke tests — baseline validation for the start of every session.

Run in <30 seconds with no external services (no DB, no Redis, no network).
These verify that core components are importable and minimally functional.

Usage:
    pytest tests/test_smoke.py -v --timeout=30
"""

import json
import importlib
import pytest
from pathlib import Path


DETECTOR_MODULES = [
    "app.detection.loop",
    "app.detection.corruption",
    "app.detection.persona",
    "app.detection.coordination",
    "app.detection.hallucination",
    "app.detection.injection",
    "app.detection.overflow",
    "app.detection.derailment",
    "app.detection.context",
    "app.detection.communication",
    "app.detection.specification",
    "app.detection.decomposition",
    "app.detection.workflow",
    "app.detection.withholding",
    "app.detection.completion",
    "app.detection.validation",
    "app.detection.cost",
]

DATA_DIR = Path(__file__).parent.parent / "data"


class TestDetectorImports:
    """All detector modules must be importable without error."""

    @pytest.mark.parametrize("module_path", DETECTOR_MODULES)
    def test_detector_imports(self, module_path):
        mod = importlib.import_module(module_path)
        assert mod is not None


class TestDetectorMinimalRun:
    """Each ICP detector runs on a trivial input without crashing."""

    def test_loop_detector(self):
        from app.detection.loop import loop_detector, StateSnapshot
        states = [
            StateSnapshot(agent_id="a", content="hello", state_delta={}, sequence_num=0),
            StateSnapshot(agent_id="a", content="world", state_delta={}, sequence_num=1),
        ]
        result = loop_detector.detect_loop(states)
        assert hasattr(result, "detected")
        assert hasattr(result, "confidence")

    def test_injection_detector(self):
        from app.detection.injection import injection_detector
        result = injection_detector.detect_injection("hello world")
        assert hasattr(result, "detected")

    def test_hallucination_detector(self):
        from app.detection.hallucination import hallucination_detector
        result = hallucination_detector.detect_hallucination("The sky is blue")
        assert hasattr(result, "detected")

    def test_corruption_detector(self):
        from app.detection.corruption import corruption_detector
        result = corruption_detector.detect_from_text(task="Write report", output="Here is the report")
        assert hasattr(result, "detected")

    def test_overflow_detector(self):
        from app.detection.overflow import overflow_detector
        result = overflow_detector.detect_overflow(current_tokens=100, model="gpt-4")
        assert hasattr(result, "detected")

    def test_completion_detector(self):
        from app.detection.completion import completion_detector
        result = completion_detector.detect(task="Write report", agent_output="Here is the report")
        assert hasattr(result, "detected")

    def test_derailment_detector(self):
        from app.detection.derailment import TaskDerailmentDetector
        d = TaskDerailmentDetector()
        result = d.detect(task="Write a report", output="Here is the report")
        assert hasattr(result, "detected")

    def test_context_detector(self):
        from app.detection.context import ContextNeglectDetector
        d = ContextNeglectDetector()
        result = d.detect(context="Use formal language", output="Here is the formal response")
        assert hasattr(result, "detected")

    def test_communication_detector(self):
        from app.detection.communication import CommunicationBreakdownDetector
        d = CommunicationBreakdownDetector()
        result = d.detect(sender_message="Please do X", receiver_response="Done X")
        assert hasattr(result, "detected")

    def test_specification_detector(self):
        from app.detection.specification import SpecificationMismatchDetector
        d = SpecificationMismatchDetector()
        result = d.detect(user_intent="Return JSON", task_specification='{"key": "val"}')
        assert hasattr(result, "detected")

    def test_decomposition_detector(self):
        from app.detection.decomposition import TaskDecompositionDetector
        d = TaskDecompositionDetector()
        result = d.detect(task_description="Build a house", decomposition="1. Foundation 2. Walls 3. Roof")
        assert hasattr(result, "detected")

    def test_workflow_detector(self):
        from app.detection.workflow import FlawedWorkflowDetector, WorkflowNode
        d = FlawedWorkflowDetector()
        nodes = [WorkflowNode(id="n1", name="start", node_type="trigger", incoming=[], outgoing=[])]
        result = d.detect(nodes=nodes)
        assert hasattr(result, "detected")

    def test_withholding_detector(self):
        from app.detection.withholding import InformationWithholdingDetector
        d = InformationWithholdingDetector()
        result = d.detect(internal_state="I know X and Y", agent_output="Here is X")
        assert hasattr(result, "detected")


class TestGoldenDatasetLoads:
    """Golden dataset must load without errors."""

    def test_default_golden_dataset_loads(self):
        from app.detection_enterprise.golden_dataset import create_default_golden_dataset
        dataset = create_default_golden_dataset()
        assert len(dataset.entries) > 0

    def test_golden_dataset_has_most_types(self):
        from app.detection_enterprise.golden_dataset import create_default_golden_dataset
        dataset = create_default_golden_dataset()
        present_types = {e.detection_type for e in dataset.entries.values()}
        assert len(present_types) >= 15


class TestCapabilityRegistry:
    """Capability registry must exist and be structurally valid."""

    def test_registry_exists_and_valid(self):
        registry_path = DATA_DIR / "capability_registry.json"
        if not registry_path.exists():
            pytest.skip("Registry not yet generated — run: python -m app.detection_enterprise.calibrate --registry")
        data = json.loads(registry_path.read_text())
        assert "capabilities" in data
        assert "summary" in data
        assert data["summary"]["total"] >= 15


class TestCalibrationReportFresh:
    """Calibration report should exist and have valid structure."""

    def test_calibration_report_exists(self):
        report_path = DATA_DIR / "calibration_report.json"
        assert report_path.exists(), "No calibration report — run: python -m app.detection_enterprise.calibrate"

    def test_calibration_report_structure(self):
        report_path = DATA_DIR / "calibration_report.json"
        if not report_path.exists():
            pytest.skip("No calibration report")
        data = json.loads(report_path.read_text())
        assert "results" in data
        assert data["detector_count"] >= 15
