# PISAMA Demo Video Script

**Target Duration:** 3-5 minutes
**Format:** Loom screen recording with voiceover
**Audience:** Developers building AI agents

---

## Pre-Recording Checklist

- [ ] Clear browser cache / use incognito for fresh walkthrough
- [ ] Ensure frontend is running: `npm run dev`
- [ ] Ensure backend is running (optional for CLI demo)
- [ ] Test all demo scenarios work
- [ ] Clear localStorage to trigger guided tour: `localStorage.removeItem('pisama_demo_tour_seen')`
- [ ] Have sample trace file ready for upload demo
- [ ] Open terminal with `pisama-cc` installed

---

## Video Structure

### Section 1: Hook (0:00 - 0:30)

**Voiceover:**
> "If you're building AI agents, you've probably experienced this: you come back from a break to find your agent has burned through $50 in API tokens doing absolutely nothing. It got stuck in a loop, and you had no idea.
>
> PISAMA detects these failures in under 10 seconds and can automatically fix them. Let me show you how."

**On Screen:**
- Show dashboard briefly
- Flash a detection alert

---

### Section 2: Interactive Demo (0:30 - 2:00)

**Action:** Navigate to `/demo`

**Voiceover:**
> "Let's start with an interactive demo. PISAMA detects 16 types of agent failures, but let's focus on the most common one: infinite loops."

**Action:** Follow the guided walkthrough:

1. **Select "Infinite Loop" scenario**
   > "I'll select the infinite loop scenario..."

2. **Click "Start Demo"**
   > "...and start the simulation."

3. **Watch agents execute**
   > "Watch as the agents execute. You can see real-time metrics: active agents, messages, token usage, and costs."

4. **Wait for detection**
   > "And there it is. PISAMA detected a loop in under 8 seconds. It identified the exact pattern: the agent repeated the same action multiple times without making progress."

5. **Show the explanation**
   > "Notice the plain-English explanation. No need to dig through logs to understand what happened."

6. **Show fix suggestion (if visible)**
   > "And here's the suggested fix. One click to apply it."

---

### Section 3: Try Your Own Trace (2:00 - 2:45)

**Action:** Scroll down to "Try Your Own Trace"

**Voiceover:**
> "But you don't have to take my word for it. You can upload your own traces and see PISAMA analyze them right now."

**Action:** Drag and drop a sample trace file

> "I'll drop in a trace from one of our test sessions..."

**Action:** Watch analysis complete

> "And there we go. It found a semantic loop - the agent kept asking the same question in different words. This is something that's really hard to catch manually, but PISAMA's embedding-based detection caught it instantly."

---

### Section 4: CLI Installation (2:45 - 3:30)

**Action:** Switch to terminal

**Voiceover:**
> "Getting this for your own agents takes about 30 seconds."

**Action:** Show installation
```bash
pip install pisama-claude-code
pisama-cc install
pisama-cc demo
```

> "Install the package, run the install command to set up the hooks, and run the demo to see it in action with your first trace."

**Action:** Show demo output

> "That's it. From now on, every agent session is monitored. Loops are caught before they waste your budget."

---

### Section 5: Key Features (3:30 - 4:00)

**Action:** Quick montage of features

**Voiceover:**
> "Quick recap of what PISAMA gives you:
>
> - Real-time detection for 16 failure modes - loops, state corruption, coordination failures, and more
> - Plain-English explanations so you understand what went wrong
> - One-click fixes to resolve issues immediately
> - Framework support for LangGraph, AutoGen, CrewAI, Claude Code, and n8n
> - All running locally - your traces never leave your machine"

---

### Section 6: CTA (4:00 - 4:30)

**Action:** Show benchmarks page briefly

**Voiceover:**
> "Our detection accuracy is publicly benchmarked - check out our benchmarks page to see how we perform on over 20,000 real-world traces."

**Action:** Show getting started docs

> "Ready to try it? Check out our getting started guide at pisama.dev/docs. The free tier includes unlimited local analysis.
>
> Stop debugging agent failures manually. Let PISAMA catch them for you."

**End card:**
- PISAMA logo
- pisama.dev
- "pip install pisama-claude-code"

---

## Post-Production Notes

### Captions
Add auto-generated captions via Loom

### Thumbnail
Create thumbnail showing:
- Split screen: frustrated developer vs. PISAMA dashboard with detection
- Text: "Stop Agent Loops in 10 Seconds"

### Publishing Checklist
- [ ] Upload to Loom
- [ ] Generate embed code
- [ ] Add to landing page
- [ ] Add to README
- [ ] Share on Twitter/LinkedIn
- [ ] Add to docs getting started page

---

## Sample Trace Files

For the "Try Your Own" section, use these pre-prepared traces:

### 1. Healthy Trace (no detection)
```json
{
  "trace_id": "demo-healthy-001",
  "framework": "langgraph",
  "states": [
    {"agent_id": "planner", "content": "Planning task..."},
    {"agent_id": "executor", "content": "Executing step 1..."},
    {"agent_id": "executor", "content": "Executing step 2..."},
    {"agent_id": "reviewer", "content": "Review complete. Task done."}
  ]
}
```

### 2. Loop Trace (triggers detection)
```json
{
  "trace_id": "demo-loop-001",
  "framework": "claude_code",
  "failure_mode": "F1",
  "states": [
    {"agent_id": "agent", "content": "Searching for file..."},
    {"agent_id": "agent", "content": "Searching for file..."},
    {"agent_id": "agent", "content": "Searching for file..."},
    {"agent_id": "agent", "content": "Searching for file..."}
  ]
}
```

### 3. Semantic Loop (triggers detection)
```json
{
  "trace_id": "demo-semantic-001",
  "framework": "autogen",
  "failure_mode": "F3",
  "states": [
    {"agent_id": "assistant", "content": "Could you clarify what you mean?"},
    {"agent_id": "assistant", "content": "I need more details. Can you explain?"},
    {"agent_id": "assistant", "content": "I'm not sure I understand. Could you elaborate?"},
    {"agent_id": "assistant", "content": "What exactly are you looking for?"}
  ]
}
```

---

## Recording Tips

1. **Pace:** Speak slightly slower than natural - viewers can speed up but not slow down
2. **Pauses:** Pause 1 second after key moments for emphasis
3. **Mouse movement:** Move mouse smoothly, avoid jittery movements
4. **Errors:** If you make a mistake, pause, then re-do that section (edit later)
5. **Energy:** Sound enthusiastic but not salesy - developer audience is skeptical
6. **Avoid:** Marketing jargon, "revolutionary", "game-changing" - stick to facts

---

## Alternative Short Version (60 seconds)

For Twitter/LinkedIn:

1. (0-10s) Hook: "Your AI agent just cost you $50 doing nothing"
2. (10-30s) Show loop detection in action
3. (30-45s) Show fix application
4. (45-60s) "pip install pisama-claude-code" + CTA

---

*Last updated: 2025-01-05*
