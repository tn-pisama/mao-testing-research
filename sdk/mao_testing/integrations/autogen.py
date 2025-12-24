"""AutoGen integration for MAO Testing SDK."""

from __future__ import annotations
import functools
import json
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from ..tracer import MAOTracer
from ..session import TraceSession

T = TypeVar("T")


class AutoGenTracer(MAOTracer):
    """Tracer with AutoGen-specific instrumentation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_session: Optional[TraceSession] = None
        self._instrumented_agents: Dict[str, Any] = {}
    
    def instrument(self, agent: T) -> T:
        """Instrument an AutoGen agent for automatic tracing."""
        try:
            import autogen
        except ImportError:
            raise ImportError("pyautogen is required. Install with: pip install pyautogen")
        
        agent_name = getattr(agent, "name", str(id(agent)))
        
        if hasattr(agent, "generate_reply"):
            original_generate_reply = agent.generate_reply
            
            @functools.wraps(original_generate_reply)
            def traced_generate_reply(messages=None, sender=None, *args, **kwargs):
                if self._active_session is None:
                    return original_generate_reply(messages=messages, sender=sender, *args, **kwargs)
                
                with self._active_session.span(f"agent:{agent_name}:generate_reply") as span:
                    span.set_attribute("autogen.agent.name", agent_name)
                    span.set_attribute("gen_ai.agent.name", agent_name)
                    
                    if sender:
                        sender_name = getattr(sender, "name", str(sender))
                        span.set_attribute("autogen.sender", sender_name)
                    
                    if messages:
                        span.set_attribute("autogen.message_count", len(messages))
                        try:
                            last_message = messages[-1] if messages else {}
                            span.set_attribute("gen_ai.prompt", json.dumps(last_message)[:4096])
                        except (TypeError, ValueError):
                            pass
                    
                    result = original_generate_reply(messages=messages, sender=sender, *args, **kwargs)
                    
                    if result:
                        try:
                            span.set_attribute("gen_ai.completion", str(result)[:4096])
                        except (TypeError, ValueError):
                            pass
                        
                        self._active_session.capture_state(
                            f"reply:{agent_name}",
                            {"agent": agent_name, "reply": str(result)[:1024]},
                            agent_id=agent_name,
                        )
                    
                    return result
            
            agent.generate_reply = traced_generate_reply
        
        if hasattr(agent, "initiate_chat"):
            original_initiate_chat = agent.initiate_chat
            
            @functools.wraps(original_initiate_chat)
            def traced_initiate_chat(recipient, message=None, *args, **kwargs):
                recipient_name = getattr(recipient, "name", str(recipient))
                session_name = f"autogen-chat:{agent_name}->{recipient_name}"
                
                with self.trace(session_name, framework="autogen") as session:
                    self._active_session = session
                    
                    session.set_metadata({
                        "initiator": agent_name,
                        "recipient": recipient_name,
                    })
                    
                    if message:
                        session.capture_state("initial_message", {
                            "from": agent_name,
                            "to": recipient_name,
                            "message": str(message)[:1024],
                        })
                    
                    try:
                        result = original_initiate_chat(recipient, message=message, *args, **kwargs)
                        return result
                    finally:
                        self._active_session = None
            
            agent.initiate_chat = traced_initiate_chat
        
        self._instrumented_agents[agent_name] = agent
        return agent
    
    def instrument_all(self, agents: list) -> list:
        """Instrument multiple agents."""
        return [self.instrument(agent) for agent in agents]
