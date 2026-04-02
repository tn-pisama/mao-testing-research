# Podcast Pitch Emails

---

## 1. AI Agents Podcast (Jotform)

**To:** Aytekin Tank & Demetri Panici
**From:** Tuomo Nikulainen, Founder, Pisama (tuomo@pisama.ai)
**Subject:** The 20 ways AI agents fail silently (and how to catch them for $0)

Hi Aytekin and Demetri,

I've been following AI Agents Podcast and appreciate how you dig into the real mechanics of building with agents, not just the hype.

I'd love to share something your listeners are probably hitting right now: the gap between "my agent works in demo" and "my agent works in production." I've cataloged 20 distinct failure modes in multi-agent systems — loops, state corruption, persona drift, hallucination, coordination breakdowns — and built detection for all of them at Pisama.

The counterintuitive finding: simple heuristics (hash checks, cycle detection, word overlap) outperform expensive LLM-as-judge on most failure types. We hit 60.1% on the TRAIL benchmark at zero cost.

**Suggested episode title:** "The 20 Failure Modes Every Agent Builder Should Know"

**Talking points:**
- The taxonomy of agent failures — what breaks and why traditional monitoring misses it
- Why cheap heuristics beat LLM-as-judge for most detection tasks (with data)
- Practical patterns for adding failure detection to any agent framework

Happy to share specific production failure examples that would make great discussion material.

Best,
Tuomo

---

## 2. Latent Space

**To:** swyx & Alessio
**From:** Tuomo Nikulainen, Founder, Pisama (tuomo@pisama.ai)
**Subject:** Agent evals are broken — here's the 100x cheaper alternative

Hey swyx and Alessio,

Latent Space has been the podcast I recommend to anyone serious about AI engineering, and your coverage of evals and agent architectures is the best out there.

I think your audience would find this interesting: we built a tiered detection system for multi-agent failures that achieves 60.1% TRAIL accuracy at $0, while LLM-as-judge costs $0.02-0.15 per eval. The trick is treating agent failure detection as a classification problem with escalation tiers — deterministic checks first, embeddings second, LLM only for genuinely ambiguous cases. 70%+ of failures resolve at the cheapest tier.

We calibrated against 7,212 labeled entries from 13 external sources across 20 failure types. Some findings are surprising — word overlap beats embeddings for grounding, cycle detection trivially solves loops.

**Suggested episode title:** "Agent Forensics: Why Simple Heuristics Beat LLM-as-Judge"

**Talking points:**
- Tiered escalation architecture: hash -> statistical -> LLM (with escalation rate data)
- Which of the 20 agent failure types are trivial to detect and which remain hard
- The calibration methodology — building golden datasets from 13 external sources

Would be happy to go as deep and technical as you want.

Tuomo

---

## 3. Practical AI (Changelog)

**To:** Practical AI team
**From:** Tuomo Nikulainen, Founder, Pisama (tuomo@pisama.ai)
**Subject:** A practical guide to monitoring AI agents in production

Hi there,

Practical AI is my go-to recommendation for developers who want actionable AI content, not theory. I have a topic I think fits perfectly.

Teams are deploying multi-agent systems without any way to detect when agents fail semantically — loops, hallucination, state corruption, persona drift. Traditional monitoring shows green dashboards while agents deliver garbage. LLM-based evaluation works but costs too much for continuous use.

At Pisama, I've built detection for 20 agent failure types using a tiered approach that developers can actually afford to run on every interaction. I'd love to walk your listeners through the practical "how" — what to monitor, what patterns to look for, and how to set up detection without blowing your budget.

**Suggested episode title:** "How to Monitor AI Agents Without Going Broke"

**Talking points:**
- The 5 most common agent failures and how to detect each one with concrete code patterns
- Setting up tiered detection: what to check with heuristics vs. when to call an LLM
- Integration with OpenTelemetry and existing observability stacks

Best,
Tuomo Nikulainen
Founder, Pisama (pisama.ai)

---

## 4. Everyday AI (Jordan Wilson)

**To:** Jordan Wilson
**From:** Tuomo Nikulainen, Founder, Pisama (tuomo@pisama.ai)
**Subject:** Your AI agent is probably lying to you — here's how to know

Hi Jordan,

I know Everyday AI gets flooded with pitches, so I'll get straight to the point: AI agents fail silently. They don't crash — they complete tasks confidently while delivering wrong results. The customer service agent that loops on the same answer. The research assistant that invents citations. The workflow that looks perfect but quietly dropped a step.

This matters to your audience because anyone using AI agents for real work — and that's a growing share of your listeners — has no way to know when the output is wrong. I've identified 20 specific ways agents fail and built detection that catches them. The most useful thing I can share is helping people recognize *what bad agent behavior actually looks like* so they can spot it themselves.

**Suggested episode title:** "20 Ways Your AI Agent Is Failing (And You Don't Know It)"

**Talking points:**
- The 5 agent failures every business user should recognize (with real examples)
- Why "it completed without errors" doesn't mean "it worked correctly"
- Simple checks anyone can apply today to verify agent outputs

Would love to make this genuinely useful for your audience, not a product pitch.

Tuomo

---

## 5. The TWIML AI Podcast (Sam Charrington)

**To:** Sam Charrington
**From:** Tuomo Nikulainen, Founder, Pisama (tuomo@pisama.ai)
**Subject:** Failure taxonomies and tiered detection for multi-agent systems

Hi Sam,

TWIML has consistently been one of the best shows for understanding ML systems in practice, and I think your audience would appreciate the research angle on this.

Multi-agent systems introduce failure modes with no single-model analog — coordination breakdowns, state corruption across agents, persona drift, information withholding. We developed a taxonomy of 20 failure types from production multi-agent traces and built tiered detectors calibrated on 7,212 labeled entries from 13 external data sources.

The research contribution: a tiered escalation architecture (deterministic -> statistical -> LLM) that achieves 60.1% TRAIL accuracy at zero inference cost. The key insight is that most agent failures have structural signatures detectable without language understanding — cycles for loops, hash divergence for corruption, lexical overlap for grounding.

**Suggested episode title:** "A Taxonomy of Multi-Agent Failure Modes and Practical Detection"

**Talking points:**
- The 20-type failure taxonomy: how it was derived and where it maps to existing ML safety research
- Tiered detection methodology and per-detector calibration results (F1 across 18 production detectors)
- Open problems: failure types where heuristics fail and LLM judgment remains necessary

Best,
Tuomo Nikulainen
Founder, Pisama (pisama.ai)
