# Pisama Pricing

**Date:** 2026-03-21
**Version:** 2.0
**Status:** Active

---

## Billing Model: Per-Project

Pisama uses flat per-project pricing. No usage metering, no surprise bills.

**What counts as a project?** One app or repo you're monitoring with Pisama.

Why per-project (not usage-based):
- Vibe-coders think in projects, not API calls or spans
- Flat pricing = predictable costs
- No usage anxiety or surprise overages
- Simple to explain: "Monitor up to 3 projects for $29/mo"

---

## Pricing Tiers

| | Free | Pro | Team | Enterprise |
|---|---|---|---|---|
| **Price** | $0 | $29/mo | $79/mo | Custom |
| **Annual** | - | $23/mo | $63/mo | Negotiable |
| **Projects** | 1 | 3 | 10 | Unlimited |
| **Team members** | 1 | 1 | 5 | Unlimited |
| **History** | 7 days | 30 days | 90 days | Custom |
| | | | | |
| **Detection** | | | | |
| All 42 failure detectors | Yes | Yes | Yes | Yes |
| | | | | |
| **Fix Suggestions** | | | | |
| Basic fix descriptions | Yes | Yes | Yes | Yes |
| Code-level fixes | - | Yes | Yes | Yes |
| AI-generated runbooks | - | - | Yes | Yes |
| | | | | |
| **Alerts** | | | | |
| Email alerts | 5/day | 50/day | 500/day | Unlimited |
| Slack + Discord + webhooks | - | Yes | Yes | Yes |
| PagerDuty / OpsGenie | - | - | Yes | Yes |
| Custom alert rules | - | - | Yes | Yes |
| | | | | |
| **Cost Analytics** | | | | |
| Basic token usage | Yes | Yes | Yes | Yes |
| Cost breakdown per project | - | Yes | Yes | Yes |
| Trend analysis + projections | - | - | Yes | Yes |
| | | | | |
| **API & Export** | | | | |
| Dashboard access | Yes | Yes | Yes | Yes |
| REST API access | - | Yes | Yes | Yes |
| CSV/JSON data export | - | Yes | Yes | Yes |
| | | | | |
| **Team & Admin** | | | | |
| Activity logs / audit | - | - | Yes | Yes |
| SSO / SAML | - | - | - | Yes |
| Advanced RBAC | - | - | - | Yes |
| | | | | |
| **Self-Healing** | | | | |
| Playbook fixes | - | - | - | Yes |
| Automated fix application | - | - | - | Yes |
| Approval workflows | - | - | - | Yes |
| | | | | |
| **Support** | | | | |
| Community (Discord) | Yes | Yes | Yes | Yes |
| Email support | - | Yes | Yes | Yes |
| Priority support | - | - | Yes | Yes |
| Dedicated support + SLA | - | - | - | Yes |
| | | | | |
| **Frameworks** | All | All | All | All |
| **Integration** | SDK + CLI | SDK + CLI | SDK + CLI | SDK + CLI |

---

## Free Tier

**"Try it, it works."**

All 42 failure detectors included — not a crippled demo. The upgrade triggers are project count and fix quality, not detection capability.

| Dimension | Limit | Rationale |
|-----------|-------|-----------|
| Projects | 1 | Single app focus |
| Team members | 1 | Solo use |
| History | 7 days | Debug recent issues |
| Email alerts | 5/day | Prevent spam |
| API access | No | Dashboard only |

No credit card required.

---

## Pro Tier ($29/mo)

**"My side projects are covered."**

Target: Solo builder with 2-3 active projects who wants copy-paste fixes and Slack alerts.

Upgrade triggers from Free:
- "I have a second project"
- "I want code-level fixes, not just descriptions"
- "I need Slack alerts"

Annual: $23/mo ($276/yr, 20% off).

---

## Team Tier ($79/mo)

**"My team needs this."**

Target: Small team (2-5 people) shipping AI-powered products together.

Upgrade triggers from Pro:
- "My co-founder needs access"
- "I need longer history to see trends"
- "I have more than 3 active projects"

Annual: $63/mo ($756/yr, 20% off).

---

## Enterprise (Custom)

**"We need compliance, self-healing, and regulatory readiness."**

Target: Companies with compliance needs, EU AI Act obligations, or production-critical agent systems.

**EU AI Act Ready** — Pisama's runtime monitoring satisfies post-market monitoring requirements (Article 9, Article 72):

| EU AI Act Requirement | Pisama Enterprise Feature |
|---|---|
| Continuous performance monitoring | 42 failure detectors on production traces |
| Comprehensive logging | OTEL trace ingestion with full audit trail |
| Serious incident reporting | Alert escalation with regulatory timestamps |
| Human oversight mechanisms | Healing approval workflows (human-in-the-loop) |
| Risk management documentation | Compliance report export (detection history, risk levels, resolutions) |

Additional Enterprise features:
- Unlimited projects and team members
- Automated fix application with approval workflows
- SSO / SAML, advanced RBAC
- Custom retention (up to 2 years)
- Data residency options (EU, US)
- Dedicated support with SLA
- SOC 2 report
- Compliance report export (PDF, regulatory-ready)
- Incident log with severity classification

Typical pricing:

| Company Size | Typical Annual |
|---|---|
| 50-200 employees | $15,000-30,000 |
| 200-1000 employees | $30,000-100,000 |
| 1000+ employees | $100,000+ |

---

## Backend Guardrails

To prevent abuse without complicating pricing, soft limits exist but are not surfaced to users:

| Tier | Agent runs/day | API requests/min | Alerts/day |
|------|---------------|------------------|------------|
| Free | 50 | 30 | 5 |
| Pro | 500 | 200 | 50 |
| Team | 5,000 | 1,000 | 500 |
| Enterprise | Unlimited | 10,000 | Unlimited |

When a free user hits the daily run limit, show a friendly upgrade nudge — don't hard-block.

---

## Upgrade / Downgrade

- **Upgrade**: Instant. Prorated billing for remainder of current period.
- **Downgrade**: Takes effect at end of current billing period. Extra projects are paused (not deleted) for 30 days.
- **Cancel**: Reverts to Free at end of billing period. Data retained per Free tier limits (7 days).

---

## Competitive Comparison

Competitors use different billing models (per-call, per-seat, usage-based). Here's what each actually costs at common usage levels:

### Solo Dev (1 project, ~1,500 traces/mo)

| Platform | Monthly Cost | What You Get |
|---|---|---|
| **Pisama** | **$0** | 42 detectors, basic fixes, email alerts, 7-day history |
| Patronus AI | $15 | Hallucination eval only, no dashboard |
| LangSmith | $0 | Tracing only, 5K trace limit, 1 user |
| Langfuse | $0 | Tracing only, 50K obs limit, 2 users |
| Braintrust | $0 | Tracing + evals, 1M span limit |
| Arize | $0 | Tracing, 3 users, 14-day retention |

### Small Team (3 devs, 5 projects, ~10K traces/mo)

| Platform | Monthly Cost | What You Get |
|---|---|---|
| **Pisama** | **$79** | 42 detectors, code fixes, runbooks, Slack, 5 members |
| Patronus AI | $100+ | Hallucination + custom evals, enterprise sales required |
| LangSmith | $117 ($39 x 3) | Tracing + evals, LangChain only |
| Langfuse | $30-199 | Tracing + prompt mgmt, no detection |
| Braintrust | $0-249 | Tracing + evals (free tier may still cover) |
| Arize | $50 | Tracing + basic monitoring |

### Feature Comparison

| Capability | Pisama | Patronus | LangSmith | Langfuse | Braintrust | Arize |
|---|---|---|---|---|---|---|
| Failure detection | 42 modes | Hallucination | None | None | None | Drift |
| Fix suggestions | Yes | No | No | No | No | No |
| Self-healing | Enterprise | No | No | No | No | No |
| Tracing | Yes | No | Yes | Yes | Yes | Yes |
| Framework-agnostic | Yes | Yes | LangChain-first | Yes | Yes | Yes |
| Billing model | Flat/project | Per-call | Per-seat | Usage | Usage | Usage |

**Pisama advantage**: Only platform with failure detection + fix suggestions at every tier. Flat per-project pricing — no usage anxiety.

---

## FAQ

**Do I need a credit card for Free?**
No.

**What counts as a project?**
One app or repo you're monitoring with Pisama.

**Can I upgrade anytime?**
Yes. Instant upgrade, prorated billing.

**What if I hit the daily limit?**
We'll nudge you to upgrade. No data loss.

**What happens if I downgrade?**
Your extra projects are paused (not deleted) for 30 days.

**Do all tiers get all 42 detectors?**
Yes. Detection capability is the same across all tiers. Upgrade triggers are project count, fix quality, and team features.

---

## Implementation

### Stripe Products

| Product | Price ID Env Var |
|---------|-----------------|
| Pisama Pro Monthly ($29) | `STRIPE_PRICE_ID_PRO_MONTHLY` |
| Pisama Pro Annual ($276) | `STRIPE_PRICE_ID_PRO_ANNUAL` |
| Pisama Team Monthly ($79) | `STRIPE_PRICE_ID_TEAM_MONTHLY` |
| Pisama Team Annual ($756) | `STRIPE_PRICE_ID_TEAM_ANNUAL` |

### Backend Constants

Plan definitions in `backend/app/billing/constants.py`:
- `PlanTier.FREE` / `PlanTier.PRO` / `PlanTier.TEAM` / `PlanTier.ENTERPRISE`
- `get_project_limit(plan)` — returns project limit for a plan
- `get_daily_run_limit(plan)` — returns daily run limit
- `get_rate_limit(plan)` — returns API rate limit config

### Database

Tenant model (`backend/app/storage/models.py`):
- `plan` — current plan (free/pro/team/enterprise)
- `project_limit` — project limit (default: 1)
- `stripe_customer_id` — Stripe customer
- `stripe_subscription_id` — Stripe subscription
- `subscription_status` — active/canceled/etc.
- `current_period_end` — billing period end

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-05 | Initial pricing structure (span-based) |
| 1.1 | 2026-01-05 | Clarified metering model, capture levels |
| 2.0 | 2026-03-21 | Full overhaul: per-project billing, renamed tiers (Startup->Pro, Growth->Team), new prices ($29/$79), 42 detectors, vibe-coder audience |
