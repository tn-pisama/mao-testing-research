"""Workflow sample data fixtures for quality assessment tests."""

import pytest


def make_low_quality_workflow():
    """Factory: deliberately low-quality 3-node n8n workflow.

    Has: trigger + bare AI agent + output (with connections).
    Missing: system prompt, error handling, pinData, error trigger.
    Shared across healing test suites -- do not modify without running
    test_quality_healing_*.py tests.
    """
    return {
        "id": "low-quality-shared",
        "name": "Low Quality Workflow",
        "nodes": [
            {
                "id": "trigger-1",
                "name": "Webhook Trigger",
                "type": "n8n-nodes-base.webhook",
                "parameters": {"path": "/test"},
                "position": [0, 0],
            },
            {
                "id": "agent-1",
                "name": "AI Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {},
                "position": [200, 0],
            },
            {
                "id": "output-1",
                "name": "Output",
                "type": "n8n-nodes-base.respondToWebhook",
                "parameters": {},
                "position": [400, 0],
            },
        ],
        "connections": {
            "Webhook Trigger": {
                "main": [[{"node": "AI Agent", "type": "main", "index": 0}]]
            },
            "AI Agent": {
                "main": [[{"node": "Output", "type": "main", "index": 0}]]
            },
        },
        "settings": {},
    }


@pytest.fixture
def sample_workflow():
    """Sample n8n workflow JSON for quality testing."""
    return {
        "id": "wf-test-quality",
        "name": "Test Quality Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook Trigger",
                "type": "n8n-nodes-base.webhook",
                "parameters": {}
            },
            {
                "id": "2",
                "name": "Data Analyst",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "continueOnFail": True,
                "parameters": {
                    "systemMessage": "You are a data analyst. Analyze input and return JSON.",
                    "options": {
                        "temperature": 0.3,
                        "timeout": 30000,
                        "retryOnFail": True
                    }
                }
            },
            {
                "id": "3",
                "name": "Output",
                "type": "n8n-nodes-base.respond",
                "parameters": {}
            }
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Data Analyst"}]]},
            "Data Analyst": {"main": [[{"node": "Output"}]]}
        }
    }


@pytest.fixture
def sample_agent_node():
    """Sample agent node JSON for quality testing."""
    return {
        "id": "agent-test",
        "name": "Test Agent",
        "type": "@n8n/n8n-nodes-langchain.agent",
        "continueOnFail": True,
        "parameters": {
            "systemMessage": "You are a helpful assistant. Always respond in JSON format.",
            "options": {
                "temperature": 0.5,
                "timeout": 30000
            }
        }
    }


@pytest.fixture
def minimal_workflow():
    """Minimal workflow for testing low-quality scenarios."""
    return {
        "id": "wf-minimal",
        "name": "Minimal Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {}
            }
        ],
        "connections": {}
    }


@pytest.fixture
def low_quality_workflow():
    """Fixture wrapper around make_low_quality_workflow()."""
    return make_low_quality_workflow()


@pytest.fixture
def well_configured_workflow():
    """Well-configured workflow for testing high-quality scenarios."""
    return {
        "id": "wf-excellent",
        "name": "Excellent Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook Trigger",
                "type": "n8n-nodes-base.webhook",
                "parameters": {}
            },
            {
                "id": "2",
                "name": "Senior Data Analyst",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "continueOnFail": True,
                "alwaysOutputData": True,
                "parameters": {
                    "systemMessage": """You are a senior data analyst specializing in business intelligence.
Your role is to analyze data and provide actionable insights.
Your task is to examine the provided dataset and identify trends.

You must respond with a JSON object in this format:
{
  "summary": "Brief analysis summary",
  "insights": ["insight 1", "insight 2"],
  "confidence": 0.0-1.0
}

Do not make assumptions about missing data.
Only respond to data analysis requests.""",
                    "options": {
                        "temperature": 0.2,
                        "timeout": 60000,
                        "retryOnFail": True,
                        "maxRetries": 3
                    },
                    "tools": [
                        {
                            "name": "search_data",
                            "description": "Search the data warehouse",
                            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}
                        }
                    ]
                }
            },
            {
                "id": "3",
                "name": "Checkpoint",
                "type": "n8n-nodes-base.set",
                "parameters": {}
            },
            {
                "id": "4",
                "name": "Send Response",
                "type": "n8n-nodes-base.respond",
                "parameters": {}
            },
            {
                "id": "5",
                "name": "Error Handler",
                "type": "n8n-nodes-base.errorTrigger",
                "parameters": {}
            }
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Senior Data Analyst"}]]},
            "Senior Data Analyst": {"main": [[{"node": "Checkpoint"}]]},
            "Checkpoint": {"main": [[{"node": "Send Response"}]]}
        },
        "settings": {
            "saveManualExecutions": True,
            "saveDataErrorExecution": "all"
        }
    }


@pytest.fixture
def execution_history_consistent():
    """Consistent execution history for output consistency testing."""
    return [
        {"output": {"result": "A", "confidence": 0.9}},
        {"output": {"result": "B", "confidence": 0.8}},
        {"output": {"result": "C", "confidence": 0.95}},
    ]


@pytest.fixture
def execution_history_inconsistent():
    """Inconsistent execution history for output consistency testing."""
    return [
        {"output": {"result": "A", "confidence": 0.9}},
        {"output": {"answer": "B", "score": 0.8}},
        {"output": {"data": "C"}},
    ]
