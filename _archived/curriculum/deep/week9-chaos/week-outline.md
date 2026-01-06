# Week 9: Chaos Engineering & Observability - Complete Outline

**Duration:** 5 days (20-30 hours total)
**Prerequisites:** Weeks 1-8
**Outcome:** Production-grade resilience testing and monitoring

---

## Day-by-Day Breakdown

### Day 41: Chaos Engineering Principles
- Netflix Chaos Monkey origins
- Chaos engineering for AI systems
- Hypothesis → Experiment → Analyze
- Blast radius management
- Steady state definition
- Rollback strategies
- **Reading:** "Chaos Engineering" book excerpts

### Day 42: Fault Injection Framework
- Agent fault types:
  - Grumpy agent (unhelpful responses)
  - Slow agent (latency injection)
  - Hallucinator (confident wrong answers)
  - Role thief (boundary violations)
  - State corruptor (invalid state)
  - Token burner (excessive output)
- Implementation patterns
- **Deliverable:** 6 fault injectors

### Day 43: OpenTelemetry Implementation
- GenAI semantic conventions
- Span creation for agents
- Attribute standards
- Trace context propagation
- Metric collection
- Log correlation
- **Deliverable:** OTEL-instrumented agent

### Day 44: Alerting and Dashboards
- Key metrics to monitor:
  - Token usage / cost
  - Latency percentiles
  - Error rates by type
  - Loop detection rate
  - MAST failure rates
- Grafana dashboard design
- PagerDuty/Slack alerting
- **Deliverable:** Monitoring dashboard

### Day 45: Gameday Runbooks
- Gameday planning
- Scenario design
- Communication protocols
- Incident response
- Post-mortem templates
- Improvement tracking
- **Deliverable:** 3 gameday scenarios

---

## Fault Injection Catalog

```
┌─────────────────────────────────────────────────────────────────┐
│                    FAULT INJECTION CATALOG                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AGENT FAULTS                                                    │
│  ────────────                                                    │
│  grumpy_agent      → Returns unhelpful responses                │
│  slow_agent        → Adds latency (10s-60s)                     │
│  hallucinator      → Returns confident but wrong info           │
│  role_thief        → Does other agents' work                    │
│  token_burner      → Returns excessively long responses         │
│  refuser           → Refuses to perform task                    │
│                                                                  │
│  TOOL FAULTS                                                     │
│  ───────────                                                     │
│  tool_timeout      → Tool doesn't respond                       │
│  tool_error        → Tool returns error                         │
│  tool_wrong        → Tool returns incorrect data                │
│  tool_partial      → Tool returns incomplete data               │
│                                                                  │
│  STATE FAULTS                                                    │
│  ────────────                                                    │
│  state_corrupt     → Invalid values in state                    │
│  state_missing     → Required fields missing                    │
│  state_stale       → Outdated information                       │
│                                                                  │
│  NETWORK FAULTS                                                  │
│  ──────────────                                                  │
│  api_timeout       → LLM API doesn't respond                    │
│  api_rate_limit    → 429 responses                              │
│  api_error         → 500 responses                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## OTEL Span Attributes

```python
# Standard GenAI attributes
span.set_attribute("gen_ai.system", "langgraph")
span.set_attribute("gen_ai.request.model", "gpt-4")
span.set_attribute("gen_ai.response.model", "gpt-4-0613")
span.set_attribute("gen_ai.usage.input_tokens", 150)
span.set_attribute("gen_ai.usage.output_tokens", 50)
span.set_attribute("gen_ai.usage.total_tokens", 200)

# Agent-specific attributes
span.set_attribute("gen_ai.agent.name", "researcher")
span.set_attribute("gen_ai.agent.iteration", 3)
span.set_attribute("gen_ai.agent.tool_calls", 2)

# Custom MAO testing attributes
span.set_attribute("mao.failure_mode", "F6_task_derailment")
span.set_attribute("mao.detection_confidence", 0.85)
span.set_attribute("mao.cost_usd", 0.023)
```

---

## Dashboard Panels

1. **Cost Overview** - Total spend, by agent, by model
2. **Latency Distribution** - P50, P95, P99
3. **Error Rate** - By type, by agent
4. **Token Usage** - Input vs output, trends
5. **Loop Detection** - Caught vs missed
6. **MAST Failures** - By category, trends
7. **Active Threads** - Concurrent executions
8. **SLA Compliance** - Latency and availability
