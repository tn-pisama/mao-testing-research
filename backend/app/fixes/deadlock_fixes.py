"""Fix generators for coordination deadlock detections."""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class DeadlockFixGenerator(BaseFixGenerator):
    """Generates fixes for coordination deadlock detections."""
    
    def can_handle(self, detection_type: str) -> bool:
        return "deadlock" in detection_type or "coordination" in detection_type or "parallel_sync" in detection_type
    
    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})
        waiting_agents = details.get("waiting_agents", [])
        
        fixes.append(self._timeout_fix(detection_id, details, context))
        fixes.append(self._priority_fix(detection_id, waiting_agents, context))
        fixes.append(self._async_handoff_fix(detection_id, context))
        fixes.append(self._dependency_resolver_fix(detection_id, waiting_agents, context))
        
        return fixes
    
    def _timeout_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import asyncio
from typing import TypeVar, Callable, Any
from functools import wraps

T = TypeVar("T")

class TimeoutError(Exception):
    """Operation timed out."""
    pass

def with_timeout(timeout_seconds: float = 30.0, fallback: Any = None):
    """Decorator to add timeout to async agent operations."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"{func.__name__} timed out after {timeout_seconds}s"
                )
                if fallback is not None:
                    return fallback
                raise TimeoutError(
                    f"Operation {func.__name__} exceeded {timeout_seconds}s timeout"
                )
        return wrapper
    return decorator


# For synchronous code
def sync_timeout(timeout_seconds: float = 30.0):
    """Timeout decorator for synchronous functions using threading."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout_seconds)
                except FutureTimeout:
                    logger.warning(f"{func.__name__} timed out")
                    raise TimeoutError(f"Sync operation timed out")
        return wrapper
    return decorator


# Usage with agents
class TimeoutAwareAgent:
    def __init__(self, name: str, timeout: float = 30.0):
        self.name = name
        self.timeout = timeout
    
    @with_timeout(30.0, fallback={"error": "timeout", "partial": True})
    async def execute(self, task: dict) -> dict:
        # Agent execution logic
        result = await self._process(task)
        return result
    
    @with_timeout(10.0)
    async def wait_for_dependency(self, dependency_id: str) -> dict:
        # Wait for another agent's output
        return await self._fetch_dependency(dependency_id)


# Global timeout configuration
AGENT_TIMEOUTS = {
    "researcher": 60.0,   # Research can take longer
    "writer": 45.0,
    "validator": 15.0,    # Validation should be fast
    "coordinator": 30.0,
    "default": 30.0,
}

def get_agent_timeout(agent_name: str) -> float:
    return AGENT_TIMEOUTS.get(agent_name, AGENT_TIMEOUTS["default"])'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="coordination_deadlock",
            fix_type=FixType.TIMEOUT_ADDITION,
            confidence=FixConfidence.HIGH,
            title="Add operation timeouts to prevent indefinite waiting",
            description="Wrap agent operations with timeouts to prevent deadlocks from waiting indefinitely.",
            rationale="Deadlock detected where agents were waiting on each other. Timeouts ensure operations fail gracefully instead of blocking forever.",
            code_changes=[
                CodeChange(
                    file_path="utils/timeout.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Timeout decorators for sync and async operations",
                )
            ],
            estimated_impact="Prevents indefinite blocking, enables graceful failure",
            tags=["deadlock", "timeout", "reliability"],
        )
    
    def _priority_fix(
        self,
        detection_id: str,
        waiting_agents: List[str],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        agents_str = ", ".join(f'"{a}"' for a in waiting_agents[:4]) if waiting_agents else '"agent1", "agent2"'
        
        code = f'''from enum import IntEnum
from dataclasses import dataclass
from typing import Dict, Optional
import threading

class Priority(IntEnum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4

@dataclass
class AgentConfig:
    name: str
    priority: Priority
    can_preempt: bool = False

# Define agent priorities to break deadlocks
AGENT_PRIORITIES: Dict[str, AgentConfig] = {{
    agent: AgentConfig(name=agent, priority=Priority.NORMAL)
    for agent in [{agents_str}]
}}

# Higher priority agents get resources first
AGENT_PRIORITIES["coordinator"] = AgentConfig("coordinator", Priority.HIGH, can_preempt=True)
AGENT_PRIORITIES["validator"] = AgentConfig("validator", Priority.CRITICAL, can_preempt=True)


class PriorityResourceManager:
    """Manage shared resources with priority-based access."""
    
    def __init__(self):
        self._locks: Dict[str, threading.Lock] = {{}}
        self._owners: Dict[str, str] = {{}}
        self._waiters: Dict[str, list] = {{}}
    
    def acquire(self, resource: str, agent: str, timeout: float = 30.0) -> bool:
        """Acquire resource with priority handling."""
        if resource not in self._locks:
            self._locks[resource] = threading.Lock()
            self._waiters[resource] = []
        
        agent_priority = AGENT_PRIORITIES.get(agent, AgentConfig(agent, Priority.NORMAL))
        
        # Check if we can preempt current owner
        current_owner = self._owners.get(resource)
        if current_owner:
            owner_config = AGENT_PRIORITIES.get(current_owner, AgentConfig(current_owner, Priority.NORMAL))
            if agent_priority.priority < owner_config.priority and agent_priority.can_preempt:
                # Preempt lower priority agent
                self._preempt(resource, current_owner)
        
        acquired = self._locks[resource].acquire(timeout=timeout)
        if acquired:
            self._owners[resource] = agent
        return acquired
    
    def release(self, resource: str, agent: str):
        """Release resource."""
        if self._owners.get(resource) == agent:
            self._owners[resource] = None
            if resource in self._locks:
                try:
                    self._locks[resource].release()
                except RuntimeError:
                    pass
    
    def _preempt(self, resource: str, agent: str):
        """Force agent to release resource."""
        logger.warning(f"Preempting {{agent}} from resource {{resource}}")
        # Signal agent to release (implementation depends on agent framework)


# Deadlock prevention through ordered locking
def acquire_ordered(resources: list[str], agent: str, manager: PriorityResourceManager) -> bool:
    """Acquire multiple resources in consistent order to prevent deadlock."""
    sorted_resources = sorted(resources)  # Canonical ordering
    acquired = []
    
    try:
        for resource in sorted_resources:
            if not manager.acquire(resource, agent):
                raise DeadlockPreventionError(f"Could not acquire {{resource}}")
            acquired.append(resource)
        return True
    except (ValueError, TypeError, KeyError) as e:
        # Rollback on failure
        logger.warning(f"Resource acquisition failed: {{e}}")
        for resource in reversed(acquired):
            manager.release(resource, agent)
        raise'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="coordination_deadlock",
            fix_type=FixType.PRIORITY_ADJUSTMENT,
            confidence=FixConfidence.MEDIUM,
            title="Add priority-based resource allocation",
            description="Assign priorities to agents and use ordered resource acquisition to prevent and break deadlocks.",
            rationale="Deadlocks occur when multiple agents wait for resources held by each other. Priority-based allocation and ordered locking prevent this.",
            code_changes=[
                CodeChange(
                    file_path="utils/priority_manager.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Priority-based resource manager with deadlock prevention",
                )
            ],
            estimated_impact="Prevents resource deadlocks through priority ordering",
            tags=["deadlock", "priority", "resource-management"],
        )
    
    def _async_handoff_fix(
        self,
        detection_id: str,
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
import uuid

@dataclass
class TaskHandoff:
    task_id: str
    from_agent: str
    to_agent: str
    payload: Dict[str, Any]
    callback_queue: str

class AsyncHandoffManager:
    """
    Manage async task handoffs between agents to prevent blocking.
    Uses message queues instead of synchronous calls.
    """
    
    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._pending: Dict[str, asyncio.Future] = {}
    
    def _get_queue(self, agent: str) -> asyncio.Queue:
        if agent not in self._queues:
            self._queues[agent] = asyncio.Queue()
        return self._queues[agent]
    
    async def handoff(
        self,
        from_agent: str,
        to_agent: str,
        payload: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Hand off a task to another agent without blocking.
        Returns a future that resolves when the task is complete.
        """
        task_id = str(uuid.uuid4())
        callback_queue = f"callback_{task_id}"
        
        handoff = TaskHandoff(
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            payload=payload,
            callback_queue=callback_queue,
        )
        
        # Create callback queue and future
        self._queues[callback_queue] = asyncio.Queue()
        future = asyncio.get_event_loop().create_future()
        self._pending[task_id] = future
        
        # Send to target agent's queue
        await self._get_queue(to_agent).put(handoff)
        
        # Wait for response with timeout
        try:
            result = await asyncio.wait_for(
                self._queues[callback_queue].get(),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            return {"error": "handoff_timeout", "task_id": task_id}
        finally:
            del self._queues[callback_queue]
            del self._pending[task_id]
    
    async def receive(self, agent: str) -> Optional[TaskHandoff]:
        """Receive next task for an agent."""
        try:
            return await asyncio.wait_for(
                self._get_queue(agent).get(),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            return None
    
    async def complete(self, task_id: str, result: Dict[str, Any]):
        """Complete a task and send result back."""
        callback_queue = f"callback_{task_id}"
        if callback_queue in self._queues:
            await self._queues[callback_queue].put(result)


# Usage pattern
handoff_manager = AsyncHandoffManager()

async def coordinator_agent(state: dict):
    # Instead of calling researcher directly (can deadlock)
    # Use async handoff
    result = await handoff_manager.handoff(
        from_agent="coordinator",
        to_agent="researcher",
        payload={"query": state["query"]},
        timeout=60.0,
    )
    
    if "error" in result:
        # Handle timeout/failure gracefully
        return {"status": "partial", "reason": result["error"]}
    
    return {"research_result": result}

async def researcher_agent():
    while True:
        task = await handoff_manager.receive("researcher")
        if task:
            result = await do_research(task.payload)
            await handoff_manager.complete(task.task_id, result)'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="coordination_deadlock",
            fix_type=FixType.ASYNC_HANDOFF,
            confidence=FixConfidence.HIGH,
            title="Replace synchronous calls with async handoffs",
            description="Use message queues for agent-to-agent communication instead of blocking calls.",
            rationale="Synchronous inter-agent calls can deadlock when agents wait on each other. Async handoffs with timeouts prevent blocking.",
            code_changes=[
                CodeChange(
                    file_path="utils/handoff.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Async task handoff manager for non-blocking agent communication",
                )
            ],
            estimated_impact="Eliminates synchronous deadlocks between agents",
            tags=["deadlock", "async", "message-queue"],
        )
    
    def _dependency_resolver_fix(
        self,
        detection_id: str,
        waiting_agents: List[str],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Dict, Set, List, Optional
from dataclasses import dataclass, field

@dataclass
class DependencyNode:
    agent: str
    waiting_for: Set[str] = field(default_factory=set)
    waited_by: Set[str] = field(default_factory=set)

class DependencyGraph:
    """Track and detect circular dependencies between agents."""
    
    def __init__(self):
        self.nodes: Dict[str, DependencyNode] = {}
    
    def add_dependency(self, agent: str, depends_on: str) -> Optional[List[str]]:
        """
        Add a dependency. Returns cycle if one is created.
        """
        if agent not in self.nodes:
            self.nodes[agent] = DependencyNode(agent)
        if depends_on not in self.nodes:
            self.nodes[depends_on] = DependencyNode(depends_on)
        
        # Check for cycle BEFORE adding
        cycle = self._find_cycle(depends_on, agent)
        if cycle:
            return cycle
        
        self.nodes[agent].waiting_for.add(depends_on)
        self.nodes[depends_on].waited_by.add(agent)
        return None
    
    def remove_dependency(self, agent: str, depends_on: str):
        """Remove a dependency when satisfied."""
        if agent in self.nodes:
            self.nodes[agent].waiting_for.discard(depends_on)
        if depends_on in self.nodes:
            self.nodes[depends_on].waited_by.discard(agent)
    
    def _find_cycle(self, start: str, target: str, visited: Set[str] = None) -> Optional[List[str]]:
        """DFS to find cycle from start back to target."""
        if visited is None:
            visited = set()
        
        if start == target:
            return [start]
        
        if start in visited:
            return None
        
        visited.add(start)
        
        if start in self.nodes:
            for dep in self.nodes[start].waiting_for:
                cycle = self._find_cycle(dep, target, visited)
                if cycle:
                    return [start] + cycle
        
        return None
    
    def detect_deadlock(self) -> Optional[List[str]]:
        """Detect any deadlock cycle in the graph."""
        for agent in self.nodes:
            for dep in self.nodes[agent].waiting_for:
                cycle = self._find_cycle(dep, agent, set())
                if cycle:
                    return [agent] + cycle
        return None


class DeadlockResolver:
    """Resolve detected deadlocks."""
    
    def __init__(self, graph: DependencyGraph):
        self.graph = graph
    
    def resolve(self, cycle: List[str]) -> str:
        """
        Resolve deadlock by breaking the weakest link.
        Returns the agent that should abort.
        """
        # Strategy: abort the agent with lowest priority or newest request
        priorities = {agent: self._get_priority(agent) for agent in cycle}
        victim = max(priorities, key=priorities.get)  # Lowest priority = highest number
        
        # Remove victim's dependencies
        node = self.graph.nodes.get(victim)
        if node:
            for dep in list(node.waiting_for):
                self.graph.remove_dependency(victim, dep)
        
        return victim
    
    def _get_priority(self, agent: str) -> int:
        # Lower number = higher priority
        priority_map = {"coordinator": 0, "validator": 1}
        return priority_map.get(agent, 10)


# Usage
dependency_graph = DependencyGraph()
resolver = DeadlockResolver(dependency_graph)

async def wait_for_agent(waiting_agent: str, target_agent: str):
    cycle = dependency_graph.add_dependency(waiting_agent, target_agent)
    
    if cycle:
        victim = resolver.resolve(cycle)
        if victim == waiting_agent:
            raise DeadlockAbortError(f"{waiting_agent} aborted to break deadlock")
        # Otherwise, continue - someone else was aborted
    
    try:
        result = await actually_wait_for(target_agent)
        return result
    finally:
        dependency_graph.remove_dependency(waiting_agent, target_agent)'''
        
        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="coordination_deadlock",
            fix_type=FixType.TIMEOUT_ADDITION,
            confidence=FixConfidence.MEDIUM,
            title="Add dependency graph for cycle detection",
            description="Track agent dependencies and detect/resolve circular waits before they cause deadlocks.",
            rationale="Proactive cycle detection catches deadlocks at the moment they would form, allowing immediate resolution instead of timeout-based detection.",
            code_changes=[
                CodeChange(
                    file_path="utils/dependency_graph.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Dependency tracking with cycle detection and resolution",
                )
            ],
            estimated_impact="Prevents deadlocks proactively instead of detecting after the fact",
            tags=["deadlock", "dependency", "cycle-detection"],
        )
