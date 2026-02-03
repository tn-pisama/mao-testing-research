# PISAMA Demo Video - Talking Points (7 Variations)

**Task**: PIS-W1-2-C-007
**Format**: Bullet-point outlines, NOT word-for-word scripts
**Duration**: 3-5 minutes per variation
**Last Updated**: 2026-02-03

---

## How to Use This

- Pick the variation that feels most natural to you
- Use bullets as reminders, not lines to memorize
- Focus on SHOWING > TELLING
- Improvise around the structure
- Include the key numbers (17 detectors, $5K loop, 3¢/trace)

---

## Variation 1: Pain-Focused ($5K Loop Story)

**Best for**: Social media, Product Hunt intro, catching attention

### [0:00-0:20] Hook
- Show text: "$5,200 API bill from 8-hour loop"
- **You say**: Real story, production system, no error thrown
- Problem: Traditional testing doesn't catch this

### [0:20-1:00] Quick Intro
- Hi, I'm [Name], I built PISAMA for this
- **What it is**: Testing platform for multi-agent systems
- **What it does**: Detects 17 failure modes agents have
  - Loops, state corruption, coordination failures
- **How**: 3 lines of code, real-time detection

### [1:00-2:30] Live Demo: Loop Detection
- **Screen**: Show VS Code with agent code
- **You say**: Here's a research agent, looks fine
- **Show**: Hidden loop condition
- **Action**: Run pytest
- **Result**: PISAMA catches it immediately
  - Show alert, execution path, state comparison
  - Show suggested fix
- **Action**: Apply fix, re-run, passes

### [2:30-3:15] Key Features
- Multi-tier detection (hash → state → embeddings → LLM)
- Average cost: 3¢ per trace
- Works with: LangGraph, CrewAI, AutoGen, n8n, custom
- CI/CD ready: Add to pytest, you're protected

### [3:15-3:30] CTA
- Open source, free to start
- 1,000 traces free, no credit card
- **Action**: Visit pisama.ai or star on GitHub
- **Remember**: Stop catching failures in production

---

## Variation 2: Solution-Focused (What PISAMA Does)

**Best for**: Landing page, YouTube tutorial, product-focused

### [0:00-0:20] Hook
- **You say**: Multi-agent systems fail differently than single agents
- Loops, contradictions, coordination breakdowns
- Traditional testing misses these

### [0:20-1:00] What PISAMA Is
- Testing platform specifically for multi-agent AI
- 17 specialized failure detectors
- Categories:
  - Coordination (loops, handoffs)
  - LLM behavior (drift, hallucinations)
  - Workflow (derailment, completion)
  - Resources (cost, token limits)

### [1:00-2:30] How It Works
- **Screen**: Show integration code
- **You say**: 3 lines to instrument your agent
- **Screen**: Show dashboard receiving traces
- **Show**: Detection running in background
- **Demo**: Pick a detection (loop or drift)
  - Show before/after
  - Show execution visualization
  - Show fix suggestion

### [2:30-3:15] Why It Matters
- Catches failures before production
- Saves API costs (show example: $5K loop prevented)
- Integrates with existing tools (pytest, CI/CD)
- Framework-agnostic (works with anything)

### [3:15-3:30] CTA
- Try it: pisama.ai
- Free tier: 1,000 traces/month
- Open source, GitHub available
- Get started in 5 minutes

---

## Variation 3: Demo-First (Show, Don't Tell)

**Best for**: Developer audience, quick proof, Twitter video

### [0:00-0:15] Quick Hook
- **Screen**: Code editor already open
- **You say**: Let me show you a problem...

### [0:15-2:30] Straight to Demo
- **Screen**: Agent code with subtle bug
- **You say**: Research agent, nothing obviously wrong
- **Action**: Run tests (no PISAMA) - passes!
- **Problem**: But production has infinite loop
- **Action**: Now run with PISAMA
- **Result**: Immediate detection
  - Show alert UI
  - Explain what it caught
  - Show visualization
  - Show why traditional tests missed it
- **Action**: Apply suggested fix
- **Result**: Now safe for production

### [2:30-3:15] What Just Happened
- That was PISAMA detecting exact cycle
- One of 17 detectors we have
- **Quick list**: loops, state corruption, drift, coordination
- Works with: LangGraph, CrewAI, AutoGen, custom
- Cost: ~3¢ per trace

### [3:15-3:30] Try It
- Free to start: pisama.ai
- Takes 5 minutes to integrate
- Open source on GitHub

---

## Variation 4: Personal Story (Builder Journey)

**Best for**: Building in public posts, founder-focused, authenticity

### [0:00-0:30] Why I Built This
- **You say**: Last year I was building multi-agent systems
- Kept hitting weird failures
- LangSmith showed me traces, but not WHY things failed
- **Specific example**: Agent looping for hours, no error
- Traditional testing didn't catch it

### [0:30-1:15] What I Learned
- Found MAST taxonomy: 17 failure modes specific to multi-agent systems
- These aren't bugs, they're emergent behaviors
- **Examples**: coordination, loops, drift
- No tools addressed this → opportunity

### [1:15-2:45] What I Built
- **Screen**: Show PISAMA dashboard
- **You say**: Built this over 6 months
- **Show features**:
  - 17 detection algorithms
  - 9 with perfect accuracy (F1 = 1.0)
  - Tiered detection (fast + accurate)
  - Framework adapters
- **Demo**: Quick loop detection example
  - Show it catching something you experienced

### [2:45-3:15] What's Next
- Launching Q1 2026
- Looking for design partners
- Open source, free tier available
- **Vision**: Make agent testing as easy as pytest

### [3:15-3:30] Join Me
- Try it: pisama.ai
- Star on GitHub, give feedback
- DM me if you're building agents
- Let's make agents reliable together

---

## Variation 5: Comparison (PISAMA vs LangSmith/Langfuse)

**Best for**: Educated audience, positioning, thought leadership

### [0:00-0:20] The Gap
- **You say**: LangSmith/Langfuse are great for tracing
- They show you WHAT happened
- But they don't tell you WHY it failed
- They're not designed for TESTING

### [0:20-1:00] Different Tool, Different Job
- **LangSmith/Langfuse**: Observability (production)
  - See traces, debug issues, analytics
- **PISAMA**: Testing (pre-production)
  - Detect patterns, catch failures, suggest fixes
- **Analogy**: Console.log vs pytest

### [1:00-2:30] What PISAMA Detects
- **Screen**: Show comparison table
- **You say**: 17 failure modes specific to multi-agent systems
- **Examples**:
  - Exact loops (hash matching)
  - Structural loops (pattern matching)
  - Semantic loops (embedding similarity)
  - State corruption (state delta analysis)
  - Persona drift (role confusion)
  - Coordination breakdowns
- **Demo**: Pick one to show live
  - Show detection in action
  - Explain how it works
  - Show suggested fix

### [2:30-3:15] Use Both
- **You say**: Use PISAMA in testing
- Use LangSmith/Langfuse in production
- They're complementary
- **Flow**: Test with PISAMA → Deploy → Monitor with LangSmith

### [3:15-3:30] Try PISAMA
- Free tier, open source
- Visit pisama.ai
- Works alongside your existing tools

---

## Variation 6: Speed-Focused (5-Minute Setup)

**Best for**: Practical tutorial, YouTube, devs who want to try fast

### [0:00-0:15] The Promise
- **You say**: I'll show you how to add agent testing in 5 minutes
- Catches loops, state corruption, coordination failures
- Let's do it

### [0:15-1:30] Step 1: Install
- **Screen**: Terminal
- **You say**: Install PISAMA SDK
- **Action**: `pip install pisama-claude-code`
- **Show**: Import in your code
- **Code**: 3 lines to instrument agent
  ```python
  from pisama import instrument_graph
  graph = instrument_graph(my_graph)
  ```
- **Result**: That's it for integration

### [1:30-2:45] Step 2: Run Tests
- **Action**: Run your existing pytest tests
- **Show**: PISAMA captures traces automatically
- **Demo**: Trigger a failure (loop example)
- **Result**: Detection appears in terminal + dashboard
- **Show**: Dashboard UI with detected issue
- **Show**: Suggested fix

### [2:45-3:15] Step 3: CI/CD
- **Screen**: GitHub Actions workflow
- **You say**: Add PISAMA to your CI
- **Show**: workflow file with PISAMA step
- **Result**: Every PR tested for agent failures

### [3:15-3:30] Done
- **You say**: That's it - 5 minutes, full agent testing
- Free tier: 1,000 traces/month
- Works with: LangGraph, CrewAI, AutoGen, custom
- Visit pisama.ai to start

---

## Variation 7: Technical Deep-Dive (For Engineers)

**Best for**: Conference talk, technical blog, serious developer audience

### [0:00-0:30] The Problem (Technical)
- **You say**: Multi-agent systems exhibit emergent failures
- Not bugs in code logic
- Arise from agent coordination and LLM non-determinism
- **Examples**:
  - Exact cycles (graph structure)
  - Semantic drift (embedding space)
  - State corruption (concurrent updates)

### [0:30-1:15] Detection Architecture
- **Screen**: Show tiered detection diagram
- **Tiers**:
  - Tier 1: Hash-based (instant, zero cost)
  - Tier 2: State delta analysis (fast, cheap)
  - Tier 3: Embedding similarity (accurate, moderate)
  - Tier 4: LLM-as-Judge (comprehensive, expensive)
  - Tier 5: Human review (highest accuracy)
- **Key**: Automatic escalation, 95% resolved at Tier 1-2
- **Result**: Average 3¢/trace (vs $5/trace naive LLM approach)

### [1:15-2:45] Demo: Loop Detection Algorithm
- **Screen**: Show code editor + terminal
- **You say**: Let's look at loop detection specifically
- **Show**: Agent code with cycle
- **Explain**:
  - Step 1: State hashing (catches exact loops)
  - Step 2: Graph analysis (catches structural loops)
  - Step 3: Embedding comparison (catches semantic loops)
- **Demo**: Run detection
- **Show**: Detection algorithm output
  - Hash comparison results
  - Execution path graph
  - Similarity scores
- **Show**: Confidence scores for each tier

### [2:45-3:15] Integration & Extensibility
- **Architecture**: OTEL-native (gen_ai.* conventions)
- **Works with**: Any framework emitting OTEL spans
- **Adapters**: LangGraph, CrewAI, AutoGen, n8n
- **Custom**: Write your own detector (plugin system)
- **Storage**: PostgreSQL + pgvector for embeddings
- **API**: RESTful API for custom integrations

### [3:15-3:30] Technical Resources
- Open source: github.com/tn-pisama/mao-testing-research
- Docs: Full architecture explained
- MAST benchmark: Accuracy metrics published
- Try it: pisama.ai
- Questions: DM me or open GitHub issues

---

## Recording Reminders (All Variations)

### Key Numbers to Mention
- **17 failure detectors** (unique value prop)
- **$5,200 loop** or **$5K** (pain point, memorable)
- **3¢ per trace** or **$0.03** (cost efficiency)
- **1,000 free traces** (friction-free trial)
- **3 lines of code** (ease of integration)
- **9 perfect F1 scores** (technical credibility)

### Visual Tips
- **Zoom browser to 125-150%** for readability
- **Dark theme** (brand + easier on eyes)
- **Clean browser** (no random extensions)
- **Realistic data** (not "test123")
- **Highlight key UI** (use arrows/callouts)

### Voice Tips
- **Pace**: Slightly faster than conversation (150-160 wpm)
- **Energy**: Steady, professional, enthusiastic at key moments
- **Emphasis**: Numbers, problem moments, solution reveals
- **Pauses**: Let visuals breathe, don't rush

### Screen Transitions
- **Code → Dashboard**: "And here's what PISAMA sees..."
- **Problem → Solution**: "Now watch what happens when we add PISAMA..."
- **Demo → Explanation**: "Let me break down what just happened..."

---

## Platform-Specific Recommendations

| Variation | Best Platform | Why |
|-----------|---------------|-----|
| 1. Pain-Focused | Twitter, LinkedIn, PH | Short attention, needs hook |
| 2. Solution-Focused | YouTube, Landing Page | SEO, educational |
| 3. Demo-First | Twitter, Reddit, Dev.to | Proof > promises |
| 4. Personal Story | LinkedIn, Building in Public | Authenticity, founder brand |
| 5. Comparison | YouTube, Blog, Thought Leadership | Educated audience |
| 6. Speed-Focused | YouTube Tutorial, Docs | Practical, hands-on |
| 7. Technical Deep-Dive | Conference, Technical Blog | Deep credibility |

---

## Next Steps

1. **Pick a variation** (or record 2-3)
2. **Practice once** with talking points visible
3. **Record without script** (improvise around bullets)
4. **Use visual direction** from demo-script.md
5. **Post-production**: Captions, chapters, thumbnail

---

## Quick Comparison to Full Script

| Full Script | These Talking Points |
|-------------|---------------------|
| 500 words to memorize | 50 bullets to remember |
| Sounds scripted | Sounds natural |
| One angle only | 7 different angles |
| Rigid timing | Flexible 3-5 min |
| Harder to record | Easier to record |

**Use these talking points to guide your demo, not dictate it.**
