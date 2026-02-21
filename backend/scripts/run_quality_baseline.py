#!/usr/bin/env python3
"""Run quality scoring baseline on a spectrum of test workflows.

Establishes ground truth: which workflows score high/low and whether
the scoring correctly differentiates quality levels.

Usage:
    python backend/scripts/run_quality_baseline.py
"""

import json
import sys
import os
from datetime import datetime, UTC
from pathlib import Path

# Set required env vars for standalone script execution
os.environ.setdefault("JWT_SECRET", "xK9mP2vL7nQ4wR8jT5fY3hA6bD0cE1gU")
os.environ.setdefault("DATABASE_URL", "sqlite://")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality import QualityAssessor


# --- Test Workflow Definitions ---

def make_empty_agent():
    """No prompt, no config — expected: very low score."""
    return {
        "id": "wf-empty",
        "name": "Empty Agent Workflow",
        "nodes": [
            {
                "id": "agent1",
                "name": "AI Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {},
                "position": [100, 100],
            }
        ],
        "connections": {},
        "settings": {},
    }


def make_keyword_stuffed():
    """Keyword padding to game the scorer — should score low but currently scores high."""
    return {
        "id": "wf-keyword-stuffed",
        "name": "Keyword Stuffed Workflow",
        "nodes": [
            {
                "id": "agent1",
                "name": "Stuffed Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {
                    "systemMessage": (
                        "You are you are your role your role as a as a "
                        "your task your task you will you must "
                        "respond with return output format json "
                        "provide give me answer with structure "
                        "do not don't never avoid only must not "
                        "refrain from you cannot you should not"
                    ),
                },
                "position": [100, 100],
            }
        ],
        "connections": {},
        "settings": {},
    }


def make_checkbox_warrior():
    """All config flags enabled but no meaningful prompt."""
    return {
        "id": "wf-checkbox",
        "name": "Checkbox Warrior Workflow",
        "nodes": [
            {
                "id": "agent1",
                "name": "Checkbox Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {
                    "options": {
                        "retryOnFail": True,
                        "maxRetries": 3,
                        "timeout": 30000,
                        "temperature": 0.1,
                        "maxTokens": 2000,
                    },
                },
                "continueOnFail": True,
                "alwaysOutputData": True,
                "position": [100, 100],
            }
        ],
        "connections": {},
        "settings": {},
    }


def make_genuine_basic():
    """Short but real prompt, minimal config — expected: moderate score."""
    return {
        "id": "wf-basic",
        "name": "Basic Quality Workflow",
        "nodes": [
            {
                "id": "agent1",
                "name": "Data Extractor",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {
                    "systemMessage": (
                        "You are a data extraction specialist. "
                        "Extract structured data from user-provided text. "
                        "Return results as JSON."
                    ),
                },
                "position": [100, 100],
            }
        ],
        "connections": {},
        "settings": {},
    }


def make_genuine_good():
    """Detailed prompt, proper config, error handling — expected: high score."""
    return {
        "id": "wf-good",
        "name": "Good Quality Workflow",
        "nodes": [
            {
                "id": "agent1",
                "name": "SEC Filing Analyzer",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {
                    "systemMessage": (
                        "You are a financial data extraction specialist trained on SEC filings. "
                        "Your role is to analyze 10-K and 10-Q filings and extract key financial metrics.\n\n"
                        "For each filing, extract:\n"
                        "1. Revenue (total and by segment)\n"
                        "2. Net income\n"
                        "3. EPS (basic and diluted)\n"
                        "4. Total assets and liabilities\n\n"
                        "Return results as JSON with this schema:\n"
                        '{"company": "string", "period": "string", "revenue": number, '
                        '"net_income": number, "eps_basic": number, "eps_diluted": number}\n\n'
                        "Do not hallucinate numbers. If a metric is not found, set it to null. "
                        "Do not make assumptions about missing data. "
                        "Only extract values explicitly stated in the filing."
                    ),
                    "options": {
                        "temperature": 0.1,
                        "maxTokens": 4000,
                        "retryOnFail": True,
                        "maxRetries": 2,
                        "timeout": 60000,
                    },
                },
                "continueOnFail": True,
                "alwaysOutputData": True,
                "position": [100, 100],
            },
            {
                "id": "trigger1",
                "name": "Manual Trigger",
                "type": "n8n-nodes-base.manualTrigger",
                "parameters": {},
                "position": [0, 100],
            },
        ],
        "connections": {
            "trigger1": {"main": [[{"node": "agent1", "type": "main", "index": 0}]]},
        },
        "settings": {"executionTimeout": 300},
    }


def make_production_grade():
    """Comprehensive prompt, full config, monitoring, docs — expected: near-perfect."""
    return {
        "id": "wf-production",
        "name": "Production Grade Workflow",
        "nodes": [
            {
                "id": "trigger",
                "name": "Webhook Trigger",
                "type": "n8n-nodes-base.webhook",
                "parameters": {"path": "/analyze"},
                "position": [0, 200],
            },
            {
                "id": "validator",
                "name": "Input Validator",
                "type": "n8n-nodes-base.code",
                "parameters": {
                    "code": "// Validate input schema\nif (!$input.item.json.filing_url) throw new Error('Missing filing_url');\nreturn $input.item;",
                },
                "continueOnFail": True,
                "position": [200, 200],
            },
            {
                "id": "agent1",
                "name": "SEC Filing Analyzer",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {
                    "systemMessage": (
                        "You are an SEC filing analysis specialist with expertise in 10-K, 10-Q, "
                        "and 8-K filings. Your role is to extract and validate financial metrics "
                        "from regulatory documents.\n\n"
                        "## Task\n"
                        "Analyze the provided filing and extract key financial metrics.\n\n"
                        "## Output Format\n"
                        "Return JSON matching this exact schema:\n"
                        "```json\n"
                        '{"company": "string", "ticker": "string", "period": "Q1-Q4 or FY", '
                        '"fiscal_year": 2024, "revenue_total": 0.0, "revenue_segments": [], '
                        '"net_income": 0.0, "eps_basic": 0.0, "eps_diluted": 0.0, '
                        '"total_assets": 0.0, "total_liabilities": 0.0, '
                        '"confidence": 0.0, "source_pages": []}\n'
                        "```\n\n"
                        "## Rules\n"
                        "1. Do not hallucinate or estimate numbers — only extract explicitly stated values\n"
                        "2. Set any missing metric to null, never guess\n"
                        "3. Include confidence score (0.0-1.0) based on data completeness\n"
                        "4. Reference source page numbers for each extracted value\n"
                        "5. If the document is not an SEC filing, return {\"error\": \"not_sec_filing\"}\n"
                        "6. Never output data from a different company or period than requested"
                    ),
                    "options": {
                        "temperature": 0.0,
                        "maxTokens": 4000,
                        "model": "claude-3-5-sonnet-20241022",
                        "retryOnFail": True,
                        "maxRetries": 3,
                        "timeout": 120000,
                    },
                    "tools": {
                        "values": [
                            {
                                "name": "fetch_filing",
                                "description": "Fetch SEC filing content from EDGAR URL",
                                "parameters": {"type": "object", "properties": {"url": {"type": "string"}}},
                            },
                            {
                                "name": "validate_ticker",
                                "description": "Validate company ticker symbol against SEC database",
                                "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}},
                            },
                        ]
                    },
                },
                "continueOnFail": True,
                "alwaysOutputData": True,
                "position": [400, 200],
            },
            {
                "id": "checkpoint",
                "name": "Checkpoint: Validate Output",
                "type": "n8n-nodes-base.set",
                "parameters": {
                    "values": {
                        "string": [
                            {"name": "stage", "value": "post_extraction"},
                            {"name": "has_output", "value": '={{$json.revenue_total !== null ? "true" : "false"}}'},
                        ]
                    }
                },
                "position": [600, 200],
            },
            {
                "id": "error_handler",
                "name": "Error Handler",
                "type": "n8n-nodes-base.errorTrigger",
                "parameters": {},
                "position": [400, 400],
            },
            {
                "id": "docs",
                "name": "Workflow Documentation",
                "type": "n8n-nodes-base.stickyNote",
                "parameters": {
                    "content": (
                        "## SEC Filing Analysis Pipeline\n\n"
                        "This workflow extracts financial metrics from SEC filings.\n\n"
                        "### Stages\n"
                        "1. Webhook receives filing URL\n"
                        "2. Input validator checks required fields\n"
                        "3. AI agent extracts financial metrics\n"
                        "4. Checkpoint validates extraction output\n\n"
                        "### Error Handling\n"
                        "- Input validation failures return 400\n"
                        "- Agent failures retry up to 3 times\n"
                        "- Error trigger logs to monitoring\n\n"
                        "### Monitoring\n"
                        "Errors are sent to the error handler for alerting."
                    ),
                },
                "position": [0, 0],
            },
        ],
        "connections": {
            "trigger": {"main": [[{"node": "validator", "type": "main", "index": 0}]]},
            "validator": {"main": [[{"node": "agent1", "type": "main", "index": 0}]]},
            "agent1": {"main": [[{"node": "checkpoint", "type": "main", "index": 0}]]},
        },
        "settings": {
            "executionTimeout": 300,
            "saveManualExecutions": True,
            "saveDataErrorExecution": "all",
        },
    }


def make_score_maximizer():
    """Combines all gaming techniques — proves gaming is currently possible."""
    return {
        "id": "wf-gaming",
        "name": "Score Maximizer (Gaming)",
        "nodes": [
            {
                "id": "agent1",
                "name": "Gamed Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {
                    "systemMessage": (
                        "You are a data analyst. Your role is to analyze data. "
                        "As a professional, your task is to process inputs. "
                        "You will analyze and you must be accurate. "
                        "Your purpose is to deliver results. Your job is important.\n"
                        "Respond with JSON format: {\"result\": \"...\", \"confidence\": 0.5}. "
                        "Return structured output. Provide answer with clear structure.\n"
                        "Do not hallucinate. Don't assume. Never guess. Avoid speculation. "
                        "Only use provided data. Must not fabricate. "
                        "Refrain from making things up. You cannot invent data. "
                        "You should not extrapolate beyond the evidence."
                    ),
                    "options": {
                        "temperature": 0.1,
                        "maxTokens": 2000,
                        "model": "claude-3-5-haiku-20241022",
                        "retryOnFail": True,
                        "maxRetries": 3,
                        "timeout": 30000,
                    },
                    "tools": {
                        "values": [
                            {"name": "tool1", "description": "A useful tool", "parameters": {"type": "object"}},
                            {"name": "tool2", "description": "Another tool", "parameters": {"type": "object"}},
                        ]
                    },
                },
                "continueOnFail": True,
                "alwaysOutputData": True,
                "position": [100, 100],
            }
        ],
        "connections": {},
        "settings": {"executionTimeout": 300},
    }


# --- Run Baseline ---

def run_baseline():
    """Run quality assessment on all test workflows and save results."""
    assessor = QualityAssessor(use_llm_judge=False, include_reasoning=True)

    workflows = {
        "empty_agent": make_empty_agent(),
        "keyword_stuffed": make_keyword_stuffed(),
        "checkbox_warrior": make_checkbox_warrior(),
        "genuine_basic": make_genuine_basic(),
        "genuine_good": make_genuine_good(),
        "production_grade": make_production_grade(),
        "score_maximizer": make_score_maximizer(),
    }

    results = {}
    print("=" * 70)
    print("QUALITY SCORING BASELINE")
    print("=" * 70)

    for name, workflow in workflows.items():
        report = assessor.assess_workflow(workflow)

        # Extract dimension scores per agent
        agent_dims = {}
        for agent in report.agent_scores:
            for dim in agent.dimensions:
                agent_dims[dim.dimension] = {
                    "score": round(dim.score, 3),
                    "issues": dim.issues,
                    "evidence": {k: v for k, v in dim.evidence.items() if not callable(v)},
                }

        # Extract orchestration dimension scores
        orch_dims = {}
        for dim in report.orchestration_score.dimensions:
            orch_dims[dim.dimension] = {
                "score": round(dim.score, 3),
                "issues": dim.issues,
            }

        result = {
            "workflow_name": workflow["name"],
            "overall_score": round(report.overall_score, 3),
            "overall_grade": report.overall_grade,
            "agent_dimensions": agent_dims,
            "orchestration_dimensions": orch_dims,
            "orchestration_overall": round(report.orchestration_score.overall_score, 3),
            "reasoning": report.reasoning,
            "improvements_count": len(report.improvements),
            "critical_issues": report.critical_issues_count,
        }
        results[name] = result

        # Print summary
        print(f"\n{'─' * 50}")
        print(f"  {name}: {report.overall_grade} ({report.overall_score:.0%})")
        print(f"  Agent dimensions:")
        for dim_name, dim_data in agent_dims.items():
            print(f"    {dim_name}: {dim_data['score']:.0%}")
        print(f"  Orchestration: {report.orchestration_score.overall_score:.0%}")
        if report.reasoning:
            print(f"  Reasoning: {report.reasoning[:120]}...")

    # Print comparison table
    print(f"\n{'=' * 70}")
    print("COMPARISON TABLE")
    print(f"{'=' * 70}")
    print(f"{'Workflow':<20} {'Overall':>8} {'Grade':>6} {'Gaming?':>8}")
    print(f"{'─' * 50}")

    expected_order = [
        ("empty_agent", False),
        ("keyword_stuffed", True),
        ("checkbox_warrior", True),
        ("genuine_basic", False),
        ("genuine_good", False),
        ("production_grade", False),
        ("score_maximizer", True),
    ]

    for name, is_gaming in expected_order:
        r = results[name]
        gaming_flag = "GAMING" if is_gaming else ""
        print(f"  {name:<20} {r['overall_score']:>7.0%} {r['overall_grade']:>6} {gaming_flag:>8}")

    # Check if gaming works
    gaming_detected = (
        results["keyword_stuffed"]["overall_score"] > results["genuine_basic"]["overall_score"]
        or results["score_maximizer"]["overall_score"] > results["genuine_good"]["overall_score"]
    )

    print(f"\n{'=' * 70}")
    if gaming_detected:
        print("WARNING: Gaming techniques score HIGHER than genuine quality!")
        print("This confirms the scoring system is gameable and needs LLM-based evaluation.")
    else:
        print("OK: Genuine workflows score higher than gaming attempts.")
    print(f"{'=' * 70}")

    # Save results
    output_dir = Path(__file__).parent.parent / "data" / "baselines"
    output_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "assessor_config": {"use_llm_judge": False, "scoring_mode": "heuristic_only"},
        "results": results,
        "gaming_detected": gaming_detected,
    }

    output_file = output_dir / f"quality_baseline_{datetime.now(UTC).strftime('%Y%m%d')}.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")
    return results


if __name__ == "__main__":
    run_baseline()
