---
marp: true
theme: default
paginate: true
backgroundColor: #0f172a
color: #f1f5f9
style: |
  section {
    font-family: 'Inter', system-ui, sans-serif;
  }
  h1 {
    color: #a78bfa;
    font-size: 2.5em;
  }
  h2 {
    color: #c4b5fd;
    font-size: 1.8em;
  }
  strong {
    color: #a78bfa;
  }
  table {
    font-size: 0.85em;
  }
  th {
    background-color: #1e293b;
    color: #a78bfa;
  }
  td {
    background-color: #1e293b;
  }
  code {
    background-color: #1e293b;
    color: #22d3ee;
  }
  a {
    color: #60a5fa;
  }
---

# PISAMA x Claude Skills

## Agent Forensics Powered by Anthropic's Extensibility Platform

![bg right:40% opacity:0.3](https://images.unsplash.com/photo-1639322537228-f710d846310a?w=800)

**pisama.ai**

---

# The Opportunity

## Three Strategic Integration Goals

1. **BUILD** - Use Claude Skills to accelerate PISAMA development
2. **DISTRIBUTE** - Ship PISAMA capabilities as Claude Skills
3. **COLLECT** - Access user skill execution traces for analysis

*One platform, three integration layers*

---

# What Are Claude Skills?

## Claude's Native Extensibility Mechanism

- Markdown instruction files that extend Claude Code capabilities
- Executed within Claude's environment with full tool access
- Users can install, share, and customize skills
- MCP (Model Context Protocol) servers provide integrations

### Key Insight
> Skills run inside Claude = perfect observation point for agent behavior

---

# Goal 1: BUILD with Skills

## Internal Development Acceleration

| Skill | Purpose |
|-------|---------|
| `pisama-architect` | Design detection algorithms, suggest patterns |
| `detection-designer` | Create new failure detectors from examples |
| `sdk-generator` | Auto-generate SDK code for new platforms |
| `test-synthesizer` | Generate test cases from failure patterns |

**Benefit:** 3-5x faster feature development

---

# Goal 2: DISTRIBUTE as Skills

## PISAMA Capabilities as Installable Skills

```
/install pisama-diagnose
```

### Product Skills Portfolio

- **pisama-learn** - Interactive tutorials on agent failure patterns
- **pisama-diagnose** - Analyze current project for potential issues
- **pisama-fix** - Apply recommended fixes automatically
- **pisama-review** - Pre-commit review for agent anti-patterns
- **pisama-monitor** - Set up observability in existing projects

---

# Distribution Advantage

## Why Skills as Distribution Channel?

| Traditional SaaS | Skills Distribution |
|-----------------|---------------------|
| User visits website | User types `/install` |
| Sign up flow | Already authenticated |
| Learn new UI | Uses familiar Claude |
| Integration work | Works in environment |
| Monthly subscription | Usage-based |

**Result:** Zero-friction adoption in developer workflow

---

# Goal 3: COLLECT Traces

## The Core Innovation: MCP Trace Observer

```
┌─────────────────────────────────────────┐
│           Claude Code Session           │
│  ┌─────────────────────────────────┐   │
│  │     User's Skill Execution      │   │
│  └─────────────┬───────────────────┘   │
│       ┌────────▼────────┐              │
│       │  PISAMA MCP     │              │
│       │  Trace Observer │              │
│       └────────┬────────┘              │
└────────────────┼────────────────────────┘
        ┌────────▼────────┐
        │  PISAMA Cloud   │
        └─────────────────┘
```

---

# What We Capture

## Trace Data Points

- **Tool Calls** - File reads, writes, bash commands, searches
- **Decision Points** - When Claude chooses between options
- **Iteration Patterns** - Retry loops, error corrections
- **Context Switches** - Topic changes, goal modifications
- **Timing** - Duration of each phase

### Not Captured
File contents, secrets, personal data *(privacy-first design)*

---

# Privacy Framework

## User Trust is Non-Negotiable

| Principle | Implementation |
|-----------|----------------|
| Opt-in Only | Explicit consent before collection |
| Minimal Data | Hashed identifiers, no raw content |
| User Ownership | Export, delete, view your data |
| Transparency | Open-source collection logic |
| Local-First | Analysis can run on-device |

**Certification:** SOC2, GDPR compliant from day one

---

# Detection Capabilities

## What PISAMA Identifies From Traces

- **Infinite Loops** - Repeated tool call patterns
- **State Corruption** - Semantic drift in context
- **Goal Abandonment** - Incomplete task chains
- **Resource Exhaustion** - Token/time budget overruns
- **Coordination Failures** - Multi-agent deadlocks

### Accuracy Target: 95%+ precision on known failure modes

---

# User Value Proposition

## For Claude Code Users

### Before PISAMA
> "Why did my 2-hour Claude session fail to complete the task?"

### After PISAMA
> "PISAMA detected a loop at minute 47 where Claude kept re-reading the same 3 files. Suggested fix: add explicit progress checkpoints. One-click apply."

**Time Saved:** 30-60 minutes per failed session

---

# Implementation Phases

## 16-Week Roadmap

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Foundation** | Weeks 1-4 | MCP server, basic trace capture |
| **Detection** | Weeks 5-8 | Loop & corruption detectors |
| **Skills v1** | Weeks 9-12 | pisama-diagnose, pisama-fix |
| **Scale** | Weeks 13-16 | Cloud platform, dashboards |

---

# Technical Architecture

```
┌──────────────────────────────────────────────────────┐
│                    User Environment                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐ │
│  │ Claude Code│  │ PISAMA MCP │  │ PISAMA Skills  │ │
│  │  Session   │◄─┤  Observer  │  │ (diagnose/fix) │ │
│  └────────────┘  └─────┬──────┘  └───────┬────────┘ │
└────────────────────────┼─────────────────┼──────────┘
              ┌──────────▼─────────────────▼──────────┐
              │           PISAMA Cloud                 │
              │  ┌─────────┐ ┌──────────┐ ┌────────┐  │
              │  │ Traces  │ │ Analysis │ │ Fixes  │  │
              │  └─────────┘ └──────────┘ └────────┘  │
              └────────────────────────────────────────┘
```

---

# Business Model

## Revenue Streams

| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0 | Basic diagnostics, community patterns |
| **Pro** | $29/mo | Full analysis, custom detectors |
| **Team** | $99/mo | Team dashboards, shared patterns, API |
| **Enterprise** | Custom | On-prem, SLA, dedicated support |

**Target:** $1M ARR in 18 months

---

# Competitive Moat

## Why PISAMA Wins

1. **First Mover** - No dedicated Claude Skills forensics tool exists
2. **Data Network Effect** - More users = better pattern detection
3. **Platform Integration** - Native to Claude, not bolted on
4. **Open Core** - Community contributes detection patterns
5. **AI-Native** - Built by AI developers, for AI developers

---

# Success Metrics

## KPIs to Track

| Metric | 6-Month | 12-Month |
|--------|---------|----------|
| Skills Installs | 5,000 | 50,000 |
| Monthly Active Users | 1,000 | 10,000 |
| Traces Analyzed | 100K | 2M |
| Detection Accuracy | 90% | 95% |
| Paid Conversion | 3% | 5% |

---

# Why Now?

## Market Timing

- Claude Code adoption accelerating rapidly
- No mature observability for AI coding agents
- Anthropic actively promoting MCP ecosystem
- Developer pain points are acute and unaddressed
- Skills marketplace being built out

### Window: 12-18 months before major players enter

---

# Next Steps

## Immediate Actions

1. Complete MCP server prototype (Week 1-2)
2. Build trace capture pipeline (Week 2-3)
3. Develop first detection algorithms (Week 3-4)
4. Create pisama-diagnose skill (Week 5-6)
5. Private beta with 50 users (Week 7-8)
6. Public launch on Skills marketplace (Week 12)

---

# The Ask

## What We Need

- **Development:** 2 engineers, 16 weeks
- **Infrastructure:** Cloud hosting, trace storage
- **Partnerships:** Early access to Anthropic Skills APIs
- **Validation:** 50 beta testers from Claude Code power users

**Investment:** Seeking seed round to accelerate

---

# PISAMA: Agent Forensics

## *"Find out why your AI agent failed. Fix it automatically."*

- Build faster with internal skills
- Distribute through Claude's native platform
- Collect traces to power intelligent diagnostics

**Website:** pisama.ai

![bg right:30% opacity:0.2](https://images.unsplash.com/photo-1639322537228-f710d846310a?w=800)
