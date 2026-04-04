# Pisama Synthetic Customer Agents

Autonomous agents that create their own accounts and exercise the Pisama platform as real customers would.

## Usage

```bash
pip install -e .

# List available agents
pisama-synth list

# Run all agents against local backend
pisama-synth run --target http://localhost:8000

# Run specific agents
pisama-synth run --target http://localhost:8000 --agents ava,diego

# Reuse tenant accounts across runs
pisama-synth run --target http://localhost:8000 --reuse-tenants

# Cleanup old synth tenants
pisama-synth cleanup --target http://localhost:8000
```

## Agents

| Agent | Persona | What it tests |
|-------|---------|---------------|
| Ava | LangGraph team lead | Core ingest/detect/query pipeline |
| Bram | SDK integrator | PisamaEvaluator client, check() |
| Clara | Self-healing enthusiast | Full healing state machine |
| Diego | Evaluator power user | /evaluate with all role/detector combos |
| Elin | Multi-framework migrator | Framework auto-detection (CrewAI, Bedrock, Anthropic) |
