# n8n-nodes-claude-thinking

A community node for n8n that enables extended thinking capture from Claude AI models, designed for integration with [PISAMA](https://pisama.ai) - the Multi-Agent Orchestration Testing Platform.

## 🚀 Features

- **Extended Thinking Capture**: Captures Claude's internal reasoning process alongside the final response
- **Multiple Claude Models**: Support for Sonnet 4.5, Opus 4.5, Sonnet 3.7, and Haiku 3.5
- **Configurable Thinking Budget**: Control how many tokens Claude can use for reasoning (1,024-32,000)
- **Full Parameter Control**: Temperature, max tokens, system prompts
- **PISAMA-Ready Output**: Structured output format ready for PISAMA webhook ingestion
- **Secure Credentials**: API key stored securely using n8n's credential system

## 📦 Installation

### Community Installation (Recommended)

Install directly in n8n:

1. Go to **Settings** > **Community Nodes**
2. Click **Install**
3. Search for `n8n-nodes-claude-thinking`
4. Click **Install**

### Manual Installation

```bash
cd ~/.n8n/nodes
npm install n8n-nodes-claude-thinking
```

For Docker installations:

```bash
docker exec -u node <container-name> npm install -g n8n-nodes-claude-thinking
```

## 🔧 Setup

1. **Add Credentials**:
   - Go to **Credentials** > **New**
   - Select **Claude API**
   - Enter your Anthropic API key (get one at [console.anthropic.com](https://console.anthropic.com))

2. **Add Node to Workflow**:
   - Search for "Claude (Extended Thinking)" in the node palette
   - Drag it into your workflow

3. **Configure Parameters**:
   - **Model**: Choose your Claude model
   - **Prompt**: Your user message
   - **System Prompt** (optional): System instructions
   - **Enable Extended Thinking**: Toggle to capture reasoning
   - **Thinking Budget**: Max tokens for reasoning (default: 10,000)

## 📊 Output Structure

The node outputs structured data compatible with PISAMA:

```json
{
  "thinking": "Claude's internal reasoning process...",
  "content": "The final response to the user",
  "model": "claude-sonnet-4-5-20250514",
  "usage": {
    "input_tokens": 150,
    "output_tokens": 2500
  },
  "stop_reason": "end_turn",
  "execution_time_ms": 3421
}
```

## 🔗 Integration with PISAMA

This node is designed to work seamlessly with PISAMA's failure detection system:

1. **Add PISAMA Webhook**: After the Claude Thinking node, add an HTTP Request node to send data to your PISAMA webhook
2. **Automatic Ingestion**: PISAMA will automatically extract the `thinking` field and store it as reasoning data
3. **Advanced Analysis**: PISAMA can now analyze both the final output AND the internal reasoning for failure detection

### Example Workflow

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐
│  Trigger    │───▶│ Claude Thinking  │───▶│ HTTP Request│
│             │    │ (Extended)       │    │ (PISAMA)    │
└─────────────┘    └──────────────────┘    └─────────────┘
```

## 🎯 Use Cases

- **Agent Failure Detection**: Capture reasoning to detect hallucinations, loops, and persona drift
- **Quality Assurance**: Verify agent decision-making processes
- **Debugging**: Understand why an agent made specific choices
- **Audit Trails**: Maintain complete records of AI reasoning for compliance

## ⚙️ Configuration

### Model Selection

| Model | Best For |
|-------|----------|
| **Sonnet 4.5** | Balanced performance and cost |
| **Opus 4.5** | Complex reasoning tasks |
| **Sonnet 3.7** | Fast, cost-effective |
| **Haiku 3.5** | Simple tasks, lowest cost |

### Thinking Budget

- **Low (1,024-5,000)**: Quick reasoning tasks
- **Medium (5,000-15,000)**: Standard agentic workflows
- **High (15,000-32,000)**: Complex multi-step reasoning

## 📝 Example

```typescript
// Input
{
  "prompt": "Analyze this sales data and recommend optimizations",
  "systemPrompt": "You are a data analyst. Think carefully before responding.",
  "extendedThinking": true,
  "thinkingBudget": 10000
}

// Output
{
  "thinking": "First, I'll examine the data structure... The sales trend shows... Based on this analysis, I should recommend...",
  "content": "Based on the sales data, I recommend: 1. Focus on Q3 products...",
  "model": "claude-sonnet-4-5-20250514",
  "usage": { "input_tokens": 245, "output_tokens": 1823 }
}
```

## 🐛 Troubleshooting

### "API key invalid"
- Verify your API key starts with `sk-ant-`
- Check it's entered correctly in credentials

### "Thinking not captured"
- Ensure "Enable Extended Thinking" is checked
- Verify you're using a compatible Claude model (3.7+)

### "Token limit exceeded"
- Reduce thinking budget or max tokens
- Use a model with larger context window

## 📚 Resources

- [PISAMA Documentation](https://docs.pisama.ai)
- [Anthropic API Docs](https://docs.anthropic.com)
- [n8n Community](https://community.n8n.io)

## 📄 License

MIT

## 🤝 Contributing

Issues and PRs welcome at [github.com/pisama/n8n-nodes-claude-thinking](https://github.com/pisama/n8n-nodes-claude-thinking)

## 💬 Support

- PISAMA Support: support@pisama.ai
- GitHub Issues: Report bugs or request features
