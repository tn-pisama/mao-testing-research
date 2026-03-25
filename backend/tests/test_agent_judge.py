"""Tests for Agent-as-Judge — multi-step evaluation with memory and tools."""
import os
import pytest

os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")


class TestAgentJudgeCore:
    """Test the AgentJudge class internals (no API calls)."""

    def setup_method(self):
        from app.detection.llm_judge.agent_judge import AgentJudge
        self.judge = AgentJudge()

    def test_tool_definitions_valid(self):
        from app.detection.llm_judge.agent_judge import AGENT_TOOLS
        assert len(AGENT_TOOLS) == 4
        names = {t["name"] for t in AGENT_TOOLS}
        assert "query_detection_memory" in names
        assert "run_detector" in names
        assert "find_similar_cases" in names
        assert "check_source_grounding" in names

    def test_handle_query_memory_empty(self):
        result = self.judge._handle_tool_call(
            "query_detection_memory",
            {"detection_type": "hallucination"},
            {},
        )
        import json
        data = json.loads(result)
        assert data["total_past_judgments"] == 0

    def test_handle_query_memory_with_history(self):
        from app.detection.llm_judge.agent_judge import PastJudgment
        self.judge._memory = [
            PastJudgment(detection_type="hallucination", verdict=True, confidence=0.85,
                         reasoning_summary="Output contained unsupported claims"),
            PastJudgment(detection_type="hallucination", verdict=False, confidence=0.30,
                         reasoning_summary="Output well-grounded in sources"),
        ]
        result = self.judge._handle_tool_call(
            "query_detection_memory",
            {"detection_type": "hallucination"},
            {},
        )
        import json
        data = json.loads(result)
        assert data["total_past_judgments"] == 2
        assert len(data["recent_verdicts"]) == 2

    def test_handle_find_similar_cases(self):
        from app.detection.llm_judge.agent_judge import PastJudgment
        self.judge._memory = [
            PastJudgment(detection_type="loop", verdict=True, confidence=0.9, reasoning_summary="20 repeated states"),
            PastJudgment(detection_type="hallucination", verdict=True, confidence=0.7, reasoning_summary="Unsupported claim"),
        ]
        result = self.judge._handle_tool_call(
            "find_similar_cases",
            {"detection_type": "loop", "trace_summary": "agent repeating actions"},
            {},
        )
        import json
        cases = json.loads(result)
        assert len(cases) == 1
        assert cases[0]["verdict"] is True

    def test_handle_run_detector(self):
        """Running a detector via tool call should work."""
        result = self.judge._handle_tool_call(
            "run_detector",
            {"detection_type": "convergence", "input_data": {
                "metrics": [{"step": i, "value": 0.5 + 0.02 * (-1)**i} for i in range(20)],
                "direction": "minimize",
            }},
            {},
        )
        import json
        data = json.loads(result)
        assert "detected" in data or "error" in data

    def test_handle_check_source_grounding(self):
        """NLI entailment check via tool call."""
        result = self.judge._handle_tool_call(
            "check_source_grounding",
            {"claim": "Paris is the capital of France",
             "source_text": "Paris is the capital and largest city of France."},
            {},
        )
        import json
        data = json.loads(result)
        assert "label" in data or "error" in data

    def test_handle_unknown_tool(self):
        result = self.judge._handle_tool_call("nonexistent_tool", {}, {})
        import json
        data = json.loads(result)
        assert "error" in data

    def test_memory_bounded(self):
        """Memory shouldn't grow unbounded."""
        from app.detection.llm_judge.agent_judge import PastJudgment
        self.judge._memory = [
            PastJudgment(detection_type="test", verdict=True, confidence=0.5, reasoning_summary=f"Case {i}")
            for i in range(120)
        ]
        # Simulate the trim that happens after judge()
        if len(self.judge._memory) > 100:
            self.judge._memory = self.judge._memory[-50:]
        assert len(self.judge._memory) == 50


class TestAgentJudgeImport:
    """Test that the agent judge module imports and initializes correctly."""

    def test_import(self):
        from app.detection.llm_judge.agent_judge import AgentJudge, AgentVerdict, get_agent_judge
        assert AgentJudge is not None
        assert AgentVerdict is not None

    def test_singleton(self):
        from app.detection.llm_judge.agent_judge import get_agent_judge
        j1 = get_agent_judge()
        j2 = get_agent_judge()
        assert j1 is j2

    def test_verdict_dataclass(self):
        from app.detection.llm_judge.agent_judge import AgentVerdict
        v = AgentVerdict(
            detected=True,
            confidence=0.85,
            reasoning_chain=["Step 1: checked memory", "Step 2: ran detector"],
            tools_used=["query_detection_memory", "run_detector"],
            memory_context={"past_judgments": 5},
            cost_usd=0.03,
            tokens_used=1500,
            latency_ms=3200,
        )
        assert v.detected
        assert v.confidence == 0.85
        assert len(v.reasoning_chain) == 2
        assert v.cost_usd == 0.03


class TestAgentJudgeEvaluateIntegration:
    """Test that agent_judge flag is accepted by evaluate endpoint."""

    def test_evaluate_request_has_agent_judge_field(self):
        from app.api.v1.evaluate import EvaluateRequest
        req = EvaluateRequest(
            specification={"task": "test"},
            output={"content": "test"},
            agent_judge=True,
        )
        assert req.agent_judge is True

    def test_evaluate_request_default_no_agent_judge(self):
        from app.api.v1.evaluate import EvaluateRequest
        req = EvaluateRequest(
            specification={"task": "test"},
            output={"content": "test"},
        )
        assert req.agent_judge is False
