---
title: "PISAMA Landing Page Copy"
category: marketing
sections: [hero, features, how-it-works, testimonials, pricing, faq, cta]
---

# PISAMA Landing Page Copy

## Hero Section

### Headline
**Stop Catching Agent Failures in Production**

### Subheadline
Agents never question each other's outputs. Pisama does. Detect 17 failure modes—from hallucination cascades to state corruption—before they compound through your multi-agent system.

### CTA Buttons
- **Primary**: Start Free Trial (→ Sign up page)
- **Secondary**: Watch 4-Minute Demo (→ Video modal)

### Hero Stats (Below CTA)
- ✅ 73K+ traces analyzed
- ✅ $250K+ in API costs prevented
- ✅ Open source & free to start

### Visual
Split-screen animation:
- Left: Agent system running with errors (red alerts, costs climbing)
- Right: Same system with PISAMA (green checkmarks, costs controlled)

---

## Problem Section

### Headline
**Traditional Testing Doesn't Catch Multi-Agent Failures**

### Problem Cards (3 columns)

**Card 1: Infinite Loops**
Icon: ♾️
- Agent systems can loop for hours
- One customer: $5,200 bill from 8-hour loop
- No error thrown, no timeout hit
- Traditional tests don't catch these

**Card 2: Coordination Failures**
Icon: 💥
- Agents drop tasks silently
- State corruption from race conditions
- Persona drift after long conversations
- Integration tests miss these edge cases

**Card 3: Resource Overruns**
Icon: 💸
- Context window overflow
- Unexpected cost explosions
- Token limits exceeded
- Unit tests can't simulate production scale

### Closing Line
*"Your agent system can pass all tests and still fail catastrophically in production."*

---

## The Evaluation Gap

### Headline
**The Better AI Gets, the Less Anyone Checks**

### Body
Anthropic's [AI Fluency Index](https://www.anthropic.com/research/AI-fluency-index) found that when AI produces polished outputs, humans evaluate them *less* — fact-checking drops 3.7%, reasoning questioning drops 3.1%. They call it the Artifact Paradox.

Now consider multi-agent systems. When Agent A hands output to Agent B, there's no evaluation at all. Agents accept upstream outputs at face value, always. They don't question reasoning, check facts, or identify missing context. They can't.

As models improve and intermediate outputs look more convincing, even the humans monitoring the system are less likely to spot problems. The evaluation gap widens on both sides.

### Pullquote
*"Humans skip evaluation when outputs look polished. Agents never evaluate at all. Pisama is the evaluation layer that neither provides."*

### Visual
Funnel diagram:
- Top: "Human evaluates AI output" (30% check facts — Anthropic AI Fluency Index)
- Middle: "Agent evaluates agent output" (0% — no evaluation capability)
- Bottom: "Pisama evaluates every handoff" (17 detectors, every trace, production scale)

---

## Solution Section

### Headline
**PISAMA: Testing Built for Multi-Agent Systems**

### Feature Grid (2x2)

**Loop Detection**
- Exact, structural, and semantic cycle detection
- Catches loops before they cost thousands
- Real-time alerting with suggested fixes

**State Validation**
- Track state consistency across agents
- Detect corruption and invalid transitions
- Prevent race conditions

**Persona Enforcement**
- Monitor agent role adherence
- Catch persona drift early
- Validate agent coordination

**Cost Control**
- Per-workflow budget limits
- Token usage tracking
- Resource optimization recommendations

---

## How It Works

### Headline
**Three Lines of Code. Complete Protection.**

### Steps (3 columns with code snippets)

**1. Install**
```bash
pip install pisama-claude-code
```
*2 minutes*

**2. Instrument**
```python
from pisama import PisamaTracer

with PisamaTracer().trace_workflow("support"):
    result = my_agent.run()
```
*3 lines of code*

**3. Detect**
Dashboard shows detected failures + fixes
*Real-time insights*

### Video/GIF
Screen recording showing:
1. Terminal: pip install
2. VS Code: Adding 3 lines
3. Dashboard: Trace appearing with loop detection alert

---

## Detection Methods

### Headline
**Multi-Tier Detection: Fast, Accurate, Cost-Effective**

### Tier Table

| Tier | Method | Speed | Cost | Use Case |
|------|--------|-------|------|----------|
| **1** | Hash-based | <1ms | $0 | Exact duplicate detection |
| **2** | State Delta | ~10ms | $0.01 | Structural changes |
| **3** | Embeddings | ~100ms | $0.03 | Semantic similarity |
| **4** | LLM Judge | ~500ms | $0.10 | Complex patterns |
| **5** | Human Review | Manual | - | Edge cases |

**Smart Escalation**: Start at Tier 1, escalate only when needed. Average cost per trace: **$0.03**

---

## Framework Support

### Headline
**Works With Your Stack**

### Framework Logos (Grid)
- LangGraph ✓
- CrewAI ✓
- AutoGen ✓
- n8n ✓
- Custom (via OTEL) ✓

### Integration Code Snippet
```python
# LangGraph
from pisama.integrations.langgraph import wrap_graph
graph = wrap_graph(my_graph)

# CrewAI
from pisama.integrations.crewai import wrap_crew
crew = wrap_crew(my_crew)

# AutoGen
from pisama.integrations.autogen import wrap_agent
agent = wrap_agent(my_agent)
```

---

## 17 Failure Modes Detected

### Headline
**Comprehensive Coverage**

### Failure Mode Grid (3 columns x 6 rows)

**Coordination Issues**
- ♾️ Infinite Loops
- 💥 State Corruption
- 🔄 Coordination Failures
- 📡 Communication Breakdowns

**LLM Behavior**
- 🎭 Persona Drift
- 🌫️ Hallucinations
- 👁️ Context Neglect
- 🔓 Prompt Injection

**Workflow Problems**
- 🎯 Task Derailment
- 📋 Specification Mismatches
- 🧩 Decomposition Failures
- ⚙️ Workflow Execution Errors

**Completion Issues**
- ⏩ Premature Completion
- ⏸️ Delayed Completion
- 🙊 Information Withholding

**Resource Management**
- 📦 Context Overflow
- 💰 Cost Overruns

[Link] Read full taxonomy →

---

## Social Proof

### Headline
**Trusted by AI-First Teams**

### Testimonials (3 cards)

**Testimonial 1**
"PISAMA caught a loop in our QA agent that would have cost us $3K in production. Paid for itself on day one."
— Alex Chen, CTO @ AgentCo

**Testimonial 2**
"We integrated PISAMA into CI/CD. Now every PR is tested for multi-agent failures before merge. Game changer."
— Sarah Rodriguez, Lead Engineer @ MultiAgent Labs

**Testimonial 3**
"The loop detection alone is worth it. But the state validation and persona drift detection are what keep our agent system reliable."
— Marcus Kim, Founder @ AI Support Tool

### Stats Bar
- 🏢 50+ companies using PISAMA
- ⭐ 1.2K+ GitHub stars
- 🧪 730K+ traces analyzed
- 💰 $250K+ API costs prevented

---

## Pricing

### Headline
**Start Free. Scale as You Grow.**

### Pricing Tiers (3 columns)

**Free**
$0/month

✅ 1,000 traces/month
✅ All 17 detectors (Tier 1-3)
✅ Dashboard access
✅ Community support
✅ Public GitHub repo access

[Button] Start Free

---

**Startup**
$49/month

Everything in Free, plus:
✅ 50,000 traces/month
✅ ML detection (Tier 4)
✅ Custom detection rules
✅ Email support
✅ Team collaboration (5 seats)
✅ Slack/Discord notifications

[Button] Start 14-Day Trial

**Most Popular** badge

---

**Enterprise**
Custom Pricing

Everything in Startup, plus:
✅ Unlimited traces
✅ Self-hosted option
✅ SSO & RBAC
✅ SLA & dedicated support
✅ Custom integrations
✅ Onboarding & training

[Button] Contact Sales

---

### Pricing FAQs (Below table)
- What counts as a trace? *One complete workflow execution (can contain multiple agent calls)*
- Can I upgrade/downgrade? *Yes, anytime. Pro-rated.*
- Do you offer discounts? *Yes—50% off for open-source projects, 20% off for annual plans*

---

## CI/CD Integration

### Headline
**Built for Your Development Workflow**

### CI/CD Logos
- GitHub Actions ✓
- GitLab CI ✓
- CircleCI ✓
- Jenkins ✓
- Buildkite ✓

### Code Snippet (GitHub Actions)
```yaml
- name: Test with PISAMA
  run: pytest --pisama-detect=all --pisama-fail-on-detection
  env:
    PISAMA_API_KEY: ${{ secrets.PISAMA_API_KEY }}
```

### Feature Highlights
- ✅ Fail builds on detection
- ✅ PR comments with detected issues
- ✅ Historical trend tracking
- ✅ Cost estimates per PR

---

## FAQ Section

### Headline
**Frequently Asked Questions**

**Q: How is PISAMA different from LangSmith?**
A: LangSmith is great for observability and debugging in production. PISAMA is designed for *testing* before production—it's optimized for CI/CD and detects multi-agent-specific failure modes. Use both: PISAMA in testing, LangSmith in production.

**Q: Does PISAMA work with my custom agent framework?**
A: Yes! If your framework can emit OpenTelemetry traces with `gen_ai.*` semantic conventions, PISAMA can analyze it. We have native integrations for LangGraph, CrewAI, AutoGen, and n8n.

**Q: What's the performance overhead?**
A: Minimal. Tier 1 detection adds <5ms latency. Tier 3 (embeddings) adds ~100ms. You control which tiers run via configuration. Most users run Tier 1-2 in CI, Tier 3-4 only on critical workflows.

**Q: Can I self-host PISAMA?**
A: Yes! Core detection engine is open source (MIT license). Self-hosting guide in the docs. Enterprise plan includes support for self-hosted deployments.

**Q: How do you handle my trace data?**
A: Traces are encrypted in transit and at rest. We never train on your data. Enterprise customers can self-host for complete data control. See our [privacy policy](https://pisama.ai/privacy).

**Q: What if I hit my trace limit?**
A: We'll email you at 80% and 100% usage. After hitting your limit, you can upgrade or wait until next month. We don't cut you off mid-test—current tests complete normally.

**Q: Do you offer educational discounts?**
A: Yes! Students and educators get the Startup plan free. Email support@pisama.ai with your .edu address.

**Q: Why can't we just review agent outputs manually?**
A: Research shows you probably won't. Anthropic's AI Fluency Index found that the more polished an AI output looks, the less likely humans are to evaluate it critically — fact-checking drops, reasoning questioning drops. And that's for a single human-AI interaction. In a multi-agent pipeline with dozens of handoffs per trace, manual review doesn't scale. Pisama applies systematic evaluation at every agent handoff, automatically.

**Q: What's your refund policy?**
A: 30-day money-back guarantee on paid plans, no questions asked.

---

## CTA Section

### Headline
**Start Testing Your Multi-Agent System in 5 Minutes**

### Subheadline
No credit card required. 1,000 free traces/month forever.

### CTA Buttons
- **Primary**: Sign Up Free (→ Sign up page)
- **Secondary**: Book a Demo (→ Calendly)

### Trust Signals (Below CTA)
- ✓ Open source (MIT license)
- ✓ SOC 2 Type II certified
- ✓ 99.9% uptime SLA
- ✓ 24/7 support for Enterprise

---

## Footer CTA Banner (Sticky)

**💡 Launching on Product Hunt Today!**
Support us and be among the first 100 users to get a lifetime 20% discount.
[Vote on Product Hunt →]

---

## Announcement Bar (Top of page, dismissible)

**🚀 New: Self-healing agents (beta) — Auto-fix detected issues** [Learn more →]

---

## Social Proof Logos

*"As seen in / Backed by / Used by"*

Logos:
- Y Combinator (if applicable)
- GitHub Sponsors
- Product Hunt (Golden Kitty nominee)
- Hacker News (featured discussion)

---

## Comparison Table (Optional section)

### Headline
**How PISAMA Compares**

| Feature | PISAMA | LangSmith | Langfuse | Traditional Testing |
|---------|--------|-----------|----------|---------------------|
| **Loop Detection** | ✅ 3 methods | ❌ | ❌ | ❌ |
| **State Validation** | ✅ | ⚠️ Manual | ⚠️ Manual | ❌ |
| **Persona Drift** | ✅ | ❌ | ❌ | ❌ |
| **Cost Limits** | ✅ Per-workflow | ❌ | ✅ Project-level | ❌ |
| **CI/CD Native** | ✅ | ⚠️ Via plugins | ⚠️ Via plugins | ✅ |
| **ML Detection** | ✅ Tier 4 | ✅ | ❌ | ❌ |
| **Self-Hosted** | ✅ Open source | ❌ | ✅ Enterprise | ✅ |
| **Price** | Free tier | $39+/mo | Free tier | N/A |

*PISAMA complements observability tools—use it in testing, use LangSmith/Langfuse in production.*

---

## Blog CTA Section

### Headline
**Learn How to Build Reliable Multi-Agent Systems**

### Blog Post Cards (3 latest)

**Card 1**
*Thought Leadership*
**The 17 Failure Modes of Multi-Agent Systems**
A comprehensive taxonomy of how multi-agent AI systems fail...
[Read more →]

**Card 2**
*Tutorial*
**How to Detect Infinite Loops in LangGraph**
Three detection strategies with working code examples...
[Read more →]

**Card 3**
*Case Study*
**How AgentCo Prevented $50K in API Costs**
Real-world loop detection in production...
[Read more →]

---

## Meta Tags & SEO

### Title
PISAMA - Testing Platform for Multi-Agent AI Systems

### Description (160 chars)
Test multi-agent AI systems before production. Detect loops, state corruption, persona drift & more. Free tier. Open source. Works with LangGraph, CrewAI, AutoGen.

### Keywords
multi-agent testing, AI agent testing, LangGraph testing, CrewAI testing, loop detection, agent reliability, multi-agent systems, AI testing platform

### OG Image
Screenshot of dashboard with loop detection alert + "Stop $5K Agent Loops" text

---

## Live Chat Trigger

**When to show**: After 30 seconds on page, or when user scrolls to pricing

**Message**: "👋 Hey! Got questions about PISAMA? I'm here to help."

**CTA**: "Ask me anything" / "Show me a demo" / "I'll figure it out myself"

---

## Exit Intent Popup

**Headline**: Before You Go...

**Message**: Get the "17 Failure Modes Checklist" — a printable PDF you can use to audit your agent system today.

**CTA**: [Download Free Checklist]

*(Requires email, triggers welcome sequence)*
