# Production n8n Workflows for MAO Testing

Three production workflows using **real APIs** to generate trace data for MAO failure detection testing.

## Workflows

| Workflow | Agents | Webhook | Primary Test Focus |
|----------|--------|---------|-------------------|
| HackerNews Comment Analyzer | 4 | `/hn-analyze` | Prompt Injection, Persona Drift |
| Multi-Source News Aggregator | 8 | `/news-aggregate` | Coordination Failures, Context Overflow |
| Real-Time Fact Checker | 6 | `/fact-check` | Hallucination, Information Withholding |

---

## 1. HackerNews Comment Analyzer

Fetches real HackerNews stories and comments, analyzes sentiment and safety.

### Flow
```
Webhook → Coordinator → Fetch HN API → Parse
                                         ↓
                         ┌───────────────┴───────────────┐
                         ↓                               ↓
                  Comment Analyzer              Safety Scanner
                         ↓                               ↓
                         └───────────────┬───────────────┘
                                         ↓
                                    Summarizer → Response
```

### Real APIs
- `https://hacker-news.firebaseio.com/v0/topstories.json`
- `https://hacker-news.firebaseio.com/v0/item/{id}.json`

### Test Examples

```bash
# Basic analysis
curl -X POST https://pisama.app.n8n.cloud/webhook/hn-analyze \
  -H "Content-Type: application/json" \
  -d '{"story_type": "top", "max_comments": 10}'

# With focus areas
curl -X POST https://pisama.app.n8n.cloud/webhook/hn-analyze \
  -H "Content-Type: application/json" \
  -d '{
    "story_type": "top",
    "max_comments": 20,
    "focus_areas": ["sentiment", "toxicity", "technical_accuracy"]
  }'
```

### MAO Failure Modes Tested
- **Prompt Injection**: HN comments may contain malicious prompts
- **Persona Drift**: Safety Scanner tone changes over time
- **Task Derailment**: Malicious comments derail agents
- **Information Withholding**: Skipping controversial comments

---

## 2. Multi-Source News Aggregator

Aggregates tech news from HackerNews, Reddit, and RSS feeds with deduplication.

### Flow
```
Webhook → Orchestrator
              ↓
    ┌─────────┼─────────┬─────────┐
    ↓         ↓         ↓         ↓
  HN API   Reddit    RSS Feed   (parallel)
    ↓         ↓         ↓         ↓
  HN Agent Reddit Agt RSS Agent  (parallel)
    ↓         ↓         ↓         ↓
    └─────────┴────┬────┴─────────┘
                   ↓
             Deduplicator → Synthesizer → Quality Reviewer → Response
```

### Real APIs
- HackerNews: `https://hacker-news.firebaseio.com/v0/topstories.json`
- Reddit: `https://www.reddit.com/r/technology/top.json`
- RSS: Ars Technica tech feed

### Test Examples

```bash
# Default aggregation
curl -X POST https://pisama.app.n8n.cloud/webhook/news-aggregate \
  -H "Content-Type: application/json" \
  -d '{"sources": ["hackernews", "reddit"]}'

# Full aggregation with categories
curl -X POST https://pisama.app.n8n.cloud/webhook/news-aggregate \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["hackernews", "reddit", "rss"],
    "time_range": "24h",
    "max_stories_per_source": 10,
    "categories": ["AI", "programming", "startups"]
  }'
```

### MAO Failure Modes Tested
- **Coordination Failure**: 3-way parallel merge issues
- **Circular Delegation**: Deduplicator → Specialists loop
- **Context Overflow**: 8 agents + all source data
- **State Corruption**: Schema mismatches between sources
- **Hallucination**: Synthesizer inventing stories not in sources

---

## 3. Real-Time Fact Checker

Extracts claims from content and verifies against Wikipedia and DuckDuckGo.

### Flow
```
Webhook → Claim Extractor → Query Generator → Split by Claim
                                                    ↓
                                    ┌───────────────┴───────────────┐
                                    ↓                               ↓
                                Wikipedia API              DuckDuckGo API
                                    ↓                               ↓
                                    └───────────────┬───────────────┘
                                                    ↓
                                          Verification Agent
                                                    ↓
                                        Cross-Reference Agent
                                                    ↓
                                        Report Generator → Response
```

### Real APIs
- Wikipedia: `https://en.wikipedia.org/api/rest_v1/page/summary/{title}`
- DuckDuckGo: `https://api.duckduckgo.com/?q={query}&format=json`

### Test Examples

```bash
# Basic fact check
curl -X POST https://pisama.app.n8n.cloud/webhook/fact-check \
  -H "Content-Type: application/json" \
  -d '{"content": "Python is the most popular programming language with 50% market share."}'

# Multiple claims
curl -X POST https://pisama.app.n8n.cloud/webhook/fact-check \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Python became the most popular language in 2025 with over 50% market share. The average developer salary in the US is now $250,000. GPT-5 achieved human-level reasoning.",
    "verification_depth": "thorough",
    "require_citations": true
  }'

# Testing with potentially false claims
curl -X POST https://pisama.app.n8n.cloud/webhook/fact-check \
  -H "Content-Type: application/json" \
  -d '{
    "content": "The Eiffel Tower is located in London and was built in 1920."
  }'
```

### MAO Failure Modes Tested
- **Hallucination**: Primary focus - citing non-existent sources
- **Information Withholding**: Ignoring contradictory evidence
- **Prompt Injection**: Malicious content in input
- **Context Overflow**: Many claims with multiple sources each
- **Task Derailment**: Agent opinions instead of verification

---

## Failure Mode Coverage Matrix

| Failure Mode | HN Analyzer | News Aggregator | Fact Checker |
|--------------|-------------|-----------------|--------------|
| Loop Detection | - | Dedup loops | Verify cycles |
| State Corruption | - | Schema mismatch | Claim mixing |
| Persona Drift | Safety Scanner | - | - |
| Coordination | Parallel merge | 3-way merge | - |
| Hallucination | - | Synthesizer | **Primary** |
| Prompt Injection | **Primary** | Reddit UGC | Input content |
| Context Overflow | - | 8 agents | Many claims |
| Task Derailment | Malicious comments | - | Opinions |
| Info Withholding | Skip comments | Missing sources | **Primary** |

---

## Setup

### 1. Import Workflows

Workflows are auto-uploaded to n8n cloud. To manually import:

```bash
# Using n8n API
curl -X POST "https://pisama.app.n8n.cloud/api/v1/workflows" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @hn-analyzer.json
```

### 2. Configure Credentials

Anthropic API credentials are pre-configured. To update:

1. Go to n8n → Settings → Credentials
2. Update "Anthropic API" with your key

### 3. Environment Variables

Set in n8n environment:
```bash
MAO_WEBHOOK_URL=http://localhost:8000/api/v1/n8n/webhook
MAO_API_KEY=your-tenant-key
```

---

## Verifying MAO Integration

After running workflows, check MAO received traces:

```bash
# Check latest traces
psql $DATABASE_URL -c "
SELECT id, session_id, framework, status, created_at
FROM traces
WHERE framework = 'n8n'
ORDER BY created_at DESC
LIMIT 5;
"

# Check detections for a trace
psql $DATABASE_URL -c "
SELECT detection_type, confidence, severity, details
FROM detections
WHERE trace_id = '<trace-id>'
ORDER BY confidence DESC;
"
```

---

## API Rate Limits

| API | Rate Limit | Notes |
|-----|------------|-------|
| HackerNews | ~30 req/sec | Very generous |
| Reddit | 60 req/min | Requires User-Agent header |
| Wikipedia | 200 req/sec | Generous |
| DuckDuckGo | Undocumented | Be respectful |

---

## Cost Estimation (Claude 3.5 Haiku)

| Workflow | Est. Tokens | Est. Cost |
|----------|-------------|-----------|
| HN Analyzer | ~1,500 | $0.002 |
| News Aggregator | ~4,000 | $0.006 |
| Fact Checker | ~3,000 | $0.004 |

---

## Troubleshooting

### Workflow not triggering
- Verify webhook is active in n8n
- Check URL path matches (`/hn-analyze`, `/news-aggregate`, `/fact-check`)
- Ensure Content-Type is `application/json`

### API errors
- Reddit: Ensure User-Agent header is set
- Wikipedia: Check article title encoding
- HackerNews: Story IDs change frequently

### MAO webhook failing
- Verify MAO backend is running
- Check MAO_API_KEY is set
- Review MAO backend logs

### No detections in MAO
- Workflows may not trigger all failure modes every run
- Try running multiple times
- Check trace data format in MAO ingestion logs
