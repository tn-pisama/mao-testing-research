"""Tests for fix suggestion generators."""

import pytest
from app.fixes import (
    FixGenerator,
    LoopFixGenerator,
    CorruptionFixGenerator,
    PersonaFixGenerator,
    DeadlockFixGenerator,
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
