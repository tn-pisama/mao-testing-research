---
title: "PISAMA Product Demo Script"
duration: "4 minutes"
target_audience: "Developer/Technical Decision Maker"
tone: "Professional, Technical, Clear"
---

# PISAMA Product Demo Script (4 minutes)

## [0:00-0:30] Hook & Problem (30 seconds)

**[Screen: Black with text]**

**NARRATOR:**
"This multi-agent system ran for 8 hours in production...

[Text appears: $5,200 API bill]

...calling GPT-4 in an infinite loop.

[Text appears: No error thrown. No timeout hit.]

The problem? Traditional testing doesn't catch multi-agent failures."

**[Cut to: PISAMA logo with tagline]**

"I'm Tuomo, and I built PISAMA to solve this."

---

## [0:30-1:15] What is PISAMA? (45 seconds)

**[Screen: PISAMA dashboard homepage]**

**NARRATOR:**
"PISAMA is an open-source testing platform for multi-agent AI systems. It detects 17 failure modes that appear when agents coordinate—things like infinite loops, state corruption, persona drift, and coordination failures."

**[Screen: Split view showing code on left, dashboard on right]**

"Here's how it works:

[Highlight code] You instrument your agent code with three lines...

[Show trace appearing in dashboard] ...PISAMA captures every agent interaction...

[Show detection alerts popping up] ...and flags failures in real-time."

**[Screen: Detection categories visual]**

"It checks for coordination issues, LLM behavior problems, workflow errors, and resource management—all before your code hits production."

---

## [1:15-2:30] Live Demo: Loop Detection (75 seconds)

**[Screen: VS Code with Python code]**

**NARRATOR:**
"Let me show you a real example. Here's a LangGraph research agent."

**[Code visible]:**
```python
def research_workflow(query):
    results = []
    while len(results) < 10:
        results.extend(researcher_agent(query))
        query = refine_query(results)
    return results
```

"Looks innocent, right? But there's a hidden loop when the researcher keeps saying 'need more info.'"

**[Run pytest command in terminal]**

```bash
pytest tests/test_research.py
```

**[Screen: PISAMA dashboard alert appears]**

"PISAMA catches it immediately:

[Highlight alert] 'Exact cycle detected: researcher → planner → researcher'

[Show execution path visualization] Here's the full execution path—you can see the cycle starting at iteration 4.

[Click into details] And here's the exact state comparison showing what's repeating."

**[Screen: Suggested fix panel]**

"PISAMA even suggests a fix:

[Show fix code]
'Add max iteration limit and exit condition.'"

**[Quick cut: Fixed code running successfully]**

"After applying the fix—test passes. Crisis averted."

---

## [2:30-3:15] Key Features (45 seconds)

**[Screen: Dashboard showing multi-tier detection]**

**NARRATOR:**
"PISAMA uses multi-tier detection to balance speed and accuracy:

Tier 1 [highlight]: Hash-based checks—instant, zero cost
Tier 2 [highlight]: State delta analysis—fast, cheap
Tier 3 [highlight]: Embedding similarity—accurate
Tier 4 [highlight]: LLM-as-Judge—most comprehensive

It automatically escalates only when needed. Average cost per trace? Just 3 cents."

**[Screen: Framework logos]**

"It works with LangGraph, CrewAI, AutoGen, n8n workflows, or any custom framework using OpenTelemetry."

**[Screen: CI/CD integration example]**

"And it plugs right into your CI/CD:

[Show GitHub Actions workflow]

Just add PISAMA to your pytest run, and you're protected."

---

## [3:15-3:45] Dashboard Quick Tour (30 seconds)

**[Screen: Live dashboard walkthrough]**

**NARRATOR:**
"Quick dashboard tour:

[Navigate to Traces page] Here's your trace history—every agent interaction captured.

[Click a trace] Click any trace to see the full execution tree with timing and token usage.

[Navigate to Detections page] This page shows all detected failures, sorted by severity.

[Navigate to Agents page] Track performance by agent—which agents are reliable, which are failing.

[Navigate to Analytics page] And this analytics view shows failure trends over time."

---

## [3:45-4:00] Call to Action (15 seconds)

**[Screen: PISAMA homepage with key info]**

**NARRATOR:**
"PISAMA is open source and free to start.

No credit card required for your first 1,000 traces.

Visit pisama.ai to get started in 5 minutes, or star us on GitHub.

Stop catching agent failures in production. Catch them in testing."

**[Screen: Final frame with URLs and QR codes]**

**Text on screen:**
- pisama.ai
- github.com/tn-pisama/mao-testing-research
- pip install pisama-claude-code

**[Fade to black]**

---

## Visual Direction Notes

### Color Palette
- **Primary**: Blue (#0ea5e9) - trust, tech, reliability
- **Danger**: Red (#ef4444) - alerts, failures
- **Success**: Green (#22c55e) - fixes, passing tests
- **Background**: Dark (slate-950) - modern, code-focused

### Typography
- **Headings**: Inter Bold
- **Body**: Inter Regular
- **Code**: JetBrains Mono

### Animation Style
- Clean, minimal transitions
- Highlight key UI elements with subtle glow
- Use arrows/callouts to guide attention
- Fast-paced but not rushed (developer audience)

### Screen Recording Tips
1. **Use 1920x1080** for recording
2. **Zoom browser to 125%** for readability
3. **Use a clean browser profile** (no extensions visible)
4. **Pre-populate fake but realistic data** (no "test123" names)
5. **Use dark theme** (matches brand + easier on eyes)

### Voiceover Direction
- **Tone**: Confident but not cocky, technical but accessible
- **Pace**: 150-160 words per minute (slightly faster than conversational)
- **Energy**: Steady, professional, slightly enthusiastic when showing features
- **Emphasis**: Highlight numbers ($5,200, 17 failure modes, 3 cents, 1,000 traces)

---

## B-Roll Suggestions (for marketing site)

If extending to 5 minutes with B-roll:
1. Code editor showing agent definitions
2. Terminal showing tests running
3. Graphs of cost over time (showing spike prevented)
4. Team celebrating after catching bug before production
5. Side-by-side comparison: "Before PISAMA" (stressed dev) vs "After PISAMA" (confident dev)

---

## Alternative Versions

### Short Version (60 seconds)
For social media:
- [0:00-0:10]: Hook (the $5,200 loop story)
- [0:10-0:30]: What is PISAMA + 3-line integration
- [0:30-0:50]: Quick loop detection demo
- [0:50-1:00]: CTA (pisama.ai, free to start)

### Long Version (10 minutes)
For YouTube deep dive:
- Expand loop detection demo to show other failure modes
- Show enterprise features (ML detection, custom rules)
- Include customer testimonial
- Show integration with multiple frameworks (LangGraph, CrewAI, AutoGen)
- Dive deeper into dashboard features

---

## Post-Production Checklist

- [ ] Add captions/subtitles (important for accessibility)
- [ ] Include chapter markers in YouTube description
- [ ] Add end screen with links to docs, GitHub, sign up
- [ ] Create thumbnail: "Stop $5K Agent Loops" with PISAMA logo
- [ ] Export in 1080p, 30fps
- [ ] Keep file size under 500MB for fast loading
- [ ] Add to YouTube, embed on homepage, share on social

---

## Script Timing Breakdown

| Section | Time | Words | Purpose |
|---------|------|-------|---------|
| Hook | 0:00-0:30 | 45 | Grab attention, state problem |
| Overview | 0:30-1:15 | 100 | Explain what PISAMA is |
| Demo | 1:15-2:30 | 165 | Show it working (proof) |
| Features | 2:30-3:15 | 90 | Highlight key capabilities |
| Tour | 3:15-3:45 | 65 | Show the interface |
| CTA | 3:45-4:00 | 35 | Drive action |
| **Total** | **4:00** | **~500** | |

**Note**: This pacing allows for pauses, UI transitions, and visual emphasis without feeling rushed.
