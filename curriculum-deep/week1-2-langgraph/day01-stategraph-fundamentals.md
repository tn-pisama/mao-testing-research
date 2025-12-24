# Day 1: StateGraph Fundamentals

**Duration:** 4-6 hours
**Outcome:** Complete understanding of LangGraph's core abstraction

---

## 1. The Mental Model

### What is LangGraph?

LangGraph is a **stateful orchestration framework** built on top of LangChain. It models agent workflows as **directed graphs** where:

- **Nodes** = Functions that transform state
- **Edges** = Transitions between nodes
- **State** = Typed data passed through the graph

```
┌─────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH MENTAL MODEL                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Traditional LLM:     input ──► LLM ──► output                  │
│                                                                  │
│  LangChain Chain:     input ──► prompt ──► LLM ──► parser ──► out│
│                                                                  │
│  LangGraph:           ┌─────────────────────────────────┐       │
│                       │         STATE MACHINE            │       │
│                       │                                  │       │
│                       │   ┌───┐    ┌───┐    ┌───┐       │       │
│                       │   │ A │───►│ B │───►│ C │       │       │
│                       │   └───┘    └─┬─┘    └───┘       │       │
│                       │              │                   │       │
│                       │              ▼                   │       │
│                       │            ┌───┐                │       │
│                       │            │ D │                │       │
│                       │            └───┘                │       │
│                       │                                  │       │
│                       │   State flows through edges     │       │
│                       │   Conditional routing possible   │       │
│                       │   Checkpointing built-in        │       │
│                       └─────────────────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Why Graphs?

| Problem | How Graphs Solve It |
|---------|---------------------|
| Complex control flow | Conditional edges, cycles |
| State management | Typed state schemas, reducers |
| Debugging | Checkpoint inspection, replay |
| Human oversight | Interrupt nodes, approval gates |
| Error recovery | State persistence, retry from checkpoint |

---

## 2. Core Components Deep Dive

### 2.1 StateGraph Class

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
import operator

# StateGraph is the main class - parameterized by state type
graph = StateGraph(MyStateType)
```

**Constructor parameters:**

```python
StateGraph(
    state_schema: Type[Any],           # The TypedDict defining state shape
    config_schema: Type[Any] = None,   # Optional config passed at runtime
)
```

### 2.2 State Schemas

State schemas define what data flows through your graph. Use `TypedDict` for type safety:

```python
from typing import TypedDict, Annotated, List, Optional
import operator

class BasicState(TypedDict):
    """Simple state with messages"""
    messages: List[str]
    current_step: str
    
class AnnotatedState(TypedDict):
    """State with reducers for merge behavior"""
    # Annotated fields define HOW updates are merged
    messages: Annotated[List[str], operator.add]  # Append new messages
    count: Annotated[int, operator.add]           # Sum counts
    
    # Non-annotated fields are replaced entirely
    current_agent: str
    is_complete: bool
```

**Reducer behavior:**

```python
# With operator.add on a list:
# State: {"messages": ["a", "b"]}
# Update: {"messages": ["c"]}
# Result: {"messages": ["a", "b", "c"]}  # APPENDED

# Without annotation:
# State: {"current_agent": "researcher"}
# Update: {"current_agent": "writer"}
# Result: {"current_agent": "writer"}  # REPLACED
```

### 2.3 Nodes

Nodes are functions that take state and return state updates:

```python
def my_node(state: MyState) -> dict:
    """
    Node function signature:
    - Input: Current state (full state object)
    - Output: Dict of state updates (partial, merged according to reducers)
    """
    # Read from state
    messages = state["messages"]
    
    # Do something
    new_message = process(messages)
    
    # Return updates (not full state!)
    return {"messages": [new_message]}

# Add node to graph
graph.add_node("my_node", my_node)
```

**Node patterns:**

```python
# Pattern 1: Simple function
def simple_node(state):
    return {"result": compute(state["input"])}

# Pattern 2: Class with __call__
class AgentNode:
    def __init__(self, llm, tools):
        self.agent = create_agent(llm, tools)
    
    def __call__(self, state):
        result = self.agent.invoke(state["messages"])
        return {"messages": [result]}

# Pattern 3: Async function
async def async_node(state):
    result = await async_operation(state["input"])
    return {"output": result}

# Adding nodes
graph.add_node("simple", simple_node)
graph.add_node("agent", AgentNode(llm, tools))
graph.add_node("async_op", async_node)
```

### 2.4 Edges

Edges define transitions between nodes:

```python
# Simple edge: A -> B (always)
graph.add_edge("node_a", "node_b")

# Entry point: START -> A
graph.add_edge(START, "node_a")

# Exit point: B -> END
graph.add_edge("node_b", END)
```

**Conditional edges:**

```python
from langgraph.graph import END

def router(state: MyState) -> str:
    """
    Router function:
    - Input: Current state
    - Output: Name of next node (string)
    """
    if state["is_complete"]:
        return END
    elif state["needs_research"]:
        return "researcher"
    else:
        return "writer"

# Add conditional edge
graph.add_conditional_edges(
    "router_node",      # Source node
    router,             # Router function
    {                   # Mapping (optional but recommended)
        END: END,
        "researcher": "researcher",
        "writer": "writer",
    }
)
```

---

## 3. Complete Working Examples

### Example 1: Simple Linear Graph

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class State(TypedDict):
    input: str
    processed: str
    output: str

def step_1(state: State) -> dict:
    return {"processed": state["input"].upper()}

def step_2(state: State) -> dict:
    return {"output": f"Result: {state['processed']}"}

# Build graph
graph = StateGraph(State)
graph.add_node("step_1", step_1)
graph.add_node("step_2", step_2)

graph.add_edge(START, "step_1")
graph.add_edge("step_1", "step_2")
graph.add_edge("step_2", END)

# Compile and run
app = graph.compile()
result = app.invoke({"input": "hello", "processed": "", "output": ""})
print(result)
# {'input': 'hello', 'processed': 'HELLO', 'output': 'Result: HELLO'}
```

### Example 2: Conditional Branching

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Literal

class State(TypedDict):
    query: str
    query_type: str
    result: str

def classifier(state: State) -> dict:
    """Classify the query type"""
    query = state["query"].lower()
    if "weather" in query:
        return {"query_type": "weather"}
    elif "calculate" in query or "math" in query:
        return {"query_type": "math"}
    else:
        return {"query_type": "general"}

def weather_handler(state: State) -> dict:
    return {"result": f"Weather info for: {state['query']}"}

def math_handler(state: State) -> dict:
    return {"result": f"Math result for: {state['query']}"}

def general_handler(state: State) -> dict:
    return {"result": f"General answer for: {state['query']}"}

def route_query(state: State) -> Literal["weather", "math", "general"]:
    return state["query_type"]

# Build graph
graph = StateGraph(State)

graph.add_node("classifier", classifier)
graph.add_node("weather", weather_handler)
graph.add_node("math", math_handler)
graph.add_node("general", general_handler)

graph.add_edge(START, "classifier")
graph.add_conditional_edges(
    "classifier",
    route_query,
    {
        "weather": "weather",
        "math": "math",
        "general": "general",
    }
)
graph.add_edge("weather", END)
graph.add_edge("math", END)
graph.add_edge("general", END)

# Compile and test
app = graph.compile()

print(app.invoke({"query": "What's the weather?", "query_type": "", "result": ""}))
# {'query': "What's the weather?", 'query_type': 'weather', 'result': "Weather info for: What's the weather?"}

print(app.invoke({"query": "Calculate 2+2", "query_type": "", "result": ""}))
# {'query': 'Calculate 2+2', 'query_type': 'math', 'result': 'Math result for: Calculate 2+2'}
```

### Example 3: Cyclic Graph (Loop)

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated, List
import operator

class State(TypedDict):
    messages: Annotated[List[str], operator.add]
    iteration: int
    max_iterations: int

def process(state: State) -> dict:
    msg = f"Processing iteration {state['iteration']}"
    return {
        "messages": [msg],
        "iteration": state["iteration"] + 1
    }

def should_continue(state: State) -> str:
    if state["iteration"] >= state["max_iterations"]:
        return END
    return "process"

# Build graph with cycle
graph = StateGraph(State)
graph.add_node("process", process)

graph.add_edge(START, "process")
graph.add_conditional_edges("process", should_continue)

app = graph.compile()

result = app.invoke({
    "messages": [],
    "iteration": 0,
    "max_iterations": 3
})
print(result["messages"])
# ['Processing iteration 0', 'Processing iteration 1', 'Processing iteration 2']
```

---

## 4. State Update Semantics (Critical!)

Understanding how state updates work is **critical** for avoiding bugs:

```python
from typing import TypedDict, Annotated, List
import operator

class State(TypedDict):
    # WITH reducer: values are MERGED
    messages: Annotated[List[str], operator.add]
    total: Annotated[int, operator.add]
    
    # WITHOUT reducer: values are REPLACED
    current_status: str
    config: dict

def node_a(state: State) -> dict:
    return {
        "messages": ["from A"],     # APPENDS to existing messages
        "total": 10,                # ADDS to existing total
        "current_status": "in_a",   # REPLACES current_status
        # config not returned = unchanged
    }

def node_b(state: State) -> dict:
    return {
        "messages": ["from B"],     # APPENDS again
        "total": 5,                 # ADDS again
        "current_status": "in_b",   # REPLACES again
    }

# After node_a: messages=["from A"], total=10, current_status="in_a"
# After node_b: messages=["from A", "from B"], total=15, current_status="in_b"
```

**Common reducer functions:**

```python
import operator
from typing import Annotated, List, Set

# Append to list
messages: Annotated[List[str], operator.add]

# Sum numbers
count: Annotated[int, operator.add]

# Union sets
tags: Annotated[Set[str], lambda a, b: a | b]

# Keep latest (explicit replace)
status: Annotated[str, lambda a, b: b]

# Keep first non-None
result: Annotated[str, lambda a, b: a if a is not None else b]

# Custom merge logic
def merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}
metadata: Annotated[dict, merge_dicts]
```

---

## 5. Graph Compilation

Compiling transforms the graph definition into an executable:

```python
# Basic compilation
app = graph.compile()

# With checkpointing (enables state persistence)
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
app = graph.compile(checkpointer=memory)

# With interrupt points (human-in-the-loop)
app = graph.compile(
    checkpointer=memory,
    interrupt_before=["human_review"],  # Pause BEFORE this node
    interrupt_after=["generate"],       # Pause AFTER this node
)
```

---

## 6. Invocation Methods

```python
# Basic invoke (blocking, returns final state)
result = app.invoke(initial_state)

# With config (thread_id for checkpointing)
result = app.invoke(
    initial_state,
    config={"configurable": {"thread_id": "user-123"}}
)

# Streaming (yields state after each node)
for state in app.stream(initial_state):
    print(f"Current state: {state}")

# Async invoke
result = await app.ainvoke(initial_state)

# Async streaming
async for state in app.astream(initial_state):
    print(f"Current state: {state}")
```

---

## 7. Exercises

### Exercise 1.1: Build a Three-Step Pipeline
Create a graph that:
1. Takes a topic string
2. Node 1: Generates 3 questions about the topic
3. Node 2: Picks the best question
4. Node 3: Formats the output

### Exercise 1.2: Conditional Router
Create a graph that:
1. Takes a user message
2. Classifies it as: question, command, or statement
3. Routes to different handler nodes
4. Returns appropriate response

### Exercise 1.3: Retry Loop
Create a graph that:
1. Attempts an operation
2. If it fails (simulated), retries up to 3 times
3. Tracks attempt count in state
4. Returns success or failure

---

## 8. Common Mistakes

```python
# MISTAKE 1: Returning full state instead of updates
def bad_node(state: State) -> State:
    state["messages"].append("new")  # WRONG: mutating state
    return state                      # WRONG: returning full state

def good_node(state: State) -> dict:
    return {"messages": ["new"]}      # RIGHT: return updates only

# MISTAKE 2: Forgetting reducers cause append
class State(TypedDict):
    items: Annotated[List[str], operator.add]

def node(state):
    return {"items": state["items"] + ["new"]}  # WRONG: will double-append
    return {"items": ["new"]}                    # RIGHT: reducer handles append

# MISTAKE 3: Not handling missing state keys
def fragile_node(state: State) -> dict:
    return {"output": state["input"].upper()}  # Crashes if "input" missing

def robust_node(state: State) -> dict:
    input_val = state.get("input", "")
    return {"output": input_val.upper()}

# MISTAKE 4: Infinite loops without exit condition
def router(state):
    return "process"  # WRONG: no exit condition ever

def router(state):
    if state["done"]:
        return END    # RIGHT: has exit condition
    return "process"
```

---

## 9. Key Takeaways

1. **StateGraph** = directed graph where nodes transform typed state
2. **State schemas** use TypedDict with optional Annotated reducers
3. **Nodes** return partial updates, not full state
4. **Reducers** define merge behavior (add, replace, custom)
5. **Edges** can be unconditional or conditional (router functions)
6. **Compile** transforms definition into executable
7. **Invoke** runs the graph, **stream** yields intermediate states

---

## 10. Further Reading

- LangGraph Conceptual Guide: https://langchain-ai.github.io/langgraph/concepts/
- StateGraph API Reference: https://langchain-ai.github.io/langgraph/reference/graphs/
- State Management Deep Dive: https://langchain-ai.github.io/langgraph/concepts/low_level/

---

**Next:** Day 2 - State Schemas and Reducers (Advanced)
