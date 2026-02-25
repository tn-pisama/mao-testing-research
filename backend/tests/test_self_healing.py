"""Comprehensive tests for the self-healing system."""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.healing import (
    SelfHealingEngine,
    FailureAnalyzer,
    FixApplicator,
    FixValidator,
    HealingStatus,
    HealingResult,
    AppliedFix,
    ValidationResult,
)
from app.healing.models import FailureCategory, FailureSignature, HealingConfig, FixRiskLevel
from app.healing.auto_apply import AutoApplyService, AutoApplyConfig, ApplyResult


class TestFailureAnalyzer:
    """Tests for failure analysis."""
    
    @pytest.fixture
    def analyzer(self):
        return FailureAnalyzer()
    
    def test_analyze_infinite_loop_structural(self, analyzer):
        detection = {
            "detection_type": "infinite_loop",
            "confidence": 0.9,
            "method": "structural",
            "details": {
                "loop_length": 5,
                "affected_agents": ["agent_a", "agent_b"],
                "message": "node sequence [a,b] cycles detected",
            }
        }
        
        sig = analyzer.analyze(detection)
        
        assert sig.category == FailureCategory.INFINITE_LOOP
        assert sig.pattern == "multi_agent_ping_pong"
        assert sig.confidence == 0.9
        assert "agent_a" in sig.affected_components
        assert "Loop length: 5 iterations" in sig.indicators
    
    def test_analyze_infinite_loop_state_hash(self, analyzer):
        detection = {
            "detection_type": "infinite_loop",
            "confidence": 0.85,
            "method": "state_hash",
            "details": {
                "loop_length": 3,
                "message": "state_hash repeated 3 times",
            }
        }
        
        sig = analyzer.analyze(detection)
        
        assert sig.category == FailureCategory.INFINITE_LOOP
        assert sig.pattern == "state_repetition"
        assert "state" in sig.root_cause.lower()
    
    def test_analyze_state_corruption_null(self, analyzer):
        detection = {
            "detection_type": "state_corruption",
            "confidence": 0.88,
            "details": {
                "corrupted_fields": ["data", "result"],
                "null_injection": True,
            }
        }
        
        sig = analyzer.analyze(detection)
        
        assert sig.category == FailureCategory.STATE_CORRUPTION
        assert sig.pattern == "null_injection"
        assert "data" in sig.affected_components
    
    def test_analyze_state_corruption_data_loss(self, analyzer):
        detection = {
            "detection_type": "state_corruption",
            "confidence": 0.75,
            "details": {
                "data_loss": True,
                "message": "original data was destroyed",
            }
        }
        
        sig = analyzer.analyze(detection)
        
        assert sig.category == FailureCategory.STATE_CORRUPTION
        assert sig.pattern == "data_loss"
    
    def test_analyze_persona_drift_tone(self, analyzer):
        detection = {
            "detection_type": "persona_drift",
            "confidence": 0.82,
            "details": {
                "drift_score": 0.75,
                "expected_tone": "professional",
                "actual_tone": "casual",
                "agent_name": "writer",
            }
        }
        
        sig = analyzer.analyze(detection)
        
        assert sig.category == FailureCategory.PERSONA_DRIFT
        assert sig.pattern == "tone_mismatch"
        assert "professional" in sig.root_cause
        assert "writer" in sig.affected_components
    
    def test_analyze_persona_drift_slang(self, analyzer):
        detection = {
            "detection_type": "persona_drift",
            "confidence": 0.7,
            "details": {
                "slang_detected": True,
                "emojis_detected": True,
            }
        }
        
        sig = analyzer.analyze(detection)
        
        assert sig.category == FailureCategory.PERSONA_DRIFT
        assert "slang" in sig.pattern or any("slang" in i.lower() for i in sig.indicators)
    
    def test_analyze_timeout(self, analyzer):
        detection = {
            "detection_type": "timeout",
            "confidence": 0.95,
            "details": {
                "timeout_ms": 30000,
                "node_name": "slow_node",
            }
        }
        
        sig = analyzer.analyze(detection)
        
        assert sig.category == FailureCategory.TIMEOUT
        assert "30000" in str(sig.indicators)

    def test_analyze_hallucination(self, analyzer):
        detection = {
            "detection_type": "hallucination",
            "confidence": 0.8,
            "details": {
                "hallucinated_fields": ["field1", "field2"],
                "grounding_score": 0.3,
                "fabricated_facts": ["fact1"],
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.HALLUCINATION
        assert sig.confidence == 0.8
        assert len(sig.indicators) > 0

    def test_analyze_injection(self, analyzer):
        detection = {
            "detection_type": "injection",
            "confidence": 0.9,
            "details": {
                "attack_type": "prompt_override",
                "matched_patterns": ["ignore previous", "system:"],
                "severity": "high",
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.INJECTION
        assert sig.confidence == 0.9
        assert len(sig.indicators) > 0

    def test_analyze_overflow(self, analyzer):
        detection = {
            "detection_type": "context_overflow",
            "confidence": 0.85,
            "details": {
                "current_tokens": 125000,
                "context_window": 128000,
                "usage_percent": 97.6,
                "node_name": "summarizer",
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.CONTEXT_OVERFLOW
        assert sig.confidence == 0.85
        assert len(sig.indicators) > 0

    def test_analyze_derailment(self, analyzer):
        detection = {
            "detection_type": "task_derailment",
            "confidence": 0.75,
            "details": {
                "deviation_score": 0.8,
                "original_task": "Write a summary of the report",
                "current_focus": "Discussing unrelated topics",
                "affected_agents": ["writer"],
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.TASK_DERAILMENT
        assert sig.confidence == 0.75
        assert len(sig.indicators) > 0

    def test_analyze_context_neglect(self, analyzer):
        detection = {
            "detection_type": "context_neglect",
            "confidence": 0.7,
            "details": {
                "neglected_items": ["item1", "item2", "item3"],
                "context_utilization": 0.2,
                "affected_agents": ["researcher"],
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.CONTEXT_NEGLECT
        assert sig.confidence == 0.7
        assert len(sig.indicators) > 0

    def test_analyze_communication_breakdown(self, analyzer):
        detection = {
            "detection_type": "communication_breakdown",
            "confidence": 0.75,
            "details": {
                "failed_handoffs": ["handoff1", "handoff2"],
                "misunderstood_messages": 3,
                "affected_agents": ["agent_a", "agent_b"],
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.COMMUNICATION_BREAKDOWN
        assert sig.confidence == 0.75
        assert len(sig.indicators) > 0

    def test_analyze_specification_mismatch(self, analyzer):
        detection = {
            "detection_type": "specification_mismatch",
            "confidence": 0.8,
            "details": {
                "missing_fields": ["title", "summary"],
                "requirement_coverage": 0.4,
                "affected_nodes": ["output_formatter"],
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.SPECIFICATION_MISMATCH
        assert sig.confidence == 0.8
        assert len(sig.indicators) > 0

    def test_analyze_poor_decomposition(self, analyzer):
        detection = {
            "detection_type": "poor_decomposition",
            "confidence": 0.7,
            "details": {
                "subtask_count": 2,
                "coverage_score": 0.3,
                "problematic_subtasks": ["subtask_a"],
                "affected_agents": ["planner"],
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.POOR_DECOMPOSITION
        assert sig.confidence == 0.7
        assert len(sig.indicators) > 0

    def test_analyze_flawed_workflow(self, analyzer):
        detection = {
            "detection_type": "flawed_workflow",
            "confidence": 0.75,
            "details": {
                "failed_steps": ["step1", "step2"],
                "missing_error_handlers": 3,
                "problematic_nodes": ["node_x", "node_y"],
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.FLAWED_WORKFLOW
        assert sig.confidence == 0.75
        assert len(sig.indicators) > 0

    def test_analyze_information_withholding(self, analyzer):
        detection = {
            "detection_type": "information_withholding",
            "confidence": 0.7,
            "details": {
                "withheld_items": ["item1", "item2"],
                "completeness_score": 0.5,
                "affected_agents": ["reporter"],
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.INFORMATION_WITHHOLDING
        assert sig.confidence == 0.7
        assert len(sig.indicators) > 0

    def test_analyze_completion_misjudgment(self, analyzer):
        detection = {
            "detection_type": "completion_misjudgment",
            "confidence": 0.7,
            "details": {
                "completion_type": "premature",
                "quality_score": 0.4,
                "criteria_met": 2,
                "criteria_total": 5,
                "affected_agents": ["executor"],
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.COMPLETION_MISJUDGMENT
        assert sig.confidence == 0.7
        assert len(sig.indicators) > 0

    def test_analyze_cost_overrun(self, analyzer):
        detection = {
            "detection_type": "cost_overrun",
            "confidence": 0.9,
            "details": {
                "total_cost": 1.5,
                "budget_limit": 0.5,
                "token_count": 500000,
            }
        }
        sig = analyzer.analyze(detection)
        assert sig.category == FailureCategory.COST_OVERRUN
        assert sig.confidence == 0.9
        assert len(sig.indicators) > 0


class TestFixApplicator:
    """Tests for fix application."""
    
    @pytest.fixture
    def applicator(self):
        return FixApplicator()
    
    @pytest.fixture
    def base_workflow(self):
        return {
            "name": "test_workflow",
            "nodes": [
                {"id": "node1", "name": "Node 1", "type": "llm"},
                {"id": "node2", "name": "Node 2", "type": "code"},
            ],
            "connections": {"node1": [{"node": "node2"}]},
            "settings": {},
        }
    
    def test_apply_retry_limit(self, applicator, base_workflow):
        fix = {
            "id": "fix_123",
            "fix_type": "retry_limit",
            "metadata": {"max_retries": 5},
        }
        
        result = applicator.apply(fix, base_workflow, FailureCategory.INFINITE_LOOP)
        
        assert isinstance(result, AppliedFix)
        assert result.fix_type == "retry_limit"
        assert result.rollback_available
        assert result.modified_state["settings"]["max_iterations"] == 5
        assert result.modified_state["settings"]["loop_prevention"]["enabled"]
    
    def test_apply_circuit_breaker(self, applicator, base_workflow):
        fix = {
            "id": "fix_456",
            "fix_type": "circuit_breaker",
        }
        
        result = applicator.apply(fix, base_workflow, FailureCategory.INFINITE_LOOP)
        
        settings = result.modified_state["settings"]["circuit_breaker"]
        assert settings["enabled"]
        assert settings["failure_threshold"] == 5
        assert settings["recovery_timeout_seconds"] == 60
    
    def test_apply_state_validation(self, applicator, base_workflow):
        fix = {
            "id": "fix_789",
            "fix_type": "state_validation",
            "metadata": {"required_fields": ["data", "result"]},
        }
        
        result = applicator.apply(fix, base_workflow, FailureCategory.STATE_CORRUPTION)
        
        settings = result.modified_state["settings"]["state_validation"]
        assert settings["enabled"]
        assert settings["validate_on_node_entry"]
        assert settings["validate_on_node_exit"]
    
    def test_apply_prompt_reinforcement(self, applicator, base_workflow):
        fix = {
            "id": "fix_abc",
            "fix_type": "prompt_reinforcement",
            "metadata": {"reinforcement_level": "aggressive"},
        }
        
        result = applicator.apply(fix, base_workflow, FailureCategory.PERSONA_DRIFT)
        
        settings = result.modified_state["settings"]["persona_enforcement"]
        assert settings["enabled"]
        assert settings["reinforcement_level"] == "aggressive"
    
    def test_rollback(self, applicator, base_workflow):
        fix = {"id": "fix_123", "fix_type": "retry_limit"}
        applied = applicator.apply(fix, base_workflow, FailureCategory.INFINITE_LOOP)
        
        rolled_back = applicator.rollback(applied, applied.modified_state)
        
        assert rolled_back == base_workflow
        assert "loop_prevention" not in rolled_back.get("settings", {})
    
    def test_original_state_preserved(self, applicator, base_workflow):
        fix = {"id": "fix_123", "fix_type": "retry_limit"}
        original_copy = base_workflow.copy()
        
        applied = applicator.apply(fix, base_workflow, FailureCategory.INFINITE_LOOP)
        
        assert applied.original_state["settings"] == original_copy["settings"]
        assert applied.modified_state != applied.original_state


class TestFixValidator:
    """Tests for fix validation."""
    
    @pytest.fixture
    def validator(self):
        return FixValidator()
    
    def _create_applied_fix(self, modified_state: dict) -> AppliedFix:
        return AppliedFix(
            fix_id="test_fix",
            fix_type="test_type",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={"nodes": [], "connections": {}, "settings": {}},
            modified_state=modified_state,
        )
    
    @pytest.mark.asyncio
    async def test_validate_configuration_valid(self, validator):
        fix = self._create_applied_fix({
            "nodes": [{"id": "n1", "name": "Node"}],
            "connections": {},
            "settings": {"max_iterations": 5},
        })
        
        results = await validator.validate(fix, FailureCategory.INFINITE_LOOP)
        
        config_result = next(r for r in results if r.validation_type == "configuration_validation")
        assert config_result.success
    
    @pytest.mark.asyncio
    async def test_validate_configuration_invalid_nodes(self, validator):
        fix = self._create_applied_fix({
            "nodes": "not_a_list",
            "settings": {},
        })
        
        results = await validator.validate(fix, FailureCategory.INFINITE_LOOP)
        
        config_result = next(r for r in results if r.validation_type == "configuration_validation")
        assert not config_result.success
        assert "nodes must be a list" in config_result.error_message
    
    @pytest.mark.asyncio
    async def test_validate_loop_prevention_enabled(self, validator):
        fix = self._create_applied_fix({
            "nodes": [],
            "settings": {
                "max_iterations": 10,
                "loop_prevention": {"enabled": True},
            },
        })
        
        results = await validator.validate(fix, FailureCategory.INFINITE_LOOP)
        
        loop_result = next(r for r in results if r.validation_type == "loop_prevention_validation")
        assert loop_result.success
        assert loop_result.details["has_max_iterations"]
        assert loop_result.details["has_loop_prevention"]
    
    @pytest.mark.asyncio
    async def test_validate_loop_prevention_missing(self, validator):
        fix = self._create_applied_fix({
            "nodes": [],
            "settings": {},
        })
        
        results = await validator.validate(fix, FailureCategory.INFINITE_LOOP)
        
        loop_result = next(r for r in results if r.validation_type == "loop_prevention_validation")
        assert not loop_result.success
    
    @pytest.mark.asyncio
    async def test_validate_state_integrity(self, validator):
        fix = self._create_applied_fix({
            "nodes": [],
            "settings": {
                "state_validation": {"enabled": True},
            },
        })
        
        results = await validator.validate(fix, FailureCategory.STATE_CORRUPTION)
        
        state_result = next(r for r in results if r.validation_type == "state_integrity_validation")
        assert state_result.success
    
    @pytest.mark.asyncio
    async def test_validate_persona_consistency(self, validator):
        fix = self._create_applied_fix({
            "nodes": [
                {
                    "id": "llm1",
                    "type": "llm",
                    "parameters": {
                        "messages": {
                            "values": [
                                {"role": "system", "content": "IMPORTANT: Maintain professional tone."}
                            ]
                        }
                    }
                }
            ],
            "settings": {
                "persona_enforcement": {"enabled": True, "periodic_reminder": True},
            },
        })
        
        results = await validator.validate(fix, FailureCategory.PERSONA_DRIFT)
        
        persona_result = next(r for r in results if r.validation_type == "persona_consistency_validation")
        assert persona_result.success
    
    @pytest.mark.asyncio
    async def test_validate_regression_nodes_preserved(self, validator):
        fix = AppliedFix(
            fix_id="test",
            fix_type="test",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={
                "nodes": [{"name": "A"}, {"name": "B"}],
                "connections": {"A": []},
            },
            modified_state={
                "nodes": [{"name": "A"}, {"name": "B"}],
                "connections": {"A": []},
                "settings": {"new": True},
            },
        )
        
        results = await validator.validate(fix, FailureCategory.INFINITE_LOOP)
        
        regression_result = next(r for r in results if r.validation_type == "regression_validation")
        assert regression_result.success
        assert regression_result.details["nodes_preserved"]
    
    @pytest.mark.asyncio
    async def test_validate_regression_nodes_removed(self, validator):
        fix = AppliedFix(
            fix_id="test",
            fix_type="test",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={
                "nodes": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
                "connections": {},
            },
            modified_state={
                "nodes": [{"name": "A"}],
                "connections": {},
            },
        )
        
        results = await validator.validate(fix, FailureCategory.INFINITE_LOOP)
        
        regression_result = next(r for r in results if r.validation_type == "regression_validation")
        assert not regression_result.success

    @pytest.mark.asyncio
    async def test_hallucination_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_1",
            fix_type="fact_checking",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "fact_checking": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.HALLUCINATION)
        hallucination_results = [r for r in results if "hallucination" in r.validation_type]
        assert len(hallucination_results) > 0
        assert hallucination_results[0].success is True

    @pytest.mark.asyncio
    async def test_hallucination_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_1",
            fix_type="fact_checking",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.HALLUCINATION)
        hallucination_results = [r for r in results if "hallucination" in r.validation_type]
        assert len(hallucination_results) > 0
        assert hallucination_results[0].success is False

    @pytest.mark.asyncio
    async def test_injection_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_2",
            fix_type="input_filtering",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "input_filtering": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.INJECTION)
        injection_results = [r for r in results if "injection" in r.validation_type]
        assert len(injection_results) > 0
        assert injection_results[0].success is True

    @pytest.mark.asyncio
    async def test_injection_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_2",
            fix_type="input_filtering",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.INJECTION)
        injection_results = [r for r in results if "injection" in r.validation_type]
        assert len(injection_results) > 0
        assert injection_results[0].success is False

    @pytest.mark.asyncio
    async def test_context_overflow_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_3",
            fix_type="context_pruning",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "context_pruning": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.CONTEXT_OVERFLOW)
        overflow_results = [r for r in results if "context_overflow" in r.validation_type]
        assert len(overflow_results) > 0
        assert overflow_results[0].success is True

    @pytest.mark.asyncio
    async def test_context_overflow_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_3",
            fix_type="context_pruning",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.CONTEXT_OVERFLOW)
        overflow_results = [r for r in results if "context_overflow" in r.validation_type]
        assert len(overflow_results) > 0
        assert overflow_results[0].success is False

    @pytest.mark.asyncio
    async def test_derailment_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_4",
            fix_type="task_anchoring",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "task_anchoring": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.TASK_DERAILMENT)
        derailment_results = [r for r in results if "derailment" in r.validation_type]
        assert len(derailment_results) > 0
        assert derailment_results[0].success is True

    @pytest.mark.asyncio
    async def test_derailment_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_4",
            fix_type="task_anchoring",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.TASK_DERAILMENT)
        derailment_results = [r for r in results if "derailment" in r.validation_type]
        assert len(derailment_results) > 0
        assert derailment_results[0].success is False

    @pytest.mark.asyncio
    async def test_context_neglect_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_5",
            fix_type="context_injection",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "context_injection": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.CONTEXT_NEGLECT)
        neglect_results = [r for r in results if "context_neglect" in r.validation_type]
        assert len(neglect_results) > 0
        assert neglect_results[0].success is True

    @pytest.mark.asyncio
    async def test_context_neglect_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_5",
            fix_type="context_injection",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.CONTEXT_NEGLECT)
        neglect_results = [r for r in results if "context_neglect" in r.validation_type]
        assert len(neglect_results) > 0
        assert neglect_results[0].success is False

    @pytest.mark.asyncio
    async def test_communication_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_6",
            fix_type="message_schema",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "message_schema": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.COMMUNICATION_BREAKDOWN)
        comm_results = [r for r in results if "communication" in r.validation_type]
        assert len(comm_results) > 0
        assert comm_results[0].success is True

    @pytest.mark.asyncio
    async def test_communication_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_6",
            fix_type="message_schema",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.COMMUNICATION_BREAKDOWN)
        comm_results = [r for r in results if "communication" in r.validation_type]
        assert len(comm_results) > 0
        assert comm_results[0].success is False

    @pytest.mark.asyncio
    async def test_specification_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_7",
            fix_type="spec_validation",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "spec_validation": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.SPECIFICATION_MISMATCH)
        spec_results = [r for r in results if "specification" in r.validation_type]
        assert len(spec_results) > 0
        assert spec_results[0].success is True

    @pytest.mark.asyncio
    async def test_specification_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_7",
            fix_type="spec_validation",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.SPECIFICATION_MISMATCH)
        spec_results = [r for r in results if "specification" in r.validation_type]
        assert len(spec_results) > 0
        assert spec_results[0].success is False

    @pytest.mark.asyncio
    async def test_decomposition_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_8",
            fix_type="task_decomposition",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "task_decomposition": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.POOR_DECOMPOSITION)
        decomp_results = [r for r in results if "decomposition" in r.validation_type]
        assert len(decomp_results) > 0
        assert decomp_results[0].success is True

    @pytest.mark.asyncio
    async def test_decomposition_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_8",
            fix_type="task_decomposition",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.POOR_DECOMPOSITION)
        decomp_results = [r for r in results if "decomposition" in r.validation_type]
        assert len(decomp_results) > 0
        assert decomp_results[0].success is False

    @pytest.mark.asyncio
    async def test_workflow_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_9",
            fix_type="workflow_guards",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "workflow_guards": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.FLAWED_WORKFLOW)
        workflow_results = [r for r in results if "workflow" in r.validation_type]
        assert len(workflow_results) > 0
        assert workflow_results[0].success is True

    @pytest.mark.asyncio
    async def test_workflow_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_9",
            fix_type="workflow_guards",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.FLAWED_WORKFLOW)
        workflow_results = [r for r in results if "workflow" in r.validation_type]
        assert len(workflow_results) > 0
        assert workflow_results[0].success is False

    @pytest.mark.asyncio
    async def test_withholding_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_10",
            fix_type="transparency",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "transparency": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.INFORMATION_WITHHOLDING)
        withholding_results = [r for r in results if "withholding" in r.validation_type]
        assert len(withholding_results) > 0
        assert withholding_results[0].success is True

    @pytest.mark.asyncio
    async def test_withholding_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_10",
            fix_type="transparency",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.INFORMATION_WITHHOLDING)
        withholding_results = [r for r in results if "withholding" in r.validation_type]
        assert len(withholding_results) > 0
        assert withholding_results[0].success is False

    @pytest.mark.asyncio
    async def test_completion_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_11",
            fix_type="completion_gate",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "completion_gate": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.COMPLETION_MISJUDGMENT)
        completion_results = [r for r in results if "completion" in r.validation_type]
        assert len(completion_results) > 0
        assert completion_results[0].success is True

    @pytest.mark.asyncio
    async def test_completion_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_11",
            fix_type="completion_gate",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.COMPLETION_MISJUDGMENT)
        completion_results = [r for r in results if "completion" in r.validation_type]
        assert len(completion_results) > 0
        assert completion_results[0].success is False

    @pytest.mark.asyncio
    async def test_cost_validator_passes(self, validator):
        fix = AppliedFix(
            fix_id="fix_12",
            fix_type="budget_limit",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={
                "settings": {
                    "budget_limit": {"enabled": True},
                }
            },
        )
        results = await validator.validate(fix, FailureCategory.COST_OVERRUN)
        cost_results = [r for r in results if "cost" in r.validation_type]
        assert len(cost_results) > 0
        assert cost_results[0].success is True

    @pytest.mark.asyncio
    async def test_cost_validator_fails_without_settings(self, validator):
        fix = AppliedFix(
            fix_id="fix_12",
            fix_type="budget_limit",
            applied_at=datetime.now(timezone.utc),
            target_component="workflow",
            original_state={},
            modified_state={"settings": {}},
        )
        results = await validator.validate(fix, FailureCategory.COST_OVERRUN)
        cost_results = [r for r in results if "cost" in r.validation_type]
        assert len(cost_results) > 0
        assert cost_results[0].success is False


class TestSelfHealingEngine:
    """Tests for the complete self-healing engine."""
    
    @pytest.fixture
    def engine(self):
        return SelfHealingEngine(auto_apply=True, max_fix_attempts=3)
    
    @pytest.fixture
    def engine_manual(self):
        return SelfHealingEngine(auto_apply=False)
    
    @pytest.fixture
    def sample_workflow(self):
        return {
            "name": "test",
            "framework": "langgraph",
            "nodes": [{"id": "n1", "name": "Node", "type": "llm"}],
            "connections": {},
            "settings": {},
        }
    
    @pytest.mark.asyncio
    async def test_heal_infinite_loop_success(self, engine, sample_workflow):
        detection = {
            "id": "det_123",
            "detection_type": "infinite_loop",
            "confidence": 0.9,
            "details": {"loop_length": 5, "affected_agents": ["n1"]},
        }
        
        result = await engine.heal(detection, sample_workflow)
        
        assert result.status == HealingStatus.SUCCESS
        assert result.failure_signature.category == FailureCategory.INFINITE_LOOP
        assert len(result.applied_fixes) >= 1
        assert result.all_validations_passed
    
    @pytest.mark.asyncio
    async def test_heal_state_corruption_success(self, engine, sample_workflow):
        detection = {
            "id": "det_456",
            "detection_type": "state_corruption",
            "confidence": 0.85,
            "details": {"null_injection": True, "corrupted_fields": ["data"]},
        }
        
        result = await engine.heal(detection, sample_workflow)
        
        assert result.status == HealingStatus.SUCCESS
        assert result.failure_signature.category == FailureCategory.STATE_CORRUPTION
    
    @pytest.mark.asyncio
    async def test_heal_persona_drift_success(self, engine, sample_workflow):
        detection = {
            "id": "det_789",
            "detection_type": "persona_drift",
            "confidence": 0.8,
            "details": {"drift_score": 0.7, "agent_name": "writer"},
        }
        
        result = await engine.heal(detection, sample_workflow)
        
        assert result.status == HealingStatus.SUCCESS
        assert result.failure_signature.category == FailureCategory.PERSONA_DRIFT
    
    @pytest.mark.asyncio
    async def test_heal_manual_mode_pending(self, engine_manual, sample_workflow):
        detection = {
            "id": "det_manual",
            "detection_type": "infinite_loop",
            "confidence": 0.9,
            "details": {"loop_length": 3},
        }
        
        result = await engine_manual.heal(detection, sample_workflow)
        
        assert result.status == HealingStatus.PENDING
        assert result.metadata.get("requires_approval")
        assert len(result.applied_fixes) == 0
    
    @pytest.mark.asyncio
    async def test_heal_history_tracking(self, engine, sample_workflow):
        detection1 = {"id": "d1", "detection_type": "infinite_loop", "details": {}}
        detection2 = {"id": "d2", "detection_type": "state_corruption", "details": {}}
        
        await engine.heal(detection1, sample_workflow)
        await engine.heal(detection2, sample_workflow)
        
        history = engine.get_healing_history()
        assert len(history) == 2
    
    @pytest.mark.asyncio
    async def test_heal_stats(self, engine, sample_workflow):
        for i in range(5):
            detection = {"id": f"d{i}", "detection_type": "infinite_loop", "details": {}}
            await engine.heal(detection, sample_workflow)
        
        stats = engine.get_healing_stats()
        
        assert stats["total"] == 5
        assert stats["success_rate"] > 0
        assert "by_status" in stats
        assert "by_failure_category" in stats
    
    @pytest.mark.asyncio
    async def test_heal_rollback(self, engine, sample_workflow):
        detection = {
            "id": "det_rollback",
            "detection_type": "infinite_loop",
            "details": {"loop_length": 3},
        }
        
        result = await engine.heal(detection, sample_workflow)
        
        rolled_back = engine.rollback(result.id)
        
        assert rolled_back == sample_workflow
    
    @pytest.mark.asyncio
    async def test_heal_with_trace_context(self, engine, sample_workflow):
        detection = {
            "id": "det_trace",
            "detection_type": "infinite_loop",
            "details": {"loop_length": 4},
        }
        trace = {
            "spans": [
                {"name": "n1", "duration_ms": 100},
                {"name": "n1", "duration_ms": 100},
            ]
        }
        
        result = await engine.heal(detection, sample_workflow, trace=trace)
        
        assert result.status == HealingStatus.SUCCESS


class TestHealingIntegration:
    """Integration tests for complete healing pipeline."""
    
    @pytest.mark.asyncio
    async def test_full_healing_pipeline_loop(self):
        engine = SelfHealingEngine(auto_apply=True)
        
        workflow = {
            "name": "loop_test",
            "framework": "langgraph",
            "nodes": [
                {"id": "researcher", "name": "Researcher", "type": "llm"},
                {"id": "analyst", "name": "Analyst", "type": "llm"},
            ],
            "connections": {
                "researcher": [{"node": "analyst"}],
                "analyst": [{"node": "researcher"}],
            },
            "settings": {},
        }
        
        detection = {
            "id": "integration_loop",
            "detection_type": "infinite_loop",
            "confidence": 0.95,
            "method": "structural",
            "details": {
                "loop_length": 10,
                "affected_agents": ["researcher", "analyst"],
                "message": "Circular dependency detected",
            },
        }
        
        result = await engine.heal(detection, workflow)
        
        assert result.is_successful
        assert result.failure_signature.pattern == "multi_agent_ping_pong"
        assert len(result.applied_fixes) >= 1
        
        modified = result.applied_fixes[-1].modified_state
        assert "loop_prevention" in modified["settings"]
        assert modified["settings"]["loop_prevention"]["enabled"]
    
    @pytest.mark.asyncio
    async def test_full_healing_pipeline_corruption(self):
        engine = SelfHealingEngine(auto_apply=True)
        
        workflow = {
            "name": "corruption_test",
            "framework": "crewai",
            "nodes": [
                {"id": "processor", "name": "Processor", "type": "code"},
            ],
            "connections": {},
            "settings": {},
        }
        
        detection = {
            "id": "integration_corruption",
            "detection_type": "state_corruption",
            "confidence": 0.88,
            "details": {
                "corrupted_fields": ["output", "state"],
                "null_injection": True,
                "data_loss": True,
            },
        }
        
        result = await engine.heal(detection, workflow)
        
        assert result.is_successful
        assert result.failure_signature.category == FailureCategory.STATE_CORRUPTION
        
        modified = result.applied_fixes[-1].modified_state
        assert "state_validation" in modified["settings"]
    
    @pytest.mark.asyncio
    async def test_full_healing_pipeline_drift(self):
        engine = SelfHealingEngine(auto_apply=True)
        
        workflow = {
            "name": "drift_test",
            "framework": "langgraph",
            "nodes": [
                {
                    "id": "writer",
                    "name": "Writer",
                    "type": "llm",
                    "parameters": {
                        "messages": {
                            "values": [{"role": "system", "content": "Be professional"}]
                        }
                    },
                },
            ],
            "connections": {},
            "settings": {},
        }
        
        detection = {
            "id": "integration_drift",
            "detection_type": "persona_drift",
            "confidence": 0.85,
            "details": {
                "drift_score": 0.8,
                "expected_tone": "professional",
                "actual_tone": "casual",
                "emojis_detected": True,
                "agent_name": "writer",
            },
        }
        
        result = await engine.heal(detection, workflow)
        
        assert result.is_successful
        assert result.failure_signature.category == FailureCategory.PERSONA_DRIFT
        
        modified = result.applied_fixes[-1].modified_state
        assert "persona_enforcement" in modified["settings"]
        assert modified["settings"]["persona_enforcement"]["enabled"]


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    @pytest.fixture
    def engine(self):
        return SelfHealingEngine(auto_apply=True)
    
    @pytest.mark.asyncio
    async def test_empty_detection(self, engine):
        result = await engine.heal({}, {})
        
        assert result.failure_signature is not None
    
    @pytest.mark.asyncio
    async def test_unknown_detection_type(self, engine):
        detection = {
            "id": "unknown",
            "detection_type": "unknown_failure_type",
            "details": {"message": "Something went wrong"},
        }
        
        result = await engine.heal(detection, {})
        
        assert result.failure_signature.category == FailureCategory.API_FAILURE
    
    @pytest.mark.asyncio
    async def test_rollback_not_found(self, engine):
        with pytest.raises(ValueError, match="not found"):
            engine.rollback("nonexistent_id")
    
    @pytest.mark.asyncio
    async def test_approve_wrong_status(self, engine):
        detection = {"id": "d1", "detection_type": "infinite_loop", "details": {}}
        result = await engine.heal(detection, {})
        
        with pytest.raises(ValueError, match="not pending"):
            engine.approve_and_apply(result.id, ["fix_1"])


class TestAdversarialHealing:
    """Adversarial tests for healing safety and edge cases."""

    # 1. Healing loop detection: 6 heals in window → 6th blocked
    def test_healing_loop_detection(self):
        config = AutoApplyConfig(
            healing_loop_threshold=5,
            healing_loop_window_minutes=60,
        )
        service = AutoApplyService(config)
        workflow_id = "wf_loop_test"

        # Record 5 healing timestamps (under threshold)
        for _ in range(5):
            service._healing_timestamps[workflow_id].append(
                datetime.now(timezone.utc)
            )

        # 5th attempt: at threshold → loop detected
        assert service.detect_healing_loop(workflow_id) is True
        # Rate limit should block
        assert service.check_rate_limit(workflow_id) is False

    # 2. Cascading rollback: fix applied but fails → rollback + cooldown
    @pytest.mark.asyncio
    async def test_cascading_rollback(self):
        config = AutoApplyConfig(
            rollback_on_failure=True,
            cooldown_after_rollback_seconds=300,
        )
        service = AutoApplyService(config)

        mock_client = AsyncMock()
        mock_client.get_workflow.return_value = {"nodes": [], "settings": {}}
        # Apply raises to simulate failure after backup
        mock_client.update_workflow.side_effect = RuntimeError("n8n API error")
        mock_client.clear_execution_data = AsyncMock()

        mock_backup = AsyncMock()
        mock_backup.backup_workflow.return_value = "abc123sha"
        mock_backup.rollback_to = AsyncMock()

        fix = {"id": "fix_1", "fix_type": "loop_breaker", "parameters": {"max_iterations": 5}}
        result = await service.apply_fix(
            fix=fix,
            workflow_id="wf_cascade",
            healing_id="heal_1",
            n8n_client=mock_client,
            git_backup=mock_backup,
        )

        assert result.success is False
        assert result.rolled_back is True
        assert result.backup_commit_sha == "abc123sha"
        mock_backup.rollback_to.assert_called_once()
        # Cooldown should be set
        assert "wf_cascade" in service._cooldowns
        assert service.check_rate_limit("wf_cascade") is False

    # 3. Concurrent healing race: lock prevents double-heal
    @pytest.mark.asyncio
    async def test_concurrent_healing_race(self):
        engine = SelfHealingEngine(auto_apply=False)
        mock_client = AsyncMock()
        mock_client.get_workflow.return_value = {"nodes": [], "settings": {}}

        detection = {
            "id": "det_race",
            "detection_type": "infinite_loop",
            "confidence": 0.9,
            "details": {"loop_length": 5},
        }

        # Manually acquire the lock before calling heal_n8n_workflow
        lock = engine._get_workflow_lock("wf_race")
        await lock.acquire()

        # Second call should see the lock is held and return FAILED
        result = await engine.heal_n8n_workflow(
            detection, "wf_race", mock_client
        )

        assert result.status == HealingStatus.FAILED
        assert "Concurrent healing blocked" in result.error
        lock.release()

    # 4. Fix creates new failure: workflow_runner returns new detection post-fix
    @pytest.mark.asyncio
    async def test_fix_creates_new_failure(self):
        engine = SelfHealingEngine(auto_apply=True, max_fix_attempts=1)

        detection = {
            "id": "det_new_fail",
            "detection_type": "infinite_loop",
            "confidence": 0.9,
            "details": {"loop_length": 5, "affected_agents": ["agent_a"]},
        }
        workflow = {
            "name": "test",
            "nodes": [{"id": "n1", "name": "Node", "type": "llm"}],
            "connections": {},
            "settings": {},
        }

        # workflow_runner that returns a new detection (simulates fix causing new issue)
        async def bad_runner(config, test_input):
            return {
                "success": False,
                "new_detection": {"detection_type": "state_corruption"},
            }

        result = await engine.heal(
            detection, workflow, workflow_runner=bad_runner, test_input={}
        )

        # Should still complete (validation might fail but engine shouldn't crash)
        assert result.status in (
            HealingStatus.SUCCESS,
            HealingStatus.PARTIAL_SUCCESS,
            HealingStatus.FAILED,
        )
        assert result.completed_at is not None

    # 5. Dangerous fix blocked by risk policy
    def test_dangerous_fix_blocked(self):
        config = AutoApplyConfig(auto_apply_max_risk=FixRiskLevel.SAFE)
        service = AutoApplyService(config)

        error = service.check_fix_risk("prompt_modification")
        assert error is not None
        assert "dangerous" in error
        assert "safe" in error

        # SAFE fix should pass
        assert service.check_fix_risk("retry_limit") is None

    # 6. Max consecutive failures halt
    def test_max_consecutive_failures_halt(self):
        config = AutoApplyConfig(max_consecutive_failures=2)
        service = AutoApplyService(config)
        workflow_id = "wf_fail"

        # Simulate 2 consecutive failures
        service._failure_counts[workflow_id] = 2

        assert service.check_rate_limit(workflow_id) is False

    # 7. HealingConfig propagates to AutoApplyConfig
    def test_healing_config_propagation(self):
        hc = HealingConfig(
            max_fixes_per_hour=2,
            cooldown_after_rollback_seconds=600,
            max_consecutive_failures=1,
            healing_loop_threshold=3,
            healing_loop_window_minutes=30,
        )
        engine = SelfHealingEngine(auto_apply=True, healing_config=hc)

        assert engine.auto_apply_service is not None
        aac = engine.auto_apply_service.config
        assert aac.max_fixes_per_hour == 2
        assert aac.cooldown_after_rollback_seconds == 600
        assert aac.max_consecutive_failures == 1
        assert aac.healing_loop_threshold == 3
        assert aac.healing_loop_window_minutes == 30

    # 8. Rollback without backup
    @pytest.mark.asyncio
    async def test_rollback_without_backup(self):
        service = AutoApplyService()
        apply_result = ApplyResult(
            success=True,
            healing_id="heal_no_backup",
            workflow_id="wf_no_backup",
            backup_commit_sha=None,  # No backup
        )

        mock_backup = AsyncMock()
        mock_client = AsyncMock()
        success = await service.rollback(apply_result, mock_backup, mock_client)

        assert success is False
        mock_backup.rollback_to.assert_not_called()

    # 9. Empty fix suggestions
    @pytest.mark.asyncio
    async def test_empty_fix_suggestions(self):
        engine = SelfHealingEngine(auto_apply=True)

        # Use a detection type that won't generate fixes
        detection = {
            "id": "det_empty",
            "detection_type": "rate_limit",
            "confidence": 0.5,
            "details": {},
        }
        workflow = {"nodes": [], "connections": {}, "settings": {}}

        result = await engine.heal(detection, workflow)

        assert result.status == HealingStatus.FAILED
        assert "No fix suggestions" in (result.error or "")

    # 10. Heal with invalid/empty workflow config doesn't crash
    @pytest.mark.asyncio
    async def test_heal_with_invalid_workflow(self):
        engine = SelfHealingEngine(auto_apply=True)

        detection = {
            "id": "det_invalid",
            "detection_type": "infinite_loop",
            "confidence": 0.9,
            "details": {"loop_length": 5},
        }

        # Empty workflow
        result = await engine.heal(detection, {})
        assert result.completed_at is not None
        assert result.status in (
            HealingStatus.SUCCESS,
            HealingStatus.PARTIAL_SUCCESS,
            HealingStatus.FAILED,
        )

        # None-valued fields
        result2 = await engine.heal(detection, {"nodes": None, "settings": None})
        assert result2.completed_at is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
