"""LangGraph integration for MAO Testing SDK."""

from __future__ import annotations
import functools
import json
from typing import Any, Callable, Dict, Optional, TypeVar

from ..tracer import MAOTracer
from ..session import TraceSession
from ..config import MAOConfig

T = TypeVar("T")


class LangGraphTracer(MAOTracer):
    """Tracer with LangGraph-specific instrumentation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_session: Optional[TraceSession] = None
    
    def instrument(self, graph: T) -> T:
        """Instrument a LangGraph StateGraph for automatic tracing."""
        try:
            from langgraph.graph import StateGraph
        except ImportError:
            raise ImportError("langgraph is required. Install with: pip install langgraph")
        
        if not hasattr(graph, "_nodes"):
            return graph
        
        original_nodes = dict(graph._nodes)
        
        for node_name, node_func in original_nodes.items():
            graph._nodes[node_name] = self._wrap_node(node_name, node_func)
        
        original_invoke = graph.compile().__class__.invoke
        
        def traced_invoke(compiled_self, state: Dict[str, Any], *args, **kwargs):
            with self.trace(graph.name if hasattr(graph, "name") else "langgraph-workflow", framework="langgraph") as session:
                self._active_session = session
                session.capture_state("initial", state)
                
                try:
                    result = original_invoke(compiled_self, state, *args, **kwargs)
                    session.capture_state("final", result if isinstance(result, dict) else {"result": result})
                    return result
                finally:
                    self._active_session = None
        
        compiled = graph.compile()
        compiled.invoke = lambda state, *args, **kwargs: traced_invoke(compiled, state, *args, **kwargs)
        
        return graph
    
    def _wrap_node(self, node_name: str, node_func: Callable) -> Callable:
        """Wrap a node function with tracing."""
        @functools.wraps(node_func)
        def wrapped(state: Dict[str, Any], *args, **kwargs):
            if self._active_session is None:
                return node_func(state, *args, **kwargs)
            
            with self._active_session.span(f"node:{node_name}") as span:
                span.set_attribute("langgraph.node.name", node_name)
                span.set_attribute("gen_ai.agent.name", node_name)
                
                try:
                    state_snapshot = json.dumps(state)[:4096]
                    span.set_attribute("langgraph.state.input", state_snapshot)
                except (TypeError, ValueError):
                    pass
                
                result = node_func(state, *args, **kwargs)
                
                try:
                    result_snapshot = json.dumps(result)[:4096]
                    span.set_attribute("langgraph.state.output", result_snapshot)
                except (TypeError, ValueError):
                    pass
                
                if isinstance(result, dict):
                    self._active_session.capture_state(f"after:{node_name}", result, agent_id=node_name)
                
                return result
        
        return wrapped
    
    def trace_node(self, node_name: str) -> Callable[[Callable], Callable]:
        """Decorator to trace a specific node function."""
        def decorator(func: Callable) -> Callable:
            return self._wrap_node(node_name, func)
        return decorator
