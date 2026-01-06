"""CrewAI integration for MAO Testing SDK."""

from __future__ import annotations
import functools
import json
from typing import Any, Callable, Dict, Optional, TypeVar

from ..tracer import MAOTracer
from ..session import TraceSession

T = TypeVar("T")


class CrewAITracer(MAOTracer):
    """Tracer with CrewAI-specific instrumentation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_session: Optional[TraceSession] = None
    
    def instrument(self, crew: T) -> T:
        """Instrument a CrewAI Crew for automatic tracing."""
        try:
            from crewai import Crew
        except ImportError:
            raise ImportError("crewai is required. Install with: pip install crewai")
        
        if hasattr(crew, "kickoff"):
            original_kickoff = crew.kickoff
            
            @functools.wraps(original_kickoff)
            def traced_kickoff(*args, **kwargs):
                crew_name = getattr(crew, "name", "crew")
                
                with self.trace(f"crewai-{crew_name}", framework="crewai") as session:
                    self._active_session = session
                    
                    if hasattr(crew, "agents"):
                        agent_names = [getattr(a, "role", str(a)) for a in crew.agents]
                        session.set_metadata({"agents": agent_names})
                        session.capture_state("agents", {"roles": agent_names})
                    
                    if hasattr(crew, "tasks"):
                        task_descriptions = [
                            getattr(t, "description", str(t))[:200] 
                            for t in crew.tasks
                        ]
                        session.set_metadata({"task_count": len(crew.tasks)})
                        session.capture_state("tasks", {"descriptions": task_descriptions})
                    
                    try:
                        result = original_kickoff(*args, **kwargs)
                        
                        session.capture_state("result", {
                            "output": str(result)[:2048] if result else None,
                        })
                        
                        return result
                    finally:
                        self._active_session = None
            
            crew.kickoff = traced_kickoff
        
        if hasattr(crew, "agents"):
            for agent in crew.agents:
                self._instrument_agent(agent)
        
        return crew
    
    def _instrument_agent(self, agent: Any) -> None:
        """Instrument a CrewAI agent."""
        agent_role = getattr(agent, "role", str(agent))
        
        if hasattr(agent, "execute_task"):
            original_execute = agent.execute_task
            
            @functools.wraps(original_execute)
            def traced_execute(task, *args, **kwargs):
                if self._active_session is None:
                    return original_execute(task, *args, **kwargs)
                
                task_description = getattr(task, "description", str(task))[:200]
                
                with self._active_session.span(f"agent:{agent_role}:execute") as span:
                    span.set_attribute("crewai.agent.role", agent_role)
                    span.set_attribute("gen_ai.agent.name", agent_role)
                    span.set_attribute("crewai.task.description", task_description)
                    
                    if hasattr(agent, "goal"):
                        span.set_attribute("crewai.agent.goal", agent.goal[:500])
                    
                    self._active_session.capture_state(
                        f"task_start:{agent_role}",
                        {"task": task_description, "agent": agent_role},
                        agent_id=agent_role,
                    )
                    
                    result = original_execute(task, *args, **kwargs)
                    
                    if result:
                        span.set_attribute("gen_ai.completion", str(result)[:4096])
                        self._active_session.capture_state(
                            f"task_complete:{agent_role}",
                            {"task": task_description, "result": str(result)[:1024]},
                            agent_id=agent_role,
                        )
                    
                    return result
            
            agent.execute_task = traced_execute
    
    def instrument_agent(self, agent: T) -> T:
        """Instrument a single CrewAI agent."""
        self._instrument_agent(agent)
        return agent
