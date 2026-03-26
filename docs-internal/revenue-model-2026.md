# Pisama Revenue & P&L Model

**Date:** 2026-03-21
**Version:** 2.0
**Pricing:** Free $0 / Pro $29/mo / Team $79/mo / Enterprise custom

---

## Assumptions

### User Growth

| Assumption | Value | Rationale |
|---|---|---|
| Month 1 free signups | 30 | Design partner outreach + soft launch |
| Free signup MoM growth | 20% | Flattens to 10% after month 6 |
| Free-to-paid conversion | 5% | Strong onboarding (first detection <5 min) |
| Pro/Team split (of paid) | 70% / 30% | Most vibe-coders are solo |
| Monthly churn (paid) | 6% | Annual billing default + retention features |
| First enterprise deal | Month 6 | Design partner pipeline + NeurIPS credibility |
| Enterprise ACV | $3,000/mo | Market rate for agent reliability tooling |
| Enterprise deals/quarter | 1, ramping to 2 | Referral flywheel from existing customers |
| Expansion revenue | +15% ARPU | Add-on projects ($9/ea) + premium features |

### Annual Billing

30% of new customers choose annual (presented as default):
- Pro annual: $23/mo ($276/yr, 20% off)
- Team annual: $63/mo ($756/yr, 20% off)
- Impact: reduces effective blended churn to ~4.2% for annual cohort

### Costs

| Cost Item | Monthly | Scales With |
|---|---|---|
| Fly.io backend | $30 base | +$15 per 100 active users |
| PostgreSQL (managed) | $30 base | +$10 per 100 active users |
| Redis | $15 | Flat until 1K users |
| Vercel (frontend) | $20 | Flat (Pro plan) |
| Domain + email | $15 | Flat |
| LLM detection (Claude) | Variable | $0.004/trace blended avg |
| Stripe fees | 2.9% + $0.30 | Per transaction |

### Detection Cost Model

| Tier | Cost/trace | % of traces | Weighted cost |
|---|---|---|---|
| Tier 1 (hash/rules) | $0.000 | 60% | $0.000 |
| Tier 2 (state delta) | $0.001 | 25% | $0.000 |
| Tier 3 (embeddings) | $0.005 | 10% | $0.001 |
| Tier 4 (LLM judge) | $0.050 | 5% | $0.003 |
| **Blended average** | | | **$0.004/trace** |

95% of traces resolve at Tier 1-2 (free/near-free). The tiered escalation architecture is the margin protector.

### Traces Per User

| Plan | Avg Projects | Traces/project/day | Monthly traces |
|---|---|---|---|
| Free | 1 | 15 | 450 |
| Pro | 2 | 25 | 1,500 |
| Team | 5 | 30 | 4,500 |
| Enterprise | 20 | 50 | 30,000 |

---

## 24-Month Revenue Projection

### Year 1 (Months 1-12)

| Month | Free Users | New Paid | Churned | Active Paid | Pro | Team | Ent | MRR |
|---|---|---|---|---|---|---|---|---|
| 1 | 30 | 2 | 0 | 2 | 2 | 0 | 0 | $67 |
| 2 | 36 | 2 | 0 | 4 | 3 | 1 | 0 | $166 |
| 3 | 43 | 2 | 0 | 6 | 4 | 2 | 0 | $274 |
| 4 | 100 | 5 | 0 | 11 | 8 | 3 | 0 | $506 |
| 5 | 120 | 6 | 1 | 16 | 11 | 5 | 0 | $714 |
| 6 | 144 | 7 | 1 | 22 | 15 | 7 | 1 | $4,541 |
| 7 | 158 | 8 | 1 | 29 | 20 | 9 | 1 | $4,901 |
| 8 | 174 | 9 | 2 | 36 | 25 | 11 | 1 | $5,563 |
| 9 | 191 | 10 | 2 | 44 | 30 | 12 | 2 | $8,818 |
| 10 | 210 | 11 | 3 | 52 | 36 | 14 | 2 | $9,756 |
| 11 | 231 | 12 | 3 | 61 | 42 | 16 | 3 | $13,246 |
| 12 | 254 | 13 | 4 | 70 | 48 | 19 | 3 | $14,513 |

**Year 1 summary:**
- Total free signups: ~1,691
- Active paid at month 12: 70 self-serve + 3 enterprise
- **MRR at month 12: $14,513**
- **ARR run rate: $174,156**
- **Cumulative revenue year 1: ~$63,000**

### Year 2 (Months 13-24)

| Month | Free Users | Active Paid | Pro | Team | Ent | MRR |
|---|---|---|---|---|---|---|
| 13 | 279 | 79 | 54 | 21 | 4 | $17,799 |
| 14 | 307 | 88 | 60 | 23 | 5 | $21,234 |
| 15 | 338 | 97 | 66 | 25 | 6 | $24,555 |
| 16 | 372 | 106 | 72 | 27 | 7 | $28,012 |
| 17 | 409 | 115 | 78 | 29 | 8 | $31,352 |
| 18 | 450 | 124 | 84 | 31 | 9 | $34,790 |
| 19 | 495 | 133 | 90 | 33 | 10 | $38,175 |
| 20 | 545 | 142 | 96 | 35 | 11 | $41,613 |
| 21 | 599 | 151 | 102 | 37 | 12 | $44,997 |
| 22 | 659 | 160 | 108 | 39 | 13 | $48,433 |
| 23 | 725 | 169 | 114 | 41 | 14 | $51,815 |
| 24 | 798 | 178 | 120 | 43 | 15 | $55,300 |

**Year 2 summary:**
- Active paid at month 24: 178 self-serve + 15 enterprise
- **MRR at month 24: $55,300**
- **ARR run rate: $663,600**
- **Cumulative revenue year 2: ~$438,000**
- **2-year cumulative: ~$501,000**

---

## Revenue Mix

### Month 12

| Source | Count | Monthly Rev | % of MRR |
|---|---|---|---|
| Pro ($29/mo) | 48 | $1,392 | 10% |
| Team ($79/mo) | 19 | $1,501 | 10% |
| Enterprise ($3K/mo) | 3 | $9,000 | 62% |
| Expansion add-ons | - | $2,620 | 18% |
| **Total MRR** | | **$14,513** | **100%** |

### Month 24

| Source | Count | Monthly Rev | % of MRR |
|---|---|---|---|
| Pro ($29/mo) | 120 | $3,480 | 6% |
| Team ($79/mo) | 43 | $3,397 | 6% |
| Enterprise ($3K/mo) | 15 | $45,000 | 81% |
| Expansion add-ons | - | $3,423 | 6% |
| **Total MRR** | | **$55,300** | **100%** |

Enterprise drives the growth story. Self-serve tiers serve as the pipeline and validation mechanism.

---

## P&L — Month 12

| Line Item | Monthly |
|---|---|
| **Revenue** | |
| Self-serve (Pro + Team) | $2,893 |
| Enterprise (3 x $3,000) | $9,000 |
| Expansion add-ons | $2,620 |
| **Total Revenue** | **$14,513** |
| | |
| **Cost of Revenue (Variable)** | |
| LLM detection costs | -$280 |
| Stripe fees (2.9% + $0.30) | -$440 |
| **Total COGS** | **-$720** |
| **Gross Profit** | **$13,793** |
| **Gross Margin** | **95%** |
| | |
| **Operating Expenses (Fixed)** | |
| Fly.io backend | -$75 |
| PostgreSQL | -$60 |
| Redis | -$15 |
| Vercel | -$20 |
| Domain + email | -$15 |
| **Total Infra** | **-$185** |
| | |
| **Net Operating Income** | **$13,608** |
| **Operating Margin** | **94%** |

### P&L — Month 24

| Line Item | Monthly |
|---|---|
| **Revenue** | |
| Self-serve (Pro + Team) | $6,877 |
| Enterprise (15 x $3,000) | $45,000 |
| Expansion add-ons | $3,423 |
| **Total Revenue** | **$55,300** |
| | |
| **Cost of Revenue** | |
| LLM detection costs | -$3,200 |
| Stripe fees | -$1,650 |
| **Total COGS** | **-$4,850** |
| **Gross Profit** | **$50,450** |
| **Gross Margin** | **91%** |
| | |
| **Operating Expenses** | |
| Fly.io backend (2 machines) | -$150 |
| PostgreSQL (scaled) | -$120 |
| Redis | -$30 |
| Vercel | -$20 |
| Domain + email | -$15 |
| Support tooling | -$50 |
| **Total Infra** | **-$385** |
| | |
| **Net Operating Income** | **$50,065** |
| **Operating Margin** | **91%** |

---

## Unit Economics

### Pro Plan ($29/mo)

| Metric | Value |
|---|---|
| Monthly revenue | $29 |
| LLM cost (1,500 traces x $0.004) | -$6 |
| Stripe fee | -$1.14 |
| Infra allocation | -$1 |
| **Contribution margin** | **$20.86 (72%)** |
| Expected lifetime (1/0.06 churn) | 16.7 months |
| **LTV** | **$348** |

### Team Plan ($79/mo)

| Metric | Value |
|---|---|
| Monthly revenue | $79 |
| LLM cost (4,500 traces x $0.004) | -$18 |
| Stripe fee | -$2.59 |
| Infra allocation | -$3 |
| **Contribution margin** | **$55.41 (70%)** |
| Expected lifetime | 16.7 months |
| **LTV** | **$925** |

### Enterprise ($3,000/mo avg)

| Metric | Value |
|---|---|
| Monthly revenue | $3,000 |
| LLM cost (30,000 traces x $0.004) | -$120 |
| Stripe/invoice fee | -$87 |
| Dedicated infra allocation | -$50 |
| **Contribution margin** | **$2,743 (91%)** |
| Expected lifetime | 24+ months |
| **LTV** | **$65,832** |

### CAC Targets (3:1 LTV:CAC)

| Plan | LTV | Target CAC | Acquisition strategy |
|---|---|---|---|
| Pro | $348 | $116 | Organic, content, community |
| Team | $925 | $308 | Content + targeted outreach |
| Enterprise | $65,832 | $21,944 | Sales-assisted, design partners |

Pro/Team: Must stay organic (content, SEO, community). CAC budget ~$100 supports conference talks, community sponsorships — not paid ads.

Enterprise: CAC budget of $22K supports a part-time sales hire or outbound contractor.

---

## Expansion Revenue Model

Add-ons beyond flat project pricing (available to Pro and Team):

| Add-on | Price | Target penetration | Monthly impact |
|---|---|---|---|
| Extra projects ($9/project/mo) | $9/project | 25% of Pro users avg 1 extra | +$65/month per 100 Pro users |
| Detection reports (shareable links) | $5/mo | 15% of all paid | +$7.50/month per 100 paid |
| Priority detection (LLM on all traces) | $19/mo | 10% of Pro/Team | +$19/month per 100 paid |
| **Blended ARPU uplift** | | | **~15%** |

---

## Scenario Analysis

### Month 12

| Scenario | Active Paid | Enterprise | MRR | ARR |
|---|---|---|---|---|
| Conservative (60%) | 42 | 2 | $9,375 | $112K |
| **Base case** | **70** | **3** | **$14,513** | **$174K** |
| Optimistic (1.5x) | 105 | 5 | $24,020 | $288K |

### Month 24

| Scenario | Active Paid | Enterprise | MRR | ARR |
|---|---|---|---|---|
| Conservative (60%) | 107 | 9 | $35,300 | $424K |
| **Base case** | **178** | **15** | **$55,300** | **$664K** |
| Optimistic (1.5x) | 267 | 23 | $86,200 | $1.03M |

---

## Key Milestones

| Milestone | Timeline | Significance |
|---|---|---|
| First paying customer | Month 1-2 | Product-market validation |
| $1K MRR | Month 5 | Infra costs covered 5x over |
| $5K MRR | Month 7 | Ramen profitable |
| $10K MRR | Month 10 | Sustainable solo business |
| $100K ARR | Month 9 | Seed-fundable |
| $15K MRR | Month 12 | Can justify first hire |
| $30K MRR | Month 17 | First full-time employee |
| $50K MRR | Month 23 | Small team sustainable |
| $500K ARR | Month 21 | Series A territory |
| $55K MRR | Month 24 | Team of 3-4 supported |

---

## Break-Even Analysis

| Expense Level | Monthly Cost | Covered At | Timeline |
|---|---|---|---|
| Infrastructure only | $185 | 7 Pro users | Month 2 |
| Infra + founder ($5K/mo) | $5,185 | Month 7 MRR | Month 7 |
| Infra + founder + 1 hire ($12K/mo) | $12,185 | Month 12 MRR | Month 12 |
| Infra + 3 team ($25K/mo) | $25,185 | Month 17 MRR | Month 17 |

Infrastructure break-even happens almost immediately. Founder sustainability reached by month 7. First hire supportable by end of year 1.

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| No enterprise deals | -81% of month 24 MRR | Medium | PLG pipeline from free/pro, design partners |
| Lower conversion (3%) | -40% paid users | Medium | Better onboarding, time-to-value <5 min |
| Higher churn (10%) | -40% shorter LTV | Medium | Annual billing push, usage reports |
| LLM cost spike | Margin compression | Low | Tiered escalation, more Tier 1-2 detection |
| Competitor free tier | Slower free growth | Medium | Differentiate on fixes, not price |

**Sensitivity: Without enterprise**, month 24 self-serve MRR is ~$10,300 ($124K ARR). Still viable as a solo/lifestyle business, but much slower path to $500K ARR.

---

## Summary

| Metric | Month 12 | Month 24 |
|---|---|---|
| Free users (cumulative) | 1,691 | 5,962 |
| Paid customers | 73 | 193 |
| MRR | $14,513 | $55,300 |
| ARR | $174,156 | $663,600 |
| Gross margin | 95% | 91% |
| Operating margin | 94% | 91% |
| Cumulative revenue | $63,000 | $501,000 |
| Infra break-even | Month 2 | - |
| Founder sustainability | Month 7 | - |
| $500K ARR | - | Month 21 |
