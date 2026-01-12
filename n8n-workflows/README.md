# n8n Agent Workflows for MAO Testing

Three operational n8n workflows that generate trace data with LLM inputs, reasoning, and outputs using **Claude 3.5 Haiku** (cheapest model).

## Workflows Created

1. **research-summarizer.json** - Single-agent workflow
2. **content-pipeline.json** - Multi-agent workflow (3 agents)
3. **research-team.json** - Complex multi-agent workflow (7 agents)

---

## Setup Instructions

### 1. Import Workflows into n8n

1. Open your n8n instance
2. Click "Add workflow" → "Import from File"
3. Import each JSON file:
   - `research-summarizer.json`
   - `content-pipeline.json`
   - `research-team.json`

### 2. Configure Credentials

Each workflow needs Anthropic API credentials:

1. In n8n, go to **Settings** → **Credentials**
2. Click "Add Credential" → "Anthropic API"
3. Enter your API key
4. Save as "Anthropic API" (this matches the credential name in workflows)

### 3. Set Environment Variables

Set these in your n8n environment:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# For MAO integration (optional if testing locally)
MAO_API_KEY=your-mao-tenant-api-key
MAO_WEBHOOK_URL=http://localhost:8000/api/v1/n8n/webhook
```

### 4. Activate Workflows

For each imported workflow:
1. Click the workflow name
2. Toggle "Active" to ON
3. Note the webhook URL shown

---

## Test Examples

### Workflow 1: Research Summarizer

**Webhook URL**: `http://your-n8n.com/webhook/research-summary`

**Example 1 - Brief Summary**:
```bash
curl -X POST http://your-n8n.com/webhook/research-summary \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "How do vector databases work?",
    "depth": "brief"
  }'
```

**Example 2 - Detailed Summary**:
```bash
curl -X POST http://your-n8n.com/webhook/research-summary \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Multi-agent AI testing challenges in production",
    "depth": "detailed"
  }'
```

**Example 3 - Technical Topic**:
```bash
curl -X POST http://your-n8n.com/webhook/research-summary \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "RAG pipeline optimization techniques",
    "depth": "detailed"
  }'
```

**Expected Response**:
```json
{
  "topic": "Multi-agent AI testing challenges in production",
  "depth": "detailed",
  "summary": "Research summary with reasoning...",
  "token_count": 450,
  "model": "claude-3-5-haiku-20241022",
  "timestamp": "2025-01-11T12:00:00Z",
  "execution_id": "uuid",
  "workflow_id": "uuid"
}
```

---

### Workflow 2: Content Pipeline

**Webhook URL**: `http://your-n8n.com/webhook/content-pipeline`

**Example 1 - Technical Blog**:
```bash
curl -X POST http://your-n8n.com/webhook/content-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Best practices for prompt engineering",
    "audience": "technical",
    "format": "blog"
  }'
```

**Example 2 - General Article**:
```bash
curl -X POST http://your-n8n.com/webhook/content-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "How AI is transforming healthcare",
    "audience": "general",
    "format": "article"
  }'
```

**Example 3 - Expert Report**:
```bash
curl -X POST http://your-n8n.com/webhook/content-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "LLM evaluation metrics and benchmarks",
    "audience": "expert",
    "format": "report"
  }'
```

**Expected Response**:
```json
{
  "topic": "Best practices for prompt engineering",
  "final_content": "Edited content...",
  "quality_score": 85,
  "changes_made": ["Fixed grammar", "Improved clarity"],
  "pipeline_stats": {
    "researcher_tokens": 320,
    "writer_tokens": 540,
    "editor_tokens": 280,
    "total_agents": 3
  },
  "timestamp": "2025-01-11T12:00:00Z"
}
```

---

### Workflow 3: Research Team

**Webhook URL**: `http://your-n8n.com/webhook/research-team`

**Example 1 - Production Challenges**:
```bash
curl -X POST http://your-n8n.com/webhook/research-team \
  -H "Content-Type: application/json" \
  -d '{
    "research_question": "What are the top 3 challenges in deploying multi-agent systems to production?",
    "timeline": "thorough",
    "domains": ["web", "academic", "data"]
  }'
```

**Example 2 - Technical Analysis**:
```bash
curl -X POST http://your-n8n.com/webhook/research-team \
  -H "Content-Type: application/json" \
  -d '{
    "research_question": "How effective are current LLM evaluation benchmarks?",
    "timeline": "normal",
    "domains": ["web", "academic", "data"]
  }'
```

**Example 3 - Urgent Research**:
```bash
curl -X POST http://your-n8n.com/webhook/research-team \
  -H "Content-Type: application/json" \
  -d '{
    "research_question": "What are the latest developments in retrieval-augmented generation?",
    "timeline": "urgent",
    "domains": ["web", "academic"]
  }'
```

**Example 4 - Business Strategy**:
```bash
curl -X POST http://your-n8n.com/webhook/research-team \
  -H "Content-Type: application/json" \
  -d '{
    "research_question": "What is the ROI of implementing AI observability tools?",
    "timeline": "thorough",
    "domains": ["web", "academic", "data"]
  }'
```

**Expected Response**:
```json
{
  "original_question": "What are the top 3 challenges...",
  "final_decision": "Decision maker response with confidence level...",
  "agents_completed": [
    "Coordinator",
    "Researcher 1 (Web)",
    "Researcher 2 (Academic)",
    "Researcher 3 (Data)",
    "Synthesizer",
    "Reviewer",
    "Decision Maker"
  ],
  "total_tokens": 1250,
  "total_agents": 7,
  "execution_id": "uuid",
  "timestamp": "2025-01-11T12:00:00Z"
}
```

---

## Using n8n MCP Tools

If you have n8n MCP configured, you can execute workflows programmatically:

```javascript
// Search for workflows
const workflows = await search_workflows({
  query: "Research",
  limit: 10
});

// Execute Research Summarizer
const result1 = await execute_workflow({
  workflowId: "<workflow-id-from-search>",
  inputs: {
    type: "webhook",
    webhookData: {
      method: "POST",
      body: {
        topic: "Vector embeddings in RAG systems",
        depth: "detailed"
      }
    }
  }
});

// Execute Content Pipeline
const result2 = await execute_workflow({
  workflowId: "<workflow-id>",
  inputs: {
    type: "webhook",
    webhookData: {
      method: "POST",
      body: {
        topic: "AI safety in production systems",
        audience: "technical",
        format: "blog"
      }
    }
  }
});

// Execute Research Team
const result3 = await execute_workflow({
  workflowId: "<workflow-id>",
  inputs: {
    type: "webhook",
    webhookData: {
      method: "POST",
      body: {
        research_question: "What are the best practices for LLM fine-tuning?",
        timeline: "normal",
        domains: ["web", "academic", "data"]
      }
    }
  }
});
```

---

## Verifying Trace Data in MAO

After executing workflows, check MAO database:

```bash
# Check latest traces
psql $DATABASE_URL -c "
SELECT id, session_id, framework, status, total_tokens, created_at
FROM traces
WHERE framework = 'n8n'
ORDER BY created_at DESC
LIMIT 5;
"

# Check states for a specific trace
psql $DATABASE_URL -c "
SELECT sequence_num, agent_id, token_count, latency_ms,
       substring(state_hash, 1, 16) as hash
FROM states
WHERE trace_id = '<trace-id>'
ORDER BY sequence_num;
"

# Verify AI nodes
psql $DATABASE_URL -c "
SELECT agent_id, token_count,
       state_delta->>'ai_model' as model,
       is_ai_node
FROM states
WHERE trace_id = '<trace-id>' AND token_count > 0;
"
```

---

## More Example Topics

### For Research Summarizer:
- "Explain transformer architecture for NLP"
- "Kubernetes security best practices"
- "Distributed tracing in microservices"
- "Graph neural networks applications"
- "Zero-shot learning techniques"

### For Content Pipeline:
- Topic: "Building reliable AI systems", Audience: "technical", Format: "blog"
- Topic: "Introduction to machine learning", Audience: "general", Format: "article"
- Topic: "State of AI in 2025", Audience: "expert", Format: "report"
- Topic: "Ethical considerations in AI deployment", Audience: "general", Format: "article"

### For Research Team:
- "How do companies measure AI model performance in production?"
- "What are the trade-offs between model accuracy and latency?"
- "What security risks exist in LLM-based applications?"
- "How effective is human-in-the-loop for AI quality assurance?"
- "What are the emerging standards for AI observability?"

---

## Cost Estimation

Using **Claude 3.5 Haiku** (cheapest model):
- Input: $0.25 per million tokens
- Output: $1.25 per million tokens

**Approximate costs per execution**:
- **Research Summarizer**: ~500 tokens = $0.001
- **Content Pipeline**: ~1,500 tokens (3 agents) = $0.002-0.003
- **Research Team**: ~2,500 tokens (7 agents) = $0.003-0.005

**Very affordable for testing and production use!**

---

## Troubleshooting

### Workflow not triggering
- Check webhook is active
- Verify URL is correct (check workflow settings)
- Ensure Content-Type header is application/json

### MAO webhook failing
- Verify MAO backend is running
- Check MAO_API_KEY is set correctly
- Confirm webhook URL is accessible from n8n

### Claude API errors
- Verify ANTHROPIC_API_KEY is valid
- Check API quota/rate limits
- Ensure credentials are properly configured in n8n

### No trace data in MAO
- Check n8n execution logs for errors
- Verify MAO webhook received the request
- Check MAO backend logs for parsing errors

---

## Next Steps

1. Import all 3 workflows into n8n
2. Configure Anthropic credentials
3. Test each workflow with the examples above
4. Check MAO database for trace data
5. Run MAO detection algorithms on the traces
6. Experiment with your own test cases!
