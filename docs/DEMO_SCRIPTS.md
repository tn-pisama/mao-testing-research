# MAO Testing Platform - Demo Scripts

## Overview

Three demo formats for different contexts:

| Demo | Duration | Best For | Setup Required |
|------|----------|----------|----------------|
| **Web Platform** | 5-10 min | Investors, executives, visual learners | Frontend + Backend running |
| **CLI** | 3-5 min | Engineers, CTOs, technical buyers | CLI installed, API running |
| **MCP/Claude Code** | 5-8 min | AI-native teams, Claude users | MCP server configured |

---

# Demo 1: Web Platform

## Pre-Demo Checklist

```bash
# Terminal 1: Start backend
cd /Users/tuomonikulainen/mao-testing-research/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2: Start frontend
cd /Users/tuomonikulainen/mao-testing-research/frontend
npm run dev

# Browser: Open http://localhost:3000
```

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         WEB DEMO FLOW                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ Dashboard │ -> │  Demo    │ -> │ Detection│ -> │  Healing │      │
│  │ Overview  │    │  Page    │    │  Detail  │    │  Result  │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │               │               │               │              │
│    30 sec          2 min           2 min           2 min            │
│                                                                      │
│  "Here's what    "Watch real-   "Drill into    "And here's        │
│   we monitor"     time detect"   the failure"   the auto-fix"     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Scene 1: Dashboard Overview (30 seconds)

### Screen: `/dashboard`

### What They See:
- Loop Analytics card (detection trends)
- Cost Analytics card (token waste from failures)
- Recent Detections list
- Trace Status overview

### Script:

> "This is the MAO dashboard. It shows you what's happening across all your multi-agent workflows in real-time.
>
> **[Point to Loop Analytics]** Here we're tracking detection patterns - infinite loops are the most common failure mode we see, about 40% of issues.
>
> **[Point to Cost Analytics]** This is interesting for CFOs - we track token waste from failures. Those infinite loops? They're burning money every time an agent cycles.
>
> **[Point to Recent Detections]** Live feed of issues. Let me show you how detection works..."

### Transition:
Click "Interactive Demo" in sidebar

---

## Scene 2: Interactive Demo - Healthy Flow (1 minute)

### Screen: `/demo`

### Actions:
1. Ensure "Healthy Workflow" scenario is selected
2. Click "Start Demo"
3. Let it run for 15 seconds

### What They See:
- Agent orchestration visualization
- Agents communicating (Researcher → Analyst → Writer)
- Green metrics, smooth execution
- Activity feed showing normal operations

### Script:

> "Let's start with a healthy workflow. This is a typical LangGraph setup - Researcher gathers info, Analyst processes it, Writer outputs.
>
> **[Point to visualization]** You can see the messages flowing between agents. Everything's green, no issues.
>
> **[Point to metrics]** Execution time, token usage, all normal.
>
> Now let me show you what happens when things go wrong..."

### Transition:
Click "Reset", then select "Infinite Loop" scenario

---

## Scene 3: Infinite Loop Detection (2 minutes)

### Screen: `/demo` with "Infinite Loop" scenario

### Actions:
1. Select "Infinite Loop" scenario
2. Click "Start Demo"
3. Wait 5 seconds for detection to appear
4. Click on the detection when it appears

### What They See:
- Agents start cycling (Researcher ↔ Analyst)
- Loop visualization appears (circular pattern)
- Red "Issue Detected" badge pulses
- Live Detection Feed shows the issue

### Script:

> "Now watch what happens when agents get stuck. I've injected a loop scenario.
>
> **[Wait for cycling]** See the agents going back and forth? Researcher asks Analyst, Analyst sends back to Researcher, over and over.
>
> **[When detection appears]** There it is - our detector caught it. 94% confidence, infinite loop, affecting Researcher and Analyst.
>
> **[Click to expand detection]** The key insight here: most observability tools would just show you this is happening. They'd alert you at 3am.
>
> We go further. Let me show you the fix..."

### Key Talking Point (for Jason):

> "Phoenix would get the incident when this hits production. We prevent the incident from happening. This is upstream of what you're building."

---

## Scene 4: Self-Healing Demonstration (2 minutes)

### Screen: Detection detail → Healing panel

### What To Show:
- Root cause analysis
- Fix suggestions (retry limit, circuit breaker)
- Configuration diff
- Validation results

### Script:

> "Here's where we're different from LangSmith or Arize.
>
> **[Point to root cause]** We've diagnosed the root cause: unbounded recursion between these two agents. No iteration limits, no exit conditions.
>
> **[Point to fix suggestions]** We've generated three fix options:
> 1. Add max iterations limit
> 2. Circuit breaker pattern
> 3. Exponential backoff
>
> **[Point to confidence scores]** Each has a confidence score based on our training data.
>
> **[Click Apply]** One click, fix is applied.
>
> **[Point to validation]** And we validate it worked - configuration is valid, loop prevention is active, regression tests pass.
>
> This whole cycle - detect, diagnose, fix, validate - happens in under 3 seconds."

### Closing for Web Demo:

> "That's the web platform. Real-time monitoring, automatic detection, self-healing. Questions before I show you the CLI?"

---

# Demo 2: CLI

## Pre-Demo Checklist

```bash
# Ensure CLI is installed
cd /Users/tuomonikulainen/mao-testing-research
pip install -e ./mao

# Verify it works
mao --version
# Should show: mao, version 0.1.0

# Configure (if not already)
mao config init
# Endpoint: http://localhost:8000
# Tenant: demo
# API Key: demo-key
```

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLI DEMO FLOW                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  $ mao debug --last 3                                               │
│       │                                                              │
│       ▼                                                              │
│  ┌──────────────────────────────────────┐                           │
│  │ 🔍 Trace: trace-abc123               │                           │
│  │ ├─ Framework: langgraph              │                           │
│  │ ├─ Duration: 4523ms                  │                           │
│  │ └─ Status: UNHEALTHY                 │                           │
│  │                                      │                           │
│  │ Issues Found:                        │                           │
│  │   🔴 infinite_loop (HIGH)            │                           │
│  │      Agent cycling detected          │                           │
│  └──────────────────────────────────────┘                           │
│       │                                                              │
│       ▼                                                              │
│  $ mao fix det-xyz789                                               │
│       │                                                              │
│       ▼                                                              │
│  ┌──────────────────────────────────────┐                           │
│  │ Fix Suggestions for det-xyz789       │                           │
│  │                                      │                           │
│  │ 1. Add Iteration Limit (high conf)   │                           │
│  │    + max_iterations: 10              │                           │
│  │                                      │                           │
│  │ 2. Circuit Breaker (medium conf)     │                           │
│  │    + circuit_breaker: enabled        │                           │
│  └──────────────────────────────────────┘                           │
│       │                                                              │
│       ▼                                                              │
│  $ mao fix det-xyz789 --apply                                       │
│       │                                                              │
│       ▼                                                              │
│  ✅ Fix applied successfully                                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Scene 1: Debug Recent Traces (1 minute)

### Command:
```bash
mao debug --last 3
```

### Expected Output:
```
🔍 Trace: trace-a1b2c3d4
├─ Framework: langgraph
├─ Duration: 2341ms
└─ Status: HEALTHY

✅ No issues detected

🔍 Trace: trace-e5f6g7h8
├─ Framework: crewai
├─ Duration: 8923ms
└─ Status: UNHEALTHY

Issues Found:
  🔴 infinite_loop (HIGH)  det-abc123def
     Agent cycling: researcher ↔ analyst (7 iterations)

💡 Run mao fix det-abc123def to see suggested fixes

🔍 Trace: trace-i9j0k1l2
├─ Framework: n8n
├─ Duration: 3421ms
└─ Status: UNHEALTHY

Issues Found:
  🟡 persona_drift (MEDIUM)  det-xyz789abc
     Tone mismatch: expected professional, got casual
```

### Script:

> "This is how engineers actually use MAO day-to-day. 
>
> **[Run command]** `mao debug --last 3` - analyze my recent traces.
>
> **[Point to output]** First trace is healthy, no issues. Second trace - look at this - infinite loop detected with high confidence. Third has a persona drift.
>
> **[Point to detection ID]** Every detection gets an ID. Let me get the fix..."

---

## Scene 2: Get Fix Suggestions (1 minute)

### Command:
```bash
mao fix det-abc123def
```

### Expected Output:
```
Fix Suggestions for det-abc123def

1. Add Iteration Limit (high confidence)
   Adds max_iterations parameter to prevent unbounded loops

   Code changes:
   📄 workflow.py
   ┌────────────────────────────────────────┐
   │ graph = StateGraph(AgentState)         │
   │ graph.add_node("researcher", research) │
   │ graph.add_node("analyst", analyze)     │
   │                                        │
   │ # Add iteration limit                  │
   │ graph.max_iterations = 10              │
   │ graph.add_edge("researcher", "analyst")│
   └────────────────────────────────────────┘

2. Circuit Breaker Pattern (medium confidence)
   Adds circuit breaker to stop repeated failures

💡 Run mao fix det-abc123def --apply to apply a fix
```

### Script:

> "Now the fix. **[Run command]**
>
> We generate code changes with confidence scores. High confidence means we've seen this pattern before and know this fix works.
>
> **[Point to code block]** This is ready-to-apply code. Add `max_iterations = 10` to the graph.
>
> **[Point to alternatives]** We also suggest alternatives - circuit breaker pattern, exponential backoff. Different tradeoffs."

---

## Scene 3: Apply Fix (30 seconds)

### Command:
```bash
mao fix det-abc123def --apply -y
```

### Expected Output:
```
Applying fix: Add Iteration Limit

✅ Configuration updated
✅ Validation passed
✅ Fix applied successfully

Rollback available: mao rollback det-abc123def
```

### Script:

> "One command to apply. **[Run command]**
>
> Fix applied, validated, and we keep a rollback in case anything goes wrong.
>
> This is what I mean by self-healing - not just alerting, actually fixing."

---

## Scene 4: Watch Mode (30 seconds)

### Command:
```bash
mao watch --severity high
```

### Expected Output:
```
ℹ️  Watching for new detections... (Ctrl+C to stop)

🔴 [infinite_loop] Agent cycling detected (det-new123...)
🔴 [deadlock] Circular wait between planner and executor (det-new456...)
```

### Script:

> "For real-time monitoring: `mao watch`
>
> **[Run command]** This streams detections as they happen. High severity only.
>
> This is what you'd run in your terminal while developing, or hook into your CI/CD."

---

## Scene 5: CI Integration (30 seconds)

### Command:
```bash
mao ci check --threshold 95
```

### Expected Output:
```
ℹ️  Running golden dataset checks...

Results
Accuracy: 94.2% (threshold: 95%)
Tests: 420 passed, 0 failed

❌ Error: Accuracy 94.2% below threshold 95%
```

### Script:

> "And for CI/CD: `mao ci check`
>
> This validates your detection accuracy against a golden dataset. Gate your deployments on agent reliability."

---

# Demo 3: MCP with Claude Code

## Pre-Demo Checklist

```bash
# Add MCP server to Claude Code config
# ~/.config/claude/claude_desktop_config.json (or Claude Code settings)

{
  "mcpServers": {
    "mao": {
      "command": "python",
      "args": [
        "-m", "mao.mcp.server",
        "http://localhost:8000",
        "your-api-key",
        "default"
      ]
    }
  }
}

# Restart Claude Code after adding
```

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MCP / CLAUDE CODE DEMO                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  You: "Analyze my latest agent trace"                               │
│       │                                                              │
│       ▼                                                              │
│  Claude: [Uses mao_analyze_trace tool]                              │
│       │                                                              │
│       ▼                                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ I analyzed trace-abc123 and found 2 issues:                  │   │
│  │                                                               │   │
│  │ 1. **Infinite Loop** (HIGH severity, 94% confidence)         │   │
│  │    Agents researcher and analyst are cycling indefinitely.   │   │
│  │    Detection ID: det-xyz789                                  │   │
│  │                                                               │   │
│  │ 2. **Persona Drift** (MEDIUM severity, 85% confidence)       │   │
│  │    Writer agent tone has drifted from professional to casual │   │
│  │                                                               │   │
│  │ Would you like me to get fix suggestions for these?          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│       │                                                              │
│       ▼                                                              │
│  You: "Yes, fix the loop issue"                                     │
│       │                                                              │
│       ▼                                                              │
│  Claude: [Uses mao_get_fix_suggestions tool]                        │
│       │                                                              │
│       ▼                                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Here are the fix suggestions for the infinite loop:          │   │
│  │                                                               │   │
│  │ **Recommended: Add Iteration Limit**                         │   │
│  │ Confidence: HIGH                                             │   │
│  │                                                               │   │
│  │ Add this to your StateGraph initialization:                  │   │
│  │ ```python                                                    │   │
│  │ graph = StateGraph(AgentState)                               │   │
│  │ graph.max_iterations = 10  # Add this line                   │   │
│  │ ```                                                          │   │
│  │                                                               │   │
│  │ Want me to apply this change to your workflow.py?            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Available MCP Tools

| Tool | Description | Use When |
|------|-------------|----------|
| `mao_analyze_trace` | Analyze a trace for failures | "Check my last trace" |
| `mao_get_detections` | List all detections | "What issues do I have?" |
| `mao_get_fix_suggestions` | Get fixes for a detection | "How do I fix this?" |
| `mao_get_trace` | Get full trace details | "Show me the trace data" |

---

## Demo Script

### Scene 1: Natural Language Analysis

**You say to Claude Code:**
> "Can you analyze my latest agent trace and tell me if there are any issues?"

**Claude's response (using `mao_analyze_trace`):**

```
I'll analyze your latest trace for you.

<tool_use>
mao_analyze_trace
{"trace_id": "trace-latest"}
</tool_use>

I found 2 issues in your trace:

1. **Infinite Loop** (HIGH severity)
   - Confidence: 94%
   - Your researcher and analyst agents are stuck in a cycle
   - They've repeated the same exchange 7 times
   - Detection ID: det-abc123

2. **Persona Drift** (MEDIUM severity)
   - Confidence: 85%
   - Your writer agent has drifted from its professional tone
   - Now using casual language and emojis
   - Detection ID: det-xyz789

The infinite loop is the urgent one - it's burning tokens and will 
never complete. Would you like me to get fix suggestions?
```

### Script for this scene:

> "This is the magic of MCP integration. I just ask Claude in natural language.
>
> **[Point to tool use]** Claude automatically invokes our `mao_analyze_trace` tool.
>
> **[Point to response]** It formats the results conversationally. No learning new commands."

---

### Scene 2: Getting Fix Suggestions

**You say to Claude Code:**
> "Yes, get me fixes for the infinite loop"

**Claude's response (using `mao_get_fix_suggestions`):**

```
<tool_use>
mao_get_fix_suggestions
{"detection_id": "det-abc123"}
</tool_use>

Here are your options to fix the infinite loop:

## Recommended: Add Iteration Limit
**Confidence: HIGH** - This pattern has worked 94% of the time

Add this to your StateGraph:

```python
# In your workflow.py, around line 45
graph = StateGraph(AgentState)
graph.max_iterations = 10  # <-- Add this line

# The graph will now stop after 10 iterations max
```

## Alternative: Circuit Breaker
**Confidence: MEDIUM**

```python
from langgraph.prebuilt import circuit_breaker

@circuit_breaker(failure_threshold=3, reset_timeout=60)
def research_node(state):
    # Your existing code
```

Would you like me to apply the iteration limit fix to your workflow.py?
```

### Script for this scene:

> "I ask for fixes, Claude calls `mao_get_fix_suggestions`.
>
> **[Point to code]** It returns actual code I can use. Not just 'add rate limiting' but exactly what to write and where.
>
> **[Point to alternatives]** Multiple options with tradeoffs explained."

---

### Scene 3: Applying the Fix

**You say to Claude Code:**
> "Yes, apply the iteration limit to workflow.py"

**Claude's response:**

```
I'll add the iteration limit to your workflow.py.

<tool_use>
Edit
{"file_path": "/path/to/workflow.py", "old_string": "graph = StateGraph(AgentState)", "new_string": "graph = StateGraph(AgentState)\ngraph.max_iterations = 10"}
</tool_use>

Done! I've added `graph.max_iterations = 10` to your workflow.py.

The infinite loop issue should now be resolved. The graph will stop 
after 10 iterations maximum, preventing runaway agent cycles.

Want me to run your tests to verify the fix works?
```

### Script for this scene:

> "And Claude applies the fix directly to my code. No copy-paste.
>
> This is the developer experience we're building - AI-native debugging for AI agents."

---

## MCP Demo Talking Points for Jason

### On Developer Experience:
> "You talk about reducing context-switching. This is zero context-switching - developers stay in their editor, in their flow, and fix agent issues with natural language."

### On Integration:
> "Phoenix integrates with Jira and Slack. We integrate with Claude Code, Cursor, VS Code. Same philosophy - meet developers where they are."

### On the Future:
> "In 2 years, every developer will have an AI assistant. Those assistants need tools to debug AI systems. We're building that bridge."

---

# Demo Troubleshooting

## Common Issues

| Issue | Solution |
|-------|----------|
| Backend not responding | Check `uvicorn` is running on port 8000 |
| CLI says "API key not configured" | Run `mao config init` |
| MCP tools not appearing | Restart Claude Code, check config path |
| Detection not triggering in web demo | Wait full 5 seconds after starting |
| Empty trace list | Run demo agents first to generate data |

## Backup Demo (No Backend)

If backend is down, use the self-healing demo script:

```bash
cd /Users/tuomonikulainen/mao-testing-research/demo-agent
python self_healing_demo.py --mode all --auto-apply
```

This runs entirely locally and demonstrates the core healing pipeline.

### Sample Output:
```
================================================================================
             MAO TESTING PLATFORM - SELF-HEALING DEMONSTRATION
                         2025-12-26 15:30:00
================================================================================
Mode: ALL
Auto-Apply: ENABLED

======================================================================
  SELF-HEALING DEMO: Infinite Loop
======================================================================

--- DETECTION ---
  ID: det_a1b2c3d4e5f6
  Type: infinite_loop
  Confidence: 92%
  Method: structural
  Details:
    - loop_length: 7
    - affected_agents: ['researcher', 'analyst']
  Message: Node sequence [researcher, analyst] cycles detected.

--- FAILURE ANALYSIS ---
  Category: infinite_loop
  Pattern: structural_loop
  Confidence: 92%
  Root Cause: Unbounded recursion between agents
  Indicators:
    - State hash repeated 7 times
    - No exit condition detected
  Affected: researcher, analyst

--- FIX SUGGESTIONS ---
  1. [HIGH] retry_limit
     ID: fix_abc123
  2. [MEDIUM] circuit_breaker
     ID: fix_def456

--- APPLIED FIXES ---
  1. retry_limit
     Target: graph.settings
     Applied: 15:30:02
     Rollback: Available

--- CONFIGURATION CHANGES ---
  New Settings Added:
    + loop_prevention: ENABLED
        max_iterations: 10
        detection_threshold: 3

--- VALIDATION RESULTS ---
  [PASS] configuration_validation
       - valid_json: Yes
       - nodes_present: Yes
  [PASS] loop_prevention_validation
       - enabled: Yes
       - max_iterations: 10
  [PASS] regression_validation
       - nodes_preserved: Yes

--- HEALING RESULT ---
  ID: heal_xyz789
  Status: SUCCESS
  Duration: 0.03s
  Fixes Applied: 1
  Validations: 3/3 passed

[... corruption and drift demos follow ...]

======================================================================
  SUMMARY
======================================================================
  [PASS] infinite_loop         | Fixes: 1 | Validations: 3/3
  [PASS] state_corruption      | Fixes: 1 | Validations: 3/3
  [PASS] persona_drift         | Fixes: 1 | Validations: 3/3

  Total: 3/3 healing operations successful
```

---

# Quick Reference Card

## One-Liners for Each Demo

### Web Demo (5 seconds)
> "Real-time dashboard, click to detect, one-click heal"

### CLI Demo (5 seconds)
> "`mao debug` finds issues, `mao fix` generates code"

### MCP Demo (5 seconds)
> "Ask Claude to analyze your agents, it uses our tools"

## Key Differentiators to Emphasize

1. **Self-healing, not just observability** - We fix, not just alert
2. **Multi-framework** - LangGraph, CrewAI, n8n, more coming
3. **AI-native** - Built for the Claude/GPT era
4. **Developer-first** - CLI, MCP, CI/CD integration

## For Jason Specifically

| His Concern | Our Answer |
|-------------|------------|
| Incident chaos | We prevent incidents before they happen |
| Developer burnout | AI agents fix themselves at 3am |
| Tool sprawl | MCP means one tool (Claude) does it all |
| RCA burden | We generate root cause + fix automatically |

---

*Document generated: 2025-12-26*
*Version: 1.0*
