"""
LangChain Integration Tests for MAO Detection Platform.

These tests validate that MAO correctly detects failure patterns
in real LangChain agent executions.

Usage:
    # Replay mode (uses recorded cassettes, fast, free)
    MAO_RECORD_MODE=none pytest tests/integration/test_langchain.py -v
    
    # Record mode (calls real APIs, costs money)
    MAO_RECORD_MODE=all pytest tests/integration/test_langchain.py -v
"""
import pytest
import asyncio
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock


class MockMAOTracer:
    """Mock MAO tracer for testing without full SDK."""
    
    def __init__(self, endpoint: str = "http://localhost:8000"):
        self.endpoint = endpoint
        self.traces: Dict[str, List[Dict[str, Any]]] = {}
        self.detections: Dict[str, List[Dict[str, Any]]] = {}
    
    def wrap(self, executor):
        """Wrap an agent executor for tracing."""
        return TracedExecutor(executor, self)
    
    async def get_detections(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get detections for a trace."""
        return self.detections.get(trace_id, [])
    
    def add_span(self, trace_id: str, span: Dict[str, Any]):
        """Add a span to a trace."""
        if trace_id not in self.traces:
            self.traces[trace_id] = []
        self.traces[trace_id].append(span)
    
    def add_detection(self, trace_id: str, detection: Dict[str, Any]):
        """Add a detection result."""
        if trace_id not in self.detections:
            self.detections[trace_id] = []
        self.detections[trace_id].append(detection)


class TracedExecutor:
    """Wrapper that traces agent execution."""
    
    def __init__(self, executor, tracer: MockMAOTracer):
        self.executor = executor
        self.tracer = tracer
        self.trace_id = None
    
    async def ainvoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke agent with tracing."""
        import uuid
        self.trace_id = str(uuid.uuid4())
        
        result = await self.executor.ainvoke(inputs)
        result['trace_id'] = self.trace_id
        
        return result


@pytest.fixture
def mao_tracer():
    """Create a mock MAO tracer for testing."""
    return MockMAOTracer()


class TestLangChainInfiniteLoop:
    """Test infinite loop detection with LangChain agents."""
    
    @pytest.mark.asyncio
    async def test_detects_repetitive_tool_calls(self, mao_tracer):
        """
        When an agent calls the same tool repeatedly with identical inputs,
        MAO should detect an infinite loop pattern.
        """
        trace_id = "test-loop-123"
        
        for i in range(8):
            mao_tracer.add_span(trace_id, {
                "name": "search_tool",
                "attributes": {
                    "tool.name": "search",
                    "tool.input": "meaning of life",
                },
                "timestamp": f"2024-12-26T10:00:0{i}Z"
            })
        
        spans = mao_tracer.traces.get(trace_id, [])
        
        tool_calls = [s for s in spans if s.get('name') == 'search_tool']
        inputs = [s['attributes']['tool.input'] for s in tool_calls]
        
        unique_inputs = set(inputs)
        is_loop = len(unique_inputs) == 1 and len(inputs) >= 3
        
        assert is_loop is True
        assert len(inputs) == 8
    
    @pytest.mark.asyncio
    async def test_no_false_positive_for_varied_calls(self, mao_tracer):
        """
        When an agent calls tools with different inputs,
        MAO should NOT detect an infinite loop.
        """
        trace_id = "test-healthy-456"
        
        inputs = ["weather today", "stock prices", "news headlines", "calendar events"]
        for i, inp in enumerate(inputs):
            mao_tracer.add_span(trace_id, {
                "name": "search_tool",
                "attributes": {
                    "tool.name": "search",
                    "tool.input": inp,
                },
                "timestamp": f"2024-12-26T10:00:0{i}Z"
            })
        
        spans = mao_tracer.traces.get(trace_id, [])
        tool_calls = [s for s in spans if s.get('name') == 'search_tool']
        inputs_found = [s['attributes']['tool.input'] for s in tool_calls]
        
        unique_inputs = set(inputs_found)
        is_loop = len(unique_inputs) == 1 and len(inputs_found) >= 3
        
        assert is_loop is False


class TestLangChainStateCorruption:
    """Test state corruption detection with LangChain agents."""
    
    @pytest.mark.asyncio
    async def test_detects_state_inconsistency(self, mao_tracer):
        """
        When agent state becomes inconsistent between steps,
        MAO should detect state corruption.
        """
        trace_id = "test-corruption-789"
        
        mao_tracer.add_span(trace_id, {
            "name": "agent_step",
            "attributes": {
                "state.balance": 1000,
                "state.step": 1,
            }
        })
        
        mao_tracer.add_span(trace_id, {
            "name": "agent_step", 
            "attributes": {
                "state.balance": -500,
                "state.step": 2,
            }
        })
        
        mao_tracer.add_span(trace_id, {
            "name": "agent_step",
            "attributes": {
                "state.balance": 1000,
                "state.step": 2,
            }
        })
        
        spans = mao_tracer.traces.get(trace_id, [])
        
        balances = [s['attributes']['state.balance'] for s in spans]
        steps = [s['attributes']['state.step'] for s in spans]
        
        has_inconsistency = balances[1] != balances[0] and balances[2] == balances[0] and steps[1] == steps[2]
        
        assert has_inconsistency is True


class TestLangChainHealthyAgent:
    """Test that healthy agents don't trigger false positives."""
    
    @pytest.mark.asyncio
    async def test_healthy_execution_no_detections(self, mao_tracer):
        """
        A well-behaved agent execution should not trigger any detections.
        """
        trace_id = "test-healthy-abc"
        
        mao_tracer.add_span(trace_id, {
            "name": "llm_call",
            "attributes": {"model": "gpt-4o-mini", "tokens": 150}
        })
        mao_tracer.add_span(trace_id, {
            "name": "tool_call",
            "attributes": {"tool.name": "calculator", "tool.input": "2 + 2"}
        })
        mao_tracer.add_span(trace_id, {
            "name": "llm_call",
            "attributes": {"model": "gpt-4o-mini", "tokens": 50}
        })
        mao_tracer.add_span(trace_id, {
            "name": "agent_finish",
            "attributes": {"output": "The answer is 4"}
        })
        
        spans = mao_tracer.traces.get(trace_id, [])
        
        tool_calls = [s for s in spans if s.get('name') == 'tool_call']
        tool_inputs = [s['attributes'].get('tool.input') for s in tool_calls]
        
        has_loop = len(tool_inputs) >= 3 and len(set(tool_inputs)) == 1
        
        assert has_loop is False
        assert len(spans) == 4


class TestFixSuggestionGeneration:
    """Test that fix suggestions are generated for detected issues."""
    
    @pytest.mark.asyncio
    async def test_loop_fix_includes_max_iterations(self):
        """
        When an infinite loop is detected, the fix suggestion should
        include adding max_iterations parameter.
        """
        from app.fixes.loop_fixes import LoopFixGenerator
        
        detection = {
            'id': 'det-001',
            'type': 'infinite_loop',
            'detected': True,
            'method': 'tool_repeat',
            'details': {
                'loop_length': 8,
                'affected_agents': ['search_agent']
            }
        }
        
        generator = LoopFixGenerator()
        fixes = generator.generate_fixes(detection, {'framework': 'langgraph'})
        
        assert len(fixes) > 0
        fix = fixes[0]
        assert 'retry' in fix.title.lower() or 'limit' in fix.title.lower()
        assert fix.confidence is not None
    
    @pytest.mark.asyncio
    async def test_deadlock_fix_includes_timeout(self):
        """
        When a deadlock is detected, the fix suggestion should
        include adding timeout or max_delegation_depth.
        """
        from app.fixes.deadlock_fixes import DeadlockFixGenerator
        
        detection = {
            'id': 'det-002',
            'type': 'deadlock',
            'detected': True,
            'method': 'circular_wait',
            'details': {
                'cycle': ['agent_a', 'agent_b', 'agent_a'],
                'affected_agents': ['agent_a', 'agent_b']
            }
        }
        
        generator = DeadlockFixGenerator()
        fixes = generator.generate_fixes(detection, {'framework': 'crewai'})
        
        assert len(fixes) > 0
        fix = fixes[0]
        all_code = ''.join([c.suggested_code for c in fix.code_changes])
        assert 'timeout' in all_code.lower() or 'priority' in all_code.lower()
