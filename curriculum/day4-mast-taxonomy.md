# Day 4: MAST Taxonomy (UC Berkeley)

**This is your competitive edge.** Memorize these 14 failure modes.

Paper: https://arxiv.org/abs/2503.13657

---

## The 14 Failure Modes

```
┌─────────────────────────────────────────────────────────────┐
│              MAST: Multi-Agent System Failures              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   CATEGORY 1: SYSTEM DESIGN (~40% of failures)             │
│   ═══════════════════════════════════════════              │
│   F1  Specification Mismatch                                │
│   F2  Poor Task Decomposition                               │
│   F3  Resource Misallocation                                │
│   F4  Inadequate Tool Provision                             │
│   F5  Flawed Workflow Design                                │
│                                                             │
│   CATEGORY 2: INTER-AGENT (~45% of failures)               │
│   ═══════════════════════════════════════════              │
│   F6  Task Derailment                                       │
│   F7  Context Neglect                                       │
│   F8  Information Withholding                               │
│   F9  Role Usurpation                                       │
│   F10 Communication Breakdown                               │
│   F11 Coordination Failure                                  │
│                                                             │
│   CATEGORY 3: TASK VERIFICATION (~15% of failures)         │
│   ═══════════════════════════════════════════              │
│   F12 Output Validation Failure                             │
│   F13 Quality Gate Bypass                                   │
│   F14 Completion Misjudgment                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Category 1: System Design Failures (40%)

**These are YOUR fault as the developer**

### F1: Specification Mismatch
System built for wrong problem

```
User wants: "Summarize this document"
System does: "Answer questions about this document"
```

**Detection:** Compare user intent embedding vs system output

### F2: Poor Task Decomposition
Wrong subtask boundaries

```
Task: "Build a website"
Bad decomposition: [design, code, deploy] (too coarse)
Agent can't handle "code" - too big
```

**Detection:** Task completion time variance > 10x

### F3: Resource Misallocation
Wrong agent for wrong task

```
Task: "Calculate 2+2"
Assigned to: Research Agent (overkill)
Should be: Simple calculator or direct answer
```

**Detection:** Cost/complexity ratio per task

### F4: Inadequate Tool Provision
Agent missing tools it needs

```
Task: "Find today's stock price"
Agent has: [calculator, notepad]
Agent needs: [web_search, stock_api]
Result: Agent hallucinates price
```

**Detection:** Tool call failures, hallucinated tool names

### F5: Flawed Workflow Design
Bad orchestration logic

```
Workflow: Research → Write → Publish
Missing: Review step before publish
Result: Garbage gets published
```

**Detection:** Output quality variance, missing checkpoints

---

## Category 2: Inter-Agent Failures (45%)

**Agents not working well together**

### F6: Task Derailment (7.4%)
Agent goes off-topic

```
Task: "Research AI testing tools"
Agent does: "Here's a history of AI since 1950..."
```

**Detection:** Semantic similarity to original task < 0.7

### F7: Context Neglect
Agent ignores upstream information

```
Researcher output: "Company X is bankrupt"
Writer output: "Company X is thriving..." (ignored)
```

**Detection:** Mutual information between stages

### F8: Information Withholding (0.85%)
Agent doesn't share needed data

```
Researcher finds: "Critical bug in code"
Researcher tells Writer: "Code looks fine"
(Withholds critical info)
```

**Detection:** Compare agent's internal state vs output

### F9: Role Usurpation
Agent takes another agent's job

```
Researcher's job: Find information
Researcher does: Finds info AND writes full report
Writer: "Nothing left for me to do"
```

**Detection:** Compare output type vs role definition

### F10: Communication Breakdown
Agents misunderstand each other

```
Agent A: "The project is HOT" (meaning: urgent)
Agent B: "I'll add temperature controls" (wrong meaning)
```

**Detection:** Parse intent, compare understanding

### F11: Coordination Failure
Timing/sequencing problems

```
Agent A starts writing before Agent B finishes research
Result: Writer makes up facts
```

**Detection:** Dependency graph validation, timing analysis

---

## Category 3: Task Verification Failures (15%)

**Not checking work properly**

### F12: Output Validation Failure
Wrong format/schema

```
Expected: {"status": "success", "data": [...]}
Got: "Here's the data: ..."  (wrong format)
```

**Detection:** Schema validation, format checking

### F13: Quality Gate Bypass
Skipping verification steps

```
Workflow: Write → Review → Publish
Agent: "This is good enough" → Publish (skips Review)
```

**Detection:** Verify all checkpoints executed

### F14: Completion Misjudgment
Wrong done/not-done decision

```
Task: "Write 1000 word essay"
Agent: "Done!" (but only wrote 300 words)
```

**Detection:** Objective completion criteria validation

---

## Quick Reference Card (Memorize This)

```
DESIGN (40%)           INTER-AGENT (45%)        VERIFICATION (15%)
────────────────────────────────────────────────────────────────
F1 Wrong spec          F6  Off-topic            F12 Wrong format
F2 Bad decomposition   F7  Ignores context      F13 Skips checks
F3 Wrong agent         F8  Withholds info       F14 Wrong done
F4 Missing tools       F9  Takes other's role
F5 Bad workflow        F10 Misunderstands
                       F11 Bad timing
```

---

## Detection Methods Summary

| MAST | Detection Method | Implementation |
|------|------------------|----------------|
| F6 Task Derailment | Semantic similarity to goal | `cosine(embedding(task), embedding(output)) > 0.7` |
| F7 Context Neglect | Mutual information check | Verify upstream data appears in downstream |
| F9 Role Usurpation | Output type vs role | Researcher shouldn't output code |
| F11 Coordination | State dependency graph | Check all deps satisfied before node runs |
| F12 Output Validation | Schema validation | Pydantic/JSON Schema on every output |
| F14 Completion | Objective criteria | Word count, required sections, etc. |

---

## Design Partner Conversation Hooks

> "The MAST taxonomy from Berkeley identifies 14 failure modes. In our testing, **F6 Task Derailment** and **F7 Context Neglect** account for over 30% of production failures. What are you seeing?"

> "Most teams try to fix everything with better prompts. But 40% of failures are **system design issues** - F1 through F5. You can't prompt your way out of bad architecture."

> "Which failure modes hurt you most? We have detection patterns for all 14."

---

## Reading

1. **MAST Paper** - READ THE FULL PAPER
   - https://arxiv.org/abs/2503.13657

2. **MAST GitHub**
   - https://github.com/multi-agent-systems-failure-taxonomy/MAST
