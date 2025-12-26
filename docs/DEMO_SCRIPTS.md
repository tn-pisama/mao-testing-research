# MAO Testing Platform - Comprehensive Demo Guide

## Executive Summary

**What We Demo:** Self-healing infrastructure for multi-agent AI systems
**Core Message:** "We don't just detect AI agent failures—we fix them automatically"
**Key Differentiator:** Only platform that combines detection + diagnosis + remediation + validation

---

# Part 1: Audience-Specific Preparation

## Audience Profiles

### 🎯 Investors (VCs, Angels)

**What They Care About:**
- Market size and timing
- Technical moat
- Team capability
- Path to revenue
- Competitive differentiation

**Demo Focus:** Market opportunity → Live detection → Self-healing → Business model

**Key Metrics to Mention:**
- AI agents market: $236B by 2034
- SRE/observability tools: $42.7B by 2030
- 43% of engineering orgs report increased toil despite AI adoption
- 76/76 tests passing (technical validation)

**Opening Hook:**
> "Every company is deploying AI agents. Most have no idea when they fail or why. We built the first self-healing infrastructure for multi-agent systems."

**Closing CTA:**
> "We're raising [X] to capture the developer tools layer of the AI agent stack. Let's discuss how this fits your thesis."

---

### 🤝 Strategic Partners (Framework vendors, Cloud providers)

**What They Care About:**
- Integration complexity
- Value to their customers
- Revenue share potential
- Technical compatibility

**Demo Focus:** Integration points → SDK demonstration → Partner value prop

**Key Metrics to Mention:**
- Integration time: <1 hour for LangGraph/CrewAI
- Zero code changes for n8n (webhook-based)
- Supports OpenTelemetry standard

**Opening Hook:**
> "Your customers are building agents on [LangGraph/CrewAI/your platform]. They're hitting reliability issues you can't solve in-framework. We can."

**Closing CTA:**
> "We'd like to explore a technical partnership—either integration, co-marketing, or marketplace listing. What would be most valuable for your customers?"

---

### 🏢 Enterprise Buyers (CTOs, VPs Eng, Platform teams)

**What They Care About:**
- Reduce incidents and on-call burden
- Integrate with existing tools
- Security and compliance
- Time to value

**Demo Focus:** Dashboard → Real incident scenario → Fix generation → CI/CD integration

**Key Metrics to Mention:**
- Detection accuracy: 94%+ on golden dataset
- Time to fix: <3 seconds (detect → diagnose → fix → validate)
- Rollback always available
- SOC 2 Type II roadmap (if applicable)

**Opening Hook:**
> "Last month, how many incidents were caused by AI agents or LLM-based automation? How long did it take to root cause them? We reduce that to seconds."

**Closing CTA:**
> "Let's run a pilot with one of your agent workflows. We can have you instrumented in under an hour. What's the most critical workflow to start with?"

---

### 👩‍💻 Technical Buyers (Engineers, SREs, AI/ML teams)

**What They Care About:**
- Does it actually work?
- Integration effort
- Developer experience
- Won't slow them down

**Demo Focus:** CLI → Live debugging → MCP/Claude Code → Code generation

**Key Metrics to Mention:**
- CLI commands: `mao debug`, `mao fix`, `mao watch`
- 5-line SDK integration
- MCP tools for AI-native debugging

**Opening Hook:**
> "Let me show you what debugging AI agents looks like when you have the right tools."

**Closing CTA:**
> "The CLI is open source. Try it on your workflows this week and tell me what breaks. Here's my direct line."

---

### 🔬 Researchers / Academics

**What They Care About:**
- Novel detection algorithms
- Reproducibility
- Access to failure data
- Publication opportunities

**Demo Focus:** Detection methodology → Failure taxonomy → Research roadmap

**Opening Hook:**
> "We've catalogued failure modes across three major agent frameworks and built detection algorithms with 94% accuracy. The patterns are fascinating—and largely undocumented."

**Closing CTA:**
> "We'd love to collaborate on publishing this taxonomy. We have data you can't get elsewhere."

---

# Part 2: Demo Formats

## Format Options by Time Available

| Time | Format | Best For |
|------|--------|----------|
| 2 min | Elevator pitch + 1 screenshot | Networking, cold intros |
| 5 min | Web demo only (abbreviated) | Busy executives |
| 15 min | Full web demo + Q&A | Standard investor meeting |
| 30 min | Web + CLI + MCP demos | Technical deep dive |
| 60 min | Full demo + architecture + roadmap | Partner evaluations |

---

## 2-Minute Pitch (No Demo)

### Script:

> "We're building self-healing infrastructure for AI agents.
>
> Here's the problem: Companies are deploying multi-agent systems—using LangGraph, CrewAI, n8n—but these agents fail in ways traditional monitoring can't catch. Infinite loops, state corruption, agents going off-character. When they fail, it's a 3am incident with no clear root cause.
>
> **[Show single screenshot of detection]**
>
> We detect these failures in real-time with 94% accuracy, diagnose the root cause, and generate code fixes automatically. One click to apply. Validation included.
>
> The market is $236 billion by 2034. We're the only platform doing self-healing, not just observability.
>
> I'd love 15 minutes to show you the live demo."

---

## 5-Minute Executive Demo

### Flow:
1. (30s) Market context
2. (1m) Dashboard tour
3. (2m) Live detection + healing
4. (1m) Business model + ask

### Script:

**[Open Dashboard]**

> "AI agents are the next platform shift. But they fail in ways we've never seen before.
>
> **[Point to detection feed]** These are real failures we're catching—infinite loops, state corruption, agents drifting off-script.
>
> **[Click to demo page, trigger loop scenario]** Watch this. I'm running a LangGraph workflow with a bug. See the agents cycling?
>
> **[Wait for detection]** There—detected in under 2 seconds. 94% confidence.
>
> **[Click into detection]** Here's the root cause: unbounded recursion between researcher and analyst. No exit condition.
>
> **[Show fix suggestions]** We've generated three fixes. One click to apply.
>
> **[Click apply, show validation]** Fix applied. Validated. If it breaks, rollback is here.
>
> This cycle—detect, diagnose, fix, validate—takes 3 seconds. Not 3 hours.
>
> We're the only platform doing this. LangSmith shows you the problem. We fix it.
>
> **[Pause]** What questions do you have?"

---

# Part 3: Full Demo Scripts

## Web Platform Demo (15 minutes)

### Pre-Flight Checklist

```bash
# Terminal 1: Backend
cd /Users/tuomonikulainen/mao-testing-research/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend  
cd /Users/tuomonikulainen/mao-testing-research/frontend
npm run dev

# Browser tabs ready:
# - http://localhost:3000/dashboard
# - http://localhost:3000/demo
# - Backup: self_healing_demo.py terminal ready
```

### Demo Environment Checklist
- [ ] Notifications silenced
- [ ] Browser zoom at 100%
- [ ] Dark mode enabled (looks better on projector)
- [ ] Demo data loaded (run demo agents first if needed)
- [ ] Backup demo script ready

---

### Scene 1: The Problem (2 minutes)

**Screen:** Blank or title slide

**Script:**

> "Before I show you the product, let me set context on the problem.
>
> **The Shift:** Every company is building with AI agents. Not just chatbots—multi-agent systems where AI components collaborate. Research agents feeding analysis agents feeding writing agents.
>
> **The Frameworks:** LangGraph from LangChain, CrewAI, Microsoft AutoGen, n8n for no-code. These are the building blocks.
>
> **The Problem:** These agents fail in ways traditional APM can't catch:
>
> - **Infinite loops:** Agents get stuck asking each other the same question forever
> - **State corruption:** Data gets mangled as it passes between agents
> - **Persona drift:** An agent told to be professional starts using emojis and slang
> - **Deadlocks:** Agent A waits for Agent B, Agent B waits for Agent A
>
> **The Cost:** Token burn (you're paying OpenAI for loops), incidents at 3am, and—worst—bad outputs reaching customers.
>
> **Current Solutions:** LangSmith, Arize, Weights & Biases. They're observability. They show you what happened. You still have to figure out why and how to fix it.
>
> We do that part automatically. Let me show you."

---

### Scene 2: Dashboard Overview (2 minutes)

**Screen:** `/dashboard`

**What They See:**
```
┌─────────────────────────────────────────────────────────────┐
│  MAO Testing Platform                         [Import Data] │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ Loop Analytics      │  │ Cost Analytics      │          │
│  │ ████████ 42%       │  │ $2,340 saved       │          │
│  │ ████ 28%           │  │ ████████████       │          │
│  │ ██ 18%             │  │ Token waste: -67%   │          │
│  │ █ 12%              │  │                     │          │
│  └─────────────────────┘  └─────────────────────┘          │
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ Recent Detections   │  │ Trace Status        │          │
│  │ 🔴 infinite_loop    │  │ ✅ trace-abc  OK    │          │
│  │ 🟡 persona_drift    │  │ ❌ trace-def  FAIL  │          │
│  │ 🔴 state_corruption │  │ ✅ trace-ghi  OK    │          │
│  └─────────────────────┘  └─────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

**Script:**

> "This is your command center.
>
> **[Point to Loop Analytics]** Detection breakdown by type. Infinite loops are 42% of what we catch—they're the most common and most expensive.
>
> **[Point to Cost Analytics]** This is CFO-friendly. We track token waste from failures. This customer saved $2,340 last month by catching loops before they burned through their OpenAI budget.
>
> **[Point to Recent Detections]** Live feed. Every detection has a severity, a confidence score, and a trace ID.
>
> **[Point to Trace Status]** Which workflows are healthy, which aren't.
>
> Now let me show you detection in action."

**Transition:** Click "Interactive Demo" in sidebar

---

### Scene 3: Live Detection Demo (4 minutes)

**Screen:** `/demo`

#### Part A: Healthy Workflow (1 minute)

**Actions:**
1. Select "Healthy Workflow" scenario
2. Click "Start Demo"
3. Let run for 20 seconds

**What They See:**
- Agent visualization with flowing messages
- Green status indicators
- Metrics panel showing normal execution

**Script:**

> "Let's start with a healthy workflow so you know what normal looks like.
>
> This is a LangGraph setup—three agents. Researcher gathers information, Analyst processes it, Writer produces output.
>
> **[Point to visualization]** Messages flowing left to right. Each arrow is a handoff.
>
> **[Point to metrics]** Execution time, token count, iterations—all normal.
>
> **[Point to activity feed]** You can see the play-by-play.
>
> Now let me break it."

**Action:** Click Reset, select "Infinite Loop"

---

#### Part B: Infinite Loop Detection (2 minutes)

**Actions:**
1. Select "Infinite Loop" scenario
2. Click "Start Demo"
3. Wait for detection (5 seconds)
4. Click to expand detection

**What They See:**
- Agents start cycling (bidirectional arrows)
- Loop visualization appears
- Red "Issue Detected" badge pulses
- Live Detection Feed populates

```
┌─────────────────────────────────────────────────────────────┐
│  🔴 Live Detections                            [1 Active]  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ⟳ Infinite Loop Detected                    HIGH   │   │
│  │   94% confidence • just now                         │   │
│  │                                                     │   │
│  │   Agents cycling: researcher ↔ analyst             │   │
│  │   Pattern: Research → Analyze → Research (×7)      │   │
│  │                                                     │   │
│  │   Affected: [Researcher] [Analyst]                 │   │
│  │                                                     │   │
│  │   [View Details]  [Dismiss]                        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Script:**

> "I've injected a loop bug. Watch the visualization.
>
> **[Wait for cycling]** See it? Researcher sends to Analyst, Analyst sends back to Researcher. Back and forth. This will go forever.
>
> In production, this is a 3am page. Your on-call is debugging with logs, trying to figure out what happened.
>
> **[When detection appears]** There. Detected in under 3 seconds.
>
> **[Point to confidence]** 94% confidence. High severity. We know this is a real problem, not noise.
>
> **[Point to pattern]** We identified the cycle: Research → Analyze → Research, seven times already.
>
> **[Point to affected agents]** Researcher and Analyst.
>
> Most observability tools stop here. They'd page you and say 'something's wrong.'
>
> We don't stop here. Click View Details."

---

#### Part C: Self-Healing (2 minutes)

**What They See (Detection Detail):**
```
┌─────────────────────────────────────────────────────────────┐
│  Detection: det-abc123def                                   │
├─────────────────────────────────────────────────────────────┤
│  ROOT CAUSE ANALYSIS                                        │
│  ─────────────────────────────────────────────────────────  │
│  Category: Infinite Loop (Structural)                       │
│  Confidence: 94%                                            │
│  Root Cause: Unbounded recursion between agents             │
│                                                             │
│  Indicators:                                                │
│  • State hash repeated 7 times                              │
│  • No exit condition in graph definition                    │
│  • Same tool calls with identical inputs                    │
│                                                             │
│  Affected Components: researcher, analyst                   │
├─────────────────────────────────────────────────────────────┤
│  FIX SUGGESTIONS                                            │
│  ─────────────────────────────────────────────────────────  │
│  1. [HIGH] Add Iteration Limit                              │
│     Adds max_iterations parameter to StateGraph             │
│     Code: graph.max_iterations = 10                         │
│                                                             │
│  2. [MEDIUM] Circuit Breaker Pattern                        │
│     Stops calling failing components after threshold        │
│                                                             │
│  3. [MEDIUM] Exponential Backoff                            │
│     Slows down repeated operations                          │
│                                                             │
│  [Apply Recommended Fix]  [View All Options]                │
├─────────────────────────────────────────────────────────────┤
│  VALIDATION (after apply)                                   │
│  ─────────────────────────────────────────────────────────  │
│  ✅ Configuration valid                                     │
│  ✅ Loop prevention enabled                                 │
│  ✅ Regression tests pass                                   │
│  ✅ Rollback available                                      │
└─────────────────────────────────────────────────────────────┘
```

**Script:**

> "This is where we're different.
>
> **[Point to Root Cause]** We've diagnosed why. Unbounded recursion. No exit condition. The agents have no way to know when to stop.
>
> **[Point to Indicators]** These are the signals we used. State hash repeated—same data going around. No exit condition in the graph. Identical tool calls.
>
> **[Point to Fix Suggestions]** We've generated three options with confidence scores.
>
> Option 1 is the recommended fix: add an iteration limit. This is a one-line change to the StateGraph.
>
> **[Click Apply]** One click. Fix is applied to the configuration.
>
> **[Point to Validation]** And we validate. Configuration is valid—we didn't break anything. Loop prevention is now enabled. Regression tests pass. And if something goes wrong, rollback is available.
>
> **[Pause for effect]** This whole flow—detect, diagnose, generate fix, apply, validate—took under 3 seconds.
>
> That's what self-healing means. Not 'we alert you.' We fix it."

---

### Scene 4: Other Failure Modes (2 minutes)

**Optional extension for longer demos**

**Script:**

> "Loops are the most common. Let me show you the other failure modes quickly.
>
> **[Select State Corruption scenario]** State corruption: data gets mangled between agents. We detect schema violations, impossible values, fields that shouldn't be null.
>
> **[Select Persona Drift scenario]** Persona drift: an agent's behavior changes from what you defined. Your 'professional analyst' starts using emojis. We catch tone shifts, capability creep, role abandonment.
>
> **[If time: Select Deadlock scenario]** Deadlock: Agent A waits for Agent B, Agent B waits for Agent A. Common in complex orchestrations.
>
> Each failure mode has specialized detection algorithms and fix strategies."

---

### Scene 5: Business Context (3 minutes)

**Screen:** Can stay on dashboard or go to blank

**Script:**

> "Let me put this in business context.
>
> **Market:** AI agents are a $236 billion market by 2034. Every company is deploying them. But reliability tooling is nascent.
>
> **Competition:** LangSmith does tracing—they show you what happened. Arize does ML monitoring—model metrics. Datadog has APM. None of them do self-healing. None of them understand agent-specific failure modes.
>
> **Our Moat:**
> 1. Detection algorithms trained on real agent failures across frameworks
> 2. Fix generation that's actually applicable—not generic advice
> 3. Validation that proves the fix works
>
> **Business Model:** Open core. Detection engine is open source. Self-healing, enterprise features, and cloud hosting are paid.
>
> **Traction:** [Insert actual traction—GitHub stars, design partners, waitlist]
>
> **Ask:** [Insert your specific ask]
>
> What questions do you have?"

---

## CLI Demo (10 minutes)

### Setup

```bash
# Verify CLI
mao --version
# → mao, version 0.1.0

# Verify config
mao config show
# → Endpoint: http://localhost:8000
# → API Key: ****...****
```

---

### Scene 1: The Developer Workflow (2 minutes)

**Script:**

> "Most engineers live in the terminal. That's where we meet them.
>
> Our CLI is designed for the debugging workflow: What's wrong? Why? How do I fix it?"

**Command:**
```bash
mao --help
```

**Output:**
```
Usage: mao [OPTIONS] COMMAND [ARGS]...

MAO - Multi-Agent Orchestration Testing Platform.

Debug AI agent failures, detect issues, and get fix suggestions.

Quick start:
  mao config init          Set up credentials
  mao debug <trace-id>     Analyze a trace for issues
  mao fix <detection-id>   Get fix suggestions

Commands:
  debug   Analyze traces for agent failures
  fix     Get fix suggestions for a detection
  watch   Watch for new detections in real-time
  config  Manage CLI configuration
  ci      CI/CD helper commands
```

**Script:**

> "Four main commands: `debug` to analyze, `fix` to get solutions, `watch` for real-time monitoring, and `ci` for pipeline integration."

---

### Scene 2: Debugging Traces (3 minutes)

**Command:**
```bash
mao debug --last 5
```

**Output:**
```
🔍 Trace: trace-a1b2c3d4
├─ Framework: langgraph
├─ Duration: 1,892ms
├─ Agents: 3
└─ Status: HEALTHY

✅ No issues detected

🔍 Trace: trace-e5f6g7h8
├─ Framework: langgraph
├─ Duration: 47,293ms  ← Long duration = problem
├─ Agents: 3
└─ Status: UNHEALTHY

Issues Found:
  🔴 infinite_loop (HIGH)  det-abc123456789
     Agent cycling: researcher ↔ analyst
     Iterations: 47 (limit: none)
     Token burn: ~$0.84

💡 Run 'mao fix det-abc123456789' to see suggested fixes

🔍 Trace: trace-i9j0k1l2
├─ Framework: crewai
├─ Duration: 5,621ms
├─ Agents: 4
└─ Status: UNHEALTHY

Issues Found:
  🟡 persona_drift (MEDIUM)  det-xyz789012345
     Agent 'writer' tone mismatch
     Expected: professional
     Actual: casual (emojis detected)

🔍 Trace: trace-m3n4o5p6
├─ Framework: n8n
├─ Duration: 3,102ms
├─ Agents: 2
└─ Status: HEALTHY

✅ No issues detected

🔍 Trace: trace-q7r8s9t0
├─ Framework: langgraph
├─ Duration: 12,445ms
├─ Agents: 5
└─ Status: UNHEALTHY

Issues Found:
  🔴 state_corruption (HIGH)  det-stuvwxyz1234
     Field 'analysis_result' became null
     Data loss detected between analyst → writer
```

**Script:**

> "Let me analyze my last 5 traces.
>
> **[Run command]**
>
> **[Point to first trace]** This one's healthy. 1.8 seconds, no issues.
>
> **[Point to second trace]** Here's our infinite loop. Look at that duration—47 seconds. Should have been 2 seconds. 47 iterations, no limit set. We even estimate the token cost—$0.84 burned on this one loop.
>
> **[Point to persona drift]** Different framework—CrewAI. Persona drift. The writer agent started using emojis when it should be professional.
>
> **[Point to state corruption]** n8n workflow. State corruption. A field that should have data became null.
>
> Now let me get the fix for that loop."

---

### Scene 3: Getting Fixes (3 minutes)

**Command:**
```bash
mao fix det-abc123456789
```

**Output:**
```
Fix Suggestions for det-abc123456789

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Add Iteration Limit (HIGH confidence)
   
   Adds max_iterations parameter to prevent unbounded loops.
   Estimated fix time: <1 minute
   Rollback: Available

   Code changes:
   📄 workflow.py (line 45)
   ┌──────────────────────────────────────────────────────────────┐
   │ from langgraph.graph import StateGraph                       │
   │ from my_agents import researcher, analyst, writer            │
   │                                                              │
   │ graph = StateGraph(AgentState)                               │
   │ graph.max_iterations = 10  # ← Add this line                 │
   │                                                              │
   │ graph.add_node("researcher", researcher)                     │
   │ graph.add_node("analyst", analyst)                           │
   │ graph.add_node("writer", writer)                             │
   └──────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2. Circuit Breaker Pattern (MEDIUM confidence)
   
   Stops calling failing components after 3 consecutive failures.
   More aggressive than iteration limit.

   Code changes:
   📄 workflow.py
   ┌──────────────────────────────────────────────────────────────┐
   │ from langgraph.prebuilt import circuit_breaker               │
   │                                                              │
   │ @circuit_breaker(failure_threshold=3, reset_timeout=60)      │
   │ def researcher(state: AgentState) -> AgentState:             │
   │     # existing code                                          │
   └──────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3. Exponential Backoff (LOW confidence)
   
   Slows down repeated operations. May not fully prevent loops.

💡 Run 'mao fix det-abc123456789 --apply' to apply the recommended fix
```

**Script:**

> "Three options, ranked by confidence.
>
> **[Point to option 1]** Recommended: iteration limit. One line. We even tell you which file and line number.
>
> **[Point to code block]** This is copy-paste ready. `graph.max_iterations = 10`. After 10 iterations, stop.
>
> **[Point to option 2]** Alternative: circuit breaker. More sophisticated—stops calling components that keep failing.
>
> **[Point to option 3]** Third option: backoff. Might slow the loop but won't stop it. Low confidence.
>
> Let's apply the fix."

---

### Scene 4: Applying Fixes (1 minute)

**Command:**
```bash
mao fix det-abc123456789 --apply
```

**Output:**
```
Applying fix: Add Iteration Limit

[1/4] Generating patch... done
[2/4] Validating configuration... done  
[3/4] Running regression checks... done
[4/4] Creating rollback point... done

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Fix applied successfully

Configuration Changes:
  + settings.loop_prevention.enabled: true
  + settings.loop_prevention.max_iterations: 10
  + settings.loop_prevention.detection_threshold: 3

Validation Results:
  ✅ Configuration schema valid
  ✅ Loop prevention active
  ✅ All nodes preserved
  ✅ Connections intact

Rollback command: mao rollback det-abc123456789

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Script:**

> "One command. Fix applied.
>
> **[Point to steps]** We generated the patch, validated it won't break anything, ran regression checks, and created a rollback point.
>
> **[Point to changes]** Here's exactly what changed. Loop prevention enabled, max 10 iterations.
>
> **[Point to validation]** And validation: config is valid, loop prevention is active, we didn't remove any nodes or break connections.
>
> **[Point to rollback]** If anything goes wrong: `mao rollback`. We've got you covered."

---

### Scene 5: Watch Mode and CI (1 minute)

**Command (Watch):**
```bash
mao watch --severity high
```

**Output:**
```
ℹ️  Watching for new detections... (Ctrl+C to stop)

[14:32:01] 🔴 infinite_loop detected in trace-newone123
           researcher ↔ analyst cycling (det-new001)
           
[14:32:45] 🔴 state_corruption detected in trace-another456
           null injection in 'result' field (det-new002)
```

**Script:**

> "For real-time monitoring: `mao watch`.
>
> Leave this running while you develop. See issues the moment they happen."

**Command (CI):**
```bash
mao ci check --threshold 90
```

**Output:**
```
ℹ️  Running golden dataset validation...

Detection Accuracy: 94.2%
Threshold: 90.0%

Results by Type:
  infinite_loop:     96.3% (182/189)
  state_corruption:  92.1% (105/114)
  persona_drift:     91.8% (78/85)
  deadlock:          98.2% (55/56)

Total: 420/444 correct detections

✅ Accuracy 94.2% meets threshold 90.0%
```

**Script:**

> "For CI/CD: `mao ci check`.
>
> Gate deployments on detection accuracy. If your agents aren't reliable, don't ship them."

---

## MCP / Claude Code Demo (10 minutes)

### Setup

```json
// ~/.config/claude/claude_desktop_config.json
{
  "mcpServers": {
    "mao": {
      "command": "python",
      "args": ["-m", "mao.mcp.server", "http://localhost:8000", "api-key"]
    }
  }
}
```

---

### Scene 1: Natural Language Debugging (3 minutes)

**You type in Claude Code:**
> "Can you check my latest agent trace for issues?"

**Claude responds:**
```
I'll analyze your latest trace for any issues.

[Calling mao_analyze_trace with trace_id="latest"]

I found 2 issues in trace-abc123:

## 1. Infinite Loop (HIGH severity)
- **Confidence:** 94%
- **Problem:** Your researcher and analyst agents are stuck in a cycle
- **Details:** They've exchanged the same message 7 times
- **Detection ID:** det-loop-001

## 2. Persona Drift (MEDIUM severity)  
- **Confidence:** 85%
- **Problem:** Your writer agent has drifted from its defined persona
- **Details:** Expected professional tone, but detected casual language with emojis
- **Detection ID:** det-drift-002

The infinite loop is urgent—it's burning tokens and will never complete.

Would you like me to get fix suggestions for either issue?
```

**Script:**

> "This is the AI-native experience.
>
> I didn't learn new commands. I didn't open a dashboard. I asked Claude in plain English.
>
> **[Point to tool call]** Claude automatically called our `mao_analyze_trace` tool.
>
> **[Point to results]** It summarized the issues conversationally. Two problems: a loop and a drift.
>
> Let me get the fix."

---

### Scene 2: Getting Fix Suggestions (2 minutes)

**You type:**
> "Get me fixes for the infinite loop"

**Claude responds:**
```
[Calling mao_get_fix_suggestions with detection_id="det-loop-001"]

Here are your options for fixing the infinite loop:

## Recommended: Add Iteration Limit
**Confidence: HIGH** (94% success rate in similar cases)

This is a one-line change to your StateGraph:

```python
# In workflow.py, around line 45
graph = StateGraph(AgentState)
graph.max_iterations = 10  # Add this line
```

This stops the graph after 10 iterations maximum, preventing infinite cycles.

## Alternative: Circuit Breaker
**Confidence: MEDIUM**

```python
from langgraph.prebuilt import circuit_breaker

@circuit_breaker(failure_threshold=3, reset_timeout=60)
def researcher(state):
    # your existing code
```

This stops calling the researcher after 3 consecutive similar calls.

---

Would you like me to apply the iteration limit fix to your workflow.py?
```

**Script:**

> "I asked for fixes. Claude called our fix suggestion tool.
>
> **[Point to recommended fix]** Here's the code. Not 'you should add rate limiting.' Actual code, file path, line number.
>
> Now watch this part."

---

### Scene 3: Applying the Fix (2 minutes)

**You type:**
> "Yes, apply the iteration limit fix"

**Claude responds:**
```
I'll add the iteration limit to your workflow.py.

[Reading file: /path/to/workflow.py]

[Editing file: /path/to/workflow.py]
Adding: graph.max_iterations = 10

✅ Done! I've added the iteration limit to your workflow.py.

Here's what changed:

```diff
  graph = StateGraph(AgentState)
+ graph.max_iterations = 10
  
  graph.add_node("researcher", researcher)
```

The infinite loop issue should now be resolved. Your graph will stop after 10 iterations maximum.

Want me to run your tests to verify the fix works?
```

**Script:**

> "Claude read my file, found the right place, and made the edit.
>
> **[Point to diff]** One line added. No copy-paste.
>
> This is what AI-native debugging looks like. The human describes the problem in natural language. The AI figures out the rest."

---

### Scene 4: Proactive Assistance (2 minutes)

**You type:**
> "Check all my traces from the last hour and summarize any patterns"

**Claude responds:**
```
[Calling mao_get_detections with timeframe="1h"]

I analyzed 23 traces from the last hour. Here's what I found:

## Summary
- ✅ 18 traces healthy (78%)
- ❌ 5 traces with issues (22%)

## Patterns Detected

### 1. Recurring Loop in Research Flow
**3 occurrences** — det-001, det-007, det-019
- All involve researcher ↔ analyst cycle
- Same root cause: no iteration limit
- **Recommendation:** Add global iteration limit to this workflow

### 2. Intermittent State Corruption  
**2 occurrences** — det-004, det-015
- Both show null injection in 'analysis_result' field
- Happens when analyst returns empty response
- **Recommendation:** Add null check before passing to writer

## Suggested Actions
1. Fix the iteration limit (affects 3 traces)
2. Add null validation (affects 2 traces)

Would you like me to apply both fixes?
```

**Script:**

> "Now I'm asking Claude to be proactive. Analyze an hour of data, find patterns.
>
> **[Point to patterns]** It found two recurring issues. Three traces hit the same loop bug. Two traces had the same null problem.
>
> **[Point to recommendations]** And it recommends batch fixes.
>
> This is the future of debugging. Not reactive. Proactive. Pattern-aware."

---

# Part 4: Objection Handling

## Technical Objections

| Objection | Response |
|-----------|----------|
| "How accurate is detection?" | "94.2% on our golden dataset of 444 labeled traces. We publish precision/recall by failure type." |
| "What if the fix breaks something?" | "Every fix has validation and rollback. We check schema validity, run regression tests, and preserve a rollback point." |
| "How does it handle custom agent logic?" | "We analyze execution traces, not source code. If it runs, we can trace it. Custom logic shows up as custom spans." |
| "Does it work with my framework?" | "LangGraph, CrewAI, and n8n today. AutoGen and Semantic Kernel coming Q1. We follow OpenTelemetry standards." |

## Business Objections

| Objection | Response |
|-----------|----------|
| "We already use LangSmith" | "LangSmith is observability—it shows you what happened. We're remediation—we fix it. Complementary, not competitive." |
| "Our team can debug manually" | "Of course. But at 3am? At scale? We've seen teams go from 2-hour MTTR to 3-second MTTR." |
| "What's the pricing?" | "Open core model. Detection is free. Self-healing and enterprise features are paid. Usage-based, scales with your agents." |
| "What about data privacy?" | "We process traces, not prompts. Sensitive data can be redacted. On-prem deployment available for enterprise." |

## Investor Objections

| Objection | Response |
|-----------|----------|
| "Is the market real?" | "Every company is deploying AI agents. But 43% report increased operational toil. They need better tools." |
| "What's the moat?" | "Detection algorithms trained on real failures, fix generation that works, and network effects as we see more patterns." |
| "Who's the team?" | "[Your background]. We've been building developer tools for X years." |
| "What's the competition?" | "LangSmith (tracing), Arize (ML monitoring), Datadog (APM). None do self-healing. None specialize in agents." |

---

# Part 5: Backup Demos

## If Backend Is Down

```bash
cd /Users/tuomonikulainen/mao-testing-research/demo-agent
python self_healing_demo.py --mode all --auto-apply
```

This runs locally with no network dependencies.

## If Frontend Is Down

Use CLI demo only—it's self-contained.

## If Everything Is Down

Use screenshots + narrative:

> "Let me walk you through what you would see..."

Keep screenshots in `/docs/demo-screenshots/`:
- dashboard.png
- detection-loop.png
- fix-suggestions.png
- validation-results.png

---

# Part 6: Follow-Up Materials

## After the Demo

### For Investors:
- [ ] Send deck with market sizing
- [ ] Share this demo recording
- [ ] Propose follow-up for deep dive

### For Partners:
- [ ] Send integration documentation
- [ ] Propose technical call with engineering
- [ ] Share SDK access

### For Enterprise:
- [ ] Send pilot proposal
- [ ] Identify champion and workflow
- [ ] Schedule technical onboarding

### For Engineers:
- [ ] Share CLI installation instructions
- [ ] Point to open source repo
- [ ] Invite to Discord/community

---

# Appendix: Key Metrics Reference

| Metric | Value | Source |
|--------|-------|--------|
| Detection accuracy | 94.2% | Golden dataset (444 traces) |
| Tests passing | 76/76 | E2E + unit tests |
| Detection latency | <2 seconds | Live demo |
| Fix application time | <3 seconds | Include validation |
| Frameworks supported | 3 | LangGraph, CrewAI, n8n |
| Failure modes covered | 4 | Loop, corruption, drift, deadlock |
| AI agent market (2034) | $236B | Industry reports |
| SRE tools market (2030) | $42.7B | Industry reports |

---

*Document version: 2.0*
*Last updated: 2025-12-26*
*Maintainer: MAO Team*
