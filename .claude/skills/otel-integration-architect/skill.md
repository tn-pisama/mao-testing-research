---
name: otel-integration-architect
description: |
  Designs OpenTelemetry integrations for PISAMA platform.
  Use when adding OTEL ingestion, GenAI semantic conventions, or trace parsing.
  Ensures OTLP/HTTP and OTLP/gRPC support with backward compatibility.
allowed-tools: Read, Grep, Glob, Write
---

# OTEL Integration Architect Skill

You are designing OpenTelemetry integrations for the PISAMA platform. Your goal is to ensure OTEL-native compatibility while maintaining backward compatibility with existing APIs.

## Core Principles

### 1. OTEL-First Design
- All new trace ingestion MUST support OTLP (HTTP and gRPC)
- GenAI semantic conventions are mandatory (gen_ai.* namespace)
- Support both protobuf and JSON encoding
- Maintain W3C Trace Context for propagation

### 2. GenAI Semantic Conventions (Priority Order)

**Tier 1 - Must Have:**
| Attribute | Purpose |
|-----------|---------|
| `gen_ai.agent.id` | Agent identification |
| `gen_ai.agent.name` | Agent name |
| `gen_ai.operation.name` | chat/invoke_agent/execute_tool |
| `gen_ai.request.model` | Model used |
| `gen_ai.usage.input_tokens` | Token count |
| `gen_ai.usage.output_tokens` | Token count |
| `gen_ai.tool.name` | Tool being called |
| `gen_ai.tool.call.id` | Tool call identifier |

**Tier 2 - Should Have:**
| Attribute | Purpose |
|-----------|---------|
| `gen_ai.provider.name` | openai/anthropic/aws.bedrock |
| `gen_ai.response.finish_reasons` | stop/length/tool_calls |
| `gen_ai.input.messages` | Full message history |
| `gen_ai.output.messages` | Full response |
| `gen_ai.system_instructions` | System prompt |

### 3. Backward Compatibility
- Keep existing `/api/v1/traces/ingest` endpoint
- Add `/v1/traces` as standard OTLP endpoint
- Both converge to UniversalTrace format

## Architecture Template

```
OTLP Endpoints → Parser → GenAI Mapper → Detection Pipeline
     ↓
Legacy API → Existing Parser → ─────────────────┘
```

## Review Checklist

When reviewing OTEL integration changes:

- [ ] OTLP/HTTP endpoint at `/v1/traces`
- [ ] Protobuf and JSON encoding supported
- [ ] GenAI Tier 1 attributes mapped
- [ ] Backward compatible with existing SDK
- [ ] Content-Type negotiation correct
- [ ] Authentication supports both OTEL headers and PISAMA API keys
- [ ] Performance: async parsing, batch writes
- [ ] Tests cover all attribute mappings

## Output Format

```
## OTEL Integration Review

### Compliance Check
- OTLP/HTTP: [PASS/FAIL]
- OTLP/gRPC: [PASS/FAIL/N/A]
- GenAI Conventions: [PASS/FAIL]
- Backward Compat: [PASS/FAIL]
- Performance: [PASS/FAIL]

### Issues Found
1. [CRITICAL/WARNING]: [Description]

### Recommendation
[APPROVE / REQUEST CHANGES]
```

---

## Resources

**OpenLLMetry** - https://github.com/traceloop/openllmetry
- Production-tested implementation of gen_ai.* semantic conventions
- Multi-provider support (OpenAI, Anthropic, Cohere, Bedrock, etc.)
- Vector DB instrumentation patterns (Pinecone, Chroma, Weaviate)
- Reference for validating PISAMA's OTEL instrumentation compatibility

**OTEL MCP Server** - https://github.com/traceloop/opentelemetry-mcp-server
- MCP server for querying OpenTelemetry traces (Jaeger, Tempo, Traceloop)
- Enables Claude to analyze distributed traces directly
- Specialized for LLM observability with gen_ai semantic conventions
- Optional integration for PISAMA CLI debugging workflows

**Claude Cookbooks - Observability** - https://github.com/anthropics/claude-cookbooks
- `observability/` folder with monitoring patterns for LLM applications
- `building_evals.ipynb` - Automated evaluation patterns
- `tool_use/` examples for tool integration best practices
