"""Comprehensive tests for chaos engineering module."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.enterprise.chaos.experiments import (
    ChaosExperiment,
    ExperimentStatus,
    ExperimentType,
    ExperimentResult,
    LatencyExperiment,
    ErrorExperiment,
    MalformedOutputExperiment,
    ToolUnavailableExperiment,
    UncooperativeAgentExperiment,
    ContextTruncationExperiment,
)
from app.enterprise.chaos.targeting import (
    TargetType,
    ChaosTarget,
    TargetBuilder,
    target,
)
from app.enterprise.chaos.safety import (
    BlastRadius,
    SafetyConfig,
    SafetyMonitor,
    DEFAULT_SAFETY_CONFIG,
    STRICT_SAFETY_CONFIG,
    RELAXED_SAFETY_CONFIG,
)
from app.enterprise.chaos.controller import (
    ChaosSession,
    ChaosController,
    create_latency_experiment,
    create_error_experiment,
    create_tool_failure_experiment,
    create_uncooperative_agent_experiment,
)


# ============================================================================
# Experiment Tests
# ============================================================================

class TestLatencyExperiment:
    """Tests for LatencyExperiment."""

    def test_creation_with_defaults(self):
        """Should create experiment with default values."""
        exp = LatencyExperiment(
            name="Test Latency",
            description="Test description",
        )
        assert exp.experiment_type == ExperimentType.LATENCY
        assert exp.min_delay_ms == 100
        assert exp.max_delay_ms == 5000
        assert exp.fixed_delay_ms is None
        assert exp.enabled is True
        assert exp.probability == 1.0

    def test_creation_with_fixed_delay(self):
        """Should allow fixed delay configuration."""
        exp = LatencyExperiment(
            name="Fixed Latency",
            description="Fixed delay",
            fixed_delay_ms=500,
        )
        assert exp.fixed_delay_ms == 500

    @pytest.mark.asyncio
    async def test_apply_fixed_delay(self):
        """Should apply fixed delay."""
        exp = LatencyExperiment(
            name="Fixed",
            description="Fixed delay",
            fixed_delay_ms=10,  # 10ms for fast test
        )
        context = {}
        start = datetime.utcnow()
        result = await exp.apply(context)
        elapsed = (datetime.utcnow() - start).total_seconds()

        assert "chaos_applied" in result
        assert result["chaos_applied"]["type"] == ExperimentType.LATENCY
        assert result["chaos_applied"]["delay_ms"] == 10
        assert elapsed >= 0.01  # At least 10ms

    @pytest.mark.asyncio
    async def test_apply_random_delay(self):
        """Should apply random delay within range."""
        exp = LatencyExperiment(
            name="Random",
            description="Random delay",
            min_delay_ms=5,
            max_delay_ms=15,
        )
        context = {}
        result = await exp.apply(context)

        delay = result["chaos_applied"]["delay_ms"]
        assert 5 <= delay <= 15

    def test_get_effect_description_fixed(self):
        """Should describe fixed delay effect."""
        exp = LatencyExperiment(
            name="Fixed",
            description="Fixed delay",
            fixed_delay_ms=100,
        )
        desc = exp.get_effect_description()
        assert "100ms" in desc
        assert "Fixed" in desc

    def test_get_effect_description_random(self):
        """Should describe random delay effect."""
        exp = LatencyExperiment(
            name="Random",
            description="Random delay",
            min_delay_ms=50,
            max_delay_ms=200,
        )
        desc = exp.get_effect_description()
        assert "50" in desc
        assert "200" in desc

    def test_should_trigger_enabled(self):
        """Should trigger when enabled with 100% probability."""
        exp = LatencyExperiment(
            name="Test",
            description="Test",
            enabled=True,
            probability=1.0,
        )
        assert exp.should_trigger() is True

    def test_should_not_trigger_disabled(self):
        """Should not trigger when disabled."""
        exp = LatencyExperiment(
            name="Test",
            description="Test",
            enabled=False,
        )
        assert exp.should_trigger() is False

    def test_should_trigger_with_probability(self):
        """Should respect probability setting."""
        exp = LatencyExperiment(
            name="Test",
            description="Test",
            enabled=True,
            probability=0.0,
        )
        assert exp.should_trigger() is False


class TestErrorExperiment:
    """Tests for ErrorExperiment."""

    def test_creation_with_defaults(self):
        """Should create with default error codes."""
        exp = ErrorExperiment(
            name="Test Error",
            description="Test",
        )
        assert exp.experiment_type == ExperimentType.ERROR
        assert 500 in exp.error_codes
        assert 502 in exp.error_codes
        assert 503 in exp.error_codes

    @pytest.mark.asyncio
    async def test_apply_sets_error_flag(self):
        """Should set chaos_error flag."""
        exp = ErrorExperiment(
            name="Error",
            description="Error test",
        )
        context = {}
        result = await exp.apply(context)

        assert result["chaos_error"] is True
        assert "chaos_applied" in result
        assert result["chaos_applied"]["error_code"] in exp.error_codes

    def test_get_effect_description(self):
        """Should describe error codes."""
        exp = ErrorExperiment(
            name="Test",
            description="Test",
            error_codes=[500, 503],
        )
        desc = exp.get_effect_description()
        assert "500" in desc
        assert "503" in desc


class TestMalformedOutputExperiment:
    """Tests for MalformedOutputExperiment."""

    @pytest.mark.asyncio
    async def test_truncate_corruption(self):
        """Should truncate output."""
        exp = MalformedOutputExperiment(
            name="Truncate",
            description="Test",
            corruption_types=["truncate"],
        )
        context = {"output": "Hello World, this is a test"}
        result = await exp.apply(context)

        assert len(result["output"]) < len(result["original_output"])
        assert result["chaos_applied"]["corruption_type"] == "truncate"

    @pytest.mark.asyncio
    async def test_json_break_corruption(self):
        """Should break JSON structure."""
        exp = MalformedOutputExperiment(
            name="JSON Break",
            description="Test",
            corruption_types=["json_break"],
        )
        context = {"output": '{"key": "value"}'}
        result = await exp.apply(context)

        assert '{"incomplete": true' in result["output"]

    @pytest.mark.asyncio
    async def test_empty_corruption(self):
        """Should return empty output."""
        exp = MalformedOutputExperiment(
            name="Empty",
            description="Test",
            corruption_types=["empty"],
        )
        context = {"output": "Some content"}
        result = await exp.apply(context)

        assert result["output"] == ""

    @pytest.mark.asyncio
    async def test_empty_output_handling(self):
        """Should handle empty initial output."""
        exp = MalformedOutputExperiment(
            name="Test",
            description="Test",
            corruption_types=["truncate"],
        )
        context = {"output": ""}
        result = await exp.apply(context)

        assert result["output"] == ""


class TestToolUnavailableExperiment:
    """Tests for ToolUnavailableExperiment."""

    @pytest.mark.asyncio
    async def test_blocks_targeted_tool(self):
        """Should block targeted tool."""
        exp = ToolUnavailableExperiment(
            name="Block Tool",
            description="Test",
            target_tools=["search_api"],
            failure_mode="error",
        )
        context = {"tool_name": "search_api"}
        result = await exp.apply(context)

        assert result["tool_blocked"] is True
        assert result["chaos_error"] is True

    @pytest.mark.asyncio
    async def test_ignores_non_targeted_tool(self):
        """Should ignore non-targeted tools."""
        exp = ToolUnavailableExperiment(
            name="Block Tool",
            description="Test",
            target_tools=["search_api"],
            failure_mode="error",
        )
        context = {"tool_name": "other_api"}
        result = await exp.apply(context)

        assert result.get("tool_blocked") is None

    @pytest.mark.asyncio
    async def test_blocks_all_when_no_targets(self):
        """Should block all tools when target_tools is empty."""
        exp = ToolUnavailableExperiment(
            name="Block All",
            description="Test",
            target_tools=[],
            failure_mode="error",
        )
        context = {"tool_name": "any_tool"}
        result = await exp.apply(context)

        assert result["tool_blocked"] is True

    def test_get_effect_description_specific(self):
        """Should describe specific tools."""
        exp = ToolUnavailableExperiment(
            name="Test",
            description="Test",
            target_tools=["api1", "api2"],
            failure_mode="timeout",
        )
        desc = exp.get_effect_description()
        assert "api1" in desc
        assert "api2" in desc
        assert "timeout" in desc


class TestUncooperativeAgentExperiment:
    """Tests for UncooperativeAgentExperiment."""

    @pytest.mark.asyncio
    async def test_refuse_behavior(self):
        """Should make agent refuse."""
        exp = UncooperativeAgentExperiment(
            name="Refuse",
            description="Test",
            target_agents=["agent1"],
            behaviors=["refuse"],
        )
        context = {"agent_name": "agent1", "output": "Normal output"}
        result = await exp.apply(context)

        assert result["agent_refused"] is True
        assert "cannot complete" in result["output"]

    @pytest.mark.asyncio
    async def test_partial_behavior(self):
        """Should give partial output."""
        exp = UncooperativeAgentExperiment(
            name="Partial",
            description="Test",
            target_agents=["agent1"],
            behaviors=["partial"],
        )
        context = {"agent_name": "agent1", "output": "This is a complete response"}
        result = await exp.apply(context)

        assert len(result["output"]) < len("This is a complete response")

    @pytest.mark.asyncio
    async def test_wrong_format_behavior(self):
        """Should return wrong format."""
        exp = UncooperativeAgentExperiment(
            name="Wrong Format",
            description="Test",
            target_agents=["agent1"],
            behaviors=["wrong_format"],
        )
        context = {"agent_name": "agent1", "output": "Normal output"}
        result = await exp.apply(context)

        assert "ERROR" in result["output"]


class TestContextTruncationExperiment:
    """Tests for ContextTruncationExperiment."""

    @pytest.mark.asyncio
    async def test_truncate_from_end(self):
        """Should truncate from end."""
        exp = ContextTruncationExperiment(
            name="Truncate End",
            description="Test",
            truncation_percent=0.5,
            truncate_from="end",
        )
        context = {"agent_context": "Hello World"}
        result = await exp.apply(context)

        assert result["agent_context"] == "Hello"  # First half
        assert result["original_context"] == "Hello World"

    @pytest.mark.asyncio
    async def test_truncate_from_start(self):
        """Should truncate from start."""
        exp = ContextTruncationExperiment(
            name="Truncate Start",
            description="Test",
            truncation_percent=0.5,
            truncate_from="start",
        )
        context = {"agent_context": "Hello World"}
        result = await exp.apply(context)

        assert result["agent_context"] == "World"  # Last half

    @pytest.mark.asyncio
    async def test_no_context_handling(self):
        """Should handle missing context."""
        exp = ContextTruncationExperiment(
            name="Test",
            description="Test",
        )
        context = {}
        result = await exp.apply(context)

        assert "chaos_applied" not in result


# ============================================================================
# Targeting Tests
# ============================================================================

class TestChaosTarget:
    """Tests for ChaosTarget."""

    def test_all_target_matches(self):
        """Should match all in non-production."""
        target = ChaosTarget(target_type=TargetType.ALL)
        context = {"environment": "staging"}
        assert target.matches(context) is True

    def test_excludes_production_by_default(self):
        """Should exclude production by default."""
        target = ChaosTarget(target_type=TargetType.ALL)
        context = {"environment": "production"}
        assert target.matches(context) is False

    def test_includes_production_when_configured(self):
        """Should include production when explicitly configured."""
        target = ChaosTarget(target_type=TargetType.ALL, exclude_production=False)
        context = {"environment": "production"}
        # Will match based on percentage (100% default)
        assert target.matches(context) is True

    def test_agent_target_matches(self):
        """Should match specific agent."""
        target = ChaosTarget(
            target_type=TargetType.AGENT,
            agent_names=["agent1", "agent2"],
        )
        assert target.matches({"agent_name": "agent1"}) is True
        assert target.matches({"agent_name": "agent3"}) is False

    def test_tool_target_matches(self):
        """Should match specific tool."""
        target = ChaosTarget(
            target_type=TargetType.TOOL,
            tool_names=["search"],
        )
        assert target.matches({"tool_name": "search"}) is True
        assert target.matches({"tool_name": "other"}) is False

    def test_tenant_target_matches(self):
        """Should match specific tenant."""
        target = ChaosTarget(
            target_type=TargetType.TENANT,
            tenant_ids=["tenant1"],
        )
        assert target.matches({"tenant_id": "tenant1"}) is True
        assert target.matches({"tenant_id": "tenant2"}) is False

    def test_trace_target_matches(self):
        """Should match specific trace."""
        target = ChaosTarget(
            target_type=TargetType.TRACE,
            trace_ids=["trace123"],
        )
        assert target.matches({"trace_id": "trace123"}) is True
        assert target.matches({"trace_id": "other"}) is False

    def test_percentage_targeting(self):
        """Should respect percentage targeting."""
        target = ChaosTarget(
            target_type=TargetType.PERCENTAGE,
            percentage=0.0,  # 0% should never match
        )
        assert target.matches({}) is False

    def test_describe_all(self):
        """Should describe ALL target."""
        target = ChaosTarget(target_type=TargetType.ALL, percentage=50.0)
        desc = target.describe()
        assert "All" in desc
        assert "50" in desc

    def test_describe_agent(self):
        """Should describe AGENT target."""
        target = ChaosTarget(
            target_type=TargetType.AGENT,
            agent_names=["agent1"],
        )
        desc = target.describe()
        assert "agent1" in desc


class TestTargetBuilder:
    """Tests for TargetBuilder fluent interface."""

    def test_all_target(self):
        """Should build ALL target."""
        t = target().all().build()
        assert t.target_type == TargetType.ALL

    def test_agents_target(self):
        """Should build AGENT target."""
        t = target().agents("agent1", "agent2").build()
        assert t.target_type == TargetType.AGENT
        assert "agent1" in t.agent_names
        assert "agent2" in t.agent_names

    def test_tools_target(self):
        """Should build TOOL target."""
        t = target().tools("tool1").build()
        assert t.target_type == TargetType.TOOL
        assert "tool1" in t.tool_names

    def test_tenants_target(self):
        """Should build TENANT target."""
        t = target().tenants("t1", "t2").build()
        assert t.target_type == TargetType.TENANT
        assert len(t.tenant_ids) == 2

    def test_traces_target(self):
        """Should build TRACE target."""
        t = target().traces("trace1").build()
        assert t.target_type == TargetType.TRACE

    def test_percentage_modifier(self):
        """Should set percentage."""
        t = target().all().percentage(25.0).build()
        assert t.percentage == 25.0

    def test_include_production(self):
        """Should include production."""
        t = target().all().include_production().build()
        assert t.exclude_production is False

    def test_chaining(self):
        """Should support method chaining."""
        t = target().agents("a1").percentage(50.0).include_production().build()
        assert t.target_type == TargetType.AGENT
        assert t.percentage == 50.0
        assert t.exclude_production is False


# ============================================================================
# Safety Tests
# ============================================================================

class TestSafetyConfig:
    """Tests for SafetyConfig."""

    def test_default_config(self):
        """Should have reasonable defaults."""
        config = SafetyConfig()
        assert config.max_blast_radius == BlastRadius.SINGLE_TENANT
        assert config.max_affected_requests == 100
        assert config.max_affected_tenants == 1
        assert config.auto_abort_on_cascade is True

    def test_strict_config(self):
        """Should have strict settings."""
        config = STRICT_SAFETY_CONFIG
        assert config.max_blast_radius == BlastRadius.SINGLE_REQUEST
        assert config.max_affected_requests == 10
        assert "sandbox" in config.allowed_environments

    def test_relaxed_config(self):
        """Should have relaxed settings."""
        config = RELAXED_SAFETY_CONFIG
        assert config.max_affected_requests == 1000
        assert config.require_sandbox is False


class TestSafetyMonitor:
    """Tests for SafetyMonitor."""

    def test_start_resets_state(self):
        """Should reset state on start."""
        monitor = SafetyMonitor(SafetyConfig())
        monitor.affected_requests = 50
        monitor.start()
        assert monitor.affected_requests == 0
        assert monitor.started_at is not None

    def test_record_affected_counts(self):
        """Should count affected requests."""
        monitor = SafetyMonitor(SafetyConfig())
        monitor.start()
        monitor.record_affected("tenant1")
        monitor.record_affected("tenant1")
        assert monitor.affected_requests == 2
        assert len(monitor.affected_tenants) == 1

    def test_record_affected_aborts_on_limit(self):
        """Should abort when request limit exceeded."""
        config = SafetyConfig(max_affected_requests=2)
        monitor = SafetyMonitor(config)
        monitor.start()

        assert monitor.record_affected("t1") is True
        assert monitor.record_affected("t1") is True
        assert monitor.record_affected("t1") is False
        assert monitor.aborted is True
        assert "requests" in monitor.abort_reason

    def test_record_affected_aborts_on_tenant_limit(self):
        """Should abort when tenant limit exceeded."""
        config = SafetyConfig(max_affected_tenants=1)
        monitor = SafetyMonitor(config)
        monitor.start()

        assert monitor.record_affected("t1") is True
        assert monitor.record_affected("t2") is False
        assert "tenants" in monitor.abort_reason

    def test_record_cascade(self):
        """Should count cascades."""
        config = SafetyConfig(cascade_threshold=3)
        monitor = SafetyMonitor(config)
        monitor.start()

        assert monitor.record_cascade() is True
        assert monitor.record_cascade() is True
        assert monitor.record_cascade() is False
        assert monitor.aborted is True

    def test_check_environment_allowed(self):
        """Should allow configured environments."""
        monitor = SafetyMonitor(SafetyConfig(allowed_environments=["dev"]))
        assert monitor.check_environment("dev") is True
        assert monitor.check_environment("prod") is False

    def test_check_blast_radius(self):
        """Should check blast radius limits."""
        config = SafetyConfig(max_blast_radius=BlastRadius.SINGLE_AGENT)
        monitor = SafetyMonitor(config)

        assert monitor.check_blast_radius(BlastRadius.SINGLE_REQUEST) is True
        assert monitor.check_blast_radius(BlastRadius.SINGLE_AGENT) is True
        assert monitor.check_blast_radius(BlastRadius.MULTI_TENANT) is False

    def test_is_safe_to_continue_after_abort(self):
        """Should not be safe after abort."""
        monitor = SafetyMonitor(SafetyConfig())
        monitor.start()
        monitor._abort("Test abort")
        assert monitor.is_safe_to_continue() is False

    def test_get_status(self):
        """Should return status dict."""
        monitor = SafetyMonitor(SafetyConfig())
        monitor.start()
        monitor.record_affected("t1")

        status = monitor.get_status()
        assert "affected_requests" in status
        assert status["affected_requests"] == 1
        assert "aborted" in status
        assert status["aborted"] is False


# ============================================================================
# Controller Tests
# ============================================================================

class TestChaosSession:
    """Tests for ChaosSession."""

    def test_creation(self):
        """Should create session with defaults."""
        session = ChaosSession(
            name="Test Session",
            target=ChaosTarget(target_type=TargetType.ALL),
        )
        assert session.id is not None
        assert session.status == ExperimentStatus.PENDING
        assert len(session.experiments) == 0

    def test_creation_with_experiments(self):
        """Should create session with experiments."""
        exp = LatencyExperiment(name="Test", description="Test")
        session = ChaosSession(
            name="Test Session",
            target=ChaosTarget(target_type=TargetType.ALL),
            experiments=[exp],
        )
        assert len(session.experiments) == 1


class TestChaosController:
    """Tests for ChaosController."""

    def test_create_session(self):
        """Should create chaos session."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.TENANT, tenant_ids=["t1"])
        experiments = [LatencyExperiment(name="Test", description="Test")]

        session = controller.create_session(
            name="Test Session",
            target=target,
            experiments=experiments,
        )

        assert session.name == "Test Session"
        assert len(session.experiments) == 1

    def test_start_session(self):
        """Should start session."""
        # Use SINGLE_TENANT target to stay within default blast radius
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.TENANT, tenant_ids=["t1"])
        session = controller.create_session(
            name="Test",
            target=target,
            experiments=[],
        )

        result = controller.start_session(session)

        assert result is True
        assert session.id in controller.active_sessions
        assert session.status == ExperimentStatus.RUNNING

    def test_start_session_blocked_by_blast_radius(self):
        """Should fail to start session exceeding blast radius."""
        controller = ChaosController()
        # ALL target with 100% maps to MULTI_TENANT which exceeds default
        target = ChaosTarget(target_type=TargetType.ALL, percentage=100)
        session = controller.create_session("Test", target, [])

        result = controller.start_session(session)

        assert result is False
        assert session.status == ExperimentStatus.FAILED

    def test_start_session_already_active(self):
        """Should not start already active session."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.TENANT, tenant_ids=["t1"])
        session = controller.create_session("Test", target, [])

        controller.start_session(session)
        result = controller.start_session(session)

        assert result is False

    def test_stop_session(self):
        """Should stop session."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.TENANT, tenant_ids=["t1"])
        session = controller.create_session("Test", target, [])
        controller.start_session(session)

        result = controller.stop_session(session.id)

        assert result is not None
        assert result.status == ExperimentStatus.COMPLETED
        assert session.id not in controller.active_sessions
        assert session in controller.session_history

    def test_abort_session(self):
        """Should abort session with reason."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.TENANT, tenant_ids=["t1"])
        session = controller.create_session("Test", target, [])
        controller.start_session(session)

        result = controller.abort_session(session.id, "Test reason")

        assert result is not None
        assert result.status == ExperimentStatus.ABORTED

    @pytest.mark.asyncio
    async def test_apply_chaos_with_matching_session(self):
        """Should apply chaos when session matches."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.TENANT, tenant_ids=["t1"])
        exp = LatencyExperiment(
            name="Test",
            description="Test",
            fixed_delay_ms=5,
        )
        session = controller.create_session("Test", target, [exp])
        controller.start_session(session)

        context = {"environment": "staging", "tenant_id": "t1"}
        result, applied = await controller.apply_chaos(context)

        assert len(applied) == 1
        assert "latency" in applied[0]

    @pytest.mark.asyncio
    async def test_apply_chaos_no_match(self):
        """Should not apply chaos when no match."""
        controller = ChaosController()
        target = ChaosTarget(
            target_type=TargetType.AGENT,
            agent_names=["specific_agent"],
        )
        exp = LatencyExperiment(name="Test", description="Test")
        session = controller.create_session("Test", target, [exp])
        controller.start_session(session)

        context = {"agent_name": "other_agent", "tenant_id": "t1"}
        result, applied = await controller.apply_chaos(context)

        assert len(applied) == 0

    def test_get_active_sessions(self):
        """Should return active sessions."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.TENANT, tenant_ids=["t1"])

        session1 = controller.create_session("Test1", target, [])
        session2 = controller.create_session("Test2", target, [])
        controller.start_session(session1)
        controller.start_session(session2)

        active = controller.get_active_sessions()
        assert len(active) == 2

    def test_get_session_status_active(self):
        """Should get status of active session."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.TENANT, tenant_ids=["t1"])
        session = controller.create_session("Test", target, [])
        controller.start_session(session)

        status = controller.get_session_status(session.id)

        assert status is not None
        assert "session" in status
        assert "safety" in status

    def test_get_session_status_historical(self):
        """Should get status of completed session."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.TENANT, tenant_ids=["t1"])
        session = controller.create_session("Test", target, [])
        controller.start_session(session)
        controller.stop_session(session.id)

        status = controller.get_session_status(session.id)

        assert status is not None
        assert status["safety"] is None

    def test_get_session_status_not_found(self):
        """Should return None for unknown session."""
        controller = ChaosController()
        status = controller.get_session_status("unknown")
        assert status is None

    def test_determine_blast_radius_all(self):
        """Should determine blast radius for ALL target."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.ALL, percentage=100)
        radius = controller._determine_blast_radius(target)
        assert radius == BlastRadius.MULTI_TENANT

    def test_determine_blast_radius_low_percentage(self):
        """Should reduce blast radius for low percentage."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.ALL, percentage=0.5)
        radius = controller._determine_blast_radius(target)
        assert radius == BlastRadius.SINGLE_REQUEST

    def test_determine_blast_radius_trace(self):
        """Should return SINGLE_TRACE for trace target."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.TRACE)
        radius = controller._determine_blast_radius(target)
        assert radius == BlastRadius.SINGLE_TRACE

    def test_determine_blast_radius_agent(self):
        """Should return SINGLE_AGENT for agent target."""
        controller = ChaosController()
        target = ChaosTarget(target_type=TargetType.AGENT)
        radius = controller._determine_blast_radius(target)
        assert radius == BlastRadius.SINGLE_AGENT


class TestFactoryFunctions:
    """Tests for experiment factory functions."""

    def test_create_latency_experiment(self):
        """Should create latency experiment."""
        exp = create_latency_experiment(
            name="Test Latency",
            min_delay_ms=50,
            max_delay_ms=100,
            probability=0.5,
        )
        assert exp.min_delay_ms == 50
        assert exp.max_delay_ms == 100
        assert exp.probability == 0.5

    def test_create_error_experiment(self):
        """Should create error experiment."""
        exp = create_error_experiment(
            name="Test Error",
            error_codes=[500],
            probability=1.0,
        )
        assert exp.error_codes == [500]

    def test_create_error_experiment_defaults(self):
        """Should use default error codes."""
        exp = create_error_experiment(name="Test")
        assert 500 in exp.error_codes
        assert 502 in exp.error_codes

    def test_create_tool_failure_experiment(self):
        """Should create tool failure experiment."""
        exp = create_tool_failure_experiment(
            name="Test Tool Failure",
            tools=["api1", "api2"],
            failure_mode="error",
        )
        assert exp.target_tools == ["api1", "api2"]
        assert exp.failure_mode == "error"

    def test_create_uncooperative_agent_experiment(self):
        """Should create uncooperative agent experiment."""
        exp = create_uncooperative_agent_experiment(
            name="Test Uncooperative",
            agents=["agent1"],
            behaviors=["refuse"],
        )
        assert exp.target_agents == ["agent1"]
        assert exp.behaviors == ["refuse"]


# ============================================================================
# Experiment Result Tests
# ============================================================================

class TestExperimentResult:
    """Tests for ExperimentResult."""

    def test_creation(self):
        """Should create result with all fields."""
        result = ExperimentResult(
            experiment_id="exp123",
            experiment_type=ExperimentType.LATENCY,
            status=ExperimentStatus.COMPLETED,
            started_at=datetime.utcnow(),
            affected_requests=10,
        )
        assert result.experiment_id == "exp123"
        assert result.affected_requests == 10
        assert result.cascade_detected is False

    def test_defaults(self):
        """Should have correct defaults."""
        result = ExperimentResult(
            experiment_id="exp123",
            experiment_type=ExperimentType.ERROR,
            status=ExperimentStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        assert result.completed_at is None
        assert result.affected_requests == 0
        assert result.triggered_detections == 0


# ============================================================================
# Enum Tests
# ============================================================================

class TestEnums:
    """Tests for enum values."""

    def test_experiment_status_values(self):
        """Should have all expected status values."""
        assert ExperimentStatus.PENDING == "pending"
        assert ExperimentStatus.RUNNING == "running"
        assert ExperimentStatus.COMPLETED == "completed"
        assert ExperimentStatus.ABORTED == "aborted"
        assert ExperimentStatus.FAILED == "failed"

    def test_experiment_type_values(self):
        """Should have all expected type values."""
        assert ExperimentType.LATENCY == "latency"
        assert ExperimentType.ERROR == "error"
        assert ExperimentType.MALFORMED_OUTPUT == "malformed_output"
        assert ExperimentType.TOOL_UNAVAILABLE == "tool_unavailable"

    def test_target_type_values(self):
        """Should have all expected target type values."""
        assert TargetType.ALL == "all"
        assert TargetType.AGENT == "agent"
        assert TargetType.TOOL == "tool"
        assert TargetType.TENANT == "tenant"

    def test_blast_radius_values(self):
        """Should have all expected blast radius values."""
        assert BlastRadius.SINGLE_REQUEST == "single_request"
        assert BlastRadius.SINGLE_TENANT == "single_tenant"
        assert BlastRadius.MULTI_TENANT == "multi_tenant"
