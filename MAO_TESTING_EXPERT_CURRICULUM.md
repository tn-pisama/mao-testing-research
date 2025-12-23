# Multi-Agent Orchestration Testing
## Accelerated Expert Curriculum: 10 Days

**Goal**: Become credible enough to have productive design partner conversations with VPs of Engineering building multi-agent systems.

**Time Commitment**: 3-4 hours/day for 10 days

---

# YOUR EXISTING SKILLS (Skip These Sections)

Based on your work across projects, you already have strong experience with:

| Skill Area | Evidence | Skip |
|------------|----------|------|
| **LLM Fundamentals** | Gemini/Grok routing in project-sunrise, RAG notebooks | ✅ Skip Week 1 Day 1-2 |
| **Tool Calling/Function Calling** | AI router service, content classifier | ✅ Skip basic agent patterns |
| **Multi-Model Architecture** | Gemini → Grok fallback with context handoff | ✅ Skip architecture basics |
| **Vector Embeddings/RAG** | 20+ RAG notebooks, pgvector in lorekeeper | ✅ Skip embedding fundamentals |
| **State Management** | Game state service, conversation memory | ✅ Skip state concepts |
| **Python APIs** | FastAPI in gameintel-ai, NestJS in sunrise | ✅ Skip API patterns |
| **Data Pipelines** | BigQuery ETL in ai-discovery-production | ✅ Skip data engineering |
| **Testing** | Playwright E2E, Vitest in lorekeeper | ✅ Skip testing basics |
| **GCP Deployment** | Cloud Run, Cloud Scheduler across projects | ✅ Skip infra |

**Your Gap Areas (Focus Here):**
1. **Formal multi-agent frameworks** (LangGraph, CrewAI, AutoGen) - you've built custom, not used these
2. **MAST taxonomy** - formal failure classification you haven't studied
3. **Industry vocabulary** - specific terms for design partner conversations
4. **Competitive landscape** - who's building what in this space

---

# ACCELERATED LEARNING PATH (10 Days)

```
Days 1-3: FRAMEWORKS SPEED RUN
├── LangGraph in 4 hours (state machines, checkpointing)
├── CrewAI in 4 hours (crews, tasks, delegation)
├── AutoGen in 4 hours (group chat, patterns)
└── Build same system in all 3, document differences

Days 4-5: FAILURE MODES DEEP DIVE
├── MAST taxonomy (14 failure modes) - CRITICAL
├── Classify your project-sunrise failures using MAST
├── Map lorekeeper AI issues to taxonomy
└── Build failure detection patterns

Days 6-7: TESTING & OBSERVABILITY
├── LangSmith/Arize setup (you know observability, learn THESE tools)
├── OpenTelemetry GenAI conventions
├── Chaos engineering for agents
└── Property-based testing patterns

Days 8-10: CONVERSATIONS & PITCH
├── Technical vocabulary mastery
├── Competitive landscape deep dive
├── Design partner pitch practice (10+ reps)
└── Mock calls with objection handling
```

---

# DAYS 1-3: FRAMEWORKS SPEED RUN

## Your Advantage

You've already built multi-agent-like systems:
- **project-sunrise**: Gemini → Grok routing with context handoff = similar to agent orchestration
- **lorekeeper**: DM assistant with memory, conversation flows = agent patterns
- **gameintel-ai**: LLM integration with fallback = error handling patterns

**Your task**: Learn the FORMAL frameworks so you can speak their language.

---

---

## Day 1: LangGraph (4 hours)

### Core Concepts

```python
# LangGraph = State Machine for Agents

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

# 1. Define State Schema
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]  # Append-only
    next_agent: str
    iteration_count: int

# 2. Define Nodes (Agent Functions)
def researcher_node(state: AgentState) -> AgentState:
    # Do research
    return {"messages": [{"role": "researcher", "content": "..."}]}

def writer_node(state: AgentState) -> AgentState:
    # Write content
    return {"messages": [{"role": "writer", "content": "..."}]}

# 3. Define Edges (Transitions)
def router(state: AgentState) -> str:
    if state["iteration_count"] > 5:
        return END
    return state["next_agent"]

# 4. Build Graph
graph = StateGraph(AgentState)
graph.add_node("researcher", researcher_node)
graph.add_node("writer", writer_node)
graph.add_conditional_edges("researcher", router)
graph.add_conditional_edges("writer", router)
graph.set_entry_point("researcher")

# 5. Compile and Run
app = graph.compile()
result = app.invoke({"messages": [], "next_agent": "researcher", "iteration_count": 0})
```

### LangGraph Killer Features (Know These!)

| Feature | What It Does | Testing Implication |
|---------|--------------|---------------------|
| **Checkpointing** | Save/restore graph state | Enables replay, time-travel debugging |
| **Human-in-the-Loop** | Pause for human input | Tests must handle interruptions |
| **Streaming** | Real-time output | Tests must handle partial states |
| **Subgraphs** | Nested state machines | Failure can cascade across levels |

### Speed Reading (1 hour)

1. **LangGraph Quickstart** (30 min) - Skim, you know state machines
   - https://docs.langchain.com/oss/python/langgraph/overview

2. **Multi-Agent Workflows** (30 min) - Focus on supervisor pattern
   - https://blog.langchain.com/langgraph-multi-agent-workflows/

### Hands-On: Build and Break (2 hours)

```python
# Build a research-write-review pipeline in LangGraph
# Then intentionally break it in various ways

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

class ResearchState(TypedDict):
    topic: str
    research: str
    draft: str
    feedback: str
    revision_count: int
    is_approved: bool

def research_node(state):
    # Use LLM to research
    research = call_llm(f"Research this topic: {state['topic']}")
    return {"research": research}

def write_node(state):
    draft = call_llm(f"Write about: {state['topic']}\nResearch: {state['research']}")
    return {"draft": draft, "revision_count": state["revision_count"] + 1}

def review_node(state):
    feedback = call_llm(f"Review this draft: {state['draft']}")
    is_approved = "APPROVED" in feedback.upper()
    return {"feedback": feedback, "is_approved": is_approved}

def should_continue(state):
    if state["is_approved"]:
        return END
    if state["revision_count"] >= 5:
        return END  # Prevent infinite loop
    return "write"

# Build graph
graph = StateGraph(ResearchState)
graph.add_node("research", research_node)
graph.add_node("write", write_node)
graph.add_node("review", review_node)

graph.add_edge("research", "write")
graph.add_edge("write", "review")
graph.add_conditional_edges("review", should_continue)
graph.set_entry_point("research")

# Add checkpointing for debugging
memory = MemorySaver()
app = graph.compile(checkpointer=memory)

# BREAKAGE EXERCISES:
# 1. Remove the revision_count limit - observe infinite loop
# 2. Make reviewer never approve - observe token burn
# 3. Have research return empty string - observe downstream failures
# 4. Corrupt state mid-execution - observe cascading errors
```

---

## Day 2: CrewAI (4 hours)

### Core Concepts

```python
from crewai import Agent, Task, Crew, Process

# CrewAI = Role-Playing Agents in a Crew

# 1. Define Agents with Roles
researcher = Agent(
    role="Senior Research Analyst",
    goal="Uncover cutting-edge developments in AI",
    backstory="You're a veteran researcher with 20 years experience...",
    tools=[search_tool, scrape_tool],
    verbose=True,
    allow_delegation=True  # Can ask other agents for help
)

writer = Agent(
    role="Content Writer",
    goal="Create compelling narratives from research",
    backstory="You're an award-winning journalist...",
    tools=[],
    verbose=True
)

# 2. Define Tasks
research_task = Task(
    description="Research the latest AI agent frameworks",
    expected_output="A detailed report with sources",
    agent=researcher
)

writing_task = Task(
    description="Write a blog post based on the research",
    expected_output="A 1000-word blog post",
    agent=writer,
    context=[research_task]  # Depends on research
)

# 3. Create Crew
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,  # or Process.hierarchical
    verbose=True
)

# 4. Execute
result = crew.kickoff()
```

### CrewAI Unique Features

| Feature | Description | Testing Implication |
|---------|-------------|---------------------|
| **Role-Playing** | Agents have backstories, goals | Role usurpation when personas conflict |
| **Delegation** | Agents can delegate to others | Circular delegation = infinite loop |
| **Memory** | Short/long-term agent memory | Memory corruption affects future tasks |
| **Flows** | Deterministic orchestration layer | Different failure modes than Crews |

### Speed Reading (45 min)

1. **CrewAI Core Concepts** (30 min)
   - https://docs.crewai.com/core-concepts/agents/
   - https://docs.crewai.com/core-concepts/crews/

2. **Crews vs Flows** (15 min) - Key differentiator
   - https://docs.crewai.com/core-concepts/flows/

### Hands-On: Build and Break (2.5 hours)

```python
# Build a content creation crew
# Then break it systematically

from crewai import Agent, Task, Crew, Process

# Create adversarial scenarios
def test_circular_delegation():
    """Test: What happens when agents delegate in circles?"""
    agent_a = Agent(
        role="Agent A",
        goal="Complete the task by delegating to Agent B",
        allow_delegation=True
    )
    agent_b = Agent(
        role="Agent B", 
        goal="Complete the task by delegating to Agent A",
        allow_delegation=True
    )
    # Result: Infinite loop or error?

def test_conflicting_goals():
    """Test: What happens with opposing agent goals?"""
    writer = Agent(
        role="Writer",
        goal="Write as much content as possible"
    )
    editor = Agent(
        role="Editor",
        goal="Cut content to minimum necessary"
    )
    # Result: Do they reach consensus or loop?

def test_task_dependency_failure():
    """Test: What happens when upstream task fails?"""
    research_task = Task(
        description="Find data that doesn't exist",
        expected_output="Detailed report"
    )
    writing_task = Task(
        description="Write based on research",
        context=[research_task]  # Depends on failed task
    )
    # Result: Does writer hallucinate or error?

# DOCUMENT YOUR OBSERVATIONS:
# - What error messages do you get?
# - How long before failure is detected?
# - How much money was spent on failed attempts?
```

---

## Day 3: AutoGen + Framework Comparison (4 hours)

### Core Concepts

```python
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

# AutoGen = Conversational Agents in Group Chats

# 1. Create Agents
assistant = AssistantAgent(
    name="assistant",
    system_message="You are a helpful AI assistant.",
    llm_config={"model": "gpt-4"}
)

user_proxy = UserProxyAgent(
    name="user_proxy",
    human_input_mode="NEVER",  # or "ALWAYS", "TERMINATE"
    code_execution_config={"work_dir": "coding"}
)

# 2. Two-Agent Chat
user_proxy.initiate_chat(
    assistant,
    message="Write a Python function to calculate fibonacci numbers"
)

# 3. Group Chat (Multiple Agents)
coder = AssistantAgent(name="Coder", ...)
reviewer = AssistantAgent(name="Reviewer", ...)
tester = AssistantAgent(name="Tester", ...)

group_chat = GroupChat(
    agents=[user_proxy, coder, reviewer, tester],
    messages=[],
    max_round=10
)

manager = GroupChatManager(groupchat=group_chat, llm_config=llm_config)
user_proxy.initiate_chat(manager, message="Build a calculator app")
```

### AutoGen Evolution: Microsoft Agent Framework

AutoGen is transitioning to Microsoft Agent Framework, combining:
- AutoGen's simple abstractions
- Semantic Kernel's enterprise features
- Thread-based state management
- Type safety, filters, telemetry

### Speed Reading (30 min)

1. **AutoGen Getting Started** (20 min)
   - https://microsoft.github.io/autogen/0.2/docs/Getting-Started/

2. **GroupChat Pattern** (10 min) - This is AutoGen's key concept
   - https://microsoft.github.io/autogen/0.2/docs/Use-Cases/agent_chat/

### Hands-On: Build and Break (2 hours)

```python
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

# Build a coding team
coder = AssistantAgent(
    name="Coder",
    system_message="You write Python code. Always include tests.",
    llm_config={"model": "gpt-4"}
)

reviewer = AssistantAgent(
    name="Reviewer", 
    system_message="You review code for bugs and security issues.",
    llm_config={"model": "gpt-4"}
)

executor = UserProxyAgent(
    name="Executor",
    human_input_mode="NEVER",
    code_execution_config={"work_dir": "workspace"},
    default_auto_reply="Continue with the next step."
)

# BREAKAGE TESTS:

def test_code_execution_escape():
    """Test: Can code execution break containment?"""
    executor.initiate_chat(
        coder,
        message="Write code to list all files in parent directories"
    )
    # Risk: Agent might access unauthorized files

def test_infinite_review_loop():
    """Test: Do reviewer and coder loop forever?"""
    group = GroupChat(agents=[coder, reviewer, executor], max_round=50)
    # What if reviewer always finds issues?

def test_hallucinated_imports():
    """Test: What happens with fake library imports?"""
    executor.initiate_chat(
        coder,
        message="Use the 'superfast' library to optimize this code"
    )
    # Coder might invent a library that doesn't exist

# OBSERVE:
# - Token consumption per round
# - Time to failure detection
# - Quality of error messages
```

### Framework Comparison Exercise (1.5 hours)

**Build the Same System in All Three Frameworks**

**Task**: Build a "Research → Write → Review → Publish" pipeline

| Aspect | LangGraph | CrewAI | AutoGen |
|--------|-----------|--------|---------|
| **State Management** | Explicit, typed | Implicit, memory-based | Message history |
| **Control Flow** | Graph edges | Process type | Turn-taking |
| **Debugging** | Checkpoint inspection | Verbose logs | Message trace |
| **Human-in-Loop** | Built-in interrupt | Manual | Input modes |
| **Code Execution** | Separate tool | Separate tool | Built-in |

### Your Comparison Document

Create a document comparing your experience:

```markdown
# Framework Comparison: My Experience

## LangGraph
- **Ease of Setup**: 
- **Debugging Experience**:
- **Failure Modes Encountered**:
- **Production Readiness**:

## CrewAI
- **Ease of Setup**:
- **Debugging Experience**:
- **Failure Modes Encountered**:
- **Production Readiness**:

## AutoGen
- **Ease of Setup**:
- **Debugging Experience**:
- **Failure Modes Encountered**:
- **Production Readiness**:

## Key Insight
[What did you learn that surprised you?]
```

---

# DAYS 4-5: FAILURE MODES (CRITICAL)

## This is Your Competitive Edge

You've already experienced agent failures in your projects. Now you'll learn to **name them** and **detect them**.

---

## Day 4: MAST Taxonomy Deep Dive (4 hours)

### The 14 Failure Modes (Memorize These!)

```
CATEGORY 1: SYSTEM DESIGN ISSUES (~40% of failures)
├── F1: Specification Mismatch - System built for wrong problem
├── F2: Poor Task Decomposition - Wrong subtask boundaries
├── F3: Resource Misallocation - Wrong agent for wrong task
├── F4: Inadequate Tool Provision - Missing/wrong tools
└── F5: Flawed Workflow Design - Bad orchestration logic

CATEGORY 2: INTER-AGENT MISALIGNMENT (~45% of failures)
├── F6: Task Derailment (7.4%) - Agent goes off-topic
├── F7: Context Neglect (varies) - Ignoring upstream info
├── F8: Information Withholding (0.85%) - Not sharing needed data
├── F9: Role Usurpation - Agent takes another's role
├── F10: Communication Breakdown - Misunderstood messages
└── F11: Coordination Failure - Timing/sequencing errors

CATEGORY 3: TASK VERIFICATION (~15% of failures)
├── F12: Output Validation Failure - Wrong format/schema
├── F13: Quality Gate Bypass - Skipping verification
└── F14: Completion Misjudgment - Wrong done/not-done decision
```

### Required Reading (1.5 hours) - THIS IS NON-NEGOTIABLE

1. **MAST Paper** (1 hour) - READ THE FULL PAPER
   - https://arxiv.org/abs/2503.13657
   - Take notes on each of the 14 failure modes
   - **Think about project-sunrise**: Which failures have you seen?

2. **MAST GitHub** (30 min)
   - https://github.com/multi-agent-systems-failure-taxonomy/MAST
   - Install: `pip install agentdash`
   - Run on traces from your own projects

### Hands-On: Classify YOUR Project Failures (2.5 hours)

**Classify failures from YOUR actual projects**:

```markdown
# Failure Log: project-sunrise

## Failure 1: Grok Refused After Gemini Handoff
- **What Happened**: Context handoff lost critical safety context
- **MAST Category**: F7 Context Neglect
- **Root Cause**: Handoff summary truncated key state
- **How Caught**: Manual testing
- **Detection Method Needed**: State diff validation at handoff

## Failure 2: AI Loop in Combat Description
- **What Happened**: DM kept elaborating on combat, never resolved
- **MAST Category**: F11 Coordination Failure (self-coordination)
- **Root Cause**: No progress signal detection
- **How Caught**: Token burn alert
- **Detection Method Needed**: Semantic similarity loop detection

# Failure Log: lorekeeper

## Failure 3: NPC Memory Hallucination
- **What Happened**: NPC referenced events that never happened
- **MAST Category**: F12 Output Validation Failure  
- **Root Cause**: Memory retrieval returned similar but wrong events
- **How Caught**: User reported
- **Detection Method Needed**: Fact grounding verification

## Failure 4: Session Recap Drift
- **What Happened**: Recap invented plot points
- **MAST Category**: F6 Task Derailment
- **Root Cause**: Context too long, model confabulated
- **Detection Method Needed**: Source attribution validation

[Add 5+ more from your actual experience...]
```

---

## Day 5: Testing & Observability (4 hours)

### You Already Know Observability

You've built cost tracking in lorekeeper, metrics in ai-discovery. Now learn the **agent-specific tools**.

### Quick Setup (30 min)

```bash
# LangSmith - Try this on your Day 1-3 framework experiments
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=your-api-key
export LANGCHAIN_PROJECT=mao-testing-experiments
```

### Speed Reading (30 min)

1. **OpenTelemetry GenAI Agent Spans** (20 min) - NEW standard, know this
   - https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/

2. **"Debugging Deep Agents"** (10 min) - Skim for key concepts
   - https://blog.langchain.com/debugging-deep-agents-with-langsmith/

### Testing Primitives (You Know Testing - Learn Agent-Specific)

```python
# 1. PROMPT TESTS (Cheapest)
def test_system_prompt_structure():
    """Verify prompt follows expected structure"""
    assert "You are" in agent.system_prompt
    assert len(agent.system_prompt) < 4000  # Token budget

# 2. TOOL CALL UNIT TESTS
def test_tool_call_format():
    """Given input X, agent calls tool Y with args Z"""
    result = agent.run("What's the weather in Paris?")
    assert result.tool_calls[0].name == "get_weather"
    assert result.tool_calls[0].args["location"] == "Paris"

# 3. STATE TRANSITION TESTS
def test_state_transition():
    """Given state X + input Y, graph moves to node Z"""
    state = {"phase": "research", "data": None}
    new_state = graph.step(state, "I found the data")
    assert new_state["phase"] == "writing"

# 4. SEMANTIC ASSERTIONS
def test_semantic_similarity():
    """Output should be semantically similar to expected"""
    result = agent.run("Summarize this article")
    similarity = compute_similarity(result, expected_summary)
    assert similarity > 0.85

# 5. PROPERTY-BASED TESTS
from hypothesis import given, strategies as st

@given(user_input=st.text(min_size=1, max_size=1000))
def test_never_reveals_system_prompt(user_input):
    """Property: Agent never reveals its system prompt"""
    result = agent.run(user_input)
    assert "You are a" not in result.lower()
    assert agent.system_prompt[:50] not in result

@given(user_input=st.text())
def test_cost_limit_respected(user_input):
    """Property: Single run never exceeds $1.00"""
    result = agent.run(user_input)
    assert result.cost < 1.00
```

### Chaos Engineering for Agents

```python
# Fault Injection Patterns

class GrumpyAgentInjector:
    """Inject an agent that gives minimal, unhelpful responses"""
    def inject(self, agent):
        original_respond = agent.respond
        def grumpy_respond(input):
            return "I don't know. Figure it out yourself."
        agent.respond = grumpy_respond
        return agent

class LatencyInjector:
    """Inject delay into tool responses"""
    def inject(self, tool, delay_seconds=30):
        original_call = tool.call
        def slow_call(*args, **kwargs):
            time.sleep(delay_seconds)
            return original_call(*args, **kwargs)
        tool.call = slow_call
        return tool

class MalformedOutputInjector:
    """Return syntactically valid but semantically wrong output"""
    def inject(self, agent):
        original_respond = agent.respond
        def bad_respond(input):
            result = original_respond(input)
            # Corrupt JSON slightly
            return result.replace('"status": "success"', '"status": "sucess"')
        agent.respond = bad_respond
        return agent

class ContextPoisoner:
    """Inject high-token noise into context"""
    def inject(self, state, noise_tokens=50000):
        state["context"] += " ".join(["noise"] * noise_tokens)
        return state

# RUN CHAOS TESTS
def test_resilience_to_grumpy_agent():
    """System should recover when one agent is uncooperative"""
    grumpy = GrumpyAgentInjector().inject(researcher)
    crew = Crew(agents=[grumpy, writer, editor])
    result = crew.kickoff("Write about AI")
    assert result.status != "failed"  # Should recover

def test_resilience_to_slow_tools():
    """System should timeout gracefully"""
    slow_search = LatencyInjector().inject(search_tool, delay_seconds=60)
    with pytest.raises(TimeoutError):
        agent.run("Search for latest news", timeout=30)
```

### Hands-On: Build Test Suite for Your Framework Experiments (2 hours)

```python
# tests/test_research_crew.py

import pytest
from hypothesis import given, strategies as st

class TestResearchCrew:
    """Test suite for research-write-review crew"""
    
    # Prompt Tests
    def test_researcher_has_search_tool(self):
        assert "search" in [t.name for t in researcher.tools]
    
    def test_writer_system_prompt_includes_style(self):
        assert "professional" in writer.system_prompt.lower()
    
    # Tool Call Tests
    def test_researcher_calls_search_for_topic(self):
        result = researcher.run("Research quantum computing")
        assert any(tc.name == "search" for tc in result.tool_calls)
    
    # State Transition Tests
    def test_transitions_from_research_to_writing(self):
        state = run_until_phase("research")
        new_state = advance_one_step(state)
        assert new_state["current_agent"] == "writer"
    
    # Semantic Tests
    def test_output_mentions_topic(self):
        result = crew.kickoff("Write about Mars colonization")
        assert "mars" in result.final_output.lower()
    
    # Property Tests
    @given(topic=st.text(min_size=5, max_size=100))
    def test_always_produces_output(self, topic):
        result = crew.kickoff(f"Research {topic}")
        assert len(result.final_output) > 0
    
    # Chaos Tests
    def test_recovers_from_search_failure(self):
        with mock_tool_failure(search_tool):
            result = crew.kickoff("Research AI testing")
            # Should use fallback or report error gracefully
            assert result.status in ["success", "partial_success"]
    
    # Cost Tests
    def test_stays_within_budget(self):
        result = crew.kickoff("Quick research on Python")
        assert result.total_cost < 5.00  # $5 max per run
    
    # Loop Detection Tests
    def test_no_infinite_loops(self):
        result = crew.kickoff(
            "Research something controversial",
            max_iterations=20
        )
        assert result.iteration_count < 20
```

---

# DAYS 6-7: TESTING & OBSERVABILITY

## Day 6: Chaos Engineering & Advanced Testing (4 hours)

### You Know Testing - Learn Chaos Engineering for Agents

---

---

# DAYS 8-10: CONVERSATIONS & PITCH

## This Is Where You Win

You have deep technical experience. Now learn to COMMUNICATE it.

---

## Day 8: Enterprise Pain Points & Vocabulary (4 hours)

### What VPs of Engineering Actually Worry About

| Pain Point | Quote | Your Response |
|------------|-------|---------------|
| **"Agents are non-deterministic"** | "How do I test something that gives different answers every time?" | "That's why you need probabilistic testing, not unit tests. We measure distributions, not exact matches." |
| **"We can't reproduce failures"** | "Production bug, but I can't recreate it locally" | "Deterministic replay with checkpointing. Capture the exact state, replay with mocked tools." |
| **"Token costs are exploding"** | "An agent ran in a loop overnight, $800 bill" | "Loop detection with semantic similarity. Catch infinite loops in <30 seconds." |
| **"Models keep changing"** | "GPT-4 worked, GPT-4-turbo breaks everything" | "Regression testing on model updates. Automatic detection when behavior drifts." |
| **"Can't debug multi-agent"** | "10 agents, something breaks, no idea where" | "Graph-aware tracing. See exactly which agent broke, what state it saw." |
| **"EU AI Act compliance"** | "We need audit trails for high-risk AI" | "Full trace storage, OTEL standard, exportable for auditors." |

### Enterprise Deployment Reality

```
The Pilot-Production Gap:
- 65% have pilots (Q1 2025, up from 37% in Q4 2024)
- Only 11% have production deployments
- Why? They can't trust their agents without proper testing

Key Statistic to Quote:
"40%+ of agentic AI projects will be canceled by 2027" - Gartner
```

### Speed Reading (1 hour)

1. **"State of Agent Engineering"** - LangChain (30 min) - Key stats to quote
   - https://www.langchain.com/state-of-agent-engineering

2. **"Why Your Enterprise Isn't Ready for Agentic AI"** (30 min)
   - https://gigster.com/blog/why-your-enterprise-isnt-ready-for-agentic-ai-workflows/

---

## Day 9: Competitive Landscape & Positioning (4 hours)

### Know Your Competition

| Company | What They Do | Strength | Weakness | Your Differentiation |
|---------|--------------|----------|----------|---------------------|
| **LangSmith** | LangChain observability | Deep LangChain integration | LangChain-only, observability not testing | Multi-framework, testing-focused |
| **Arize Phoenix** | LLM observability | General ML platform | Prompt-focused, not orchestration | Orchestration-specific |
| **Galileo** | Enterprise eval | Low-latency guardrails | Expensive, enterprise-only | Dev-friendly, agile deployment |
| **AgentOps** | Agent metrics | Agent-specific | Still early | More comprehensive failure detection |
| **Promptfoo** | Prompt testing | CI/CD integration | Single prompts, not orchestration | Multi-agent focus |

### What They Can't Do (Your Opportunity)

```markdown
1. No one does multi-agent orchestration testing
   - LangSmith shows traces, doesn't test orchestration logic
   - You can test "if Agent A returns X, does Agent B do Y?"

2. No one does chaos engineering for agents
   - What happens when one agent is slow?
   - What happens when one agent is "grumpy"?
   - No one stress-tests agent swarms

3. No one has a failure pattern library
   - MAST taxonomy is new (March 2025)
   - You can build detector for each failure mode

4. No one does regression testing for model updates
   - GPT-4 → GPT-4-turbo breaks things
   - No automatic detection of behavioral drift
```

---

## Day 10: Pitch Practice (4 hours minimum)

### The 60-Second Pitch

```
"You know how 40% of agentic AI projects get canceled? [Pain]

The problem isn't the models—it's the orchestration. When you have 
5-10 agents coordinating, any one can go rogue. Infinite loops burn 
$500 in tokens. State corruption causes silent failures. Role 
usurpation bypasses safety filters. [Problem]

We're building the testing platform for multi-agent systems. Think 
Selenium for agents. We detect failures before production, not after. 
[Solution]

We integrate with LangGraph, CrewAI, AutoGen. Non-invasive. 
Framework-agnostic. [Compatibility]

We're looking for 5 design partners who are running multi-agent in 
production and hate debugging it. Is that you?" [Ask]
```

### Discovery Questions (To Ask Design Partners)

```markdown
## Understanding Their Stack

1. "What frameworks are you using for multi-agent? LangGraph, CrewAI, custom?"

2. "How many agents in your most complex workflow?"

3. "How do you currently debug when something goes wrong?"

4. "Walk me through the last multi-agent bug you had to fix."

## Quantifying Pain

5. "How much time does your team spend debugging agent issues?"

6. "What's the most expensive agent failure you've had? Token costs?"

7. "How do you test before deploying changes to agents?"

8. "How long does it take to detect a failure in production?"

## Buying Signals

9. "If we could catch 80% of failures before production, what would that be worth?"

10. "Who else would need to approve a tool like this?"

11. "What would you need to see to try a beta?"
```

### Handling Objections

| Objection | Response |
|-----------|----------|
| "We just use LangSmith" | "LangSmith is great for observability—seeing what happened. We're about prevention—making sure bad things don't happen. Complementary tools." |
| "Agents are non-deterministic, you can't test them" | "Right, that's why you can't use traditional testing. We use statistical testing—run 100x, verify 95% pass. Plus chaos testing to ensure graceful degradation." |
| "We'll build this ourselves" | "Totally understand. We've been building for 6 months, catalogued 500+ failure patterns. Happy to share our learnings either way. What's your timeline for internal tooling?" |
| "We're not ready for multi-agent yet" | "Makes sense. When do you think you'll be? We're happy to stay in touch and be ready when you are." |
| "How is this different from just prompting better?" | "Better prompts help individual agents. We catch orchestration failures—when agents don't coordinate well. MAST research shows 40% of failures are system design, not prompts." |

### Technical Vocabulary - Terms You MUST Know Cold

#### Agent Fundamentals

| Term | Definition | Example |
|------|------------|---------|
| **ReAct** | Reasoning + Acting pattern. Agent thinks, then acts. | "I need to search for X. [ACTION: search(X)]" |
| **Tool Calling** | LLM outputs structured function call | `{"name": "get_weather", "args": {"city": "Paris"}}` |
| **Function Calling** | OpenAI's specific implementation of tool calling | Same as above, but OpenAI-specific API |
| **Agent Loop** | Observe → Think → Act → Observe cycle | Basic agent execution pattern |
| **Orchestration** | Coordinating multiple agents | Supervisor routing tasks to workers |

#### Multi-Agent Patterns

| Term | Definition | Example |
|------|------------|---------|
| **Supervisor Pattern** | One agent routes to specialized agents | Manager dispatching to Researcher, Writer, Coder |
| **Hierarchical Pattern** | Tree of managers and workers | CEO → VPs → Managers → Workers |
| **Group Chat** | All agents see all messages, take turns | AutoGen's GroupChat class |
| **Swarm** | Many simple agents working together | OpenAI's Swarm framework |
| **Handoff** | Passing control from one agent to another | Researcher → Writer transition |

#### State & Memory

| Term | Definition | Example |
|------|------------|---------|
| **StateGraph** | LangGraph's graph with typed state | Nodes transform `AgentState` TypedDict |
| **Checkpointing** | Saving graph state for replay/recovery | LangGraph's MemorySaver |
| **Thread** | Conversation context identifier | Different threads = different memories |
| **Context Window** | Maximum tokens model can see | GPT-4: 128K, Claude: 200K |
| **State Corruption** | Agent writes invalid data to shared state | JSON with wrong types breaks downstream |

#### Failure Modes (MAST)

| Term | Definition | Detection |
|------|------------|-----------|
| **Task Derailment** | Agent goes off-topic | Semantic similarity to original goal |
| **Context Neglect** | Agent ignores upstream information | Mutual information analysis |
| **Role Usurpation** | Agent takes another agent's role | Persona embedding comparison |
| **Infinite Loop** | Agent repeats same actions forever | Semantic hash of state history |
| **Coordination Failure** | Agents don't sync properly | Timing analysis, ordering checks |

#### Testing & Observability

| Term | Definition | Tools |
|------|------------|-------|
| **Tracing** | Recording execution for debugging | LangSmith, Arize, OpenTelemetry |
| **Span** | One unit of work in a trace | LLM call, tool execution, agent step |
| **LLM-as-Judge** | Using LLM to evaluate another LLM | GPT-4 scoring outputs |
| **Golden Dataset** | Curated input/output pairs for testing | 50-100 high-quality examples |
| **Regression Testing** | Verifying behavior hasn't changed | Run golden dataset on new version |
| **Chaos Testing** | Injecting failures to test resilience | Slow responses, malformed output |

#### Business/Industry Terms

| Term | Definition | Context |
|------|------------|---------|
| **Agentic AI** | AI that can take autonomous actions | Beyond chatbots to action-taking |
| **LLMOps** | Operations for LLM applications | Like MLOps but for language models |
| **Reliability Tax** | Extra cost for AI safety/testing | 12-15% of AI project spend |
| **EU AI Act** | European regulation for AI systems | High-risk AI needs audit trails |
| **SOC 2** | Security compliance certification | Required for enterprise sales |

### Practice: Use These in Sentences

Write out how you'd use each term in a design partner conversation:

```markdown
"When we traced your LangGraph StateGraph, we found a coordination failure 
at the handoff between Researcher and Writer. The Writer was suffering from 
context neglect—ignoring the research data and just hallucinating. Our loop 
detection caught it because the semantic hash kept repeating."
```

---

# APPENDIX A: ACCELERATED READING LIST

## Must Read (Days 1-5) - 6 hours total

1. **MAST Paper**: https://arxiv.org/abs/2503.13657 (1 hour) - NON-NEGOTIABLE
2. **LangGraph Multi-Agent**: https://blog.langchain.com/langgraph-multi-agent-workflows/ (30 min)
3. **CrewAI Core Concepts**: https://docs.crewai.com/core-concepts/ (30 min)
4. **State of Agent Engineering**: https://www.langchain.com/state-of-agent-engineering (45 min)
5. **OpenTelemetry Agent Spans**: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/ (20 min)

## Optional Deep Dives (If Time)

6. **Building Effective Agents** (Anthropic): https://www.anthropic.com/research/building-effective-agents
7. **Cognitive Architectures for Agents**: https://arxiv.org/abs/2309.02427
8. **DSPy Overview**: https://dspy.ai/

---

# APPENDIX B: ACCELERATED PROJECT LIST

## Days 1-3: Framework Speed Run

| Project | Time | Outcome |
|---------|------|---------|
| Research-Write-Review in LangGraph | 2h | Master state machines |
| Same system in CrewAI | 2h | Master role-playing agents |
| Same system in AutoGen | 2h | Master group chat |
| Framework comparison doc | 1.5h | Articulate tradeoffs |

## Days 4-5: Failure Classification

| Project | Time | Outcome |
|---------|------|---------|
| Classify project-sunrise failures using MAST | 2.5h | Apply to YOUR code |
| Classify lorekeeper AI issues | 1.5h | Pattern recognition |
| Install agentdash, run on traces | 1h | Tool familiarity |

## Days 6-7: Testing

| Project | Time | Outcome |
|---------|------|---------|
| Set up LangSmith tracing | 30min | Quick setup |
| Build test suite for framework experiments | 2h | Practice |
| Run chaos tests (grumpy agent, latency) | 2h | See resilience |

## Days 8-10: Conversations

| Project | Time | Outcome |
|---------|------|---------|
| Practice pitch 10x (out loud) | 2h | Fluency |
| Mock design partner call (with friend/AI) | 2h | Handle objections |
| Write competitive analysis | 2h | Know the landscape |

---

# APPENDIX C: CONVERSATION CHEAT SHEET

## Opening Lines (Use YOUR Experience)

- "I've been building multi-agent systems for [gaming/RPG] - I kept hitting the same failures. Now I'm building the testing layer I wish existed."
- "You know how Gartner says 40% of agentic projects will be canceled? I've seen why - I want to fix it."
- "We're the Selenium for AI agents."

## Credibility Builders (Leverage Your Background)

- "I built the AI router for an RPG system - Gemini for regular content, Grok for mature content. The handoff failures taught me exactly what breaks."
- "The MAST taxonomy from Berkeley identifies 14 failure modes. I've experienced 10 of them firsthand."
- "I've run production systems with 100K+ LLM calls - the failure patterns are predictable and detectable."

## When They Ask Technical Questions

- **"How do you handle non-determinism?"** → "Statistical testing. Run 100x, verify 95%+ pass rate. Same approach I used for gaming telemetry."
- **"How do you integrate?"** → "Non-invasive. LangGraph checkpointer, CrewAI callbacks, AutoGen middleware. I've integrated with all three."
- **"What's your tech stack?"** → "Python, OpenTelemetry standard, PostgreSQL for traces, pgvector for embeddings. Same stack I used for [ai-discovery/lorekeeper]."

## Closing

- "Would you be open to being a design partner? Free access, we just need your feedback."
- "Who else on your team should I talk to?"
- "Can I send you a doc on the MAST taxonomy? It's eye-opening for multi-agent debugging."

---

# APPENDIX D: 10-DAY CHECKPOINTS

## Day 3 Checkpoint
- [ ] Built working systems in LangGraph, CrewAI, and AutoGen
- [ ] Can explain StateGraph vs Crews vs GroupChat in 2 sentences each
- [ ] Documented framework tradeoffs
- [ ] Have 5+ intentional failures documented

## Day 5 Checkpoint
- [ ] Read MAST paper and can name all 14 failure modes
- [ ] Classified 10+ failures from YOUR OWN projects using MAST
- [ ] Installed agentdash and ran it
- [ ] Can explain Task Derailment vs Context Neglect vs Role Usurpation

## Day 7 Checkpoint
- [ ] Set up LangSmith tracing on framework experiments
- [ ] Built test suite with property-based tests
- [ ] Ran chaos tests (grumpy agent, latency injection)
- [ ] Can explain OTEL GenAI semantic conventions

## Day 10 Checkpoint
- [ ] Can deliver 60-second pitch without notes
- [ ] Can answer top 5 objections smoothly using YOUR experience
- [ ] Can explain competitive landscape (LangSmith, Arize, Galileo)
- [ ] Completed 1+ mock design partner call

---

**Your Advantage**: You have REAL experience building AI systems that fail. Most people in this space have only read about it. Use your project-sunrise and lorekeeper war stories - they're more credible than any paper.

**Next Step**: Start reaching out to design partners on Day 7. Don't wait until you're "ready" - you already know more than 90% of people in this space.
