"""Tests for Moltbot benchmark validation."""

import json
from pathlib import Path

import pytest


MOLTBOT_BENCHMARK_DIR = Path(__file__).parent.parent / "data" / "moltbot"


def load_benchmark_file(filename: str) -> dict:
    """Load a benchmark JSON file."""
    filepath = MOLTBOT_BENCHMARK_DIR / filename
    with open(filepath) as f:
        return json.load(f)


class TestMoltbotBenchmarks:
    """Test suite for Moltbot benchmark files."""

    @pytest.mark.parametrize(
        "filename",
        [
            "loop_detection.json",
            "overflow_detection.json",
            "persona_detection.json",
            "coordination_detection.json",
            "injection_detection.json",
            "completion_detection.json",
            "corruption_detection.json",
        ],
    )
    def test_benchmark_file_exists(self, filename: str):
        """Test that all benchmark files exist."""
        filepath = MOLTBOT_BENCHMARK_DIR / filename
        assert filepath.exists(), f"Benchmark file {filename} not found"

    @pytest.mark.parametrize(
        "filename",
        [
            "loop_detection.json",
            "overflow_detection.json",
            "persona_detection.json",
            "coordination_detection.json",
            "injection_detection.json",
            "completion_detection.json",
            "corruption_detection.json",
        ],
    )
    def test_benchmark_structure(self, filename: str):
        """Test that benchmark files have required structure."""
        data = load_benchmark_file(filename)

        # Required top-level fields
        assert "description" in data
        assert "purpose" in data
        assert "platform" in data
        assert "detector" in data
        assert "cases" in data

        # Platform should be moltbot
        assert data["platform"] == "moltbot"

        # Cases should be a list
        assert isinstance(data["cases"], list)
        assert len(data["cases"]) > 0

    @pytest.mark.parametrize(
        "filename",
        [
            "loop_detection.json",
            "overflow_detection.json",
            "persona_detection.json",
            "coordination_detection.json",
            "injection_detection.json",
            "completion_detection.json",
            "corruption_detection.json",
        ],
    )
    def test_case_structure(self, filename: str):
        """Test that each case has required fields."""
        data = load_benchmark_file(filename)

        for case in data["cases"]:
            # Required case fields
            assert "case_id" in case
            assert "description" in case
            assert "expected_detection" in case
            assert "difficulty" in case
            assert "reason" in case
            assert "trace" in case

            # Case ID should start with MOLTBOT_
            assert case["case_id"].startswith("MOLTBOT_")

            # Difficulty should be valid
            assert case["difficulty"] in ["easy", "medium", "hard"]

            # Expected detection should be boolean
            assert isinstance(case["expected_detection"], bool)

    @pytest.mark.parametrize(
        "filename",
        [
            "loop_detection.json",
            "overflow_detection.json",
            "persona_detection.json",
            "coordination_detection.json",
            "injection_detection.json",
            "completion_detection.json",
            "corruption_detection.json",
        ],
    )
    def test_trace_structure(self, filename: str):
        """Test that traces have required PISAMA trace structure."""
        data = load_benchmark_file(filename)

        for case in data["cases"]:
            trace = case["trace"]

            # Required trace fields
            assert "trace_id" in trace
            assert "platform" in trace
            assert "session_id" in trace
            assert "spans" in trace

            # Platform should be moltbot
            assert trace["platform"] == "moltbot"

            # Should have at least one span
            assert len(trace["spans"]) > 0

    @pytest.mark.parametrize(
        "filename",
        [
            "loop_detection.json",
            "overflow_detection.json",
            "persona_detection.json",
            "coordination_detection.json",
            "injection_detection.json",
            "completion_detection.json",
            "corruption_detection.json",
        ],
    )
    def test_span_structure(self, filename: str):
        """Test that spans have required fields."""
        data = load_benchmark_file(filename)

        for case in data["cases"]:
            trace = case["trace"]

            for span in trace["spans"]:
                # Required span fields
                assert "span_id" in span
                assert "name" in span
                assert "kind" in span
                assert "start_time" in span
                assert "status" in span

                # Kind should be valid
                valid_kinds = [
                    "agent",
                    "agent_turn",
                    "task",
                    "workflow",
                    "tool",
                    "llm",
                    "message",
                    "handoff",
                    "system",
                    "user_input",
                    "user_output",
                ]
                assert span["kind"] in valid_kinds

                # Status should be valid
                valid_statuses = ["unset", "in_progress", "ok", "error", "timeout"]
                assert span["status"] in valid_statuses

    def test_detector_coverage(self):
        """Test that we have benchmarks for key Moltbot detectors."""
        expected_detectors = {
            "loop",
            "overflow",
            "persona",
            "coordination",
            "injection",
            "completion",
            "corruption",
        }

        actual_detectors = set()
        for filepath in MOLTBOT_BENCHMARK_DIR.glob("*_detection.json"):
            data = load_benchmark_file(filepath.name)
            actual_detectors.add(data["detector"])

        assert (
            expected_detectors == actual_detectors
        ), f"Missing detectors: {expected_detectors - actual_detectors}"

    def test_total_case_count(self):
        """Test that we have sufficient test cases."""
        total_cases = 0

        for filepath in MOLTBOT_BENCHMARK_DIR.glob("*_detection.json"):
            data = load_benchmark_file(filepath.name)
            total_cases += len(data["cases"])

        # Should have at least 7 cases (one per detector minimum)
        assert total_cases >= 7, f"Only {total_cases} cases found, need at least 7"

    def test_case_id_uniqueness(self):
        """Test that case IDs are unique across all benchmarks."""
        case_ids = set()

        for filepath in MOLTBOT_BENCHMARK_DIR.glob("*_detection.json"):
            data = load_benchmark_file(filepath.name)
            for case in data["cases"]:
                case_id = case["case_id"]
                assert case_id not in case_ids, f"Duplicate case_id: {case_id}"
                case_ids.add(case_id)


class TestMoltbotIntegration:
    """Integration tests for Moltbot adapter."""

    @pytest.mark.skip(reason="Requires running Moltbot instance")
    def test_adapter_connection(self):
        """Test that adapter can connect to Moltbot gateway."""
        # This would test the actual adapter connection
        # Requires: MOLTBOT_GATEWAY_URL environment variable
        pass

    @pytest.mark.skip(reason="Requires running PISAMA backend")
    def test_trace_export(self):
        """Test that traces are exported to PISAMA."""
        # This would test end-to-end trace export
        # Requires: PISAMA_API_URL and PISAMA_API_KEY
        pass
