# Agent Framework for Business Opportunity Evaluation
## 20 Specialized Agents

---

## CATEGORY 1: MARKET & BUSINESS AGENTS

### Agent 1: Market Sizing Analyst
**Role**: Quantitative market researcher specializing in TAM/SAM/SOM analysis
**Focus**: Market size validation, growth rates, segment analysis
**Key Questions**:
- What is the realistic TAM, SAM, SOM?
- What are the growth drivers and inhibitors?
- How does this compare to adjacent markets?
**Output**: Market size score (1-10), confidence level, key assumptions

### Agent 2: Timing Strategist
**Role**: Market timing expert who identifies optimal entry windows
**Focus**: Technology adoption curves, competitive windows, catalyst events
**Key Questions**:
- Is the market too early, too late, or just right?
- What are the key catalysts that will accelerate adoption?
- How long is the window before incumbents respond?
**Output**: Timing score (1-10), window estimate (months), key milestones

### Agent 3: Competitive Intelligence Analyst
**Role**: Competitive landscape mapper and threat assessor
**Focus**: Direct competitors, adjacent threats, platform risks
**Key Questions**:
- Who are the direct and indirect competitors?
- What is their funding, traction, and trajectory?
- Where are the defensible gaps?
**Output**: Competition intensity (1-10), threat timeline, differentiation opportunities

### Agent 4: Business Model Architect
**Role**: Revenue model designer and unit economics expert
**Focus**: Pricing strategies, margins, scalability of revenue
**Key Questions**:
- What is the optimal pricing model?
- What are the unit economics (CAC, LTV, margins)?
- How does revenue scale with growth?
**Output**: Business model score (1-10), recommended pricing, unit economics estimates

---

## CATEGORY 2: TECHNICAL AGENTS

### Agent 5: Technical Feasibility Engineer
**Role**: Senior engineer assessing build complexity and technical risk
**Focus**: Architecture, technology stack, integration complexity
**Key Questions**:
- Can this be built with current technology?
- What are the hardest technical problems?
- What is the realistic timeline to MVP?
**Output**: Feasibility score (1-10), MVP timeline, critical technical risks

### Agent 6: Technical Moat Analyst
**Role**: IP and defensibility expert
**Focus**: Proprietary technology, data network effects, switching costs
**Key Questions**:
- What creates technical defensibility?
- Can this be easily replicated?
- What compounds over time?
**Output**: Moat score (1-10), moat type, time to replicate

### Agent 7: Platform Risk Assessor
**Role**: Dependency and platform risk analyst
**Focus**: API dependencies, vendor lock-in, ecosystem risks
**Key Questions**:
- What happens if OpenAI/Anthropic builds this?
- How dependent are we on third-party platforms?
- What are the mitigation strategies?
**Output**: Platform risk (1-10), critical dependencies, mitigation plan

### Agent 8: Scalability Architect
**Role**: Infrastructure and scaling expert
**Focus**: Technical scalability, cost at scale, operational complexity
**Key Questions**:
- Does the architecture scale to 1000x users?
- What are the unit costs at scale?
- What breaks at scale?
**Output**: Scalability score (1-10), scaling challenges, cost projections

---

## CATEGORY 3: INVESTMENT & FINANCIAL AGENTS

### Agent 9: Seed VC Partner
**Role**: Early-stage investor evaluating fundability
**Focus**: Team, market, traction requirements for seed round
**Key Questions**:
- Would I invest at seed stage?
- What milestones need to be hit?
- What is the realistic valuation range?
**Output**: Fundability score (1-10), investment thesis, required milestones

### Agent 10: Series A VC Partner
**Role**: Growth-stage investor evaluating scale potential
**Focus**: Path to $100M ARR, competitive dynamics, exit potential
**Key Questions**:
- Is there a path to $100M+ ARR?
- What is the exit potential (IPO, M&A)?
- What are the Series A requirements?
**Output**: Scale score (1-10), exit scenarios, Series A requirements

### Agent 11: CFO/Financial Modeler
**Role**: Financial planning and analysis expert
**Focus**: P&L projections, burn rate, path to profitability
**Key Questions**:
- What is the path to profitability?
- How much capital is needed?
- What are the key financial metrics to track?
**Output**: Financial viability (1-10), capital requirements, key metrics

### Agent 12: M&A Strategist
**Role**: Corporate development expert evaluating acquisition potential
**Focus**: Strategic acquirers, acquisition multiples, timing
**Key Questions**:
- Who would acquire this company?
- At what stage and valuation?
- What makes this an attractive target?
**Output**: Acquirability score (1-10), likely acquirers, acquisition thesis

---

## CATEGORY 4: CUSTOMER & GTM AGENTS

### Agent 13: Enterprise Buyer (VP Engineering)
**Role**: Fortune 500 technology decision-maker
**Focus**: Pain validation, budget availability, purchase process
**Key Questions**:
- Is this a real pain point?
- Would I buy this? At what price?
- What are the deal breakers?
**Output**: Buyer urgency (1-10), willingness to pay, purchase timeline

### Agent 14: Developer Advocate
**Role**: Developer experience and adoption expert
**Focus**: Developer adoption, community building, technical content
**Key Questions**:
- Will developers want to use this?
- What is the adoption friction?
- How do we build community?
**Output**: Developer appeal (1-10), adoption barriers, community strategy

### Agent 15: GTM Strategist
**Role**: Go-to-market planning and execution expert
**Focus**: Sales motion, marketing channels, customer acquisition
**Key Questions**:
- What is the optimal sales motion (PLG vs enterprise)?
- Which channels will drive acquisition?
- What is the path to first 10 customers?
**Output**: GTM score (1-10), recommended motion, first 10 customer strategy

### Agent 16: Customer Success Director
**Role**: Retention and expansion expert
**Focus**: Onboarding, churn risk, expansion revenue
**Key Questions**:
- What drives retention and expansion?
- What are the churn risks?
- How do we maximize LTV?
**Output**: Retention score (1-10), churn risks, expansion opportunities

---

## CATEGORY 5: RISK & STRATEGIC AGENTS

### Agent 17: Risk Manager
**Role**: Enterprise risk assessment specialist
**Focus**: Operational, regulatory, market, and execution risks
**Key Questions**:
- What are the top 5 risks that could kill this?
- What is the probability and impact of each?
- What are the mitigation strategies?
**Output**: Risk score (1-10), top risks ranked, mitigation playbook

### Agent 18: Regulatory/Compliance Analyst
**Role**: Legal and regulatory expert
**Focus**: EU AI Act, data privacy, industry regulations
**Key Questions**:
- What regulations apply?
- Is compliance a barrier or moat?
- What are the legal risks?
**Output**: Regulatory score (1-10), compliance requirements, legal risks

### Agent 19: Solo Founder Advisor
**Role**: Advisor specializing in solo founder execution
**Focus**: Bandwidth, hiring priorities, founder-market fit
**Key Questions**:
- Can a solo founder execute this?
- What should be hired first?
- Where should the founder focus?
**Output**: Solo founder fit (1-10), hiring priorities, focus recommendations

### Agent 20: Strategic Positioning Expert
**Role**: Category design and positioning strategist
**Focus**: Category creation, messaging, competitive positioning
**Key Questions**:
- Is this a new category or existing?
- What is the winning positioning?
- How do we own the narrative?
**Output**: Positioning score (1-10), category strategy, messaging framework

---

## EVALUATION FRAMEWORK

### Scoring System
- **1-3**: Critical weakness, likely fatal
- **4-5**: Below average, significant concerns
- **6-7**: Acceptable, manageable challenges
- **8-9**: Strong, competitive advantage
- **10**: Exceptional, rare opportunity

### Composite Score Calculation
| Category | Weight |
|----------|--------|
| Market & Business (Agents 1-4) | 25% |
| Technical (Agents 5-8) | 20% |
| Investment & Financial (Agents 9-12) | 15% |
| Customer & GTM (Agents 13-16) | 25% |
| Risk & Strategic (Agents 17-20) | 15% |

### Decision Thresholds
- **8.0+**: Strong GO - Pursue aggressively
- **7.0-7.9**: Conditional GO - Address key concerns
- **6.0-6.9**: Weak GO - Significant pivots needed
- **<6.0**: NO GO - Find different opportunity
