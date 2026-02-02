---
title: "Introducing PISAMA: Testing for Multi-Agent AI Systems"
date: 2026-02-02
category: launch
author: Tuomo Nikulainen
tags: [launch, product-hunt, multi-agent, testing, announcement]
description: "We're launching PISAMA on Product Hunt today! An open-source testing platform that detects 17 failure modes in multi-agent AI systems before they hit production."
---

# Introducing PISAMA: Testing for Multi-Agent AI Systems

**TL;DR**: We're launching [PISAMA](https://pisama.ai) on Product Hunt today—an open-source platform for testing multi-agent AI systems. It detects 17 failure modes (loops, state corruption, persona drift, etc.) before they hit production.

[→ Check us out on Product Hunt](https://producthunt.com) | [→ Try it now](https://pisama.ai) | [→ Star us on GitHub](https://github.com/tn-pisama/mao-testing-research)

---

## The Problem

Multi-agent systems are powerful. They can break down complex tasks, coordinate between specialized agents, and handle workflows that single-LLM apps can't touch.

They're also *fragile*.

After building agent systems for the past year, we kept hitting the same failures in production:
- **Infinite loops** that ran for hours, costing thousands
- **State corruption** from agents overwriting each other
- **Persona drift** where agents forgot their roles
- **Coordination failures** where agents dropped tasks

Traditional testing didn't catch these. Unit tests passed. Integration tests passed. Then in production, an agent would loop for 8 hours straight.

We needed better testing tools. So we built PISAMA.

---

## What is PISAMA?

PISAMA is an open-source testing platform designed specifically for multi-agent systems built with LangGraph, CrewAI, AutoGen, n8n, or custom frameworks.

### It detects 17 failure modes:

**Coordination Issues:**
- Infinite loops (exact, structural, semantic)
- State corruption & invalid transitions
- Coordination failures & dropped tasks
- Communication breakdowns

**LLM Behavior:**
- Persona drift & role confusion
- Hallucinations
- Context neglect
- Prompt injection attempts

**Workflow Problems:**
- Task derailment
- Specification mismatches
- Decomposition failures
- Workflow execution errors

**Completion Issues:**
- Premature completion
- Delayed completion
- Information withholding

**Resource Management:**
- Context overflow
- Cost overruns

### How it works:

1. **Instrument your agent code** with PISAMA SDK (3 lines of code)
2. **Run your tests** as normal (pytest, CI/CD, etc.)
3. **PISAMA analyzes traces** in real-time and flags failures
4. **Get actionable reports** with exact failure location and suggested fixes

---

## Key Features

### 🔍 Multi-Tier Detection
- **Tier 1**: Hash-based (instant, zero cost)
- **Tier 2**: State delta analysis (fast, cheap)
- **Tier 3**: Embedding similarity (accurate)
- **Tier 4**: LLM-as-Judge (most comprehensive)
- **Tier 5**: Human review (for edge cases)

Start cheap, escalate only when needed. Average cost per trace: **$0.03**.

### 📊 Real-Time Dashboard
- Live trace visualization
- Failure mode heatmaps
- Cost tracking per agent/workflow
- Performance metrics

### 🔧 Framework-Agnostic
Works with:
- LangGraph
- CrewAI
- AutoGen
- n8n workflows
- Custom agent frameworks (via OTEL)

### 🚀 Easy Integration
```python
# Install
pip install pisama-claude-code

# Instrument (3 lines)
from pisama import PisamaTracer

tracer = PisamaTracer(api_key="your-key")
with tracer.trace_workflow("research"):
    result = my_agent_workflow()
```

### 🧪 CI/CD Ready
```yaml
# .github/workflows/test.yml
- name: Run PISAMA tests
  run: pytest --pisama-detect=all
```

### 💰 Open Source + SaaS
- **Core detection**: Open source (MIT license)
- **Dashboard + hosting**: Free tier available
- **Enterprise features**: ML detection, custom rules, SSO

---

## Why We Built This

I'm a solo technical founder who's been building multi-agent systems for the past year. Every time I deployed a new agent feature, I'd cross my fingers and hope it didn't loop.

Three months ago, a "simple" research agent ran for 8 hours in production, calling GPT-4 in a loop. Bill: $5,200. Cause: No loop detection.

I looked for testing tools. Found great options for:
- **Single-LLM apps**: LangSmith, Langfuse, Weights & Biases
- **Traditional software**: Pytest, Jest, Selenium
- **API monitoring**: Datadog, New Relic

But nothing designed specifically for multi-agent coordination failures.

So I built PISAMA. Started with just loop detection. Then added state validation. Then persona drift detection. Eventually catalogued 17 failure modes.

Now I'm launching it to help other builders avoid the same painful (and expensive) lessons.

---

## What Makes PISAMA Different?

### vs LangSmith
- **LangSmith**: Great for observability and debugging
- **PISAMA**: Specialized detection of multi-agent failure modes, designed for testing/CI

### vs Langfuse
- **Langfuse**: Production monitoring and analytics
- **PISAMA**: Pre-production testing and failure prevention

### vs Traditional Testing
- **Unit/Integration tests**: Check individual components and happy paths
- **PISAMA**: Checks coordination, state consistency, resource usage in multi-agent interactions

**PISAMA complements existing tools**—use it in CI/CD to catch failures before they hit production, then use LangSmith/Langfuse for production observability.

---

## Pricing

### Free Tier
- Up to 1,000 traces/month
- All 17 detectors
- Dashboard access
- Community support

### Startup ($49/mo)
- Up to 50,000 traces/month
- ML-based detection (Tier 4)
- Custom detection rules
- Email support

### Enterprise (Custom)
- Unlimited traces
- Self-hosted option
- SSO/RBAC
- SLA + dedicated support
- Custom integrations

**Try it free**: No credit card required for first 1,000 traces.

---

## What's Next?

This is just the beginning. Roadmap for next 3 months:

**February 2026**:
- Self-healing agents (auto-fix detected issues)
- Enhanced n8n workflow support
- Slack/Discord notifications

**March 2026**:
- Visual workflow debugger
- A/B testing for agent prompts
- Cost optimization recommendations

**April 2026**:
- Retrieval quality detection
- Agent benchmark suite (MAST)
- Playwright integration for UI agents

---

## Try PISAMA Today

🔗 **Website**: [pisama.ai](https://pisama.ai)
🐙 **GitHub**: [github.com/tn-pisama/mao-testing-research](https://github.com/tn-pisama/mao-testing-research)
📦 **PyPI**: `pip install pisama-claude-code`
🚀 **Product Hunt**: [Vote for us!](https://producthunt.com)
💬 **Discord**: [Join our community](https://discord.gg/pisama)

---

## Get Started in 5 Minutes

### 1. Install PISAMA
```bash
pip install pisama-claude-code
```

### 2. Set up your API key
```bash
export PISAMA_API_KEY="your-key-here"
# or sign up for free at pisama.ai
```

### 3. Instrument your code
```python
from pisama import PisamaTracer

tracer = PisamaTracer()

# Trace your workflow
with tracer.trace_workflow("customer-support"):
    # Your agent code here
    result = my_agent_system.run(user_message)
```

### 4. Run your tests
```bash
pytest  # PISAMA automatically detects issues
```

### 5. View results
Visit [app.pisama.ai](https://app.pisama.ai) to see detected failures, traces, and recommendations.

---

## Join Us

Building multi-agent systems? We'd love to hear from you:
- 🐛 **Found a bug?** [Open an issue](https://github.com/tn-pisama/mao-testing-research/issues)
- 💡 **Have a feature idea?** [Start a discussion](https://github.com/tn-pisama/mao-testing-research/discussions)
- 🤝 **Want to contribute?** Check our [contributing guide](https://github.com/tn-pisama/mao-testing-research/blob/main/CONTRIBUTING.md)
- 💬 **Questions?** Join our [Discord](https://discord.gg/pisama)

---

## Thank You

Special thanks to:
- Early design partners who tested PISAMA and gave invaluable feedback
- The LangGraph, CrewAI, and AutoGen communities for building amazing frameworks
- Everyone who supported this project

Let's build more reliable multi-agent systems together. 🚀

---

**Launching today on Product Hunt!** [Vote for PISAMA →](https://producthunt.com)

---

*About the author: I'm Tuomo, a solo technical founder building tools for AI agent developers. Previously built [other projects]. You can follow my journey on [Twitter/X](https://twitter.com/yourusername) or [LinkedIn](https://linkedin.com/in/yourprofile).*
