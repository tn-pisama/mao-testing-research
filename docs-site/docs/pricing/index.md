# Pricing

PISAMA uses span-based billing aligned with industry standards (OpenTelemetry). A **span** is one tool operation within an agent session (e.g., a Bash execution, a file read, or an LLM call). No surprise bills -- all plans have hard limits.

---

## Plan Comparison

| Feature | Free | Startup ($49/mo) | Growth ($199/mo) | Enterprise |
|---|---|---|---|---|
| **Spans/month** | 10,000 | 250,000 | 2,500,000 | Unlimited |
| **Capture level** | Standard | Full | Full | Full |
| **Projects** | 1 | 5 | 25 | Unlimited |
| **Retention** | 7 days | 30 days | 90 days | Custom (up to 2 years) |
| **Team members** | 1 | 3 | 10 | Unlimited |
| **Frameworks** | All | All | All | All |
| | | | | |
| **Detection** | | | | |
| Failure detection (14+ modes) | Yes | Yes | Yes | Yes |
| Detection history | 7 days | 30 days | 90 days | Custom |
| | | | | |
| **Fix Suggestions** | | | | |
| Basic fix suggestions | Yes | Yes | Yes | Yes |
| Code-level fixes | -- | Yes | Yes | Yes |
| Fix confidence scores | -- | Yes | Yes | Yes |
| AI-generated runbooks | -- | -- | Yes | Yes |
| | | | | |
| **Alerting** | | | | |
| Email alerts | Yes | Yes | Yes | Yes |
| Slack integration | -- | Yes | Yes | Yes |
| Webhook support | -- | Yes | Yes | Yes |
| PagerDuty/OpsGenie | -- | -- | Yes | Yes |
| Custom alert rules | -- | -- | Yes | Yes |
| | | | | |
| **Cost Analytics** | | | | |
| Token usage (basic) | Yes | Yes | Yes | Yes |
| Cost breakdown | -- | Yes | Yes | Yes |
| Budget alerts | -- | Yes | Yes | Yes |
| Cost projections | -- | -- | Yes | Yes |
| Optimization suggestions | -- | -- | Yes | Yes |
| | | | | |
| **API & Export** | | | | |
| Dashboard access | Yes | Yes | Yes | Yes |
| API access | -- | Yes | Yes | Yes |
| OTEL export | -- | Yes | Yes | Yes |
| Data export (CSV/JSON) | -- | Yes | Yes | Yes |
| OTEL native ingestion | -- | -- | -- | Yes |
| | | | | |
| **Team & Admin** | | | | |
| Basic roles | -- | Yes | Yes | Yes |
| Advanced RBAC | -- | -- | -- | Yes |
| SSO/SAML | -- | -- | -- | Yes |
| Audit logs | -- | -- | Yes | Yes |
| | | | | |
| **Self-Healing** | | | | |
| Playbook fixes | -- | -- | Yes | Yes |
| AI-generated fixes | -- | -- | -- | Yes |
| Auto-apply (canary) | -- | -- | -- | Yes |
| | | | | |
| **Support** | | | | |
| Community (Discord) | Yes | Yes | Yes | Yes |
| Email support | -- | Yes | Yes | Yes |
| Priority support | -- | -- | Yes | Yes |
| Dedicated support | -- | -- | -- | Yes |
| SLA | -- | -- | -- | Yes |

---

## Annual Discount

| Tier | Monthly | Annual (per month) | Savings |
|---|---|---|---|
| Startup | $49 | $41 | 17% |
| Growth | $199 | $166 | 17% |
| Enterprise | Custom | Custom | Negotiable |

---

## What Counts as a Span?

| Counts as a Span | Does Not Count |
|---|---|
| Bash execution | Pre-flight checks |
| File read/write/edit | Internal state updates |
| LLM call | Retries (same span ID) |
| Tool call | Blocked operations |
| Subagent task | -- |
| Grep/Glob search | -- |
| MCP tool calls | -- |

## Capture Levels

| Level | Input | Reasoning | Output | Tool I/O | Metadata |
|---|---|---|---|---|---|
| **Full** | Yes | Yes | Yes | Yes | Yes |
| **Standard** | Yes | -- | Yes | Yes | Yes |
| **Minimal** | -- | -- | -- | Summary | Yes |

- Free tier: Standard capture (no reasoning blocks, saves 60% storage)
- Paid tiers: Full capture (configurable)

---

## Free Tier Details

The free tier delivers real value, not a crippled demo.

**Included:**

- 10,000 spans/month (~330/day, covers a solo dev comfortably)
- All 14 ICP failure mode detectors
- Basic fix suggestions with every detection
- Email alerts (up to 10/day)
- Full dashboard access
- All frameworks supported

**Not included (upgrade triggers):**

| Feature | Upgrade Trigger |
|---|---|
| Slack/webhook alerts | "My team needs to see alerts" |
| Code-level fixes | "I want copy-paste fixes" |
| API access | "I want to automate" |
| OTEL export | "I need this in Datadog" |
| Cost breakdown | "I need to show my CTO" |
| Multiple projects | "I have multiple apps" |
| Extended retention | "I need to see trends" |
| Team members | "My team needs access" |

**Rate limits:**

| Limit | Value |
|---|---|
| Spans/minute | 100 |
| Spans/hour | 1,000 |
| Concurrent sessions | 3 |

**Overage policy:** Hard limit, no surprise bills. When you hit 10,000 spans, new spans are rejected until the monthly reset. Existing data is retained.

---

## Startup Tier ($49/mo)

For AI team leads who can approve <$500/mo.

- 250,000 spans/month
- Full capture (including reasoning blocks)
- 5 projects, 3 team members
- 30-day retention
- Slack integration, API access, OTEL export
- Code-level fixes with confidence scores
- Email support

**Overage:** Hard limit at 250K spans. Warnings at 80% and 90%.

---

## Growth Tier ($199/mo)

For CTOs who approve $200-500/mo for team tools.

- 2,500,000 spans/month
- 25 projects, 10 team members
- 90-day retention
- PagerDuty/OpsGenie, custom alert rules
- Cost projections, optimization suggestions
- AI-generated runbooks
- Self-healing playbooks
- Audit logs
- Priority support

---

## Enterprise Tier (Custom)

For organizations with compliance and scale requirements.

- Unlimited spans
- Unlimited projects and team members
- Custom retention (up to 2 years)
- SSO/SAML, advanced RBAC
- OTEL native ingestion
- AI-generated fixes, auto-apply (canary)
- Data residency options
- Dedicated support with SLA
- SOC 2 report

| Company Size | Typical Annual |
|---|---|
| 200-500 employees | $25,000-50,000 |
| 500-2000 employees | $50,000-150,000 |
| 2000+ employees | $150,000+ |

---

## Competitive Comparison

| Feature | PISAMA Free | LangSmith Free | Arize Free |
|---|---|---|---|
| Spans/month | 10,000 | 5,000 traces | 1,000 |
| Retention | 7 days | 14 days | 7 days |
| All frameworks | Yes | LangChain only | Yes |
| Failure detection | 14 modes | Basic | Drift only |
| Fix suggestions | Yes | -- | -- |
| Reasoning capture | Paid only | Yes | -- |

**PISAMA advantage:** Fix suggestions included free. More generous span limits. Framework agnostic.

---

## FAQ

**Why no credit card for the free tier?**
Reduce friction. Maximum signups, filter later.

**Why hard limits instead of overage charges?**
No surprise bills. Trust builds loyalty.

**Why 10,000 spans for free?**
Covers a solo dev comfortably (~330/day). Based on typical usage: 20-50 spans/session, 2-5 sessions/day.

**What's the difference between a span and a session?**
A span is one tool operation. A session is a collection of spans from one conversation. We bill on spans because sessions vary wildly in size.

**Can users downgrade?**
Yes, at any time. Data beyond new limits is archived (not deleted) for 30 days.
