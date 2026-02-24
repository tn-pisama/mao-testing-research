"""Orchestration quality fix generators.

Each generator targets a specific OrchestrationDimension and produces
concrete QualityFixSuggestion instances that can be applied (or previewed)
by the healing pipeline.
"""

from typing import Dict, Any, List

from ..models import DimensionScore, OrchestrationDimension
from .models import QualityFixSuggestion, QualityFixCategory
from .fix_generator import BaseQualityFixGenerator


# ---------------------------------------------------------------------------
# 1. DataFlowClarityFixGenerator
# ---------------------------------------------------------------------------

class DataFlowClarityFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for data_flow_clarity dimension.

    Targets generic node names and missing explicit data mappings between
    connected nodes.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.DATA_FLOW_CLARITY.value

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        evidence = dimension_score.evidence
        workflow_id = context.get("workflow_id", "unknown")

        # Fix 1: Rename generic nodes
        generic_name_ratio = evidence.get("generic_name_ratio", 0.0)
        if generic_name_ratio > 0.3:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.DATA_FLOW_CLARITY.value,
                    category=QualityFixCategory.DATA_FLOW_CLARITY,
                    title="Rename generic nodes",
                    description=(
                        "Several nodes use default names like 'Code' or 'Set' "
                        "which obscure the data flow.  Rename them to describe "
                        "their purpose so the workflow reads like documentation."
                    ),
                    confidence=0.8,
                    expected_improvement=0.15,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "rename_nodes",
                        "renames": {
                            "Code": "Parse API Response",
                            "Set": "Format Output",
                        },
                    },
                    effort="low",
                    code_example=(
                        '// Before\n'
                        '{"name": "Code", "type": "n8n-nodes-base.code"}\n'
                        '// After\n'
                        '{"name": "Parse API Response", "type": "n8n-nodes-base.code"}'
                    ),
                )
            )

        # Fix 2: Add explicit data mappings
        connection_coverage = evidence.get("connection_coverage", 1.0)
        if connection_coverage < 0.7:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.DATA_FLOW_CLARITY.value,
                    category=QualityFixCategory.DATA_FLOW_CLARITY,
                    title="Add explicit data mappings",
                    description=(
                        "Connections between nodes lack explicit expression "
                        "mappings, making the data flow implicit and fragile. "
                        "Add expression-based mappings to document which fields "
                        "flow between nodes."
                    ),
                    confidence=0.7,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_expression_mappings",
                        "node_pairs": [],
                    },
                    effort="medium",
                    code_example=(
                        '// Add explicit mapping in a Set node between producer and consumer\n'
                        '{\n'
                        '  "name": "Map Fields",\n'
                        '  "type": "n8n-nodes-base.set",\n'
                        '  "parameters": {\n'
                        '    "values": {\n'
                        '      "string": [\n'
                        '        {"name": "userId", "value": "={{$json.id}}"}\n'
                        '      ]\n'
                        '    }\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        return fixes


# ---------------------------------------------------------------------------
# 2. ComplexityManagementFixGenerator
# ---------------------------------------------------------------------------

class ComplexityManagementFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for complexity_management dimension.

    Suggests extracting groups of nodes into sub-workflows when the
    workflow exceeds manageable size thresholds.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.COMPLEXITY_MANAGEMENT.value

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        evidence = dimension_score.evidence
        workflow_id = context.get("workflow_id", "unknown")

        # Fix 1: Suggest sub-workflow extraction
        node_count = evidence.get("node_count", 0)
        if node_count > 15:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.COMPLEXITY_MANAGEMENT.value,
                    category=QualityFixCategory.COMPLEXITY_MANAGEMENT,
                    title="Suggest sub-workflow extraction",
                    description=(
                        f"This workflow has {node_count} nodes which makes it "
                        "difficult to reason about.  Consider extracting "
                        "logically related groups into sub-workflows to reduce "
                        "cognitive load and improve reusability."
                    ),
                    confidence=0.6,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "suggest_extraction",
                        "note": "Extract nodes X-Y into sub-workflow",
                    },
                    breaking_changes=True,
                    effort="high",
                    code_example=(
                        '// Replace a group of nodes with an Execute Workflow node\n'
                        '{\n'
                        '  "name": "Run Sub-Workflow: Data Preparation",\n'
                        '  "type": "n8n-nodes-base.executeWorkflow",\n'
                        '  "parameters": {\n'
                        '    "workflowId": "={{$vars.sub_workflow_id}}"\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        return fixes


# ---------------------------------------------------------------------------
# 3. AgentCouplingFixGenerator
# ---------------------------------------------------------------------------

class AgentCouplingFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for agent_coupling dimension.

    Reduces tight coupling between AI agents by inserting validation
    checkpoints and breaking long sequential chains.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.AGENT_COUPLING.value

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        evidence = dimension_score.evidence
        workflow_id = context.get("workflow_id", "unknown")

        # Fix 1: Add validation checkpoint between agents
        coupling_ratio = evidence.get("coupling_ratio", 0.0)
        if coupling_ratio > 0.6:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.AGENT_COUPLING.value,
                    category=QualityFixCategory.AGENT_COUPLING,
                    title="Add validation checkpoint between agents",
                    description=(
                        "Agents are tightly coupled with a coupling ratio of "
                        f"{coupling_ratio:.2f}.  Insert a validation checkpoint "
                        "between agent handoffs to verify output quality before "
                        "passing data downstream."
                    ),
                    confidence=0.75,
                    expected_improvement=0.15,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_node_between",
                        "node": {
                            "type": "n8n-nodes-base.set",
                            "name": "Checkpoint: Validate Handoff",
                            "parameters": {
                                "values": {
                                    "string": [
                                        {
                                            "name": "handoff_valid",
                                            "value": '={{$json.output ? "true" : "false"}}',
                                        }
                                    ]
                                }
                            },
                        },
                    },
                    effort="medium",
                    code_example=(
                        '// Insert between two agent nodes\n'
                        '{\n'
                        '  "name": "Checkpoint: Validate Handoff",\n'
                        '  "type": "n8n-nodes-base.set",\n'
                        '  "parameters": {\n'
                        '    "values": {\n'
                        '      "string": [\n'
                        '        {"name": "handoff_valid",\n'
                        '         "value": "={{$json.output ? \\"true\\" : \\"false\\"}}"}\n'
                        '      ]\n'
                        '    }\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        # Fix 2: Break long agent chain
        max_agent_chain = evidence.get("max_agent_chain", 0)
        if max_agent_chain > 4:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.AGENT_COUPLING.value,
                    category=QualityFixCategory.AGENT_COUPLING,
                    title="Break long agent chain",
                    description=(
                        f"Detected a chain of {max_agent_chain} sequential "
                        "agents.  Long chains amplify errors and increase "
                        "latency.  Insert a checkpoint every 3 agents to "
                        "validate intermediate results."
                    ),
                    confidence=0.7,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_node_between",
                        "position": "every_3_agents",
                        "node": {
                            "type": "n8n-nodes-base.set",
                            "name": "Chain Checkpoint",
                            "parameters": {
                                "values": {
                                    "string": [
                                        {
                                            "name": "chain_stage",
                                            "value": "={{$runIndex}}",
                                        }
                                    ]
                                }
                            },
                        },
                    },
                    effort="medium",
                    code_example=(
                        '// Insert every 3 agents in the chain\n'
                        '{\n'
                        '  "name": "Chain Checkpoint",\n'
                        '  "type": "n8n-nodes-base.set",\n'
                        '  "parameters": {\n'
                        '    "values": {\n'
                        '      "string": [\n'
                        '        {"name": "chain_stage", "value": "={{$runIndex}}"}\n'
                        '      ]\n'
                        '    }\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        return fixes


# ---------------------------------------------------------------------------
# 4. ObservabilityFixGenerator
# ---------------------------------------------------------------------------

class ObservabilityFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for observability dimension.

    Adds checkpoint nodes, error triggers, and monitoring webhooks so
    workflow executions are traceable and failures are surfaced quickly.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.OBSERVABILITY.value

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        evidence = dimension_score.evidence
        workflow_id = context.get("workflow_id", "unknown")

        # Fix 1: Add checkpoint nodes
        observability_nodes = evidence.get("observability_nodes", 0)
        if observability_nodes == 0:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.OBSERVABILITY.value,
                    category=QualityFixCategory.OBSERVABILITY,
                    title="Add checkpoint nodes",
                    description=(
                        "No observability checkpoints found.  Add Set nodes "
                        "after key stages to record progress, making it easy "
                        "to pinpoint where a failure occurred during execution."
                    ),
                    confidence=0.85,
                    expected_improvement=0.15,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_node",
                        "connect_after": "last_ai_node",
                        "node": {
                            "type": "n8n-nodes-base.set",
                            "name": "Checkpoint: Stage Complete",
                            "parameters": {
                                "values": {
                                    "string": [
                                        {
                                            "name": "checkpoint_stage",
                                            "value": "stage_1_complete",
                                        },
                                        {
                                            "name": "checkpoint_ts",
                                            "value": "={{$now.toISO()}}",
                                        },
                                    ]
                                }
                            },
                        },
                    },
                    effort="low",
                    code_example=(
                        '{\n'
                        '  "name": "Checkpoint: Stage Complete",\n'
                        '  "type": "n8n-nodes-base.set",\n'
                        '  "parameters": {\n'
                        '    "values": {\n'
                        '      "string": [\n'
                        '        {"name": "checkpoint_stage", "value": "stage_1_complete"},\n'
                        '        {"name": "checkpoint_ts", "value": "={{$now.toISO()}}"}\n'
                        '      ]\n'
                        '    }\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        # Fix 2: Add error trigger
        error_triggers = evidence.get("error_triggers", 0)
        if error_triggers == 0:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.OBSERVABILITY.value,
                    category=QualityFixCategory.OBSERVABILITY,
                    title="Add error trigger",
                    description=(
                        "No error trigger node found.  An error trigger "
                        "captures workflow-level failures so they can be "
                        "routed to alerting or logged for post-mortem analysis."
                    ),
                    confidence=0.85,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_node",
                        "is_trigger": True,
                        "node": {
                            "type": "n8n-nodes-base.errorTrigger",
                            "name": "Error Trigger",
                            "parameters": {},
                        },
                    },
                    effort="low",
                    code_example=(
                        '{\n'
                        '  "name": "Error Trigger",\n'
                        '  "type": "n8n-nodes-base.errorTrigger",\n'
                        '  "parameters": {}\n'
                        '}'
                    ),
                )
            )

        # Fix 3: Add monitoring webhook
        monitoring_webhooks = evidence.get("monitoring_webhooks", 0)
        if monitoring_webhooks == 0:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.OBSERVABILITY.value,
                    category=QualityFixCategory.OBSERVABILITY,
                    title="Add monitoring webhook",
                    description=(
                        "No monitoring webhook detected.  Add an HTTP Request "
                        "node to send trace data to MAO after each execution "
                        "so quality metrics stay up to date."
                    ),
                    confidence=0.7,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_node",
                        "connect_after": "last_main_node",
                        "node": {
                            "type": "n8n-nodes-base.httpRequest",
                            "name": "Send Trace to MAO",
                            "parameters": {
                                "url": "={{$vars.mao_webhook_url}}",
                                "method": "POST",
                                "sendBody": True,
                                "bodyParameters": {
                                    "parameters": [
                                        {
                                            "name": "workflow_id",
                                            "value": "={{$workflow.id}}",
                                        },
                                        {
                                            "name": "execution_id",
                                            "value": "={{$execution.id}}",
                                        },
                                    ]
                                },
                            },
                        },
                    },
                    effort="low",
                    code_example=(
                        '{\n'
                        '  "name": "Send Trace to MAO",\n'
                        '  "type": "n8n-nodes-base.httpRequest",\n'
                        '  "parameters": {\n'
                        '    "url": "={{$vars.mao_webhook_url}}",\n'
                        '    "method": "POST",\n'
                        '    "sendBody": true,\n'
                        '    "bodyParameters": {\n'
                        '      "parameters": [\n'
                        '        {"name": "workflow_id", "value": "={{$workflow.id}}"},\n'
                        '        {"name": "execution_id", "value": "={{$execution.id}}"}\n'
                        '      ]\n'
                        '    }\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        return fixes


# ---------------------------------------------------------------------------
# 5. BestPracticesFixGenerator
# ---------------------------------------------------------------------------

class BestPracticesFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for best_practices dimension.

    Covers global error handling, execution timeouts, and retry
    configuration standardisation.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.BEST_PRACTICES.value

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        evidence = dimension_score.evidence
        workflow_id = context.get("workflow_id", "unknown")

        # Fix 1: Add global error handler
        error_handler_present = evidence.get("has_global_error_handler", False)
        if not error_handler_present:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.BEST_PRACTICES.value,
                    category=QualityFixCategory.BEST_PRACTICES,
                    title="Add global error handler",
                    description=(
                        "No global error handler workflow is configured.  "
                        "Set the errorWorkflow setting so that unhandled "
                        "failures are routed to a centralized handler for "
                        "alerting and recovery."
                    ),
                    confidence=0.85,
                    expected_improvement=0.15,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_node",
                        "is_trigger": True,
                        "node": {
                            "type": "n8n-nodes-base.errorTrigger",
                            "name": "Error Trigger",
                            "parameters": {},
                            "position": [250, 600],
                        },
                    },
                    effort="low",
                    code_example=(
                        '// Add error trigger node to workflow\n'
                        '{\n'
                        '  "type": "n8n-nodes-base.errorTrigger",\n'
                        '  "name": "Error Trigger",\n'
                        '  "parameters": {}\n'
                        '}'
                    ),
                )
            )

        # Fix 2: Add execution timeout
        execution_timeout = evidence.get("execution_timeout", None)
        if not execution_timeout:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.BEST_PRACTICES.value,
                    category=QualityFixCategory.BEST_PRACTICES,
                    title="Add execution timeout",
                    description=(
                        "No execution timeout is set.  Without a timeout, "
                        "a stuck workflow can consume resources indefinitely.  "
                        "A 300-second timeout is a safe starting point."
                    ),
                    confidence=0.8,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "set_workflow_setting",
                        "settings": {
                            "executionTimeout": 300,
                        },
                    },
                    effort="low",
                    code_example=(
                        '// In workflow settings\n'
                        '{\n'
                        '  "settings": {\n'
                        '    "executionTimeout": 300\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        # Fix 3: Standardize retry config
        config_uniformity = evidence.get("config_uniformity", 1.0)
        if config_uniformity < 0.5:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.BEST_PRACTICES.value,
                    category=QualityFixCategory.BEST_PRACTICES,
                    title="Standardize retry config",
                    description=(
                        "Retry configuration varies across nodes "
                        f"(uniformity {config_uniformity:.2f}).  Standardize "
                        "retry settings to ensure consistent failure recovery "
                        "behaviour across the workflow."
                    ),
                    confidence=0.75,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "standardize_settings",
                        "settings": {
                            "retryOnFail": True,
                            "maxRetries": 3,
                        },
                    },
                    effort="medium",
                    code_example=(
                        '// Apply to every HTTP / Code / AI node\n'
                        '{\n'
                        '  "retryOnFail": true,\n'
                        '  "maxRetries": 3,\n'
                        '  "waitBetweenRetries": 1000\n'
                        '}'
                    ),
                )
            )

        return fixes


# ---------------------------------------------------------------------------
# 6. DocumentationQualityFixGenerator
# ---------------------------------------------------------------------------

class DocumentationQualityFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for documentation_quality dimension.

    Addresses missing workflow descriptions and absent explanatory sticky
    notes.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.DOCUMENTATION_QUALITY.value

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        evidence = dimension_score.evidence
        workflow_id = context.get("workflow_id", "unknown")
        workflow_name = context.get("workflow_name", "Unnamed Workflow")

        # Fix 1: Add workflow description
        has_description = evidence.get("has_description", False)
        if not has_description:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.DOCUMENTATION_QUALITY.value,
                    category=QualityFixCategory.DOCUMENTATION_QUALITY,
                    title="Add workflow description",
                    description=(
                        "The workflow has no description.  A concise summary "
                        "helps collaborators understand the workflow's purpose "
                        "without reading every node."
                    ),
                    confidence=0.85,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "set_workflow_setting",
                        "settings": {
                            "description": (
                                f"Workflow that orchestrates the "
                                f"{workflow_name} pipeline."
                            ),
                        },
                    },
                    effort="low",
                    code_example=(
                        '// In workflow settings\n'
                        '{\n'
                        '  "settings": {\n'
                        '    "description": "Workflow that orchestrates the '
                        f'{workflow_name} pipeline."\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        # Fix 2: Add sticky notes
        sticky_note_count = evidence.get("sticky_note_count", 0)
        if sticky_note_count == 0:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.DOCUMENTATION_QUALITY.value,
                    category=QualityFixCategory.DOCUMENTATION_QUALITY,
                    title="Add sticky notes",
                    description=(
                        "No sticky notes found.  Add at least one note per "
                        "logical stage to explain the workflow's structure and "
                        "decision points visually."
                    ),
                    confidence=0.8,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_node",
                        "node": {
                            "type": "n8n-nodes-base.stickyNote",
                            "name": "Stage Overview",
                            "parameters": {
                                "content": (
                                    "## Stage 1: Input Processing\\n"
                                    "Validates and normalizes incoming data "
                                    "before passing it to the AI agents."
                                ),
                            },
                            "position": [0, -200],
                        },
                    },
                    effort="low",
                    code_example=(
                        '{\n'
                        '  "name": "Stage Overview",\n'
                        '  "type": "n8n-nodes-base.stickyNote",\n'
                        '  "parameters": {\n'
                        '    "content": "## Stage 1: Input Processing\\n'
                        'Validates and normalizes incoming data."\n'
                        '  },\n'
                        '  "position": [0, -200]\n'
                        '}'
                    ),
                )
            )

        return fixes


# ---------------------------------------------------------------------------
# 7. AIArchitectureFixGenerator
# ---------------------------------------------------------------------------

class AIArchitectureFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for ai_architecture dimension.

    Ensures AI agent outputs are validated and that agents have diverse
    connection types (memory, tools, output parsers).
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.AI_ARCHITECTURE.value

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        evidence = dimension_score.evidence
        workflow_id = context.get("workflow_id", "unknown")

        # Fix 1: Add output validation after AI
        ai_agent_count = evidence.get("ai_agent_count", 0)
        has_output_validation = evidence.get("has_output_validation", False)
        if ai_agent_count > 0 and not has_output_validation:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.AI_ARCHITECTURE.value,
                    category=QualityFixCategory.AI_ARCHITECTURE,
                    title="Add output validation after AI",
                    description=(
                        "AI agent outputs are consumed without validation.  "
                        "Add a Code node after each AI agent to assert the "
                        "output structure and reject malformed responses "
                        "before they propagate."
                    ),
                    confidence=0.8,
                    expected_improvement=0.15,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_node_after",
                        "after_node_type": "ai_agent",
                        "node": {
                            "type": "n8n-nodes-base.code",
                            "name": "Validate AI Output",
                            "parameters": {
                                "jsCode": (
                                    "const output = $input.first().json;\n"
                                    "if (!output || !output.output) {\n"
                                    "  throw new Error('AI agent returned empty output');\n"
                                    "}\n"
                                    "return [{json: output}];"
                                ),
                            },
                        },
                    },
                    effort="medium",
                    code_example=(
                        '{\n'
                        '  "name": "Validate AI Output",\n'
                        '  "type": "n8n-nodes-base.code",\n'
                        '  "parameters": {\n'
                        '    "jsCode": "const output = $input.first().json;\\n'
                        "if (!output || !output.output) {\\n"
                        "  throw new Error('AI agent returned empty output');\\n"
                        '}\\n'
                        'return [{json: output}];"\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        # Fix 2: Add memory connection
        ai_connection_diversity = evidence.get("ai_connection_diversity", 1.0)
        if ai_connection_diversity < 0.5:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.AI_ARCHITECTURE.value,
                    category=QualityFixCategory.AI_ARCHITECTURE,
                    title="Add memory connection",
                    description=(
                        "AI agents lack diverse connection types "
                        f"(diversity {ai_connection_diversity:.2f}).  "
                        "Add a memory connection so agents can retain context "
                        "across invocations, improving coherence in "
                        "multi-turn interactions."
                    ),
                    confidence=0.7,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_ai_connection",
                        "connection_type": "ai_memory",
                        "node": {
                            "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
                            "name": "Window Buffer Memory",
                            "parameters": {
                                "sessionKey": "chat_history",
                                "contextWindowLength": 10,
                            },
                        },
                    },
                    effort="medium",
                    code_example=(
                        '{\n'
                        '  "name": "Window Buffer Memory",\n'
                        '  "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",\n'
                        '  "parameters": {\n'
                        '    "sessionKey": "chat_history",\n'
                        '    "contextWindowLength": 10\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        return fixes


# ---------------------------------------------------------------------------
# 8. MaintenanceQualityFixGenerator
# ---------------------------------------------------------------------------

class MaintenanceQualityFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for maintenance_quality dimension.

    Removes dead weight (disabled nodes) and flags outdated node versions
    that may have known bugs or missing features.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.MAINTENANCE_QUALITY.value

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        evidence = dimension_score.evidence
        workflow_id = context.get("workflow_id", "unknown")

        # Fix 1: Remove disabled nodes
        disabled_nodes = evidence.get("disabled_nodes", 0)
        if disabled_nodes > 0:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.MAINTENANCE_QUALITY.value,
                    category=QualityFixCategory.MAINTENANCE_QUALITY,
                    title="Remove disabled nodes",
                    description=(
                        f"Found {disabled_nodes} disabled node(s) cluttering "
                        "the workflow.  Disabled nodes add visual noise and "
                        "can confuse collaborators.  Remove them or move "
                        "experimental nodes to a separate workflow."
                    ),
                    confidence=0.85,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "remove_nodes",
                        "filter": "disabled",
                    },
                    effort="low",
                    code_example=(
                        '// Remove all nodes where disabled === true\n'
                        '// Before: {"name": "Old Code", "disabled": true, ...}\n'
                        '// After:  (node removed from workflow JSON)'
                    ),
                )
            )

        # Fix 2: Update outdated node versions
        outdated_versions = evidence.get("outdated_versions", 0)
        if outdated_versions > 0:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.MAINTENANCE_QUALITY.value,
                    category=QualityFixCategory.MAINTENANCE_QUALITY,
                    title="Update outdated node versions",
                    description=(
                        f"Found {outdated_versions} node(s) running outdated "
                        "type versions.  Newer versions often include bug fixes "
                        "and improved defaults.  Update them to the latest "
                        "available version."
                    ),
                    confidence=0.7,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "update_versions",
                        "target": "latest",
                    },
                    breaking_changes=True,
                    effort="medium",
                    code_example=(
                        '// Before\n'
                        '{"typeVersion": 1, "type": "n8n-nodes-base.httpRequest"}\n'
                        '// After\n'
                        '{"typeVersion": 4, "type": "n8n-nodes-base.httpRequest"}'
                    ),
                )
            )

        return fixes


# ---------------------------------------------------------------------------
# 9. TestCoverageFixGenerator
# ---------------------------------------------------------------------------

class TestCoverageFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for test_coverage dimension.

    Adds pin-data fixtures to nodes so the workflow can be executed in
    test mode without hitting live services.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.TEST_COVERAGE.value

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        evidence = dimension_score.evidence
        workflow_id = context.get("workflow_id", "unknown")

        coverage_ratio = evidence.get("coverage_ratio", 0.0)

        # Fix 1: Add test data fixtures (zero coverage)
        if coverage_ratio == 0:
            # Build pin_data dict using actual node names from evidence
            uncovered_names = evidence.get("uncovered_node_names", [])
            pin_data: Dict[str, Any] = {}
            for name in uncovered_names[:5]:  # Cap at 5 nodes
                pin_data[name] = [
                    {
                        "json": {
                            "id": 1,
                            "input": "test input",
                            "timestamp": "2025-01-01T00:00:00Z",
                        }
                    }
                ]
            # Fallback if no node names available
            if not pin_data:
                pin_data["Trigger"] = [
                    {"json": {"id": 1, "input": "test input"}}
                ]

            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.TEST_COVERAGE.value,
                    category=QualityFixCategory.TEST_COVERAGE,
                    title="Add test data fixtures",
                    description=(
                        "No nodes have pinned test data.  Add sample data "
                        "fixtures to trigger and key processing nodes so the "
                        "workflow can be tested without live dependencies."
                    ),
                    confidence=0.75,
                    expected_improvement=0.2,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_pin_data",
                        "pin_data": pin_data,
                    },
                    effort="medium",
                    code_example=(
                        '// Add pinData to workflow JSON\n'
                        '{\n'
                        '  "pinData": {\n'
                        '    "Trigger Node": [\n'
                        '      {"json": {"id": 1, "input": "test input"}}\n'
                        '    ]\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        # Fix 2: Increase test coverage (partial coverage)
        elif coverage_ratio < 0.5:
            uncovered_names = evidence.get("uncovered_node_names", [])
            pin_data_partial: Dict[str, Any] = {}
            for name in uncovered_names[:5]:
                pin_data_partial[name] = [
                    {"json": {"result": "expected output"}}
                ]
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.TEST_COVERAGE.value,
                    category=QualityFixCategory.TEST_COVERAGE,
                    title="Increase test coverage",
                    description=(
                        f"Test coverage is at {coverage_ratio:.0%}, "
                        "below the recommended 50% minimum.  Add pinned data "
                        "to additional nodes to improve coverage and catch "
                        "regressions earlier."
                    ),
                    confidence=0.7,
                    expected_improvement=0.15,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "add_pin_data",
                        "pin_data": pin_data_partial,
                    },
                    effort="medium",
                    code_example=(
                        '// Extend pinData with additional nodes\n'
                        '{\n'
                        '  "pinData": {\n'
                        '    "Existing Node": [...],\n'
                        '    "Uncovered Node": [\n'
                        '      {"json": {"result": "expected output"}}\n'
                        '    ]\n'
                        '  }\n'
                        '}'
                    ),
                )
            )

        return fixes


# ---------------------------------------------------------------------------
# 10. LayoutQualityFixGenerator
# ---------------------------------------------------------------------------

class LayoutQualityFixGenerator(BaseQualityFixGenerator):
    """Generate fixes for layout_quality dimension.

    Resolves overlapping nodes and misalignment so the visual layout
    matches the logical data flow.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.LAYOUT_QUALITY.value

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        evidence = dimension_score.evidence
        workflow_id = context.get("workflow_id", "unknown")

        # Fix 1: Fix overlapping nodes
        overlapping_nodes = evidence.get("overlapping_nodes", 0)
        if overlapping_nodes > 0:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.LAYOUT_QUALITY.value,
                    category=QualityFixCategory.LAYOUT_QUALITY,
                    title="Fix overlapping nodes",
                    description=(
                        f"Found {overlapping_nodes} overlapping node(s).  "
                        "Overlapping nodes make the workflow hard to read and "
                        "can hide connections.  Auto-space them with a minimum "
                        "gap of 50px."
                    ),
                    confidence=0.85,
                    expected_improvement=0.15,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "reorganize_layout",
                        "strategy": "auto_space",
                        "min_gap": 50,
                    },
                    effort="low",
                    code_example=(
                        '// Adjust node positions to eliminate overlap\n'
                        '// Before: {"position": [100, 200]}, {"position": [110, 210]}\n'
                        '// After:  {"position": [100, 200]}, {"position": [260, 200]}'
                    ),
                )
            )

        # Fix 2: Align to grid
        alignment_score = evidence.get("alignment_score", 1.0)
        if alignment_score < 0.5:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.LAYOUT_QUALITY.value,
                    category=QualityFixCategory.LAYOUT_QUALITY,
                    title="Align to grid",
                    description=(
                        f"Node alignment score is {alignment_score:.2f}.  "
                        "Snapping nodes to a 20px grid improves visual "
                        "consistency and makes the workflow easier to navigate."
                    ),
                    confidence=0.8,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "reorganize_layout",
                        "strategy": "grid_align",
                        "grid_size": 20,
                    },
                    effort="low",
                    code_example=(
                        '// Snap positions to 20px grid\n'
                        '// Before: {"position": [113, 247]}\n'
                        '// After:  {"position": [120, 240]}'
                    ),
                )
            )

        return fixes


# ---------------------------------------------------------------------------
# 11. CoordinationFixGenerator — inter-agent handoff protocols
# ---------------------------------------------------------------------------

class CoordinationFixGenerator(BaseQualityFixGenerator):
    """Generate inter-agent coordination fixes.

    When multiple agents are connected in a chain, this generator adds
    handoff protocol instructions to their system prompts so each agent
    knows what format its upstream produces and what its downstream expects.
    Also adds continueOnFail to intermediate agents to prevent silent
    chain failures.

    Triggered by low agent_coupling scores on multi-agent workflows.
    """

    def can_handle(self, dimension: str) -> bool:
        return dimension == OrchestrationDimension.AGENT_COUPLING.value

    def generate_fixes(
        self,
        dimension_score: DimensionScore,
        context: Dict[str, Any],
    ) -> List[QualityFixSuggestion]:
        fixes: List[QualityFixSuggestion] = []
        evidence = dimension_score.evidence
        workflow_id = context.get("workflow_id", "unknown")

        # Fix: Add handoff protocol instructions to connected agents
        agent_pairs = evidence.get("connected_agent_pairs", [])
        coupling_ratio = evidence.get("coupling_ratio", 0.0)

        if coupling_ratio > 0.4 and len(agent_pairs) >= 1:
            for pair in agent_pairs[:3]:  # Cap at 3 pairs
                source = pair.get("source", "Agent A")
                target = pair.get("target", "Agent B")
                fixes.append(
                    QualityFixSuggestion.create(
                        dimension=OrchestrationDimension.AGENT_COUPLING.value,
                        category=QualityFixCategory.AGENT_COUPLING,
                        title=f"Add handoff protocol: {source} -> {target}",
                        description=(
                            f"Agent '{source}' connects to '{target}' without "
                            "explicit handoff instructions. Add protocol text to "
                            f"'{source}' system prompt describing what format "
                            f"'{target}' expects, and to '{target}' describing "
                            "what it will receive."
                        ),
                        confidence=0.7,
                        expected_improvement=0.1,
                        target_type="orchestration",
                        target_id=workflow_id,
                        changes={
                            "action": "add_handoff_protocol",
                            "source_agent": source,
                            "target_agent": target,
                        },
                        effort="low",
                        code_example=(
                            f'// Add to {source} system prompt:\n'
                            f'// "Your output will be consumed by {target}. '
                            'Ensure your response is structured JSON."\n'
                            f'// Add to {target} system prompt:\n'
                            f'// "You will receive structured input from {source}."'
                        ),
                    )
                )

        # Fix: Add continueOnFail to intermediate agents in chains
        agent_count = evidence.get("agent_count", 0)
        max_chain = evidence.get("max_agent_chain", 0)
        if max_chain >= 3 and agent_count >= 3:
            fixes.append(
                QualityFixSuggestion.create(
                    dimension=OrchestrationDimension.AGENT_COUPLING.value,
                    category=QualityFixCategory.AGENT_COUPLING,
                    title="Add error resilience to agent chain",
                    description=(
                        f"Agent chain of length {max_chain} has no error "
                        "resilience. If a middle agent fails, the entire chain "
                        "fails silently. Add continueOnFail to intermediate "
                        "agents so failures are handled gracefully."
                    ),
                    confidence=0.75,
                    expected_improvement=0.1,
                    target_type="orchestration",
                    target_id=workflow_id,
                    changes={
                        "action": "set_continue_on_fail_chain",
                        "target": "intermediate_agents",
                    },
                    effort="low",
                    code_example=(
                        '// Set on each intermediate agent in the chain\n'
                        '{\n'
                        '  "continueOnFail": true,\n'
                        '  "alwaysOutputData": true\n'
                        '}'
                    ),
                )
            )

        return fixes


# ---------------------------------------------------------------------------
# Convenience: registry of all orchestration fix generators
# ---------------------------------------------------------------------------

ALL_ORCHESTRATION_FIX_GENERATORS: List[BaseQualityFixGenerator] = [
    DataFlowClarityFixGenerator(),
    ComplexityManagementFixGenerator(),
    AgentCouplingFixGenerator(),
    CoordinationFixGenerator(),
    ObservabilityFixGenerator(),
    BestPracticesFixGenerator(),
    DocumentationQualityFixGenerator(),
    AIArchitectureFixGenerator(),
    MaintenanceQualityFixGenerator(),
    TestCoverageFixGenerator(),
    LayoutQualityFixGenerator(),
]
