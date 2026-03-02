"""Tests for self-healing across LangGraph, Dify, and OpenClaw frameworks.

Verifies the full healing pipeline (analyze -> generate fix -> apply -> verify)
for each framework, including API client mocking, auto-apply, and verification.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.healing.engine import SelfHealingEngine
from app.healing.models import HealingStatus, HealingConfig
from app.healing.auto_apply import AutoApplyService, AutoApplyConfig, ApplyResult
from app.healing.verification import VerificationOrchestrator, VerificationResult


# ============================================================================
# Helpers
# ============================================================================

def _make_detection(detection_type: str, confidence: float = 0.85) -> dict:
    """Create a mock detection dict."""
    return {
        "id": f"det_{detection_type[:6]}",
        "detection_type": detection_type,
        "confidence": confidence,
        "method": "hash",
        "details": {
            "message": f"Detected {detection_type}",
            "affected_agents": ["agent_1"],
        },
    }


def _mock_langgraph_client():
    """Create a mock LangGraph API client."""
    client = AsyncMock()
    client.get_assistant = AsyncMock(return_value={
        "assistant_id": "asst-123",
        "name": "test-graph",
        "config": {"configurable": {"recursion_limit": 100}},
        "metadata": {},
        "nodes": [
            {"id": "start", "type": "agent"},
            {"id": "tool", "type": "tool_node"},
        ],
        "edges": [{"source": "start", "target": "tool"}],
    })
    client.update_assistant = AsyncMock(return_value={"assistant_id": "asst-123"})
    client.run_graph = AsyncMock(return_value={
        "run_id": "run-456",
        "thread_id": "thread-789",
        "status": "success",
    })
    client.test_connection = AsyncMock(return_value=True)
    return client


def _mock_dify_client():
    """Create a mock Dify API client."""
    client = AsyncMock()
    client.get_app = AsyncMock(return_value={
        "id": "app-123",
        "name": "test-workflow",
        "mode": "workflow",
        "model_config": {},
    })
    client.get_app_config = AsyncMock(return_value={
        "nodes": [
            {"id": "start", "data": {"type": "start", "title": "Start"}},
            {"id": "llm-1", "data": {"type": "llm", "title": "LLM Node"}},
            {"id": "iter-1", "data": {"type": "iteration", "title": "Iterator"}},
        ],
        "edges": [{"source": "start", "target": "llm-1"}],
    })
    client.update_app = AsyncMock(return_value={"id": "app-123"})
    client.update_app_config = AsyncMock(return_value={})
    client.run_and_wait = AsyncMock(return_value={
        "workflow_run": {
            "id": "run-123",
            "status": "succeeded",
        },
    })
    client.test_connection = AsyncMock(return_value=True)
    return client


def _mock_openclaw_client():
    """Create a mock OpenClaw API client."""
    client = AsyncMock()
    client.get_agent = AsyncMock(return_value={
        "id": "agent-123",
        "name": "test-agent",
        "tools": [
            {"name": "web_search", "enabled": True},
            {"name": "file_read", "enabled": True},
        ],
        "permissions": {},
        "limits": {},
        "sandbox": {"enabled": False},
        "metadata": {},
    })
    client.update_agent = AsyncMock(return_value={"id": "agent-123"})
    client.run_session = AsyncMock(return_value={
        "session_id": "sess-456",
        "status": "completed",
    })
    client.test_connection = AsyncMock(return_value=True)
    return client


# ============================================================================
# LangGraph Healing Tests
# ============================================================================


class TestLangGraphHealing:
    """Tests for LangGraph graph healing pipeline."""

    @pytest.fixture
    def engine(self):
        return SelfHealingEngine(
            auto_apply=True,
            auto_apply_config=AutoApplyConfig(require_git_backup=False),
        )

    @pytest.fixture
    def client(self):
        return _mock_langgraph_client()

    @pytest.mark.asyncio
    async def test_heal_langgraph_recursion(self, engine, client):
        """Should heal a langgraph_recursion detection by adding recursion guard."""
        detection = _make_detection("langgraph_recursion", confidence=0.9)

        result = await engine.heal_langgraph_graph(
            detection=detection,
            assistant_id="asst-123",
            langgraph_client=client,
            skip_verification=True,
        )

        assert result.status == HealingStatus.SUCCESS
        assert len(result.applied_fixes) >= 1
        assert result.metadata.get("framework") == "langgraph"
        assert result.metadata.get("verification_skipped") is True

    @pytest.mark.asyncio
    async def test_heal_langgraph_state_corruption(self, engine, client):
        """Should heal a langgraph_state_corruption detection."""
        detection = _make_detection("langgraph_state_corruption", confidence=0.85)

        result = await engine.heal_langgraph_graph(
            detection=detection,
            assistant_id="asst-123",
            langgraph_client=client,
            skip_verification=True,
        )

        assert result.status == HealingStatus.SUCCESS
        assert len(result.applied_fixes) >= 1

    @pytest.mark.asyncio
    async def test_heal_langgraph_edge_misroute(self, engine, client):
        """Should heal a langgraph_edge_misroute detection."""
        detection = _make_detection("langgraph_edge_misroute", confidence=0.7)

        result = await engine.heal_langgraph_graph(
            detection=detection,
            assistant_id="asst-123",
            langgraph_client=client,
            skip_verification=True,
        )

        assert result.status == HealingStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_heal_langgraph_with_verification(self, engine, client):
        """Should verify LangGraph healing with Level 2 execution-based verification."""
        detection = _make_detection("langgraph_recursion", confidence=0.9)

        result = await engine.heal_langgraph_graph(
            detection=detection,
            assistant_id="asst-123",
            langgraph_client=client,
            skip_verification=False,
        )

        assert result.status == HealingStatus.SUCCESS
        assert "verification" in result.metadata
        assert result.metadata["verification"]["passed"] is True

    @pytest.mark.asyncio
    async def test_heal_langgraph_concurrent_blocked(self, engine, client):
        """Concurrent healing on same assistant should be blocked."""
        detection = _make_detection("langgraph_recursion")

        # Create a slow mock to hold the lock
        async def slow_get(*args, **kwargs):
            await asyncio.sleep(0.5)
            return client.get_assistant.return_value

        client.get_assistant = AsyncMock(side_effect=slow_get)

        # Start first healing
        task1 = asyncio.create_task(
            engine.heal_langgraph_graph(
                detection=detection,
                assistant_id="asst-123",
                langgraph_client=client,
                skip_verification=True,
            )
        )

        # Give task1 time to acquire lock
        await asyncio.sleep(0.05)

        # Second healing should be blocked
        result2 = await engine.heal_langgraph_graph(
            detection=detection,
            assistant_id="asst-123",
            langgraph_client=client,
            skip_verification=True,
        )

        assert result2.status == HealingStatus.FAILED
        assert "Concurrent healing blocked" in result2.error

        task1.cancel()
        try:
            await task1
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_heal_langgraph_no_auto_apply(self):
        """Without auto_apply, healing should return PENDING status."""
        engine = SelfHealingEngine(auto_apply=False)
        client = _mock_langgraph_client()
        detection = _make_detection("langgraph_recursion")

        result = await engine.heal_langgraph_graph(
            detection=detection,
            assistant_id="asst-123",
            langgraph_client=client,
        )

        assert result.status == HealingStatus.PENDING
        assert result.metadata.get("requires_approval") is True


# ============================================================================
# Dify Healing Tests
# ============================================================================


class TestDifyHealing:
    """Tests for Dify workflow healing pipeline."""

    @pytest.fixture
    def engine(self):
        return SelfHealingEngine(
            auto_apply=True,
            auto_apply_config=AutoApplyConfig(require_git_backup=False),
        )

    @pytest.fixture
    def client(self):
        return _mock_dify_client()

    @pytest.mark.asyncio
    async def test_heal_dify_iteration_escape(self, engine, client):
        """Should heal a dify_iteration_escape detection."""
        detection = _make_detection("dify_iteration_escape", confidence=0.88)

        result = await engine.heal_dify_workflow(
            detection=detection,
            app_id="app-123",
            dify_client=client,
            skip_verification=True,
        )

        assert result.status == HealingStatus.SUCCESS
        assert len(result.applied_fixes) >= 1
        assert result.metadata.get("framework") == "dify"

    @pytest.mark.asyncio
    async def test_heal_dify_rag_poisoning(self, engine, client):
        """RAG poisoning fix (input_filtering) is DANGEROUS risk — requires manual approval."""
        detection = _make_detection("dify_rag_poisoning", confidence=0.92)

        result = await engine.heal_dify_workflow(
            detection=detection,
            app_id="app-123",
            dify_client=client,
            skip_verification=True,
        )

        # input_filtering is classified as DANGEROUS risk, so auto-apply blocks it
        assert result.status == HealingStatus.FAILED
        assert "risk level" in (result.error or "") or "fix attempts failed" in (result.error or "")

    @pytest.mark.asyncio
    async def test_heal_dify_variable_leak(self, engine, client):
        """Should heal a dify_variable_leak detection."""
        detection = _make_detection("dify_variable_leak", confidence=0.8)

        result = await engine.heal_dify_workflow(
            detection=detection,
            app_id="app-123",
            dify_client=client,
            skip_verification=True,
        )

        assert result.status == HealingStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_heal_dify_with_verification(self, engine, client):
        """Should verify Dify healing with execution-based verification."""
        detection = _make_detection("dify_iteration_escape", confidence=0.85)

        result = await engine.heal_dify_workflow(
            detection=detection,
            app_id="app-123",
            dify_client=client,
            skip_verification=False,
        )

        assert result.status == HealingStatus.SUCCESS
        assert "verification" in result.metadata
        assert result.metadata["verification"]["passed"] is True

    @pytest.mark.asyncio
    async def test_heal_dify_no_auto_apply(self):
        """Without auto_apply, Dify healing should return PENDING."""
        engine = SelfHealingEngine(auto_apply=False)
        client = _mock_dify_client()
        detection = _make_detection("dify_iteration_escape")

        result = await engine.heal_dify_workflow(
            detection=detection,
            app_id="app-123",
            dify_client=client,
        )

        assert result.status == HealingStatus.PENDING
        assert result.metadata.get("requires_approval") is True


# ============================================================================
# OpenClaw Healing Tests
# ============================================================================


class TestOpenClawHealing:
    """Tests for OpenClaw agent healing pipeline."""

    @pytest.fixture
    def engine(self):
        return SelfHealingEngine(
            auto_apply=True,
            auto_apply_config=AutoApplyConfig(require_git_backup=False),
        )

    @pytest.fixture
    def client(self):
        return _mock_openclaw_client()

    @pytest.mark.asyncio
    async def test_heal_openclaw_session_loop(self, engine, client):
        """Should heal an openclaw_session_loop detection."""
        detection = _make_detection("openclaw_session_loop", confidence=0.87)

        result = await engine.heal_openclaw_session(
            detection=detection,
            agent_id="agent-123",
            openclaw_client=client,
            skip_verification=True,
        )

        assert result.status == HealingStatus.SUCCESS
        assert len(result.applied_fixes) >= 1
        assert result.metadata.get("framework") == "openclaw"

    @pytest.mark.asyncio
    async def test_heal_openclaw_tool_abuse(self, engine, client):
        """Should heal an openclaw_tool_abuse detection."""
        detection = _make_detection("openclaw_tool_abuse", confidence=0.75)

        result = await engine.heal_openclaw_session(
            detection=detection,
            agent_id="agent-123",
            openclaw_client=client,
            skip_verification=True,
        )

        assert result.status == HealingStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_heal_openclaw_sandbox_escape(self, engine, client):
        """Sandbox escape fix (safety_boundary) is DANGEROUS risk — requires manual approval."""
        detection = _make_detection("openclaw_sandbox_escape", confidence=0.95)

        result = await engine.heal_openclaw_session(
            detection=detection,
            agent_id="agent-123",
            openclaw_client=client,
            skip_verification=True,
        )

        # safety_boundary is DANGEROUS risk, auto-apply blocks it
        assert result.status == HealingStatus.FAILED

    @pytest.mark.asyncio
    async def test_heal_openclaw_elevated_risk(self, engine, client):
        """Elevated risk fix (permission_gate) is DANGEROUS risk — requires manual approval."""
        detection = _make_detection("openclaw_elevated_risk", confidence=0.82)

        result = await engine.heal_openclaw_session(
            detection=detection,
            agent_id="agent-123",
            openclaw_client=client,
            skip_verification=True,
        )

        # permission_gate is DANGEROUS risk, auto-apply blocks it
        assert result.status == HealingStatus.FAILED

    @pytest.mark.asyncio
    async def test_heal_openclaw_with_verification(self, engine, client):
        """Should verify OpenClaw healing with execution-based verification."""
        detection = _make_detection("openclaw_session_loop", confidence=0.87)

        result = await engine.heal_openclaw_session(
            detection=detection,
            agent_id="agent-123",
            openclaw_client=client,
            skip_verification=False,
        )

        assert result.status == HealingStatus.SUCCESS
        assert "verification" in result.metadata
        assert result.metadata["verification"]["passed"] is True

    @pytest.mark.asyncio
    async def test_heal_openclaw_no_auto_apply(self):
        """Without auto_apply, OpenClaw healing should return PENDING."""
        engine = SelfHealingEngine(auto_apply=False)
        client = _mock_openclaw_client()
        detection = _make_detection("openclaw_session_loop")

        result = await engine.heal_openclaw_session(
            detection=detection,
            agent_id="agent-123",
            openclaw_client=client,
        )

        assert result.status == HealingStatus.PENDING
        assert result.metadata.get("requires_approval") is True


# ============================================================================
# Auto-Apply Framework Dispatch Tests
# ============================================================================


class TestAutoApplyFrameworkDispatch:
    """Tests for framework-specific fix application via AutoApplyService."""

    @pytest.fixture
    def service(self):
        return AutoApplyService(AutoApplyConfig(require_git_backup=False))

    @pytest.mark.asyncio
    async def test_apply_langgraph_fix(self, service):
        """Should dispatch to LangGraph fix applicator."""
        client = _mock_langgraph_client()
        fix = {"id": "fix-1", "fix_type": "circuit_breaker", "parameters": {"recursion_limit": 25}}

        result = await service.apply_fix_generic(
            fix=fix,
            entity_id="asst-123",
            healing_id="heal-1",
            framework="langgraph",
            client=client,
        )

        assert result.success is True
        client.get_assistant.assert_called_once()
        client.update_assistant.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_dify_fix(self, service):
        """Should dispatch to Dify fix applicator."""
        client = _mock_dify_client()
        fix = {"id": "fix-1", "fix_type": "circuit_breaker", "parameters": {"max_iterations": 10}}

        result = await service.apply_fix_generic(
            fix=fix,
            entity_id="app-123",
            healing_id="heal-1",
            framework="dify",
            client=client,
        )

        assert result.success is True
        client.get_app_config.assert_called_once()
        client.update_app_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_openclaw_fix(self, service):
        """Should dispatch to OpenClaw fix applicator."""
        client = _mock_openclaw_client()
        fix = {"id": "fix-1", "fix_type": "circuit_breaker", "parameters": {"max_iterations": 50}}

        result = await service.apply_fix_generic(
            fix=fix,
            entity_id="agent-123",
            healing_id="heal-1",
            framework="openclaw",
            client=client,
        )

        assert result.success is True
        client.get_agent.assert_called_once()
        client.update_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_unsupported_framework(self, service):
        """Should return error for unsupported framework."""
        client = AsyncMock()
        fix = {"id": "fix-1", "fix_type": "circuit_breaker"}

        result = await service.apply_fix_generic(
            fix=fix,
            entity_id="some-id",
            healing_id="heal-1",
            framework="unknown_framework",
            client=client,
        )

        assert result.success is False
        assert "Unsupported framework" in result.error

    @pytest.mark.asyncio
    async def test_apply_rate_limited(self, service):
        """Should rate-limit fixes per entity."""
        client = _mock_langgraph_client()
        fix = {"id": "fix-1", "fix_type": "circuit_breaker", "parameters": {}}

        # Exhaust rate limit
        for _ in range(5):
            await service.apply_fix_generic(
                fix=fix, entity_id="asst-rate", healing_id="heal-1",
                framework="langgraph", client=client,
            )

        # Next should be blocked (either rate limit or healing loop detection)
        result = await service.apply_fix_generic(
            fix=fix, entity_id="asst-rate", healing_id="heal-6",
            framework="langgraph", client=client,
        )

        assert result.success is False
        assert "Rate limited" in result.error or "Healing loop" in result.error


# ============================================================================
# Verification Tests
# ============================================================================


class TestFrameworkVerification:
    """Tests for framework-specific Level 2 verification."""

    @pytest.fixture
    def orchestrator(self):
        return VerificationOrchestrator(verification_timeout=30.0)

    @pytest.mark.asyncio
    async def test_verify_langgraph_success(self, orchestrator):
        """Level 2 verification for LangGraph should pass on successful execution."""
        client = _mock_langgraph_client()

        result = await orchestrator.verify_level2_generic(
            detection_type="langgraph_recursion",
            original_confidence=0.9,
            original_state={"config": {"configurable": {}}},
            applied_fixes={"fix_applied": {"fix_type": "circuit_breaker"}},
            framework="langgraph",
            client=client,
            entity_id="asst-123",
        )

        assert result.passed is True
        assert result.level == 2
        assert result.after_confidence < result.before_confidence

    @pytest.mark.asyncio
    async def test_verify_dify_success(self, orchestrator):
        """Level 2 verification for Dify should pass on successful execution."""
        client = _mock_dify_client()

        result = await orchestrator.verify_level2_generic(
            detection_type="dify_iteration_escape",
            original_confidence=0.85,
            original_state={"nodes": []},
            applied_fixes={"fix_applied": {"fix_type": "circuit_breaker"}},
            framework="dify",
            client=client,
            entity_id="app-123",
        )

        assert result.passed is True
        assert result.level == 2
        assert result.after_confidence < result.before_confidence

    @pytest.mark.asyncio
    async def test_verify_openclaw_success(self, orchestrator):
        """Level 2 verification for OpenClaw should pass on successful execution."""
        client = _mock_openclaw_client()

        result = await orchestrator.verify_level2_generic(
            detection_type="openclaw_session_loop",
            original_confidence=0.87,
            original_state={"limits": {}},
            applied_fixes={"fix_applied": {"fix_type": "circuit_breaker"}},
            framework="openclaw",
            client=client,
            entity_id="agent-123",
        )

        assert result.passed is True
        assert result.level == 2
        assert result.after_confidence < result.before_confidence

    @pytest.mark.asyncio
    async def test_verify_falls_back_on_error(self, orchestrator):
        """If execution-based verification fails, fall back to Level 1."""
        client = _mock_langgraph_client()
        client.run_graph = AsyncMock(side_effect=ConnectionError("service unavailable"))

        result = await orchestrator.verify_level2_generic(
            detection_type="langgraph_recursion",
            original_confidence=0.9,
            original_state={},
            applied_fixes={"fix_applied": {"fix_type": "circuit_breaker"}},
            framework="langgraph",
            client=client,
            entity_id="asst-123",
        )

        assert result.level == 2
        assert result.error is not None
        assert "fell_back_to_level1" in result.details


# ============================================================================
# Client Unit Tests
# ============================================================================


class TestLangGraphClient:
    """Unit tests for LangGraphClient."""

    def test_import(self):
        from app.integrations.langgraph_client import LangGraphClient, LangGraphApiError
        client = LangGraphClient(instance_url="http://localhost:8123", api_key="test")
        assert client.instance_url == "http://localhost:8123"

    def test_error_class(self):
        from app.integrations.langgraph_client import LangGraphApiError
        err = LangGraphApiError("test error", status_code=404, response_body="not found")
        assert err.status_code == 404
        assert err.message == "test error"

    def test_config_diff(self):
        from app.integrations.langgraph_client import LangGraphConfigDiff
        diff = LangGraphConfigDiff.generate_diff(
            original={"nodes": [{"id": "a"}], "edges": []},
            modified={"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"source": "a", "target": "b"}]},
        )
        assert "Added node: b" in diff["changes"]
        assert diff["before"]["nodes"] == 1
        assert diff["after"]["nodes"] == 2


class TestDifyClient:
    """Unit tests for DifyClient."""

    def test_import(self):
        from app.integrations.dify_client import DifyClient, DifyApiError
        client = DifyClient(instance_url="http://localhost:5001", api_key="test")
        assert client.instance_url == "http://localhost:5001"

    def test_error_class(self):
        from app.integrations.dify_client import DifyApiError
        err = DifyApiError("test", status_code=500)
        assert err.status_code == 500

    def test_workflow_diff(self):
        from app.integrations.dify_client import DifyWorkflowDiff
        diff = DifyWorkflowDiff.generate_diff(
            original={"nodes": [{"id": "a", "data": {"title": "Start"}}], "edges": []},
            modified={"nodes": [{"id": "a", "data": {"title": "Start"}}, {"id": "b", "data": {"title": "New"}}], "edges": []},
        )
        assert any("Added node" in c for c in diff["changes"])


class TestOpenClawClient:
    """Unit tests for OpenClawClient."""

    def test_import(self):
        from app.integrations.openclaw_client import OpenClawClient, OpenClawApiError
        client = OpenClawClient(instance_url="http://localhost:8000", api_key="test")
        assert client.instance_url == "http://localhost:8000"

    def test_error_class(self):
        from app.integrations.openclaw_client import OpenClawApiError
        err = OpenClawApiError("test", status_code=403)
        assert err.status_code == 403

    def test_config_diff(self):
        from app.integrations.openclaw_client import OpenClawConfigDiff
        diff = OpenClawConfigDiff.generate_diff(
            original={"tools": [{"name": "search"}], "permissions": {}, "limits": {}},
            modified={"tools": [{"name": "search"}, {"name": "write"}], "permissions": {"restricted": True}, "limits": {}},
        )
        assert "Added tool: write" in diff["changes"]
        assert "Permissions modified" in diff["changes"]
