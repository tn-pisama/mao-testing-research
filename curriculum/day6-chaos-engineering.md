# Day 6: Chaos Engineering for Agents

**Netflix invented chaos engineering for infrastructure. Now apply it to agents.**

---

## The Principle

```
┌─────────────────────────────────────────────────────────────┐
│                  CHAOS ENGINEERING                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  "Intentionally inject failures to verify the system         │
│   degrades gracefully instead of catastrophically"           │
│                                                              │
│  INFRASTRUCTURE                    AGENTS                    │
│  ──────────────                    ──────                    │
│  Kill random servers               Inject bad agent behavior │
│  Add network latency               Add LLM latency           │
│  Corrupt data                      Corrupt state             │
│  Exhaust resources                 Exhaust tokens            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## The 6 Agent Fault Injectors

### 1. The Grumpy Agent

```
Normal Agent:     "Here's the research you requested..."
Grumpy Agent:     "I don't know. Figure it out yourself."
```

**Tests:** Does the system recover when one agent is unhelpful?

**MAST:** Catches F7 Context Neglect handling

### 2. The Slow Agent

```
Normal: 2 second response
Slow:   60 second response
```

**Tests:** Timeout handling, user experience during delays

**MAST:** Catches F11 Coordination Failure (timing)

### 3. The Hallucinator

```
Normal: Returns factual information
Hallucinator: Returns confident but wrong information

"The company was founded in 1847" (actually 1987)
```

**Tests:** Do downstream agents or validators catch wrong facts?

**MAST:** Catches F12 Output Validation gaps

### 4. The Role Thief

```
Normal Researcher: Returns research data
Role Thief:        Returns research AND writes the article
```

**Tests:** Do role boundaries hold? Does Writer still get work?

**MAST:** Catches F9 Role Usurpation

### 5. The State Corruptor

```
Normal state:  { "count": 1, "data": [...] }
Corrupted:     { "count": -999, "data": null }
```

**Tests:** Schema validation, error handling for invalid state

**MAST:** Catches F10 Communication Breakdown

### 6. The Token Burner

```
Normal: Returns concise response
Burner: Returns 10,000 word response for simple question
```

**Tests:** Token limits, cost controls, context window handling

**MAST:** Catches F3 Resource Misallocation

---

## Chaos Test Matrix

```
               │ Grumpy │ Slow │ Halluc │ Thief │ Corrupt │ Burner │
───────────────┼────────┼──────┼────────┼───────┼─────────┼────────┤
Retry logic    │   ✓    │  ✓   │        │       │    ✓    │        │
Timeout        │        │  ✓   │        │       │         │        │
Fact checking  │        │      │   ✓    │       │         │        │
Role guards    │        │      │        │   ✓   │         │        │
Schema valid   │        │      │        │       │    ✓    │        │
Cost limits    │        │      │        │       │         │   ✓    │
```

---

## Chaos Test Scenarios

### Scenario 1: Supervisor with Grumpy Worker

```
┌────────────┐     "Research AI"      ┌────────────┐
│ SUPERVISOR │ ──────────────────────►│ RESEARCHER │
└────────────┘                        │  (GRUMPY)  │
                                      └────────────┘
                                            │
                              "I don't know. Ask someone else."
                                            │
                                            ▼
Expected:
• Supervisor retries
• Or routes to different agent
• Or asks human for help
• NOT: Crash or infinite loop
```

### Scenario 2: Slow Agent in Pipeline

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ RESEARCH │───►│  WRITE   │───►│  REVIEW  │
│  (2 sec) │    │ (60 sec) │    │  (2 sec) │
└──────────┘    │  SLOW!   │    └──────────┘
                └──────────┘

Expected:
• Total timeout triggers at 30 sec
• Partial result returned
• User notified of delay
• NOT: Silent hang for 60 sec
```

### Scenario 3: Hallucinator Upstream

```
┌────────────┐    WRONG DATA    ┌────────────┐
│ RESEARCHER │─────────────────►│   WRITER   │
│(HALLUC)    │  "Founded 1847"  └────────────┘
└────────────┘                        │
                                      ▼
                              ┌────────────┐
                              │  REVIEWER  │
                              └────────────┘
Expected:
• Reviewer catches error
• Fact-check step exists
• NOT: Wrong data published
```

---

## Chaos Engineering Maturity Model

```
LEVEL 1: NO CHAOS TESTING
─────────────────────────
• Hope nothing breaks
• Fix bugs after production incidents
• "It worked in my demo"

LEVEL 2: MANUAL FAULT INJECTION
───────────────────────────────
• Occasionally test edge cases
• Developer manually breaks things
• Some timeout handling

LEVEL 3: AUTOMATED CHAOS SUITE
──────────────────────────────
• CI/CD includes chaos tests
• All 6 injectors automated
• Alerts on new failure modes

LEVEL 4: CONTINUOUS CHAOS (Netflix-level)
─────────────────────────────────────────
• Random faults injected in production
• Auto-rollback on degradation
• Chaos tests run on every deploy

MOST COMPANIES: Level 1
TARGET FOR MVP: Level 2-3
```

---

## Design Partner Questions

> "What happens when one of your agents times out?"

> "If your researcher returns garbage, does the writer catch it?"

> "Have you tested what happens when an agent goes into an infinite loop?"

> "What's your token budget per request? What happens when you hit it?"

---

## Your Differentiator

```
┌─────────────────────────────────────────────────────────────┐
│              NO ONE ELSE DOES THIS                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LangSmith:  Observes failures AFTER they happen             │
│  Arize:      Monitors metrics AFTER deployment               │
│  Promptfoo:  Tests prompts, not orchestration                │
│                                                              │
│  YOU:        Inject failures BEFORE production               │
│              Verify graceful degradation                     │
│              Catch orchestration bugs in CI/CD               │
│                                                              │
│  "We're the chaos engineering layer for multi-agent systems" │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```
