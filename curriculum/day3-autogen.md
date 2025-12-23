# Day 3: AutoGen (Microsoft)

**Key insight:** AutoGen = **Group Chat** - Agents talk in a shared conversation

---

## The Mental Model

```
LANGGRAPH              CREWAI                 AUTOGEN
─────────────────────────────────────────────────────────────
State Machine          Role-Play Team         Group Chat

┌─┐→┌─┐→┌─┐           🧑‍🔬→🧑‍💻→🧑‍🎨              ┌─────────────────┐
│A│ │B│ │C│                                   │  Chat Room      │
└─┘ └─┘ └─┘           Delegation &            │                 │
                      Backstory               │  👤 Agent A     │
Typed state                                   │  👤 Agent B     │
Explicit edges        Implicit flow           │  👤 Agent C     │
                                              │                 │
                                              │  All see all    │
                                              │  messages       │
                                              └─────────────────┘
```

---

## Core Concepts

```
┌─────────────────────────────────────────────────────────────┐
│                      GROUP CHAT                              │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Assistant    │  │ UserProxy    │  │ Coder        │      │
│  │ Agent        │  │ Agent        │  │ Agent        │      │
│  │              │  │              │  │              │      │
│  │ Responds to  │  │ Executes     │  │ Writes       │      │
│  │ queries      │  │ code         │  │ code         │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                 │               │
│         └─────────────────┼─────────────────┘               │
│                           ▼                                 │
│                   ┌──────────────┐                         │
│                   │ GroupChat    │                         │
│                   │ Manager      │                         │
│                   │              │                         │
│                   │ Decides who  │                         │
│                   │ speaks next  │                         │
│                   └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

**Key Types:**
- **AssistantAgent**: LLM-powered, responds to messages
- **UserProxyAgent**: Can execute code, represent human
- **GroupChatManager**: Orchestrates turn-taking

---

## AutoGen's Killer Feature: Code Execution

```
┌─────────────────────────────────────────────────────────────┐
│  USER: "Calculate fibonacci of 10"                          │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────┐                │
│  │ CODER AGENT                              │                │
│  │                                          │                │
│  │ def fibonacci(n):                        │                │
│  │     if n <= 1: return n                  │                │
│  │     return fibonacci(n-1) + fibonacci(n-2)               │
│  │                                          │                │
│  │ print(fibonacci(10))                     │                │
│  └─────────────────────────────────────────┘                │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────┐                │
│  │ USERPROXY AGENT (Code Executor)         │                │
│  │                                          │                │
│  │ >>> Executing in sandbox...              │                │
│  │ >>> Output: 55                           │ ← ACTUAL CODE  │
│  └─────────────────────────────────────────┘   RUNS HERE    │
│                                                              │
│  🚨 SECURITY RISK: What if code is malicious?               │
└─────────────────────────────────────────────────────────────┘
```

---

## AutoGen Failure Modes

### 1. Turn-Taking Chaos

```
Agent A: "I'll handle this"
Agent B: "No, I'll handle this"
Agent A: "I said I'll handle this"
Agent B: "But I'm better suited"
... (burns tokens arguing)
```

**MAST:** F11 Coordination Failure

### 2. Code Execution Escape

```
Coder: import os; os.system("rm -rf /")
UserProxy: "Executing..." 💀
```

**MAST:** F4 Inadequate Tool Provision (missing sandbox)

### 3. Hallucinated Imports

```
Coder: from superfast import optimize  # doesn't exist
UserProxy: ModuleNotFoundError
Coder: from ultrafast import optimize  # also fake
UserProxy: ModuleNotFoundError
... (loops trying fake libraries)
```

**MAST:** F6 Task Derailment + F14 Completion Misjudgment

### 4. Context Window Explosion

```
All agents see ALL messages
After 50 turns: 100K+ tokens in context
Result: Slow, expensive, incoherent
```

**MAST:** F3 Resource Misallocation

---

## Framework Comparison Summary

| Aspect | LangGraph | CrewAI | AutoGen |
|--------|-----------|--------|---------|
| **Paradigm** | State Machine | Role-Play Team | Group Chat |
| **Control** | High (explicit) | Medium (roles) | Low (emergent) |
| **State** | Typed, checkpointed | Agent memory | Message history |
| **Code Exec** | Separate tool | Separate tool | Built-in |
| **Debugging** | State inspection | Conversation logs | Message trace |
| **Main Risk** | State corruption | Role confusion | Turn-taking chaos |
| **Best For** | Deterministic flows | Creative tasks | Code generation |

---

## Framework-Specific vs Shared Failures

```
                     SHARED FAILURES (All frameworks)
                     ────────────────────────────────
                     • Infinite loops
                     • Token burn
                     • Hallucination
                     • Context loss

    ┌───────────────────┬───────────────────┬───────────────────┐
    │    LANGGRAPH      │     CREWAI        │     AUTOGEN       │
    │    SPECIFIC       │     SPECIFIC      │     SPECIFIC      │
    ├───────────────────┼───────────────────┼───────────────────┤
    │ • State           │ • Circular        │ • Turn-taking     │
    │   corruption      │   delegation      │   conflicts       │
    │                   │                   │                   │
    │ • Edge routing    │ • Backstory       │ • Code execution  │
    │   errors          │   bleed           │   escape          │
    │                   │                   │                   │
    │ • Checkpoint      │ • Goal            │ • Context window  │
    │   desync          │   conflicts       │   explosion       │
    └───────────────────┴───────────────────┴───────────────────┘
```

---

## Reading

1. **AutoGen Getting Started** (20 min)
   - https://microsoft.github.io/autogen/0.2/docs/Getting-Started/

2. **GroupChat Pattern** (10 min)
   - https://microsoft.github.io/autogen/0.2/docs/Use-Cases/agent_chat/
