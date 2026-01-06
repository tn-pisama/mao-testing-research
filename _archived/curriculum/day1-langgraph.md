# Day 1: LangGraph Deep Dive

**Key insight:** LangGraph = **State Machine for Agents**

---

## The Mental Model

```
┌─────────────────────────────────────────────────────┐
│                    StateGraph                        │
│                                                      │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐   │
│   │ research │ ──► │  write   │ ──► │  review  │   │
│   └──────────┘     └──────────┘     └──────────┘   │
│                                            │        │
│                         ┌──────────────────┘        │
│                         ▼                           │
│                  ┌─────────────┐                    │
│                  │ should_     │                    │
│                  │ continue?   │                    │
│                  └─────────────┘                    │
│                    │         │                      │
│              approved    needs work                 │
│                    │         │                      │
│                    ▼         ▼                      │
│                  [END]    [write]                   │
└─────────────────────────────────────────────────────┘
```

## Three Core Concepts

| Concept | What It Is | Why It Matters for Testing |
|---------|-----------|---------------------------|
| **State** | TypedDict passed between nodes | State corruption = cascading failures |
| **Nodes** | Functions that transform state | Each node can fail independently |
| **Edges** | Routing logic (conditional) | Wrong routing = infinite loops |

---

## The 4 LangGraph Failure Modes

### Failure 1: Infinite Loop (No Termination)

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ research │ ──► │  write   │ ──► │  review  │
└──────────┘     └──────────┘     └──────────┘
                      ▲                 │
                      │    "needs work" │
                      └─────────────────┘
                           FOREVER
                           
Token burn: $50-500+ before anyone notices
```

**What breaks:** Router always returns `"write"`, never `END`

**MAST Category:** F11 Coordination Failure

**Detection:** Track semantic similarity of outputs. If 3+ consecutive outputs are >90% similar → loop detected.

---

### Failure 2: Token Burn (Impossible Task)

```
Revision 1:  "Not good enough"     →  500 tokens
Revision 2:  "Still not good"      →  500 tokens
Revision 3:  "Needs more work"     →  500 tokens
...
Revision 10: "Still not satisfied" →  500 tokens
                                      ─────────
                                      5,000+ tokens wasted
```

**What breaks:** Reviewer has impossible standards. Even with iteration limit, you burn resources on hopeless task.

**MAST Category:** F5 Flawed Workflow Design

**Detection:** Track approval rate. If reviewer rejects 5+ consecutive drafts → flag for human review.

---

### Failure 3: Empty Upstream (Hallucination Cascade)

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ research │ ──► │  write   │ ──► │  review  │
└──────────┘     └──────────┘     └──────────┘
      │                │
      ▼                ▼
   returns ""     HALLUCINATES
   (empty)        content with
                  no factual basis
```

**What breaks:** Research returns empty/garbage → Writer invents "facts" → Reviewer can't tell it's wrong

**MAST Category:** F7 Context Neglect + F12 Output Validation Failure

**Detection:** Validate upstream output before passing downstream. `if len(research) < 100: raise Error`

---

### Failure 4: State Corruption

```
State at Node 1:  { revision_count: 0, draft: "..." }
                           │
                    CORRUPTION ─────► { revision_count: -999 }
                           │
State at Node 2:  { revision_count: -999 }
                           │
Router logic:     if revision_count >= 3: END
                  -999 >= 3? FALSE → keeps running
                           │
                     UNDEFINED BEHAVIOR
```

**What breaks:** One node writes invalid data → downstream nodes make wrong decisions

**MAST Category:** F10 Communication Breakdown

**Detection:** Schema validation at every state transition. Pydantic/Zod for type checking.

---

## Supervisor Pattern

The most common multi-agent architecture. One agent decides who does what.

```
                         USER REQUEST
                              │
                              ▼
                    ┌─────────────────┐
                    │   SUPERVISOR    │
                    │                 │
                    │  "Who should    │
                    │   handle this?" │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌────────────┐    ┌────────────┐    ┌────────────┐
    │ RESEARCHER │    │   CODER    │    │   WRITER   │
    └─────┬──────┘    └─────┬──────┘    └─────┬──────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │   SUPERVISOR    │
                    │  "Done, or      │
                    │   who's next?"  │
                    └─────────────────┘
```

### Where Supervisor Pattern Fails

| # | Failure | Example | MAST Code |
|---|---------|---------|-----------|
| 1 | **Wrong Routing** | User asks "what's 2+2", supervisor sends to Researcher instead of just answering | F3 Resource Misallocation |
| 2 | **Ambiguous Dispatch** | "Help me with my project" - Supervisor can't decide, picks randomly or loops asking | F2 Poor Task Decomposition |
| 3 | **Task Derailment** | Supervisor says "search for X", Researcher searches for Y instead | F6 Task Derailment |
| 4 | **Role Usurpation** | Researcher starts writing code instead of handing off to Coder | F9 Role Usurpation |
| 5 | **Output Parsing** | Coder returns malformed JSON, Supervisor crashes or hallucinates next step | F12 Output Validation Failure |

---

## Reading

1. **LangGraph Quickstart** (30 min)
   - https://docs.langchain.com/oss/python/langgraph/overview

2. **Multi-Agent Workflows** (30 min)
   - https://blog.langchain.com/langgraph-multi-agent-workflows/
