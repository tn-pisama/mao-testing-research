"""Fix generators for infinite loop detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class LoopFixGenerator(BaseFixGenerator):
    """Generates fixes for infinite loop detections."""
    
    def can_handle(self, detection_type: str) -> bool:
        return "loop" in detection_type or "infinite" in detection_type or "recursion" in detection_type
    
    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})
        method = detection.get("method", "")
        loop_length = details.get("loop_length", 3)
        affected_agents = details.get("affected_agents", [])

        # v1.1: Context-aware parameterization from failure signature
        signature = context.get("failure_signature")
        if signature:
            # Override loop_length from signature indicators if available
            for indicator in getattr(signature, "indicators", []):
                if "loop length" in indicator.lower():
                    try:
                        loop_length = int("".join(c for c in indicator if c.isdigit()) or loop_length)
                    except (ValueError, TypeError):
                        pass
            # Use affected_components from signature if detection doesn't provide them
            if not affected_agents and hasattr(signature, "affected_components"):
                affected_agents = signature.affected_components or []

        fixes.append(self._retry_limit_fix(detection_id, loop_length, context))
        fixes.append(self._exponential_backoff_fix(detection_id, context))
        fixes.append(self._circuit_breaker_fix(detection_id, affected_agents, context))

        if method == "structural" and len(affected_agents) >= 2:
            fixes.append(self._conversation_terminator_fix(detection_id, affected_agents, context))

        return fixes
    
    def _retry_limit_fix(
        self,
        detection_id: str,
        loop_length: int,
        context: Dict[str, Any],
    ) -> FixSuggestion:
        framework = context.get("framework", "langgraph")
        max_retries = max(3, loop_length + 2)
        
        if framework == "langgraph":
            code = f'''from langgraph.graph import StateGraph

def create_graph_with_retry_limit():
    graph = StateGraph(AgentState)
    
    # Add retry counter to state
    def with_retry_limit(func, max_retries={max_retries}):
        def wrapper(state):
            retry_count = state.get("_retry_count", 0)
            if retry_count >= max_retries:
                return {{"_loop_terminated": True, "error": "Max retries exceeded"}}
            result = func(state)
            result["_retry_count"] = retry_count + 1
            return result
        return wrapper
    
    # Wrap nodes with retry limit
    graph.add_node("agent", with_retry_limit(agent_node))
    
    # Add conditional edge to check for loop termination
    def should_continue(state):
        if state.get("_loop_terminated"):
            return "end"
        return "continue"
    
    graph.add_conditional_edges("agent", should_continue)
    return graph'''
        elif framework == "crewai":
            code = f'''from crewai import Agent, Task, Crew

class RetryLimitedAgent(Agent):
    max_iterations: int = {max_retries}
    _iteration_count: int = 0
    
    def execute_task(self, task, context=None, tools=None):
        self._iteration_count += 1
        if self._iteration_count > self.max_iterations:
            raise RuntimeError(f"Agent exceeded max iterations ({{self.max_iterations}})")
        return super().execute_task(task, context, tools)'''
        else:
            code = f'''MAX_RETRIES = {max_retries}
retry_count = 0

while should_continue and retry_count < MAX_RETRIES:
    result = execute_agent_step()
    retry_count += 1
    
if retry_count >= MAX_RETRIES:
    logger.warning("Loop terminated: max retries exceeded")'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="infinite_loop",
            fix_type=FixType.RETRY_LIMIT,
            confidence=FixConfidence.HIGH,
            title="Add retry limit to prevent infinite loops",
            description=f"Add a maximum retry limit of {max_retries} iterations to prevent the detected loop pattern.",
            rationale="The detected loop repeated the same sequence multiple times without progress. Adding a retry limit ensures the system fails gracefully instead of running indefinitely.",
            code_changes=[
                CodeChange(
                    file_path=f"agents/{framework}_agent.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description=f"Add retry limit wrapper for {framework} agents",
                )
            ],
            estimated_impact="Prevents runaway costs and ensures predictable failure behavior",
            tags=["loop-prevention", "reliability", framework],
        )
    
    def _exponential_backoff_fix(
        self,
        detection_id: str,
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import asyncio
import random

class ExponentialBackoff:
    def __init__(self, base_delay=1.0, max_delay=60.0, max_retries=5):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.attempt = 0
    
    async def wait(self):
        if self.attempt >= self.max_retries:
            raise MaxRetriesExceeded(f"Exceeded {self.max_retries} retries")
        
        delay = min(
            self.base_delay * (2 ** self.attempt) + random.uniform(0, 1),
            self.max_delay
        )
        self.attempt += 1
        await asyncio.sleep(delay)
    
    def reset(self):
        self.attempt = 0

# Usage in agent
backoff = ExponentialBackoff()

async def agent_with_backoff(state):
    while True:
        try:
            result = await process_state(state)
            if is_making_progress(result):
                backoff.reset()
                return result
            await backoff.wait()
        except MaxRetriesExceeded:
            return {"error": "Agent stuck in loop", "_terminated": True}'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="infinite_loop",
            fix_type=FixType.EXPONENTIAL_BACKOFF,
            confidence=FixConfidence.MEDIUM,
            title="Add exponential backoff for repeated operations",
            description="Implement exponential backoff with jitter to slow down and eventually terminate repeated operations.",
            rationale="When agents retry the same operation, exponential backoff prevents resource exhaustion and gives external systems time to recover.",
            code_changes=[
                CodeChange(
                    file_path="utils/backoff.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Exponential backoff utility with max retry limit",
                )
            ],
            estimated_impact="Reduces API costs during loops, provides graceful degradation",
            tags=["loop-prevention", "rate-limiting"],
        )
    
    def _circuit_breaker_fix(
        self,
        detection_id: str,
        affected_agents: List[str],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        agents_str = ", ".join(f'"{a}"' for a in affected_agents[:3]) if affected_agents else '"agent"'

        # v1.1: Context-aware thresholds based on agent count
        agent_count = len(affected_agents) if affected_agents else 1
        if agent_count >= 3:
            failure_threshold = 3  # Cascade risk — trip faster
            recovery_timeout = 30
        elif agent_count == 2:
            failure_threshold = 4
            recovery_timeout = 45
        else:
            failure_threshold = 5
            recovery_timeout = 60

        code = f'''from datetime import datetime, timedelta
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold={failure_threshold},
        recovery_timeout={recovery_timeout},
        agents=[{agents_str}],
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.agents = agents
        self._state = {{agent: CircuitState.CLOSED for agent in agents}}
        self._failures = {{agent: 0 for agent in agents}}
        self._last_failure = {{agent: None for agent in agents}}
    
    def can_execute(self, agent: str) -> bool:
        state = self._state.get(agent, CircuitState.CLOSED)
        
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.OPEN:
            if self._should_attempt_reset(agent):
                self._state[agent] = CircuitState.HALF_OPEN
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def record_success(self, agent: str):
        self._failures[agent] = 0
        self._state[agent] = CircuitState.CLOSED
    
    def record_failure(self, agent: str):
        self._failures[agent] += 1
        self._last_failure[agent] = datetime.now()
        
        if self._failures[agent] >= self.failure_threshold:
            self._state[agent] = CircuitState.OPEN
    
    def _should_attempt_reset(self, agent: str) -> bool:
        last = self._last_failure.get(agent)
        if not last:
            return True
        return datetime.now() - last > timedelta(seconds=self.recovery_timeout)

# Usage
circuit_breaker = CircuitBreaker()

def execute_with_circuit_breaker(agent_name, func, *args):
    if not circuit_breaker.can_execute(agent_name):
        raise CircuitOpenError(f"Circuit open for {{agent_name}}")
    
    try:
        result = func(*args)
        circuit_breaker.record_success(agent_name)
        return result
    except Exception as e:
        circuit_breaker.record_failure(agent_name)
        raise'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="infinite_loop",
            fix_type=FixType.CIRCUIT_BREAKER,
            confidence=FixConfidence.HIGH,
            title="Implement circuit breaker pattern for failing agents",
            description="Add a circuit breaker that stops calling agents after repeated failures, with automatic recovery attempts.",
            rationale="The circuit breaker pattern prevents cascade failures by temporarily disabling problematic agents and allowing the system to recover.",
            code_changes=[
                CodeChange(
                    file_path="utils/circuit_breaker.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Circuit breaker implementation for agent calls",
                )
            ],
            estimated_impact="Prevents cascade failures, enables graceful degradation",
            breaking_changes=False,
            tags=["loop-prevention", "reliability", "circuit-breaker"],
        )
    
    def _conversation_terminator_fix(
        self,
        detection_id: str,
        affected_agents: List[str],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''def detect_conversation_loop(messages: list, window_size=6) -> bool:
    """Detect if conversation is stuck in a loop."""
    if len(messages) < window_size:
        return False
    
    recent = messages[-window_size:]
    
    # Check for alternating pattern (A->B->A->B)
    senders = [m.get("sender") or m.get("agent") for m in recent]
    if len(set(senders)) == 2:
        pattern = senders[:2]
        if all(senders[i] == pattern[i % 2] for i in range(len(senders))):
            # Check content similarity
            contents = [m.get("content", "") for m in recent]
            if _similar_contents(contents[::2]) and _similar_contents(contents[1::2]):
                return True
    
    return False

def _similar_contents(contents: list, threshold=0.8) -> bool:
    """Check if contents are semantically similar."""
    if len(contents) < 2:
        return False
    # Simple overlap check (replace with embedding similarity for production)
    words_sets = [set(c.lower().split()) for c in contents]
    for i in range(1, len(words_sets)):
        overlap = len(words_sets[0] & words_sets[i]) / max(len(words_sets[0]), 1)
        if overlap < threshold:
            return False
    return True

# Add to your agent orchestrator
class ConversationOrchestrator:
    def __init__(self, max_turns=20):
        self.max_turns = max_turns
        self.messages = []
    
    def add_message(self, message):
        self.messages.append(message)
        
        if len(self.messages) > self.max_turns:
            return {"action": "terminate", "reason": "max_turns_exceeded"}
        
        if detect_conversation_loop(self.messages):
            return {"action": "terminate", "reason": "loop_detected"}
        
        return {"action": "continue"}'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="infinite_loop",
            fix_type=FixType.RETRY_LIMIT,
            confidence=FixConfidence.MEDIUM,
            title="Add conversation loop detector for multi-agent chat",
            description="Detect when two agents are stuck in a repetitive back-and-forth conversation and terminate gracefully.",
            rationale=f"Agents {affected_agents} were detected in an alternating conversation pattern. This fix monitors message patterns and terminates loops before they accumulate costs.",
            code_changes=[
                CodeChange(
                    file_path="utils/conversation_monitor.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Conversation loop detection and termination",
                )
            ],
            estimated_impact="Prevents $47K-style runaway API bills from agent-to-agent loops",
            tags=["loop-prevention", "multi-agent", "conversation"],
        )
