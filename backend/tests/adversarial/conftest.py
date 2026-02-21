"""Shared fixtures for adversarial gaming resistance tests.

Each fixture returns a complete workflow dict representing a specific
gaming strategy that tries to inflate quality scores without genuine quality.
"""

import os

os.environ.setdefault("JWT_SECRET", "xK9mP2vL7nQ4wR8jT5fY3hA6bD0cE1gU")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest


@pytest.fixture
def keyword_stuffed_agent():
    """Workflow with a keyword-stuffed prompt designed to trigger role/output/boundary keywords."""
    return {
        "id": "gaming-keyword-stuffed",
        "name": "Keyword Stuffed Workflow",
        "nodes": [
            {
                "id": "agent-ks",
                "name": "Stuffed Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {
                    "systemMessage": (
                        "You are you are your role your role do not do not "
                        "return JSON return JSON. You are a specialized agent. "
                        "You are very specific. Your role is to analyze."
                    ),
                    "options": {"temperature": 0.5},
                },
                "position": [0, 0],
            }
        ],
        "connections": {},
        "settings": {},
    }


@pytest.fixture
def checkbox_warrior():
    """Workflow with all n8n error-handling flags enabled but an empty prompt."""
    return {
        "id": "gaming-checkbox-warrior",
        "name": "Checkbox Warrior Workflow",
        "nodes": [
            {
                "id": "agent-cb",
                "name": "Checkbox Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "continueOnFail": True,
                "alwaysOutputData": True,
                "parameters": {
                    "systemMessage": "",
                    "options": {
                        "retryOnFail": True,
                        "maxRetries": 5,
                        "timeout": 60000,
                    },
                },
                "retryOnFail": True,
                "position": [0, 0],
            }
        ],
        "connections": {},
        "settings": {},
    }


@pytest.fixture
def tool_spam():
    """Workflow where an agent declares 20 tools with identical generic descriptions."""
    tools = [
        {"name": f"tool_{i}", "description": "This tool does things"}
        for i in range(20)
    ]
    return {
        "id": "gaming-tool-spam",
        "name": "Tool Spam Workflow",
        "nodes": [
            {
                "id": "agent-ts",
                "name": "Spammy Tool Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {
                    "systemMessage": "You are a helper.",
                    "tools": tools,
                    "options": {"temperature": 0.5},
                },
                "position": [0, 0],
            }
        ],
        "connections": {},
        "settings": {},
    }


@pytest.fixture
def score_maximizer():
    """Workflow combining all gaming techniques: keyword stuffing, checkbox flags, tool spam."""
    tools = [
        {"name": f"tool_{i}", "description": "This tool does things"}
        for i in range(20)
    ]
    return {
        "id": "gaming-score-maximizer",
        "name": "Score Maximizer Workflow",
        "nodes": [
            {
                "id": "agent-sm",
                "name": "Maximizer Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "continueOnFail": True,
                "alwaysOutputData": True,
                "parameters": {
                    "systemMessage": (
                        "You are you are your role your role do not do not "
                        "return JSON return JSON. You are a specialized agent. "
                        "You are very specific. Your role is to analyze."
                    ),
                    "tools": tools,
                    "options": {
                        "retryOnFail": True,
                        "maxRetries": 5,
                        "timeout": 60000,
                        "temperature": 0.5,
                    },
                },
                "retryOnFail": True,
                "position": [0, 0],
            }
        ],
        "connections": {},
        "settings": {},
    }
