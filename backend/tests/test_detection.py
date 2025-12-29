import pytest
from app.detection.loop import MultiLevelLoopDetector, StateSnapshot
from app.detection.corruption import SemanticCorruptionDetector, StateSnapshot as CorruptionState, Schema
from app.detection.persona import PersonaConsistencyScorer, Agent


class TestLoopDetector:
    def setup_method(self):
        self.detector = MultiLevelLoopDetector()
    
    def test_no_loop_with_few_states(self):
        states = [
            StateSnapshot(agent_id="agent1", state_delta={"x": 1}, content="state 1", sequence_num=0),
            StateSnapshot(agent_id="agent2", state_delta={"x": 2}, content="state 2", sequence_num=1),
        ]
        result = self.detector.detect_loop(states)
        assert not result.detected
    
    def test_structural_loop_detection(self):
        states = [
            StateSnapshot(agent_id="agent1", state_delta={"query": "hello"}, content="query hello", sequence_num=0),
            StateSnapshot(agent_id="agent2", state_delta={"response": "hi"}, content="response hi", sequence_num=1),
            StateSnapshot(agent_id="agent1", state_delta={"query": "hello"}, content="query hello", sequence_num=2),
            StateSnapshot(agent_id="agent2", state_delta={"response": "hi"}, content="response hi", sequence_num=3),
            StateSnapshot(agent_id="agent1", state_delta={"query": "hello"}, content="query hello", sequence_num=4),
        ]
        result = self.detector.detect_loop(states)
        assert result.detected
        assert result.method == "structural"
        assert result.confidence >= 0.65
    
    def test_hash_loop_detection(self):
        states = [
            StateSnapshot(agent_id="agent1", state_delta={"a": 1, "b": 2}, content="state", sequence_num=0),
            StateSnapshot(agent_id="agent2", state_delta={"c": 3}, content="other", sequence_num=1),
            StateSnapshot(agent_id="agent1", state_delta={"a": 1, "b": 2}, content="state again", sequence_num=2),
        ]
        result = self.detector.detect_loop(states)
        assert result.detected
        assert result.method in ("hash", "structural")
    
    def test_meaningful_progress_prevents_false_positive(self):
        states = [
            StateSnapshot(agent_id="agent1", state_delta={"step": 1}, content="step 1", sequence_num=0),
            StateSnapshot(agent_id="agent1", state_delta={"step": 2, "extra": "data"}, content="step 2", sequence_num=1),
            StateSnapshot(agent_id="agent1", state_delta={"step": 3, "extra": "more", "new": "field"}, content="step 3", sequence_num=2),
        ]
        result = self.detector.detect_loop(states)
        assert not result.detected


class TestCorruptionDetector:
    def setup_method(self):
        self.detector = SemanticCorruptionDetector()
    
    def test_schema_validation_hallucinated_key(self):
        schema = Schema(fields={"name": str, "age": int}, required_fields=["name"])
        state = CorruptionState(state_delta={"name": "John", "unknown_field": "value"}, agent_id="agent1")
        prev = CorruptionState(state_delta={}, agent_id="agent1")
        
        issues = self.detector.detect_corruption(prev, state, schema)
        assert any(i.issue_type == "hallucinated_key" for i in issues)
    
    def test_domain_constraint_age(self):
        state = CorruptionState(state_delta={"age": 200}, agent_id="agent1")
        prev = CorruptionState(state_delta={}, agent_id="agent1")
        
        issues = self.detector.detect_corruption(prev, state)
        assert any(i.issue_type == "domain_violation" and i.field == "age" for i in issues)
    
    def test_cross_field_consistency_dates(self):
        state = CorruptionState(state_delta={"start_date": "2025-12-31", "end_date": "2025-01-01"}, agent_id="agent1")
        prev = CorruptionState(state_delta={}, agent_id="agent1")
        
        issues = self.detector.detect_corruption(prev, state)
        assert any(i.issue_type == "cross_field_inconsistency" for i in issues)
    
    def test_value_copying_detection(self):
        state = CorruptionState(
            state_delta={
                "field1": "This is a long duplicated value that appears twice",
                "field2": "This is a long duplicated value that appears twice",
            },
            agent_id="agent1"
        )
        prev = CorruptionState(state_delta={}, agent_id="agent1")
        
        issues = self.detector.detect_corruption(prev, state)
        assert any(i.issue_type == "suspicious_value_copy" for i in issues)


class TestPersonaScorer:
    def setup_method(self):
        self.scorer = PersonaConsistencyScorer()
    
    def test_consistent_persona(self):
        agent = Agent(
            id="research_agent",
            persona_description="A research assistant focused on finding and analyzing academic papers",
            allowed_actions=["search", "analyze"],
        )
        output = "I found several academic papers on machine learning that analyze transformer architectures"
        
        result = self.scorer.score_consistency(agent, output)
        assert result.score > 0.3
    
    def test_inconsistent_persona(self):
        agent = Agent(
            id="research_agent",
            persona_description="A formal academic research assistant focused on finding and analyzing scientific papers",
            allowed_actions=["search", "analyze"],
        )
        output = "I love pizza and video games! My favorite color is blue and I want to go to the beach tomorrow."
        
        result = self.scorer.score_consistency(agent, output)
        assert result.score < 0.7
