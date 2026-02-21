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

_DOC_BASE = ""  # Empty until hosted docs exist — avoids 404s

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
