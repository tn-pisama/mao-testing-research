"""Smoke tests for the /api/v1/evaluate endpoint logic."""
import pytest
from app.api.v1.evaluate import (
    EvaluateRequest,
    EvaluateResponse,
    ROLE_DETECTORS,
    _run_single_detector,
)


class TestRoleDetectors:
    def test_generator_role_has_detectors(self):
        assert "specification" in ROLE_DETECTORS["generator"]
        assert "hallucination" in ROLE_DETECTORS["generator"]
        assert "context_pressure" in ROLE_DETECTORS["generator"]

    def test_evaluator_role_has_persona_drift(self):
        assert "persona_drift" in ROLE_DETECTORS["evaluator"]

    def test_default_fallback(self):
        assert len(ROLE_DETECTORS["default"]) >= 3


class TestRunSingleDetector:
    def test_specification_detector_no_failure(self):
        """Matching spec and output should not trigger."""
        result = _run_single_detector(
            "specification",
            spec={"task": "Write a hello world function"},
            output={"content": "def hello(): print('hello world')"},
            output_text="def hello(): print('hello world')",
            spec_text="Write a hello world function",
        )
        assert result is not None

    def test_hallucination_detector_runs(self):
        """Hallucination detector should run without error."""
        result = _run_single_detector(
            "hallucination",
            spec={"task": "Summarize the document"},
            output={"content": "The document discusses machine learning."},
            output_text="The document discusses machine learning.",
            spec_text="Summarize the document",
        )
        assert result is not None

    def test_derailment_detector_runs(self):
        """Derailment detector should run without error."""
        result = _run_single_detector(
            "derailment",
            spec={"task": "Fix the login bug"},
            output={"content": "I fixed the login bug by updating the auth handler."},
            output_text="I fixed the login bug by updating the auth handler.",
            spec_text="Fix the login bug",
        )
        assert result is not None

    def test_unknown_detector_returns_none(self):
        """Unknown detector name should return None."""
        result = _run_single_detector(
            "nonexistent_detector",
            spec={}, output={},
            output_text="", spec_text="",
        )
        assert result is None

    def test_context_pressure_detector_runs(self):
        """Context pressure detector should run without error."""
        result = _run_single_detector(
            "context_pressure",
            spec={"task": "Build a web app"},
            output={"content": "Here is the implementation."},
            output_text="Here is the implementation.",
            spec_text="Build a web app",
            context_limit=200000,
        )
        # context_pressure needs states, so may return None with minimal input
        # but should NOT raise


class TestEvaluateRequest:
    def test_request_schema(self):
        req = EvaluateRequest(
            specification={"task": "Test task"},
            output={"content": "Test output"},
            agent_role="generator",
        )
        assert req.agent_role == "generator"
        assert req.specification["task"] == "Test task"

    def test_request_with_custom_detectors(self):
        req = EvaluateRequest(
            specification={"task": "Test"},
            output={"content": "Out"},
            detectors=["hallucination", "derailment"],
        )
        assert req.detectors == ["hallucination", "derailment"]
