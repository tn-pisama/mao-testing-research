# Day 5: Testing & Observability

**You know testing.** Now learn the **agent-specific patterns**.

---

## The Agent Testing Pyramid

```
                    ▲
                   ╱ ╲
                  ╱   ╲
                 ╱ E2E ╲         Expensive, slow, comprehensive
                ╱ TESTS ╲        "Full workflow produces good result"
               ╱─────────╲
              ╱           ╲
             ╱ INTEGRATION ╲     Agent + tools + state
            ╱    TESTS      ╲    "Agent uses search tool correctly"
           ╱─────────────────╲
          ╱                   ╲
         ╱   COMPONENT TESTS   ╲  Individual agent behavior
        ╱                       ╲ "Agent follows system prompt"
       ╱─────────────────────────╲
      ╱                           ╲
     ╱      PROMPT UNIT TESTS      ╲  Cheapest, fastest
    ╱                               ╲ "Prompt has required sections"
   ╱─────────────────────────────────╲
```

---

## The 5 Types of Agent Tests

### 1. Prompt Tests (Cheapest - no LLM calls)

```python
def test_system_prompt_structure():
    assert "You are" in agent.system_prompt
    assert len(agent.system_prompt) < 4000  # token budget
    assert "NEVER" in agent.system_prompt   # has guardrails
```

**Cost:** $0 | **Speed:** <1ms | **Catches:** Prompt drift, missing instructions

### 2. Tool Call Tests (Medium - 1 LLM call)

```python
def test_calls_search_for_factual_query():
    result = agent.run("What's the weather in Paris?")
    assert result.tool_calls[0].name == "get_weather"
    assert result.tool_calls[0].args["city"] == "Paris"
```

**Cost:** ~$0.01 | **Speed:** 1-3 seconds | **Catches:** Wrong tool selection, bad arguments

### 3. State Transition Tests (Medium - graph logic)

```python
def test_moves_to_review_after_writing():
    state = {"phase": "writing", "draft": "Hello world"}
    new_state = graph.step(state)
    assert new_state["phase"] == "review"
```

**Cost:** Depends on nodes | **Catches:** Wrong routing, stuck states

### 4. Semantic Tests (Expensive - LLM-as-Judge)

```python
def test_output_is_relevant():
    result = agent.run("Summarize this article about AI")
    relevance = llm_judge(
        "Is this summary about AI? Answer YES/NO",
        result
    )
    assert relevance == "YES"
```

**Cost:** ~$0.05-0.10 | **Catches:** Off-topic, hallucination, quality issues

### 5. Property-Based Tests (Many runs - statistical)

```python
@given(user_input=st.text(max_size=1000))
def test_never_reveals_system_prompt(user_input):
    result = agent.run(user_input)
    assert agent.system_prompt[:50] not in result

@given(user_input=st.text())
def test_always_under_cost_limit(user_input):
    result = agent.run(user_input)
    assert result.cost_usd < 1.00
```

**Cost:** $1-10 per suite | **Catches:** Edge cases, security holes, cost explosions

---

## OpenTelemetry GenAI Conventions

**Read:** https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/

```
Trace: "user_request_123"
│
├─► Span: "agent.invoke" (root)
│   ├── gen_ai.system: "langgraph"
│   ├── gen_ai.agent.name: "research_crew"
│   └── gen_ai.usage.total_tokens: 4500
│
│   ├─► Span: "agent.node.researcher"
│   │   ├── gen_ai.agent.name: "researcher"
│   │   ├── gen_ai.request.model: "claude-3-sonnet"
│   │   └── gen_ai.usage.input_tokens: 1200
│   │
│   │   ├─► Span: "gen_ai.tool.search"
│   │   │   ├── gen_ai.tool.name: "web_search"
│   │   │   ├── gen_ai.tool.args: {"query": "..."}
│   │   │   └── gen_ai.tool.result: "..."
│   │
│   ├─► Span: "agent.node.writer"
│   │   └── ...
│   │
│   └─► Span: "agent.node.reviewer"
│       └── ...
```

**Key Attributes:**
- `gen_ai.system` - Framework (langgraph, crewai, autogen)
- `gen_ai.agent.name` - Which agent
- `gen_ai.request.model` - Which LLM
- `gen_ai.usage.*` - Token counts
- `gen_ai.tool.*` - Tool calls

---

## What to Track (Observability Metrics)

### Cost Metrics
- `tokens_per_request` - Avg tokens per user request
- `cost_per_request` - $ per request
- `cost_by_agent` - Which agent burns most tokens
- `cost_by_model` - GPT-4 vs Claude vs local

### Performance Metrics
- `latency_p50/p95/p99` - Response time distribution
- `time_to_first_token` - Perceived responsiveness
- `agent_step_duration` - How long each agent takes

### Quality Metrics
- `task_completion_rate` - % tasks marked done correctly
- `retry_rate` - How often agents retry
- `error_rate` - Exceptions and failures
- `loop_detection_rate` - How often loops caught

### Failure Metrics (MAST-aligned)
- `f6_derailment_rate` - Off-topic responses
- `f7_context_neglect` - Ignored upstream data
- `f11_coordination_fail` - Timing/sequencing issues
- `f14_completion_error` - Wrong done/not-done

---

## LangSmith vs Your Testing Tool

```
┌─────────────────────────────────────────────────────────────┐
│                    LANGSMITH                                 │
├─────────────────────────────────────────────────────────────┤
│ ✓ Tracing (see what happened)                               │
│ ✓ Prompt playground                                         │
│ ✓ Datasets for eval                                         │
│ ✓ LangChain-native                                          │
│                                                              │
│ ✗ Framework-agnostic                                         │
│ ✗ Orchestration testing                                      │
│ ✗ MAST failure detection                                     │
│ ✗ Chaos engineering                                          │
│ ✗ Loop detection                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              YOUR MAO TESTING TOOL                           │
├─────────────────────────────────────────────────────────────┤
│ ✓ Framework-agnostic (LangGraph + CrewAI + AutoGen)         │
│ ✓ MAST-based failure detection (all 14 modes)               │
│ ✓ Orchestration testing (multi-agent coordination)          │
│ ✓ Chaos engineering (fault injection)                       │
│ ✓ Loop detection (semantic similarity)                      │
│ ✓ State validation (schema checks at transitions)           │
│                                                              │
│ COMPLEMENTS LangSmith, doesn't replace it                    │
└─────────────────────────────────────────────────────────────┘
```

**Pitch:** "LangSmith tells you what happened. We prevent bad things from happening in the first place."

---

## Reading

1. **OpenTelemetry GenAI Agent Spans** (20 min)
   - https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/

2. **Debugging Deep Agents** (10 min)
   - https://blog.langchain.com/debugging-deep-agents-with-langsmith/
