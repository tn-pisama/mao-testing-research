# PISAMA Pricing Tiers

**Date:** 2026-01-05
**Version:** 1.0
**Status:** Draft - requires validation

---

## Pricing Philosophy

1. **Free tier must deliver value** - Not a crippled demo, actual utility for solo builders
2. **Clear upgrade triggers** - Users hit limits naturally when they're ready to pay
3. **Usage-based alignment** - Pay for what you use, not seat count
4. **No surprise bills** - Hard limits, not overage charges

---

## Tier Comparison

| Feature | Free | Startup ($49/mo) | Growth ($199/mo) | Enterprise |
|---------|------|------------------|------------------|------------|
| **Traces/month** | 5,000 | 100,000 | 1,000,000 | Unlimited |
| **Projects** | 1 | 5 | 25 | Unlimited |
| **Retention** | 7 days | 30 days | 90 days | Custom (up to 2 years) |
| **Team members** | 1 | 3 | 10 | Unlimited |
| **Frameworks** | All | All | All | All |
| | | | | |
| **Detection** | | | | |
| - Failure detection (14 modes) | ✓ | ✓ | ✓ | ✓ |
| - Detection history | 7 days | 30 days | 90 days | Custom |
| | | | | |
| **Fix Suggestions** | | | | |
| - Basic fix suggestions | ✓ | ✓ | ✓ | ✓ |
| - Code-level fixes | - | ✓ | ✓ | ✓ |
| - Fix confidence scores | - | ✓ | ✓ | ✓ |
| - AI-generated runbooks | - | - | ✓ | ✓ |
| | | | | |
| **Alerting** | | | | |
| - Email alerts | ✓ | ✓ | ✓ | ✓ |
| - Slack integration | - | ✓ | ✓ | ✓ |
| - Webhook support | - | ✓ | ✓ | ✓ |
| - PagerDuty/OpsGenie | - | - | ✓ | ✓ |
| - Custom alert rules | - | - | ✓ | ✓ |
| | | | | |
| **Cost Analytics** | | | | |
| - Token usage (basic) | ✓ | ✓ | ✓ | ✓ |
| - Cost breakdown | - | ✓ | ✓ | ✓ |
| - Budget alerts | - | ✓ | ✓ | ✓ |
| - Cost projections | - | - | ✓ | ✓ |
| - Optimization suggestions | - | - | ✓ | ✓ |
| | | | | |
| **API & Export** | | | | |
| - Dashboard access | ✓ | ✓ | ✓ | ✓ |
| - API access | - | ✓ | ✓ | ✓ |
| - OTEL export | - | ✓ | ✓ | ✓ |
| - Data export (CSV/JSON) | - | ✓ | ✓ | ✓ |
| - OTEL ingestion | - | - | - | ✓ |
| | | | | |
| **Team & Admin** | | | | |
| - Basic roles | - | ✓ | ✓ | ✓ |
| - Advanced RBAC | - | - | - | ✓ |
| - SSO/SAML | - | - | - | ✓ |
| - Audit logs | - | - | ✓ | ✓ |
| | | | | |
| **Self-Healing** (Phase 4) | | | | |
| - Playbook fixes | - | - | ✓ | ✓ |
| - AI-generated fixes | - | - | - | ✓ |
| - Auto-apply (canary) | - | - | - | ✓ |
| | | | | |
| **Support** | | | | |
| - Community (Discord) | ✓ | ✓ | ✓ | ✓ |
| - Email support | - | ✓ | ✓ | ✓ |
| - Priority support | - | - | ✓ | ✓ |
| - Dedicated support | - | - | - | ✓ |
| - SLA | - | - | - | ✓ |

---

## Free Tier Detail

### Limits

| Dimension | Limit | Rationale |
|-----------|-------|-----------|
| **Traces/month** | 5,000 | ~165/day, enough for solo dev/testing |
| **Projects** | 1 | Single app focus, upgrade for multi-project |
| **Retention** | 7 days | Debug recent issues, not trend analysis |
| **Team members** | 1 | Solo use only |
| **API calls/day** | 0 | Dashboard only, upgrade for API |
| **Alerts/day** | 10 | Prevent spam, encourage prioritization |

### Rate Limits

| Limit | Value | Rationale |
|-------|-------|-----------|
| Traces/minute | 50 | Prevent burst abuse |
| Traces/hour | 500 | ~8/min sustained |
| Concurrent sessions | 3 | Solo dev workload |

### Included Features

| Feature | Included | Notes |
|---------|----------|-------|
| All 14 failure modes | ✓ | Full detection capability |
| Basic fix suggestions | ✓ | Text-based, not code-level |
| Email alerts | ✓ | Up to 10/day |
| Token usage display | ✓ | Basic count, no breakdown |
| Dashboard | ✓ | Full UI access |
| All frameworks | ✓ | No framework restrictions |
| Community Discord | ✓ | Self-serve support |

### Not Included (Upgrade Triggers)

| Feature | Why Excluded | Upgrade Trigger |
|---------|--------------|-----------------|
| Slack/webhook alerts | Team feature | "I need my team to see alerts" |
| Code-level fixes | Premium value | "I want copy-paste fixes" |
| API access | Developer feature | "I want to automate" |
| OTEL export | Integration feature | "I need this in Datadog" |
| Cost breakdown | Business feature | "I need to show my CTO" |
| >1 project | Scale feature | "I have multiple apps" |
| >7 day retention | Analysis feature | "I need to see trends" |
| Team members | Collaboration | "My team needs access" |

### Abuse Prevention

| Mechanism | Implementation |
|-----------|----------------|
| Rate limiting | 50 traces/min, 500/hour hard cap |
| Project limit | 1 project, can't create more |
| No API | Dashboard only, harder to automate abuse |
| Email verification | Required for signup |
| Monthly reset | Hard reset, no rollover |
| Single user | No sharing accounts |

---

## Startup Tier Detail ($49/mo)

### Target User
Alex (AI Team Lead) who can approve <$500/mo

### Limits

| Dimension | Limit |
|-----------|-------|
| Traces/month | 100,000 |
| Projects | 5 |
| Retention | 30 days |
| Team members | 3 |
| API calls/day | 10,000 |
| Alerts/day | 100 |

### Key Unlocks from Free

| Feature | Value to User |
|---------|---------------|
| **Slack integration** | Alerts where the team lives |
| **Code-level fixes** | Copy-paste solutions |
| **API access** | Automation, CI/CD integration |
| **OTEL export** | Connect to existing observability |
| **Cost breakdown** | Understand spending by agent |
| **5 projects** | Multiple apps/environments |
| **3 team members** | Small team collaboration |
| **30 day retention** | Weekly trend analysis |
| **Email support** | Get help when stuck |

### Overage Handling

**No overage charges.** Hard limit at 100K traces.

When approaching limit:
- 80%: Email warning
- 90%: Dashboard banner
- 100%: New traces rejected, existing data retained

User can:
1. Wait for monthly reset
2. Upgrade to Growth
3. Delete old projects to free up quota (future feature)

---

## Growth Tier Detail ($199/mo)

### Target User
Jordan (CTO) who approves $200-500/mo for team tools

### Limits

| Dimension | Limit |
|-----------|-------|
| Traces/month | 1,000,000 |
| Projects | 25 |
| Retention | 90 days |
| Team members | 10 |
| API calls/day | 100,000 |
| Alerts/day | 1,000 |

### Key Unlocks from Startup

| Feature | Value to User |
|---------|---------------|
| **PagerDuty/OpsGenie** | On-call workflow integration |
| **Cost projections** | Budget planning |
| **Optimization suggestions** | Reduce AI spend |
| **AI-generated runbooks** | Operational documentation |
| **Custom alert rules** | Tailored alerting |
| **Audit logs** | Compliance, debugging |
| **Self-healing (playbooks)** | Automated fixes |
| **10 team members** | Full team access |
| **90 day retention** | Quarterly analysis |
| **Priority support** | Faster response |

---

## Enterprise Tier (Custom)

### Target User
Jordan (CTO) + Procurement for companies with compliance needs

### Typical Configuration

| Dimension | Typical | Maximum |
|-----------|---------|---------|
| Traces/month | 10M+ | Unlimited |
| Projects | 100+ | Unlimited |
| Retention | 1 year | 2 years |
| Team members | 50+ | Unlimited |

### Key Unlocks from Growth

| Feature | Value to User |
|---------|---------------|
| **OTEL native ingestion** | Enterprise observability stack |
| **SSO/SAML** | Corporate identity |
| **Advanced RBAC** | Granular permissions |
| **AI-generated fixes** | Full self-healing |
| **Auto-apply (canary)** | Automated remediation |
| **Data residency** | Compliance requirements |
| **SLA** | Guaranteed uptime |
| **Dedicated support** | Named contact |
| **Custom retention** | Compliance needs |
| **SOC 2 report** | Security compliance |

### Pricing Factors

| Factor | Impact |
|--------|--------|
| Trace volume | Primary driver |
| Retention period | Storage cost |
| Self-healing usage | AI inference cost |
| Support level | Service cost |
| Compliance needs | Audit cost |

### Typical Pricing

| Company Size | Typical Annual |
|--------------|----------------|
| 200-500 employees | $25,000-50,000 |
| 500-2000 employees | $50,000-150,000 |
| 2000+ employees | $150,000+ |

---

## Annual Discount

| Tier | Monthly | Annual (per month) | Savings |
|------|---------|-------------------|---------|
| Startup | $49 | $41 | 17% |
| Growth | $199 | $166 | 17% |
| Enterprise | Custom | Custom | Negotiable |

---

## Conversion Metrics to Track

### Free → Startup Triggers

| Trigger | Target % |
|---------|----------|
| Hit trace limit | 30% |
| Tried to add team member | 25% |
| Wanted Slack alerts | 20% |
| Needed API access | 15% |
| Other | 10% |

### Startup → Growth Triggers

| Trigger | Target % |
|---------|----------|
| Hit trace limit | 25% |
| Needed PagerDuty | 20% |
| Wanted cost projections | 20% |
| Team size >3 | 20% |
| Other | 15% |

---

## Implementation Notes

### Phase 1 Requirements

1. **Billing system integration** (Stripe)
2. **Usage tracking** (traces, API calls, alerts)
3. **Limit enforcement** (hard stops, not soft)
4. **Upgrade prompts** (contextual, not annoying)
5. **Plan management UI** (view usage, upgrade, downgrade)

### Database Schema Additions

```sql
-- Organization limits
ALTER TABLE organizations ADD COLUMN plan VARCHAR(20) DEFAULT 'free';
ALTER TABLE organizations ADD COLUMN trace_limit INTEGER DEFAULT 5000;
ALTER TABLE organizations ADD COLUMN project_limit INTEGER DEFAULT 1;
ALTER TABLE organizations ADD COLUMN retention_days INTEGER DEFAULT 7;
ALTER TABLE organizations ADD COLUMN team_limit INTEGER DEFAULT 1;

-- Usage tracking
CREATE TABLE usage_metrics (
    id UUID PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id),
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    traces_count INTEGER DEFAULT 0,
    api_calls_count INTEGER DEFAULT 0,
    alerts_sent_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Plan changes
CREATE TABLE plan_changes (
    id UUID PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id),
    from_plan VARCHAR(20),
    to_plan VARCHAR(20),
    reason VARCHAR(255),
    changed_at TIMESTAMP DEFAULT NOW()
);
```

---

## Competitive Comparison

| Feature | PISAMA Free | LangSmith Free | Arize Free |
|---------|-------------|----------------|------------|
| Traces/month | 5,000 | 5,000 | 1,000 |
| Retention | 7 days | 14 days | 7 days |
| Team members | 1 | 1 | 1 |
| All frameworks | ✓ | LangChain only | ✓ |
| Detection | 14 modes | Basic | Drift only |
| Fix suggestions | ✓ | - | - |
| Email alerts | ✓ | - | ✓ |

**PISAMA advantage:** Fix suggestions included in free tier (unique).

---

## FAQ

**Q: Why no credit card for free tier?**
A: Reduce friction. We want maximum signups, filter later.

**Q: Why hard limits instead of overage?**
A: No surprise bills. Trust builds loyalty.

**Q: Why 5,000 traces for free?**
A: Enough for solo dev (165/day), not enough for production team.

**Q: Why no Slack in free?**
A: Natural upgrade trigger for teams. Email sufficient for solo.

**Q: Why include fix suggestions in free?**
A: Key differentiator. Hook users on the unique value.

**Q: Can users downgrade?**
A: Yes, at any time. Data beyond new limits is archived (not deleted) for 30 days.

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-05 | Initial pricing structure |
