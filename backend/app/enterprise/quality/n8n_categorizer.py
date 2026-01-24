"""n8n workflow categorization based on node composition."""

from enum import Enum
from typing import Dict, Any, List


class N8nWorkflowCategory(str, Enum):
    """Categories for n8n workflows based on their composition and purpose."""

    AI_MULTI_AGENT = "ai_multi_agent"  # 2+ AI nodes
    AI_SINGLE_AGENT = "ai_single_agent"  # 1 AI node
    INTEGRATION = "integration"  # 2+ third-party integrations
    AUTOMATION_SCHEDULED = "automation_scheduled"  # Cron/schedule trigger
    AUTOMATION_EVENT = "automation_event"  # Webhook trigger
    DATA_PROCESSING = "data_processing"  # Code/Set heavy
    UTILITY = "utility"  # Other


# Integration node types (third-party services)
INTEGRATION_NODE_TYPES = {
    "n8n-nodes-base.slack",
    "n8n-nodes-base.googleSheets",
    "n8n-nodes-base.googleDrive",
    "n8n-nodes-base.github",
    "n8n-nodes-base.gmail",
    "n8n-nodes-base.notion",
    "n8n-nodes-base.airtable",
    "n8n-nodes-base.discord",
    "n8n-nodes-base.telegram",
    "n8n-nodes-base.twitter",
    "n8n-nodes-base.hubspot",
    "n8n-nodes-base.salesforce",
    "n8n-nodes-base.stripe",
    "n8n-nodes-base.asana",
    "n8n-nodes-base.trello",
    "n8n-nodes-base.jira",
    "n8n-nodes-base.monday",
    "n8n-nodes-base.zoom",
}

# Data processing node types
DATA_PROCESSING_NODE_TYPES = {
    "n8n-nodes-base.code",
    "n8n-nodes-base.set",
    "n8n-nodes-base.function",
    "n8n-nodes-base.itemLists",
    "n8n-nodes-base.aggregate",
    "n8n-nodes-base.splitInBatches",
    "n8n-nodes-base.sort",
    "n8n-nodes-base.filter",
}

# Trigger node types
SCHEDULED_TRIGGER_TYPES = {
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.cronTrigger",
    "n8n-nodes-base.interval",
}

EVENT_TRIGGER_TYPES = {
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.webhookTrigger",
    "n8n-nodes-base.formTrigger",
}


def categorize_workflow(workflow: Dict[str, Any]) -> N8nWorkflowCategory:
    """
    Categorize n8n workflow by node composition.

    Args:
        workflow: n8n workflow JSON

    Returns:
        N8nWorkflowCategory enum value
    """
    nodes = workflow.get("nodes", [])

    if not nodes:
        return N8nWorkflowCategory.UTILITY

    node_types = [n.get("type", "") for n in nodes]

    # Count AI nodes (LangChain nodes)
    ai_count = sum(
        1 for t in node_types
        if "@n8n/n8n-nodes-langchain" in t or "langchain" in t.lower()
    )

    # Check for AI workflows first
    if ai_count >= 2:
        return N8nWorkflowCategory.AI_MULTI_AGENT
    elif ai_count == 1:
        return N8nWorkflowCategory.AI_SINGLE_AGENT

    # Count integration nodes
    integration_count = sum(1 for t in node_types if t in INTEGRATION_NODE_TYPES)

    if integration_count >= 2:
        return N8nWorkflowCategory.INTEGRATION

    # Check for trigger types
    has_scheduled_trigger = any(t in node_types for t in SCHEDULED_TRIGGER_TYPES)
    has_event_trigger = any(t in node_types for t in EVENT_TRIGGER_TYPES)

    if has_scheduled_trigger:
        return N8nWorkflowCategory.AUTOMATION_SCHEDULED
    elif has_event_trigger:
        return N8nWorkflowCategory.AUTOMATION_EVENT

    # Check for data processing heavy workflows
    data_processing_count = sum(
        1 for t in node_types if t in DATA_PROCESSING_NODE_TYPES
    )
    data_processing_ratio = (
        data_processing_count / len(nodes) if nodes else 0
    )

    if data_processing_ratio >= 0.4:
        return N8nWorkflowCategory.DATA_PROCESSING

    # Default to utility
    return N8nWorkflowCategory.UTILITY


def get_category_stats(workflows: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Get category distribution across multiple workflows.

    Args:
        workflows: List of n8n workflow JSONs

    Returns:
        Dictionary mapping category names to counts
    """
    from collections import Counter

    categories = [categorize_workflow(w) for w in workflows]
    return dict(Counter(cat.value for cat in categories))
