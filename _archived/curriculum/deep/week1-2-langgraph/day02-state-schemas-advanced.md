# Day 2: State Schemas and Reducers (Advanced)

**Duration:** 4-6 hours
**Outcome:** Master complex state management patterns

---

## 1. State Schema Design Principles

### The State Design Checklist

Before writing code, answer these questions:

```
□ What data needs to persist across nodes?
□ Which fields should accumulate (append) vs replace?
□ What's the maximum size of accumulated data?
□ How will you handle errors/failures in state?
□ What validation is needed on state fields?
□ How will concurrent updates be handled?
```

### State Schema Patterns

```python
from typing import TypedDict, Annotated, List, Optional, Any
from datetime import datetime
import operator

# PATTERN 1: Message-Based State (Chat/Agent)
class MessageState(TypedDict):
    messages: Annotated[List[dict], operator.add]
    
# PATTERN 2: Pipeline State (Sequential Processing)
class PipelineState(TypedDict):
    input: str
    stage_1_output: Optional[str]
    stage_2_output: Optional[str]
    final_output: Optional[str]
    current_stage: str

# PATTERN 3: Research State (Accumulating Knowledge)
class ResearchState(TypedDict):
    query: str
    sources: Annotated[List[dict], operator.add]
    findings: Annotated[List[str], operator.add]
    synthesis: Optional[str]
    confidence: float

# PATTERN 4: Workflow State (Multi-Agent Coordination)
class WorkflowState(TypedDict):
    task: str
    assigned_agent: str
    agent_outputs: Annotated[dict, lambda a, b: {**a, **b}]
    status: str
    iteration: int
    max_iterations: int

# PATTERN 5: Error-Aware State
class RobustState(TypedDict):
    input: str
    output: Optional[str]
    error: Optional[str]
    error_count: Annotated[int, operator.add]
    retry_count: int
    status: str  # "pending", "processing", "success", "failed"
```

---

## 2. Custom Reducers Deep Dive

### Built-in Reducer Functions

```python
import operator
from typing import Annotated, List, Set, Dict

# operator.add - Works on lists, numbers, strings
messages: Annotated[List[str], operator.add]    # ["a"] + ["b"] = ["a", "b"]
count: Annotated[int, operator.add]             # 5 + 3 = 8
text: Annotated[str, operator.add]              # "a" + "b" = "ab"

# operator.or_ - Works on sets, bools
flags: Annotated[Set[str], operator.or_]        # {"a"} | {"b"} = {"a", "b"}

# operator.and_ - Works on sets, bools
common: Annotated[Set[str], operator.and_]      # {"a","b"} & {"b","c"} = {"b"}
```

### Custom Reducer Examples

```python
from typing import Annotated, List, Dict, Any, Optional
from dataclasses import dataclass
import json

# REDUCER 1: Keep Latest Non-None
def keep_latest_non_none(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the most recent non-None value"""
    return new if new is not None else existing

result: Annotated[Optional[str], keep_latest_non_none]


# REDUCER 2: Merge Dicts (Shallow)
def merge_dicts(existing: Dict, new: Dict) -> Dict:
    """Shallow merge, new values override"""
    return {**existing, **new}

metadata: Annotated[Dict[str, Any], merge_dicts]


# REDUCER 3: Merge Dicts (Deep)
def deep_merge(existing: Dict, new: Dict) -> Dict:
    """Deep merge nested dicts"""
    result = existing.copy()
    for key, value in new.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

config: Annotated[Dict[str, Any], deep_merge]


# REDUCER 4: Bounded List (Prevent Memory Explosion)
def bounded_append(existing: List, new: List, max_size: int = 100) -> List:
    """Append but keep only last N items"""
    combined = existing + new
    return combined[-max_size:]

# Create a factory for parameterized reducers
def make_bounded_reducer(max_size: int):
    def reducer(existing: List, new: List) -> List:
        return (existing + new)[-max_size:]
    return reducer

recent_messages: Annotated[List[str], make_bounded_reducer(50)]


# REDUCER 5: Timestamped Updates
from datetime import datetime

def timestamped_update(existing: Dict, new: Dict) -> Dict:
    """Track when each field was last updated"""
    result = existing.copy()
    now = datetime.utcnow().isoformat()
    for key, value in new.items():
        result[key] = {"value": value, "updated_at": now}
    return result


# REDUCER 6: Versioned History
def keep_history(existing: List[Dict], new: List[Dict], max_versions: int = 10) -> List[Dict]:
    """Keep version history of changes"""
    combined = existing + new
    return combined[-max_versions:]


# REDUCER 7: Priority Queue
def priority_merge(existing: List[tuple], new: List[tuple]) -> List[tuple]:
    """Merge and sort by priority (first element of tuple)"""
    import heapq
    combined = existing + new
    heapq.heapify(combined)
    return combined


# REDUCER 8: Deduplication
def dedupe_append(existing: List[str], new: List[str]) -> List[str]:
    """Append only items not already present"""
    seen = set(existing)
    result = existing.copy()
    for item in new:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result

unique_tags: Annotated[List[str], dedupe_append]
```

---

## 3. Complex State Schemas

### Multi-Agent Coordination State

```python
from typing import TypedDict, Annotated, List, Dict, Optional, Literal
from datetime import datetime
import operator

AgentRole = Literal["researcher", "writer", "reviewer", "editor"]
TaskStatus = Literal["pending", "in_progress", "completed", "failed", "blocked"]

class AgentMessage(TypedDict):
    """Individual message from an agent"""
    agent: str
    role: AgentRole
    content: str
    timestamp: str
    metadata: Optional[Dict]

class TaskAssignment(TypedDict):
    """Task assigned to an agent"""
    task_id: str
    agent: str
    description: str
    dependencies: List[str]
    status: TaskStatus
    result: Optional[str]

def merge_task_results(existing: Dict[str, TaskAssignment], new: Dict[str, TaskAssignment]) -> Dict[str, TaskAssignment]:
    """Merge task results, preserving completed tasks"""
    result = existing.copy()
    for task_id, task in new.items():
        if task_id in result:
            # Only update if new status is more advanced
            status_order = ["pending", "in_progress", "completed", "failed", "blocked"]
            existing_order = status_order.index(result[task_id]["status"])
            new_order = status_order.index(task["status"])
            if new_order >= existing_order:
                result[task_id] = task
        else:
            result[task_id] = task
    return result

class MultiAgentState(TypedDict):
    """Comprehensive multi-agent coordination state"""
    
    # Task management
    main_objective: str
    tasks: Annotated[Dict[str, TaskAssignment], merge_task_results]
    task_order: List[str]  # Execution order
    
    # Communication
    messages: Annotated[List[AgentMessage], operator.add]
    
    # Agent status
    active_agent: Optional[str]
    agent_states: Annotated[Dict[str, Dict], lambda a, b: {**a, **b}]
    
    # Coordination
    blocking_tasks: List[str]
    completed_tasks: Annotated[List[str], operator.add]
    
    # Control flow
    iteration: int
    max_iterations: int
    status: TaskStatus
    
    # Artifacts
    artifacts: Annotated[Dict[str, str], lambda a, b: {**a, **b}]
    
    # Error handling
    errors: Annotated[List[Dict], operator.add]
    retry_counts: Annotated[Dict[str, int], lambda a, b: {**a, **{k: a.get(k, 0) + v for k, v in b.items()}}]
```

### Research Pipeline State

```python
from typing import TypedDict, Annotated, List, Dict, Optional
import operator

class Source(TypedDict):
    url: str
    title: str
    content: str
    relevance_score: float
    fetched_at: str

class Finding(TypedDict):
    claim: str
    evidence: str
    source_urls: List[str]
    confidence: float

class ResearchPipelineState(TypedDict):
    """State for a comprehensive research pipeline"""
    
    # Input
    research_question: str
    scope: str
    constraints: Dict[str, Any]
    
    # Search phase
    search_queries: Annotated[List[str], operator.add]
    search_results: Annotated[List[Dict], operator.add]
    
    # Fetch phase
    sources: Annotated[List[Source], operator.add]
    failed_urls: Annotated[List[str], operator.add]
    
    # Analysis phase
    findings: Annotated[List[Finding], operator.add]
    contradictions: Annotated[List[Dict], operator.add]
    gaps: Annotated[List[str], operator.add]
    
    # Synthesis phase
    outline: Optional[str]
    draft: Optional[str]
    final_report: Optional[str]
    
    # Quality metrics
    source_count: int
    finding_count: int
    confidence_score: float
    
    # Control
    current_phase: str
    phases_completed: Annotated[List[str], operator.add]
    errors: Annotated[List[Dict], operator.add]
```

---

## 4. State Validation

### Using Pydantic for Validation

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class ValidatedMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system|tool)$")
    content: str = Field(..., min_length=1, max_length=100000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('content')
    def content_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Content cannot be empty or whitespace only')
        return v

class ValidatedState(BaseModel):
    """Pydantic model for state validation"""
    messages: List[ValidatedMessage] = Field(default_factory=list)
    current_agent: str = Field(..., min_length=1)
    iteration: int = Field(ge=0, le=1000)
    max_iterations: int = Field(ge=1, le=100)
    
    @validator('max_iterations')
    def max_greater_than_current(cls, v, values):
        if 'iteration' in values and v <= values['iteration']:
            raise ValueError('max_iterations must be greater than iteration')
        return v

# Usage in node
def validated_node(state: dict) -> dict:
    """Node that validates input and output"""
    # Validate input
    validated = ValidatedState(**state)
    
    # Process
    new_message = ValidatedMessage(
        role="assistant",
        content="Response"
    )
    
    # Return validated update
    return {
        "messages": [new_message.dict()],
        "iteration": validated.iteration + 1
    }
```

### Runtime Validation Node

```python
from typing import TypedDict, List, Dict, Any

class State(TypedDict):
    data: Dict[str, Any]
    errors: List[str]
    is_valid: bool

def validation_node(state: State) -> dict:
    """Generic validation node"""
    errors = []
    data = state["data"]
    
    # Validation rules
    required_fields = ["name", "value", "type"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    if "value" in data:
        if not isinstance(data["value"], (int, float)):
            errors.append("Value must be numeric")
        elif data["value"] < 0:
            errors.append("Value must be non-negative")
    
    if "type" in data:
        valid_types = ["A", "B", "C"]
        if data["type"] not in valid_types:
            errors.append(f"Type must be one of: {valid_types}")
    
    return {
        "errors": errors,
        "is_valid": len(errors) == 0
    }
```

---

## 5. State Persistence Patterns

### Serialization for Checkpointing

```python
import json
from datetime import datetime
from typing import Any, Dict

class StateSerializer:
    """Custom serialization for complex state objects"""
    
    @staticmethod
    def serialize(state: Dict[str, Any]) -> str:
        """Convert state to JSON string"""
        def default(obj):
            if isinstance(obj, datetime):
                return {"__datetime__": obj.isoformat()}
            if isinstance(obj, set):
                return {"__set__": list(obj)}
            if hasattr(obj, "__dict__"):
                return {"__class__": obj.__class__.__name__, **obj.__dict__}
            raise TypeError(f"Cannot serialize {type(obj)}")
        
        return json.dumps(state, default=default)
    
    @staticmethod
    def deserialize(json_str: str) -> Dict[str, Any]:
        """Convert JSON string back to state"""
        def object_hook(obj):
            if "__datetime__" in obj:
                return datetime.fromisoformat(obj["__datetime__"])
            if "__set__" in obj:
                return set(obj["__set__"])
            return obj
        
        return json.loads(json_str, object_hook=object_hook)

# Usage with checkpointer
from langgraph.checkpoint.memory import MemorySaver

class CustomCheckpointer(MemorySaver):
    """Checkpointer with custom serialization"""
    
    def put(self, config, checkpoint, metadata):
        # Serialize before storing
        serialized = StateSerializer.serialize(checkpoint)
        super().put(config, serialized, metadata)
    
    def get(self, config):
        # Deserialize after retrieving
        data = super().get(config)
        if data:
            return StateSerializer.deserialize(data)
        return None
```

---

## 6. State Size Management

### Preventing State Explosion

```python
from typing import TypedDict, Annotated, List, Dict
import sys

def bounded_list_reducer(max_items: int, max_bytes: int = 1_000_000):
    """Create a reducer that bounds list size by count and memory"""
    def reducer(existing: List, new: List) -> List:
        combined = existing + new
        
        # Bound by count
        if len(combined) > max_items:
            combined = combined[-max_items:]
        
        # Bound by memory (rough estimate)
        while sys.getsizeof(combined) > max_bytes and len(combined) > 1:
            combined = combined[1:]  # Remove oldest
        
        return combined
    return reducer

def summarizing_reducer(summarize_fn, threshold: int = 100):
    """Reducer that summarizes when list gets too long"""
    def reducer(existing: List, new: List) -> List:
        combined = existing + new
        
        if len(combined) > threshold:
            # Keep last 10 items, summarize the rest
            to_summarize = combined[:-10]
            recent = combined[-10:]
            
            summary = summarize_fn(to_summarize)
            return [{"type": "summary", "content": summary}] + recent
        
        return combined
    return reducer

class BoundedState(TypedDict):
    """State with memory-safe reducers"""
    # Max 1000 messages, max 1MB
    messages: Annotated[List[Dict], bounded_list_reducer(1000, 1_000_000)]
    
    # Summarize when over 100 items
    history: Annotated[List[str], summarizing_reducer(
        lambda items: f"Summary of {len(items)} previous items",
        threshold=100
    )]
```

### Token-Aware State Management

```python
import tiktoken

def token_bounded_reducer(max_tokens: int = 100000, model: str = "gpt-4"):
    """Reducer that bounds by token count"""
    encoding = tiktoken.encoding_for_model(model)
    
    def count_tokens(items: List[Dict]) -> int:
        total = 0
        for item in items:
            if isinstance(item, dict) and "content" in item:
                total += len(encoding.encode(str(item["content"])))
            else:
                total += len(encoding.encode(str(item)))
        return total
    
    def reducer(existing: List[Dict], new: List[Dict]) -> List[Dict]:
        combined = existing + new
        
        while count_tokens(combined) > max_tokens and len(combined) > 1:
            combined = combined[1:]  # Remove oldest
        
        return combined
    
    return reducer

class TokenAwareState(TypedDict):
    """State that respects token limits"""
    messages: Annotated[List[Dict], token_bounded_reducer(50000)]
```

---

## 7. Exercises

### Exercise 2.1: Design State for Code Review System
Design a state schema for a multi-agent code review system with:
- Reviewer agent, Security agent, Performance agent
- Track findings by category
- Accumulate suggestions
- Track which files have been reviewed
- Handle approval/rejection workflow

### Exercise 2.2: Implement Custom Reducer
Create a reducer that:
- Deduplicates by a specific field (e.g., "id")
- Keeps the most recent version when duplicates found
- Maintains insertion order

### Exercise 2.3: Token-Limited Conversation
Implement a state schema and reducer that:
- Keeps conversation history within token limit
- Summarizes old messages when limit approached
- Preserves system message and recent messages

---

## 8. Common Pitfalls

```python
# PITFALL 1: Mutable default in TypedDict
class BadState(TypedDict):
    items: List[str] = []  # WRONG: shared mutable default

# Fix: No defaults in TypedDict, set in initial state
class GoodState(TypedDict):
    items: List[str]

initial_state = {"items": []}  # Set default here

# PITFALL 2: Reducer modifies existing value
def bad_reducer(existing: List, new: List) -> List:
    existing.extend(new)  # WRONG: mutates existing
    return existing

def good_reducer(existing: List, new: List) -> List:
    return existing + new  # RIGHT: creates new list

# PITFALL 3: Non-deterministic reducers
import random
def bad_reducer(existing: List, new: List) -> List:
    return random.sample(existing + new, len(existing + new))  # WRONG: non-deterministic

# PITFALL 4: Reducer raises exceptions
def bad_reducer(existing: int, new: int) -> int:
    return existing / new  # WRONG: can raise ZeroDivisionError

def good_reducer(existing: int, new: int) -> int:
    if new == 0:
        return existing
    return existing / new
```

---

## 9. Key Takeaways

1. **Design state schemas before coding** - think about accumulation vs replacement
2. **Use custom reducers** for complex merge logic
3. **Bound your state** - prevent memory explosion
4. **Validate state** - use Pydantic or custom validators
5. **Handle serialization** - datetime, sets, custom objects
6. **Test reducers independently** - they're pure functions
7. **Monitor state size** - especially in long-running graphs

---

**Next:** Day 3 - Conditional Edges and Routing Patterns
