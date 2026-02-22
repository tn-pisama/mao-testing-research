"""Structured error codes for PISAMA quality dimensions.

Each error code follows the pattern QE-{DIM}-{NUM} where:
- QE = Quality Engine prefix
- DIM = Two-letter dimension abbreviation
- NUM = Three-digit error number

Error codes provide actionable context: severity, description,
remediation guidance, and documentation links.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ErrorCode:
    """A structured quality error code with remediation guidance."""

    code: str
    severity: str  # "critical", "high", "medium", "low"
    dimension: str
    description: str
    remediation: str
    doc_link: str = ""
    example_bad: str = ""
    example_good: str = ""
    quantified_target: str = ""

    def to_dict(self) -> dict:
        result = {
            "code": self.code,
            "severity": self.severity,
            "dimension": self.dimension,
            "description": self.description,
            "remediation": self.remediation,
            "doc_link": self.doc_link,
        }
        if self.example_bad:
            result["example_bad"] = self.example_bad
        if self.example_good:
            result["example_good"] = self.example_good
        if self.quantified_target:
            result["quantified_target"] = self.quantified_target
        return result


# ---------------------------------------------------------------------------
# Error code registry
# ---------------------------------------------------------------------------

_DOC_BASE = "/docs/quality/"  # Relative path for frontend to resolve

ERROR_CODES: Dict[str, ErrorCode] = {
    # ── Role Clarity (RC) ─────────────────────────────────────────────────
    "QE-RC-001": ErrorCode(
        code="QE-RC-001",
        severity="critical",
        dimension="role_clarity",
        description="No system prompt defined for the agent node.",
        remediation=(
            "Add a system prompt that clearly defines the agent's role, "
            "expected behaviour, and constraints. A missing system prompt "
            "means the agent has no guidance on how to respond."
        ),
        example_bad="(empty — no system prompt set)",
        example_good=(
            "You are a customer support triage agent. Classify incoming "
            "tickets by urgency (P0-P3) and route them to the correct team. "
            "Never promise resolution timelines. Always include the ticket ID "
            "in your response."
        ),
        quantified_target="50+ words covering role, task, constraints, and output format",
    ),
    "QE-RC-002": ErrorCode(
        code="QE-RC-002",
        severity="high",
        dimension="role_clarity",
        description="System prompt lacks role-definition keywords (e.g. 'You are', 'Act as', 'Your role').",
        remediation=(
            "Begin the system prompt with an explicit role statement such as "
            "'You are a data-extraction specialist...' to anchor the agent's "
            "identity and reduce persona drift."
        ),
        example_bad="Help the user with their request.",
        example_good=(
            "You are a contract review specialist. Your role is to identify "
            "non-standard clauses in B2B contracts and flag them by severity. "
            "Never give legal advice. Return results as a JSON array."
        ),
        quantified_target="Start with 'You are a...' and include explicit role, boundaries, and output format",
    ),
    "QE-RC-003": ErrorCode(
        code="QE-RC-003",
        severity="medium",
        dimension="role_clarity",
        description="No output format specified in the system prompt.",
        remediation=(
            "Define the expected output structure (JSON schema, bullet list, "
            "markdown table, etc.) so downstream nodes can reliably parse the "
            "agent's response."
        ),
        doc_link=f"{_DOC_BASE}QE-RC-003",
        example_bad="Analyze the customer feedback and share your thoughts.",
        example_good=(
            "Analyze the customer feedback and return a JSON object with keys: "
            '"sentiment" (positive/negative/neutral), "topics" (string array), '
            '"urgency" (1-5).'
        ),
        quantified_target="Explicit output format (JSON schema, markdown, or structured template) in every agent prompt",
    ),
    "QE-RC-004": ErrorCode(
        code="QE-RC-004",
        severity="medium",
        dimension="role_clarity",
        description="No boundary constraints defined in the system prompt.",
        remediation=(
            "Add explicit boundaries such as 'Do not make up data', "
            "'Only answer questions about X', or 'Refuse requests outside "
            "your domain' to prevent scope creep and hallucination."
        ),
        doc_link=f"{_DOC_BASE}QE-RC-004",
        example_bad="You are a helpful assistant. Answer any question the user asks.",
        example_good=(
            "You are an invoice processing agent. Only extract data from invoices. "
            "Do not answer general questions. Never fabricate amounts or dates. "
            "If a field is missing, return null instead of guessing."
        ),
        quantified_target="At least 2 boundary constraints (e.g. 'do not', 'only', 'never') per agent prompt",
    ),
    "QE-RC-005": ErrorCode(
        code="QE-RC-005",
        severity="low",
        dimension="role_clarity",
        description="System prompt is too brief (fewer than 50 characters).",
        remediation=(
            "Expand the system prompt to include role definition, output "
            "format, boundary constraints, and examples. Very short prompts "
            "leave too much ambiguity for the model."
        ),
        example_bad="Summarize the input.",
        example_good=(
            "You are an executive summary writer. Given a document, produce "
            "a 3-paragraph summary: key findings, recommendations, and next "
            "steps. Use bullet points for recommendations. Keep the summary "
            "under 300 words."
        ),
        quantified_target="50+ words with sections for role, output format, constraints, and examples",
    ),

    # ── Output Consistency (OC) ───────────────────────────────────────────
    "QE-OC-001": ErrorCode(
        code="QE-OC-001",
        severity="low",
        dimension="output_consistency",
        description="No execution history available for output consistency analysis.",
        remediation=(
            "Run the workflow at least 3-5 times and supply execution "
            "history so PISAMA can detect structural inconsistencies across "
            "runs."
        ),
        example_bad="(no executions — score is provisional)",
        example_good="5+ executions with consistent JSON output structure across runs",
        quantified_target="3-5 executions minimum for a verified output consistency score",
    ),
    "QE-OC-002": ErrorCode(
        code="QE-OC-002",
        severity="high",
        dimension="output_consistency",
        description="Inconsistent output structures detected across executions.",
        remediation=(
            "Enforce a strict output schema in the system prompt and "
            "consider adding a JSON-mode or structured-output setting. "
            "Validate outputs with a downstream schema-check node."
        ),
        doc_link=f"{_DOC_BASE}QE-OC-002",
        example_bad=(
            'Run 1: { "result": "approved" }\n'
            'Run 2: "The request is approved"\n'
            'Run 3: { "status": "approved", "reason": "..." }'
        ),
        example_good=(
            'Run 1: { "status": "approved", "confidence": 0.95 }\n'
            'Run 2: { "status": "rejected", "confidence": 0.87 }\n'
            'Run 3: { "status": "approved", "confidence": 0.91 }'
        ),
        quantified_target="100% structural consistency across runs (same keys, same types)",
    ),
    "QE-OC-003": ErrorCode(
        code="QE-OC-003",
        severity="medium",
        dimension="output_consistency",
        description="No JSON format specified for structured output agents.",
        remediation=(
            "When the agent is expected to produce structured data, enable "
            "JSON mode (responseFormat: json_object) or include an explicit "
            "JSON schema in the system prompt."
        ),
        doc_link=f"{_DOC_BASE}QE-OC-003",
        example_bad='{ "responseFormat": "text" }  // free-form text output from a data extraction agent',
        example_good=(
            '{ "responseFormat": "json_object" }\n'
            '// System prompt includes: "Return JSON matching schema: '
            '{ status: string, items: array, total: number }"'
        ),
        quantified_target="All data-producing agents must use responseFormat: json_object or equivalent",
    ),

    # ── Error Handling (EH) ───────────────────────────────────────────────
    "QE-EH-001": ErrorCode(
        code="QE-EH-001",
        severity="high",
        dimension="error_handling",
        description="No retry configuration set on the agent node.",
        remediation=(
            "Enable retries with exponential backoff (e.g. maxTries: 3, "
            "waitBetweenTries: 1000) to handle transient LLM API failures "
            "gracefully."
        ),
        example_bad='{ "retryOnFail": false }',
        example_good='{ "retryOnFail": true, "maxTries": 3, "waitBetweenTries": 1000 }',
        quantified_target="maxTries >= 2 with waitBetweenTries >= 500ms",
    ),
    "QE-EH-002": ErrorCode(
        code="QE-EH-002",
        severity="high",
        dimension="error_handling",
        description="No timeout configured for the agent node.",
        remediation=(
            "Set a request timeout (e.g. 30-120 seconds) to prevent the "
            "workflow from hanging indefinitely when the LLM provider is "
            "slow or unresponsive."
        ),
        doc_link=f"{_DOC_BASE}QE-EH-002",
        example_bad='{ "timeout": 0 }  // no timeout — request can hang forever',
        example_good='{ "timeout": 60000 }  // 60-second timeout with graceful error handling',
        quantified_target="Timeout between 30s and 120s depending on expected response complexity",
    ),
    "QE-EH-003": ErrorCode(
        code="QE-EH-003",
        severity="medium",
        dimension="error_handling",
        description="continueOnFail is not enabled on this node.",
        remediation=(
            "Enable continueOnFail if downstream nodes can handle partial "
            "failures, or add an error-output branch so the workflow can "
            "degrade gracefully instead of stopping."
        ),
        doc_link=f"{_DOC_BASE}QE-EH-003",
        example_bad='{ "continueOnFail": false }  // workflow stops on any error',
        example_good='{ "continueOnFail": true }  // downstream nodes receive error info and handle gracefully',
        quantified_target="continueOnFail=true on all non-critical nodes; false only for validators",
    ),
    "QE-EH-004": ErrorCode(
        code="QE-EH-004",
        severity="medium",
        dimension="error_handling",
        description="No error output paths connected to this node.",
        remediation=(
            "Connect an error output branch that logs the failure, sends "
            "an alert, or triggers a fallback path. Unhandled errors cause "
            "silent workflow failures."
        ),
        doc_link=f"{_DOC_BASE}QE-EH-004",
        example_bad="Agent Node -> (no error output connected)",
        example_good=(
            "Agent Node -> [error output] -> Send Slack Alert\n"
            "Agent Node -> [error output] -> Log to Database"
        ),
        quantified_target="Every agent node must have at least one error output path connected",
    ),

    # ── Tool Usage (TU) ──────────────────────────────────────────────────
    "QE-TU-001": ErrorCode(
        code="QE-TU-001",
        severity="low",
        dimension="tool_usage",
        description="No tools defined for this agent node.",
        remediation=(
            "If the agent needs to interact with external systems, define "
            "tool nodes (HTTP Request, database, code, etc.) and connect "
            "them as sub-nodes. Agents without tools are limited to text "
            "generation."
        ),
        doc_link=f"{_DOC_BASE}QE-TU-001",
        example_bad="Agent node with no connected tool sub-nodes (can only generate text)",
        example_good=(
            "Agent node with 2-3 connected tools:\n"
            "- HTTP Request tool for API calls\n"
            "- Code tool for data transformation\n"
            "- Database tool for record lookup"
        ),
        quantified_target="1-10 tools for agents that need external interactions; 0 is acceptable for pure text agents",
    ),
    "QE-TU-002": ErrorCode(
        code="QE-TU-002",
        severity="medium",
        dimension="tool_usage",
        description="One or more tools are missing descriptions.",
        remediation=(
            "Add clear, concise descriptions to every tool so the agent "
            "understands when and how to use each one. Missing descriptions "
            "lead to incorrect tool selection."
        ),
        doc_link=f"{_DOC_BASE}QE-TU-002",
        example_bad='{ "name": "HTTP Request", "description": "" }  // empty description',
        example_good=(
            '{ "name": "HTTP Request", "description": "Fetch customer order '
            "history from the Orders API. Returns a JSON array of orders "
            'with fields: order_id, date, total, status." }'
        ),
        quantified_target="Every tool must have a description of 10+ words explaining when and how to use it",
    ),
    "QE-TU-003": ErrorCode(
        code="QE-TU-003",
        severity="medium",
        dimension="tool_usage",
        description="One or more tools are missing input/output schemas.",
        remediation=(
            "Define JSON schemas for tool parameters and return values. "
            "This helps the agent construct correct tool calls and parse "
            "results reliably."
        ),
        doc_link=f"{_DOC_BASE}QE-TU-003",
        example_bad='{ "name": "lookup_order", "parameters": {} }  // no schema defined',
        example_good=(
            '{ "name": "lookup_order", "parameters": {\n'
            '    "type": "object",\n'
            '    "properties": { "order_id": { "type": "string" } },\n'
            '    "required": ["order_id"]\n'
            "} }"
        ),
        quantified_target="Every tool must have a JSON schema for parameters with required fields specified",
    ),
    "QE-TU-004": ErrorCode(
        code="QE-TU-004",
        severity="medium",
        dimension="tool_usage",
        description="Too many tools defined (>10), which may confuse the agent.",
        remediation=(
            "Reduce the number of available tools to 10 or fewer. Consider "
            "grouping related tools or splitting the agent into specialised "
            "sub-agents with focused toolsets."
        ),
        doc_link=f"{_DOC_BASE}QE-TU-004",
        example_bad="Agent with 15 tools: search, create, update, delete, list, export, import, ...",
        example_good=(
            "Split into 2 agents:\n"
            "- CRUD Agent (4 tools): create, read, update, delete\n"
            "- Analytics Agent (3 tools): search, export, report"
        ),
        quantified_target="Maximum 10 tools per agent; split into sub-agents if more are needed",
    ),

    # ── Config Appropriateness (CA) ───────────────────────────────────────
    "QE-CA-001": ErrorCode(
        code="QE-CA-001",
        severity="high",
        dimension="config_appropriateness",
        description="Temperature is out of recommended range (0.0 - 1.0).",
        remediation=(
            "Set temperature between 0.0 (deterministic) and 1.0 "
            "(creative). Values above 1.0 produce unreliable outputs; "
            "values below 0.0 are invalid for most providers."
        ),
        doc_link=f"{_DOC_BASE}QE-CA-001",
        example_bad='{ "temperature": 1.8 }  // too high — outputs become incoherent',
        example_good=(
            '{ "temperature": 0.1 }  // for data extraction and classification\n'
            '{ "temperature": 0.7 }  // for creative writing or brainstorming'
        ),
        quantified_target="0.0-0.3 for deterministic tasks; 0.5-0.8 for creative tasks; never above 1.0",
    ),
    "QE-CA-002": ErrorCode(
        code="QE-CA-002",
        severity="medium",
        dimension="config_appropriateness",
        description="Max tokens setting is too low for the task.",
        remediation=(
            "Increase maxTokens to allow the agent enough space to produce "
            "complete responses. A low limit causes truncated outputs that "
            "break downstream parsing."
        ),
        doc_link=f"{_DOC_BASE}QE-CA-002",
        example_bad='{ "maxTokens": 50 }  // truncated JSON output guaranteed',
        example_good=(
            '{ "maxTokens": 1024 }  // for short classifications\n'
            '{ "maxTokens": 4096 }  // for detailed analysis or generation'
        ),
        quantified_target="maxTokens >= 256 for classification, >= 1024 for generation, >= 2048 for analysis",
    ),
    "QE-CA-003": ErrorCode(
        code="QE-CA-003",
        severity="medium",
        dimension="config_appropriateness",
        description="No model specified; the node will use the provider default.",
        remediation=(
            "Explicitly set the model (e.g. gpt-4o, claude-sonnet-4-20250514) to "
            "ensure reproducible behaviour. Provider defaults may change "
            "without notice."
        ),
        doc_link=f"{_DOC_BASE}QE-CA-003",
        example_bad='{ "model": "" }  // provider picks whatever is default today',
        example_good='{ "model": "gpt-4o-2024-08-06" }  // pinned model version for reproducibility',
        quantified_target="Every agent node must specify an explicit model identifier",
    ),

    # ── Data Flow Clarity (DF) ────────────────────────────────────────────
    "QE-DF-001": ErrorCode(
        code="QE-DF-001",
        severity="high",
        dimension="data_flow_clarity",
        description="Low connection coverage: some nodes have no input or output connections.",
        remediation=(
            "Ensure every non-trigger node has at least one input connection "
            "and every non-terminal node has at least one output connection. "
            "Disconnected nodes indicate dead code or missing data flow."
        ),
        doc_link=f"{_DOC_BASE}QE-DF-001",
        example_bad=(
            "Webhook Trigger -> Agent A -> (output)\n"
            "Agent B (no input, no output)  // orphaned node"
        ),
        example_good=(
            "Webhook Trigger -> Agent A -> Transform -> Agent B -> Response\n"
            "// All nodes connected with clear input/output flow"
        ),
        quantified_target="100% connection coverage: every non-trigger node has input, every non-terminal has output",
    ),
    "QE-DF-002": ErrorCode(
        code="QE-DF-002",
        severity="medium",
        dimension="data_flow_clarity",
        description="Generic node names detected (e.g. 'AI Agent', 'HTTP Request').",
        remediation=(
            "Rename nodes to describe their purpose (e.g. 'Extract Invoice "
            "Data', 'Send Slack Notification'). Descriptive names make "
            "workflows self-documenting."
        ),
        doc_link=f"{_DOC_BASE}QE-DF-002",
        example_bad=(
            '{ "name": "AI Agent" }     // what does it do?\n'
            '{ "name": "HTTP Request" } // which API?'
        ),
        example_good=(
            '{ "name": "Extract Invoice Line Items" }\n'
            '{ "name": "Fetch Customer from Salesforce" }'
        ),
        quantified_target="0 generic names; every node name describes its specific purpose",
    ),
    "QE-DF-003": ErrorCode(
        code="QE-DF-003",
        severity="medium",
        dimension="data_flow_clarity",
        description="Implicit state passing detected between nodes.",
        remediation=(
            "Use explicit data connections rather than relying on global "
            "variables or shared state. Explicit data flow is easier to "
            "debug, test, and maintain."
        ),
        doc_link=f"{_DOC_BASE}QE-DF-003",
        example_bad=(
            '// Agent reads from global variable set by another node\n'
            '{{ $workflow.variables.lastResult }}'
        ),
        example_good=(
            '// Agent receives data via explicit connection\n'
            '{{ $json.previousAgent.output }}'
        ),
        quantified_target="0 global variable references; all data passed via explicit node connections",
    ),

    # ── Complexity Management (CM) ────────────────────────────────────────
    "QE-CM-001": ErrorCode(
        code="QE-CM-001",
        severity="high",
        dimension="complexity_management",
        description="Workflow has too many nodes (>50), increasing maintenance burden.",
        remediation=(
            "Break the workflow into smaller sub-workflows using the "
            "Execute Workflow node. Aim for 10-30 nodes per workflow to "
            "keep each unit understandable."
        ),
        doc_link=f"{_DOC_BASE}QE-CM-001",
        example_bad="Single workflow with 65 nodes handling ingestion, processing, and reporting",
        example_good=(
            "3 sub-workflows:\n"
            "- Ingestion (8 nodes) -> Execute Workflow\n"
            "- Processing (12 nodes) -> Execute Workflow\n"
            "- Reporting (6 nodes)"
        ),
        quantified_target="10-30 nodes per workflow; use Execute Workflow node to decompose larger flows",
    ),
    "QE-CM-002": ErrorCode(
        code="QE-CM-002",
        severity="medium",
        dimension="complexity_management",
        description="Excessive execution depth (>10 levels) detected.",
        remediation=(
            "Reduce nesting by extracting deep branches into sub-workflows "
            "or flattening conditional logic. Deep graphs are hard to debug "
            "and prone to timeout."
        ),
        doc_link=f"{_DOC_BASE}QE-CM-002",
        example_bad=(
            "Trigger -> IF -> IF -> Switch -> IF -> Agent -> IF -> ...\n"
            "// 12 levels deep, impossible to follow"
        ),
        example_good=(
            "Trigger -> Router (Switch) -> [Branch A sub-workflow]\n"
            "                           -> [Branch B sub-workflow]\n"
            "// Max 4 levels deep per branch"
        ),
        quantified_target="Maximum 10 levels of execution depth; extract deep branches into sub-workflows",
    ),
    "QE-CM-003": ErrorCode(
        code="QE-CM-003",
        severity="high",
        dimension="complexity_management",
        description="High cyclomatic complexity makes the workflow hard to test.",
        remediation=(
            "Reduce the number of conditional branches and loops. Extract "
            "complex decision logic into a dedicated Code or Function node "
            "that can be unit-tested independently."
        ),
        doc_link=f"{_DOC_BASE}QE-CM-003",
        example_bad=(
            "8 IF nodes + 3 Switch nodes = 20+ execution paths\n"
            "// Cannot reasonably test all combinations"
        ),
        example_good=(
            "Code node: classify(input) -> single category string\n"
            "Switch node: route by category (3-4 branches max)"
        ),
        quantified_target="Cyclomatic complexity <= 10; consolidate branching logic into Code nodes",
    ),

    # ── Agent Coupling (AC) ──────────────────────────────────────────────
    "QE-AC-001": ErrorCode(
        code="QE-AC-001",
        severity="high",
        dimension="agent_coupling",
        description="Long sequential agent chain detected (>4 agents in series).",
        remediation=(
            "Break long agent chains with checkpoints, validation nodes, "
            "or parallelisation. Long chains amplify errors: each agent's "
            "mistakes propagate to all downstream agents."
        ),
        doc_link=f"{_DOC_BASE}QE-AC-001",
        example_bad="Agent A -> Agent B -> Agent C -> Agent D -> Agent E -> Agent F  // 6 in series",
        example_good=(
            "Agent A -> Validate -> Agent B -> Checkpoint\n"
            "                    -> Agent C (parallel)\n"
            "Merge -> Agent D  // max 3 in series with validation"
        ),
        quantified_target="Maximum 4 agents in series; add validation or checkpoint nodes between them",
    ),
    "QE-AC-002": ErrorCode(
        code="QE-AC-002",
        severity="medium",
        dimension="agent_coupling",
        description="High agent coupling ratio: most nodes are agent nodes.",
        remediation=(
            "Add validation, transformation, and routing nodes between "
            "agents. A high coupling ratio means agents depend heavily on "
            "each other with no intermediate checks."
        ),
        doc_link=f"{_DOC_BASE}QE-AC-002",
        example_bad=(
            "8 of 10 nodes are AI Agents (80% coupling ratio)\n"
            "// No validation or transformation between them"
        ),
        example_good=(
            "4 of 12 nodes are AI Agents (33% coupling ratio)\n"
            "// Interspersed with Code, IF, and HTTP Request nodes"
        ),
        quantified_target="Agent coupling ratio <= 50%; add non-agent nodes for validation and data transformation",
    ),

    # ── Observability (OB) ───────────────────────────────────────────────
    "QE-OB-001": ErrorCode(
        code="QE-OB-001",
        severity="medium",
        dimension="observability",
        description="No checkpoint or logging nodes in the workflow.",
        remediation=(
            "Add checkpoint nodes at key stages (after data retrieval, "
            "after agent processing, before final output) to capture "
            "intermediate state for debugging."
        ),
        doc_link=f"{_DOC_BASE}QE-OB-001",
        example_bad="Trigger -> Agent -> Agent -> Response  // no visibility into intermediate states",
        example_good=(
            "Trigger -> Agent -> Log to DB -> Agent -> Log to DB -> Response\n"
            '// Each checkpoint captures: { "stage": "...", "data": {...}, "timestamp": "..." }'
        ),
        quantified_target="At least 1 checkpoint/logging node per 5 workflow nodes",
    ),
    "QE-OB-002": ErrorCode(
        code="QE-OB-002",
        severity="high",
        dimension="observability",
        description="No error trigger nodes configured in the workflow.",
        remediation=(
            "Add an Error Trigger node that captures workflow failures and "
            "routes them to alerting (Slack, email, PagerDuty) so issues "
            "are detected promptly."
        ),
        doc_link=f"{_DOC_BASE}QE-OB-002",
        example_bad="// No Error Trigger node — failures are silent",
        example_good=(
            '{ "type": "n8n-nodes-base.errorTrigger" }\n'
            "-> Send Slack message with error details\n"
            "-> Log error to monitoring dashboard"
        ),
        quantified_target="Every workflow must have at least 1 Error Trigger node connected to alerting",
    ),
    "QE-OB-003": ErrorCode(
        code="QE-OB-003",
        severity="medium",
        dimension="observability",
        description="No monitoring or alerting integration detected.",
        remediation=(
            "Integrate with a monitoring tool (Datadog, Grafana, PISAMA) "
            "to track execution frequency, latency, error rates, and token "
            "costs over time."
        ),
        doc_link=f"{_DOC_BASE}QE-OB-003",
        example_bad="// Workflow runs with no external monitoring — issues discovered manually",
        example_good=(
            "HTTP Request node -> POST to Datadog /api/v1/series\n"
            '{ "metric": "workflow.execution_time", "tags": ["workflow:invoice_processing"] }'
        ),
        quantified_target="At least 1 monitoring integration (Datadog, Grafana, or PISAMA webhook) per workflow",
    ),

    # ── Best Practices (BP) ──────────────────────────────────────────────
    "QE-BP-001": ErrorCode(
        code="QE-BP-001",
        severity="critical",
        dimension="best_practices",
        description="No global error handler configured for the workflow.",
        remediation=(
            "Add a workflow-level Error Trigger node to catch unhandled "
            "errors. Without a global handler, failures may go unnoticed "
            "and data may be lost silently."
        ),
        doc_link=f"{_DOC_BASE}QE-BP-001",
        example_bad="// No Error Trigger node in workflow — unhandled errors are silently dropped",
        example_good=(
            "Error Trigger -> Code (format error) -> Slack (alert team)\n"
            "                                     -> Database (log for audit)"
        ),
        quantified_target="Every production workflow must have exactly 1 global Error Trigger node",
    ),
    "QE-BP-002": ErrorCode(
        code="QE-BP-002",
        severity="medium",
        dimension="best_practices",
        description="Inconsistent retry configuration across agent nodes.",
        remediation=(
            "Standardise retry settings (maxTries, waitBetweenTries) "
            "across all agent nodes. Inconsistent configuration makes "
            "failure behaviour unpredictable."
        ),
        doc_link=f"{_DOC_BASE}QE-BP-002",
        example_bad=(
            "Agent A: { maxTries: 5, waitBetweenTries: 100 }\n"
            "Agent B: { maxTries: 1, waitBetweenTries: 5000 }\n"
            "Agent C: (no retry config)"
        ),
        example_good=(
            "All agents: { maxTries: 3, waitBetweenTries: 1000 }\n"
            "// Consistent retry policy across the workflow"
        ),
        quantified_target="All agent nodes must share the same retry policy (maxTries, waitBetweenTries)",
    ),
    "QE-BP-003": ErrorCode(
        code="QE-BP-003",
        severity="high",
        dimension="best_practices",
        description="No overall execution timeout configured for the workflow.",
        remediation=(
            "Set a workflow-level execution timeout (e.g. 5-15 minutes) to "
            "prevent runaway workflows from consuming resources indefinitely."
        ),
        doc_link=f"{_DOC_BASE}QE-BP-003",
        example_bad='{ "executionTimeout": -1 }  // no timeout — runaway workflows possible',
        example_good='{ "executionTimeout": 600 }  // 10-minute workflow timeout with graceful shutdown',
        quantified_target="Workflow executionTimeout between 300s (5min) and 900s (15min) for production",
    ),
}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_error_code(code: str) -> Optional[ErrorCode]:
    """Look up an error code by its identifier.

    Args:
        code: Error code string, e.g. ``"QE-RC-001"``.

    Returns:
        The :class:`ErrorCode` instance, or ``None`` if not found.
    """
    return ERROR_CODES.get(code)


def get_codes_for_dimension(dimension: str) -> List[ErrorCode]:
    """Return all error codes that belong to the given quality dimension.

    Args:
        dimension: Dimension name, e.g. ``"role_clarity"``,
            ``"error_handling"``, ``"best_practices"``.

    Returns:
        A list of matching :class:`ErrorCode` instances (may be empty).
    """
    return [ec for ec in ERROR_CODES.values() if ec.dimension == dimension]


def get_codes_by_severity(severity: str) -> List[ErrorCode]:
    """Return all error codes at the given severity level.

    Args:
        severity: One of ``"critical"``, ``"high"``, ``"medium"``, ``"low"``.

    Returns:
        A list of matching :class:`ErrorCode` instances.
    """
    return [ec for ec in ERROR_CODES.values() if ec.severity == severity]
