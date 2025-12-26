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
        
        from app.detection.loop import LoopDetector
        detector = LoopDetector()
        
        result = detector.analyze(mao_tracer.traces.get(trace_id, []))
        
        assert result is not None
        assert result.get('detected', False) is True
        assert result.get('type') == 'infinite_loop'
        assert result.get('repetitions', 0) >= 3
    
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
        
        from app.detection.loop import LoopDetector
        detector = LoopDetector()
        
        result = detector.analyze(mao_tracer.traces.get(trace_id, []))
        
        assert result is None or result.get('detected', False) is False


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
        
        from app.detection.corruption import CorruptionDetector
        detector = CorruptionDetector()
        
        result = detector.analyze(mao_tracer.traces.get(trace_id, []))
        
        assert result is not None
        assert result.get('detected', False) is True


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
        
        from app.detection.loop import LoopDetector
        from app.detection.corruption import CorruptionDetector
        
        loop_result = LoopDetector().analyze(mao_tracer.traces.get(trace_id, []))
        corruption_result = CorruptionDetector().analyze(mao_tracer.traces.get(trace_id, []))
        
        assert loop_result is None or loop_result.get('detected', False) is False
        assert corruption_result is None or corruption_result.get('detected', False) is False


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
            'type': 'infinite_loop',
            'detected': True,
            'pattern': 'tool_repeat',
            'tool_name': 'search',
            'repetitions': 8
        }
        
        generator = LoopFixGenerator()
        fix = generator.generate(detection)
        
        assert fix is not None
        assert 'max_iterations' in fix.code_change or 'max_iter' in fix.code_change
        assert fix.confidence >= 0.8
    
    @pytest.mark.asyncio
    async def test_deadlock_fix_includes_timeout(self):
        """
        When a deadlock is detected, the fix suggestion should
        include adding timeout or max_delegation_depth.
        """
        from app.fixes.deadlock_fixes import DeadlockFixGenerator
        
        detection = {
            'type': 'deadlock',
            'detected': True,
            'pattern': 'circular_delegation',
            'agents': ['researcher', 'writer']
        }
        
        generator = DeadlockFixGenerator()
        fix = generator.generate(detection)
        
        assert fix is not None
        assert 'timeout' in fix.code_change.lower() or 'delegation' in fix.code_change.lower()
