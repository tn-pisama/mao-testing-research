"""Tests for fix suggestion generators."""

import pytest
from app.fixes import (
    FixGenerator,
    LoopFixGenerator,
    CorruptionFixGenerator,
    PersonaFixGenerator,
    DeadlockFixGenerator,
    HallucinationFixGenerator,
    InjectionFixGenerator,
    OverflowFixGenerator,
    DerailmentFixGenerator,
    ContextNeglectFixGenerator,
    CommunicationFixGenerator,
    SpecificationFixGenerator,
    DecompositionFixGenerator,
    WorkflowFixGenerator,
    WithholdingFixGenerator,
    CompletionFixGenerator,
    CostFixGenerator,
    FixSuggestion,
    FixType,
    FixConfidence,
)


class TestLoopFixGenerator:
    def setup_method(self):
        self.generator = LoopFixGenerator()
    
    def test_can_handle_infinite_loop(self):
        assert self.generator.can_handle("infinite_loop") is True
        assert self.generator.can_handle("state_corruption") is False
    
    def test_generates_fixes_for_loop(self):
        detection = {
            "id": "det_123",
            "detection_type": "infinite_loop",
            "method": "hash",
            "details": {"loop_length": 5, "affected_agents": ["agent1", "agent2"]},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) >= 3
        fix_types = [f.fix_type for f in fixes]
        assert FixType.RETRY_LIMIT in fix_types
        assert FixType.EXPONENTIAL_BACKOFF in fix_types
        assert FixType.CIRCUIT_BREAKER in fix_types
    
    def test_generates_conversation_terminator_for_structural(self):
        detection = {
            "id": "det_123",
            "detection_type": "infinite_loop",
            "method": "structural",
            "details": {"loop_length": 3, "affected_agents": ["agent1", "agent2"]},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 4
    
    def test_framework_specific_code(self):
        detection = {
            "id": "det_123",
            "detection_type": "infinite_loop",
            "method": "hash",
            "details": {"loop_length": 3},
        }
        fixes = self.generator.generate_fixes(detection, {"framework": "crewai"})
        code = fixes[0].code_changes[0].suggested_code
        assert "crewai" in code.lower() or "CrewAI" in code or "RetryLimited" in code


class TestCorruptionFixGenerator:
    def setup_method(self):
        self.generator = CorruptionFixGenerator()
    
    def test_can_handle_state_corruption(self):
        assert self.generator.can_handle("state_corruption") is True
        assert self.generator.can_handle("infinite_loop") is False
    
    def test_generates_pydantic_validation(self):
        detection = {
            "id": "det_456",
            "detection_type": "state_corruption",
            "details": {"issue_type": "type_mismatch", "field": "count"},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.STATE_VALIDATION in fix_types
    
    def test_generates_schema_enforcement_for_hallucinated_key(self):
        detection = {
            "id": "det_456",
            "detection_type": "state_corruption",
            "details": {"issue_type": "hallucinated_key", "field": "fake_field"},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.SCHEMA_ENFORCEMENT in fix_types
    
    def test_generates_cross_field_validator(self):
        detection = {
            "id": "det_456",
            "detection_type": "state_corruption",
            "details": {"issue_type": "cross_field_inconsistency"},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.STATE_VALIDATION in fix_types


class TestPersonaFixGenerator:
    def setup_method(self):
        self.generator = PersonaFixGenerator()
    
    def test_can_handle_persona_drift(self):
        assert self.generator.can_handle("persona_drift") is True
        assert self.generator.can_handle("deadlock") is False
    
    def test_generates_prompt_reinforcement(self):
        detection = {
            "id": "det_789",
            "detection_type": "persona_drift",
            "details": {"agent_id": "researcher", "drift_magnitude": 0.3},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.PROMPT_REINFORCEMENT in fix_types
    
    def test_generates_role_boundary(self):
        detection = {
            "id": "det_789",
            "detection_type": "persona_drift",
            "details": {"agent_id": "writer", "drift_magnitude": 0.4},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.ROLE_BOUNDARY in fix_types
    
    def test_generates_split_softmax_for_high_drift(self):
        detection = {
            "id": "det_789",
            "detection_type": "persona_drift",
            "details": {"agent_id": "analyst", "drift_magnitude": 0.6},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 4


class TestDeadlockFixGenerator:
    def setup_method(self):
        self.generator = DeadlockFixGenerator()
    
    def test_can_handle_deadlock(self):
        assert self.generator.can_handle("coordination_deadlock") is True
        assert self.generator.can_handle("deadlock") is True
        assert self.generator.can_handle("loop") is False
    
    def test_generates_timeout_fix(self):
        detection = {
            "id": "det_abc",
            "detection_type": "coordination_deadlock",
            "details": {"waiting_agents": ["agent1", "agent2"]},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.TIMEOUT_ADDITION in fix_types
    
    def test_generates_priority_fix(self):
        detection = {
            "id": "det_abc",
            "detection_type": "coordination_deadlock",
            "details": {"waiting_agents": ["coordinator", "researcher"]},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.PRIORITY_ADJUSTMENT in fix_types
    
    def test_generates_async_handoff(self):
        detection = {
            "id": "det_abc",
            "detection_type": "deadlock",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.ASYNC_HANDOFF in fix_types


class TestFixGenerator:
    def setup_method(self):
        self.generator = FixGenerator()
        self.generator.register(LoopFixGenerator())
        self.generator.register(CorruptionFixGenerator())
        self.generator.register(PersonaFixGenerator())
        self.generator.register(DeadlockFixGenerator())
    
    def test_routes_to_correct_generator(self):
        loop_detection = {
            "id": "det_1",
            "detection_type": "infinite_loop",
            "details": {"loop_length": 3},
        }
        fixes = self.generator.generate_fixes(loop_detection, {})
        assert len(fixes) >= 3
        assert all(f.detection_type == "infinite_loop" for f in fixes)
    
    def test_returns_empty_for_unknown_type(self):
        unknown_detection = {
            "id": "det_x",
            "detection_type": "unknown_type",
            "details": {},
        }
        fixes = self.generator.generate_fixes(unknown_detection, {})
        assert fixes == []
    
    def test_batch_generation(self):
        detections = [
            {"id": "det_1", "detection_type": "infinite_loop", "details": {}},
            {"id": "det_2", "detection_type": "state_corruption", "details": {}},
            {"id": "det_3", "detection_type": "persona_drift", "details": {}},
        ]
        results = self.generator.generate_fixes_batch(detections, {})
        assert "det_1" in results
        assert "det_2" in results
        assert "det_3" in results
        assert len(results["det_1"]) > 0
        assert len(results["det_2"]) > 0
        assert len(results["det_3"]) > 0
    
    def test_fixes_sorted_by_confidence(self):
        detection = {
            "id": "det_1",
            "detection_type": "state_corruption",
            "details": {"issue_type": "hallucinated_key"},
        }
        fixes = self.generator.generate_fixes(detection, {})
        confidences = [f.confidence for f in fixes]
        high_indices = [i for i, c in enumerate(confidences) if c == FixConfidence.HIGH]
        medium_indices = [i for i, c in enumerate(confidences) if c == FixConfidence.MEDIUM]
        low_indices = [i for i, c in enumerate(confidences) if c == FixConfidence.LOW]
        if high_indices and medium_indices:
            assert max(high_indices) < min(medium_indices)
        if medium_indices and low_indices:
            assert max(medium_indices) < min(low_indices)


class TestFixSuggestionOutput:
    def test_to_dict(self):
        generator = LoopFixGenerator()
        detection = {
            "id": "det_123",
            "detection_type": "infinite_loop",
            "details": {"loop_length": 3},
        }
        fixes = generator.generate_fixes(detection, {})
        fix_dict = fixes[0].to_dict()
        assert "id" in fix_dict
        assert "detection_id" in fix_dict
        assert "fix_type" in fix_dict
        assert "confidence" in fix_dict
        assert "code_changes" in fix_dict
        assert "title" in fix_dict
        assert "description" in fix_dict
    
    def test_to_markdown(self):
        generator = CorruptionFixGenerator()
        detection = {
            "id": "det_456",
            "detection_type": "state_corruption",
            "details": {},
        }
        fixes = generator.generate_fixes(detection, {})
        md = fixes[0].to_markdown()
        assert "##" in md
        assert "Type:" in md
        assert "Confidence:" in md
        assert "```python" in md
    
    def test_code_change_diff(self):
        generator = LoopFixGenerator()
        detection = {
            "id": "det_123",
            "detection_type": "infinite_loop",
            "details": {"loop_length": 3},
        }
        fixes = generator.generate_fixes(detection, {})
        code_change = fixes[0].code_changes[0]
        diff = code_change.to_diff()
        assert "+++" in diff
        assert "@@ " in diff


class TestHallucinationFixGenerator:
    def setup_method(self):
        self.generator = HallucinationFixGenerator()

    def test_can_handle_hallucination(self):
        assert self.generator.can_handle("hallucination") is True
        assert self.generator.can_handle("injection") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "hallucination",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "hallucination",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.FACT_CHECKING in fix_types
        assert FixType.SOURCE_GROUNDING in fix_types
        assert FixType.CONFIDENCE_CALIBRATION in fix_types


class TestInjectionFixGenerator:
    def setup_method(self):
        self.generator = InjectionFixGenerator()

    def test_can_handle_injection(self):
        assert self.generator.can_handle("injection") is True
        assert self.generator.can_handle("prompt_injection") is True
        assert self.generator.can_handle("hallucination") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "injection",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "injection",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.INPUT_FILTERING in fix_types
        assert FixType.SAFETY_BOUNDARY in fix_types
        assert FixType.PERMISSION_GATE in fix_types


class TestOverflowFixGenerator:
    def setup_method(self):
        self.generator = OverflowFixGenerator()

    def test_can_handle_overflow(self):
        assert self.generator.can_handle("overflow") is True
        assert self.generator.can_handle("context_overflow") is True
        assert self.generator.can_handle("hallucination") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "overflow",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "overflow",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.CONTEXT_PRUNING in fix_types
        assert FixType.SUMMARIZATION in fix_types
        assert FixType.WINDOW_MANAGEMENT in fix_types


class TestDerailmentFixGenerator:
    def setup_method(self):
        self.generator = DerailmentFixGenerator()

    def test_can_handle_derailment(self):
        assert self.generator.can_handle("task_derailment") is True
        assert self.generator.can_handle("derailment") is True
        assert self.generator.can_handle("hallucination") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "task_derailment",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "task_derailment",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.TASK_ANCHORING in fix_types
        assert FixType.GOAL_TRACKING in fix_types
        assert FixType.PROGRESS_MONITORING in fix_types


class TestContextNeglectFixGenerator:
    def setup_method(self):
        self.generator = ContextNeglectFixGenerator()

    def test_can_handle_context_neglect(self):
        assert self.generator.can_handle("context_neglect") is True
        assert self.generator.can_handle("context") is True
        assert self.generator.can_handle("hallucination") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "context_neglect",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "context_neglect",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.CHECKPOINT_RECOVERY in fix_types
        assert FixType.PROMPT_REINFORCEMENT in fix_types
        assert FixType.STATE_VALIDATION in fix_types


class TestCommunicationFixGenerator:
    def setup_method(self):
        self.generator = CommunicationFixGenerator()

    def test_can_handle_communication(self):
        assert self.generator.can_handle("communication_breakdown") is True
        assert self.generator.can_handle("communication") is True
        assert self.generator.can_handle("hallucination") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "communication_breakdown",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "communication_breakdown",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.MESSAGE_SCHEMA in fix_types
        assert FixType.HANDOFF_PROTOCOL in fix_types
        assert FixType.RETRY_LIMIT in fix_types


class TestSpecificationFixGenerator:
    def setup_method(self):
        self.generator = SpecificationFixGenerator()

    def test_can_handle_specification(self):
        assert self.generator.can_handle("specification_mismatch") is True
        assert self.generator.can_handle("specification") is True
        assert self.generator.can_handle("hallucination") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "specification_mismatch",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "specification_mismatch",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.SPEC_VALIDATION in fix_types
        assert FixType.OUTPUT_CONSTRAINT in fix_types
        assert FixType.SCHEMA_ENFORCEMENT in fix_types


class TestDecompositionFixGenerator:
    def setup_method(self):
        self.generator = DecompositionFixGenerator()

    def test_can_handle_decomposition(self):
        assert self.generator.can_handle("poor_decomposition") is True
        assert self.generator.can_handle("decomposition") is True
        assert self.generator.can_handle("hallucination") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "poor_decomposition",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "poor_decomposition",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.TASK_DECOMPOSER in fix_types
        assert FixType.SUBTASK_VALIDATOR in fix_types
        assert FixType.PROGRESS_MONITORING in fix_types


class TestWorkflowFixGenerator:
    def setup_method(self):
        self.generator = WorkflowFixGenerator()

    def test_can_handle_workflow(self):
        assert self.generator.can_handle("flawed_workflow") is True
        assert self.generator.can_handle("workflow") is True
        assert self.generator.can_handle("hallucination") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "flawed_workflow",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "flawed_workflow",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.WORKFLOW_GUARD in fix_types
        assert FixType.STEP_VALIDATOR in fix_types
        assert FixType.CIRCUIT_BREAKER in fix_types


class TestWithholdingFixGenerator:
    def setup_method(self):
        self.generator = WithholdingFixGenerator()

    def test_can_handle_withholding(self):
        assert self.generator.can_handle("withholding") is True
        assert self.generator.can_handle("information_withholding") is True
        assert self.generator.can_handle("hallucination") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "withholding",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "withholding",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.TRANSPARENCY_ENFORCER in fix_types
        assert FixType.INFORMATION_COMPLETENESS in fix_types
        assert FixType.SOURCE_GROUNDING in fix_types


class TestCompletionFixGenerator:
    def setup_method(self):
        self.generator = CompletionFixGenerator()

    def test_can_handle_completion(self):
        assert self.generator.can_handle("completion") is True
        assert self.generator.can_handle("completion_misjudgment") is True
        assert self.generator.can_handle("hallucination") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "completion",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "completion",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.COMPLETION_GATE in fix_types
        assert FixType.QUALITY_CHECKPOINT in fix_types
        assert FixType.PROGRESS_MONITORING in fix_types


class TestCostFixGenerator:
    def setup_method(self):
        self.generator = CostFixGenerator()

    def test_can_handle_cost(self):
        assert self.generator.can_handle("cost") is True
        assert self.generator.can_handle("cost_overrun") is True
        assert self.generator.can_handle("hallucination") is False

    def test_generates_fixes(self):
        detection = {
            "id": "det_test",
            "detection_type": "cost",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        assert len(fixes) == 3
        assert all(len(f.code_changes) > 0 for f in fixes)

    def test_fix_types(self):
        detection = {
            "id": "det_test",
            "detection_type": "cost",
            "details": {},
        }
        fixes = self.generator.generate_fixes(detection, {})
        fix_types = [f.fix_type for f in fixes]
        assert FixType.BUDGET_LIMITER in fix_types
        assert FixType.COST_MONITOR in fix_types
        assert FixType.TOKEN_OPTIMIZER in fix_types
