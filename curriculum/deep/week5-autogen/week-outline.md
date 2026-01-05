# Week 5: AutoGen & Emerging Frameworks - Complete Outline

**Duration:** 5 days (20-30 hours total)
**Prerequisites:** Weeks 1-4 (LangGraph, CrewAI)
**Outcome:** Framework-agnostic expertise, ability to evaluate any new framework

---

## Day-by-Day Breakdown

### Day 21: AutoGen Core Concepts
- Architecture: agents as conversation participants
- AssistantAgent deep dive
- UserProxyAgent and code execution
- System message engineering
- LLM configuration options
- Two-agent conversation patterns
- **Exercise:** Build researcher-coder pair

### Day 22: GroupChat Mastery
- GroupChatManager internals
- Agent selection strategies
- Speaker selection customization
- Message routing
- Conversation termination
- State management in group chat
- **Exercise:** 4-agent code review team

### Day 23: Code Execution Security
- Docker sandboxing
- Local execution risks
- Code validation patterns
- Output sanitization
- Resource limits
- Timeout handling
- **Exercise:** Secure executor implementation

### Day 24: Microsoft Agent Framework Preview
- AutoGen to MAF migration
- New abstractions (Threads, Filters)
- Type safety improvements
- Telemetry integration
- Enterprise features
- Roadmap analysis
- **Exercise:** Port AutoGen app to MAF

### Day 25: Framework Comparison Project
- Build identical system in:
  - LangGraph
  - CrewAI
  - AutoGen
  - OpenAI Swarm (bonus)
- Measure: setup time, debugging, performance
- Document tradeoffs
- **Deliverable:** Framework selection guide

---

## Framework Decision Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│                 FRAMEWORK SELECTION GUIDE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CHOOSE LANGGRAPH WHEN:                                         │
│  • Need explicit control over execution flow                    │
│  • State management is critical                                 │
│  • Want checkpoint/replay for debugging                         │
│  • Building production pipelines                                │
│  • Need deterministic behavior                                  │
│                                                                  │
│  CHOOSE CREWAI WHEN:                                            │
│  • Agents have distinct "personalities"                         │
│  • Task delegation is natural fit                               │
│  • Creative/exploratory tasks                                   │
│  • Want rapid prototyping                                       │
│  • Less concerned about exact control                           │
│                                                                  │
│  CHOOSE AUTOGEN WHEN:                                           │
│  • Code generation/execution is core                            │
│  • Natural conversation flow between agents                     │
│  • Research/experimental work                                   │
│  • Microsoft ecosystem integration                              │
│  • Group brainstorming patterns                                 │
│                                                                  │
│  CHOOSE CUSTOM WHEN:                                            │
│  • Unique requirements not met by frameworks                    │
│  • Performance is critical                                      │
│  • Want minimal dependencies                                    │
│  • Already have orchestration infrastructure                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Emerging Frameworks to Watch

| Framework | Company | Key Feature | Status |
|-----------|---------|-------------|--------|
| OpenAI Swarm | OpenAI | Lightweight handoffs | Experimental |
| Letta (MemGPT) | Letta | Infinite memory | Growing |
| DSPy | Stanford | Prompt optimization | Maturing |
| Semantic Kernel | Microsoft | Enterprise .NET/Python | Stable |
| Haystack | deepset | RAG-focused agents | Stable |

---

## Key Takeaway

> "Framework expertise is temporary. Understanding orchestration patterns is permanent. Learn the patterns, not just the APIs."
