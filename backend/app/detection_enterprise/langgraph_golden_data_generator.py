"""LangGraph-native golden dataset generator with token-optimized Claude API calls.

Subclasses GoldenDataGenerator to produce LangGraph-specific test data using:
- Prompt caching for the shared LangGraph vocabulary system message
- Tiered model selection (Haiku for easy, Sonnet for medium/hard)
- Compact output format expanded client-side
- Batch generation with incremental persistence and resume support
- Graph execution templates covering all LangGraph graph types
"""

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDataset, GoldenDatasetEntry
from app.detection_enterprise.golden_data_generator import (
    GoldenDataGenerator,
    DIFFICULTY_INSTRUCTIONS,
    _parse_json,
)

logger = logging.getLogger(__name__)

try:
    from anthropic import Anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False


# ---------------------------------------------------------------------------
# Core detection types (universal across all platforms)
# ---------------------------------------------------------------------------

CORE_TYPES = [
    "loop", "corruption", "persona_drift", "hallucination", "injection",
    "overflow", "coordination", "communication", "derailment", "context",
    "specification", "decomposition", "withholding", "completion",
    "grounding", "retrieval_quality", "workflow",
]


# ---------------------------------------------------------------------------
# LangGraph system message (cached across all API calls)
# ---------------------------------------------------------------------------

LANGGRAPH_SYSTEM_MESSAGE = """You are a precise test data generator for LangGraph graph execution failure detection.

## LangGraph Node Types (use these exactly)
LLM: llm
Tool: tool
Router: router
Human: human
Subgraph: subgraph
Passthrough: passthrough
Map-Reduce: map_reduce

## LangGraph Graph Types
StateGraph, MessageGraph, CompiledGraph

## LangGraph Edge Types
fixed, conditional, send

## LangGraph Graph Execution Status Values
completed, failed, interrupted, timeout, recursion_limit

## LangGraph Node Status Values
succeeded, failed, interrupted, skipped

## State Management
State channels, reducers (operator.add, Annotated), state_schema, state_snapshots.
Superstep-based execution model: nodes within the same superstep execute in parallel, supersteps are synchronized sequentially.

## Persistence & Human-in-the-Loop
Checkpoints, checkpoint_ns, thread_id, interrupt/resume.
Special nodes: __start__, __end__.

## LangGraph Graph Execution JSON Format
{"graph_id": "graph-xxx", "thread_id": "thread-xxx", "graph_type": "<StateGraph|MessageGraph|CompiledGraph>", "started_at": "ISO8601", "finished_at": "ISO8601", "status": "<completed|failed|interrupted|timeout|recursion_limit>", "total_tokens": N, "total_supersteps": N, "recursion_limit": N, "state_schema": {"keys": ["messages", "context", ...]}, "nodes": [{"node_id": "n1", "node_type": "<type>", "title": "NodeTitle", "superstep": N, "status": "<status>", "inputs": {...}, "outputs": {...}, "token_count": N, "error": null, "metadata": {}, "started_at": "ISO8601", "finished_at": "ISO8601"}], "edges": [{"source": "n1", "target": "n2", "edge_type": "<fixed|conditional|send>", "condition": null}], "checkpoints": [{"checkpoint_id": "cp-xxx", "superstep": N, "state": {...}, "timestamp": "ISO8601"}], "state_snapshots": [{"superstep": N, "state": {...}}]}

## Superstep Execution Model
Nodes with the same superstep value execute in parallel.
Supersteps are processed sequentially (0, 1, 2, ...).
A node at superstep N cannot start until all nodes at superstep N-1 have completed.

## Compact Output Format
Return entries as: {"d": <input_data>, "e": <bool>, "mn": <float>, "mx": <float>, "desc": "<string>", "t": [<tags>]}
Where: d=input_data, e=expected_detected, mn=expected_confidence_min, mx=expected_confidence_max, desc=description, t=tags.
Always return a JSON array of these objects.

## Data Quality Rules
- Use unique, realistic graph_id values (graph-xxx format)
- Use unique thread_id values (thread-xxx format)
- Node IDs should be sequential (n1, n2, n3...)
- token_count must be non-negative integers (0 for non-LLM nodes)
- total_tokens should roughly equal sum of node token_counts
- total_supersteps should equal max superstep + 1
- For LangGraph-specific types, wrap input_data in {"graph_execution": {...}}
- For universal types (loop, corruption, etc.), use the type's native schema
- All timestamps must be valid ISO 8601
- superstep values must be non-negative integers
- Edge source/target must reference valid node_ids
- recursion_limit must be a positive integer when present

## Model Names (use these)
Claude: claude-sonnet-4-20250514, claude-haiku-4-5-20251001
OpenAI: gpt-4o, gpt-4o-mini
"""


# ---------------------------------------------------------------------------
# Graph Execution Templates (T0-T9)
# ---------------------------------------------------------------------------

GRAPH_EXECUTION_TEMPLATES = [
    # T0: Research Agent (researcher -> analyst -> writer, fixed edges)
    {
        "graph_id": "graph-t0", "thread_id": "thread-research-001",
        "graph_type": "StateGraph",
        "status": "completed", "total_tokens": 4500, "total_supersteps": 3,
        "recursion_limit": 25,
        "state_schema": {"keys": ["messages", "research_data", "analysis", "draft"]},
        "nodes": [
            {"node_id": "n1", "node_type": "llm", "title": "Researcher", "superstep": 0, "status": "succeeded",
             "inputs": {"query": "Analyze the impact of transformer architectures on NLP"},
             "outputs": {"research_data": "Transformers introduced self-attention mechanisms..."},
             "token_count": 1500},
            {"node_id": "n2", "node_type": "llm", "title": "Analyst", "superstep": 1, "status": "succeeded",
             "inputs": {"research_data": "{{n1.outputs.research_data}}"},
             "outputs": {"analysis": "Key findings: 1) Self-attention scales quadratically..."},
             "token_count": 1200},
            {"node_id": "n3", "node_type": "llm", "title": "Writer", "superstep": 2, "status": "succeeded",
             "inputs": {"analysis": "{{n2.outputs.analysis}}"},
             "outputs": {"draft": "Transformer architectures have fundamentally reshaped NLP..."},
             "token_count": 1800},
        ],
        "edges": [
            {"source": "__start__", "target": "n1", "edge_type": "fixed"},
            {"source": "n1", "target": "n2", "edge_type": "fixed"},
            {"source": "n2", "target": "n3", "edge_type": "fixed"},
            {"source": "n3", "target": "__end__", "edge_type": "fixed"},
        ],
    },
    # T1: Customer Support Router (classifier -> [technical, billing, general], conditional)
    {
        "graph_id": "graph-t1", "thread_id": "thread-support-001",
        "graph_type": "StateGraph",
        "status": "completed", "total_tokens": 2200, "total_supersteps": 2,
        "recursion_limit": 10,
        "state_schema": {"keys": ["messages", "category", "response"]},
        "nodes": [
            {"node_id": "n1", "node_type": "router", "title": "Classifier", "superstep": 0, "status": "succeeded",
             "inputs": {"query": "My API key stopped working after the last update"},
             "outputs": {"category": "technical", "confidence": 0.94},
             "token_count": 300},
            {"node_id": "n2", "node_type": "llm", "title": "Technical Support", "superstep": 1, "status": "succeeded",
             "inputs": {"query": "{{n1.inputs.query}}", "category": "technical"},
             "outputs": {"response": "API keys were rotated in the latest update. Please regenerate your key from Settings > API Keys."},
             "token_count": 800},
        ],
        "edges": [
            {"source": "__start__", "target": "n1", "edge_type": "fixed"},
            {"source": "n1", "target": "n2", "edge_type": "conditional", "condition": "category == 'technical'"},
            {"source": "n1", "target": "n3", "edge_type": "conditional", "condition": "category == 'billing'"},
            {"source": "n1", "target": "n4", "edge_type": "conditional", "condition": "category == 'general'"},
            {"source": "n2", "target": "__end__", "edge_type": "fixed"},
        ],
    },
    # T2: RAG Pipeline (retriever -> grader -> generator -> hallucination_check)
    {
        "graph_id": "graph-t2", "thread_id": "thread-rag-001",
        "graph_type": "StateGraph",
        "status": "completed", "total_tokens": 3800, "total_supersteps": 4,
        "recursion_limit": 15,
        "state_schema": {"keys": ["messages", "documents", "relevance_scores", "answer", "hallucination_score"]},
        "nodes": [
            {"node_id": "n1", "node_type": "tool", "title": "Retriever", "superstep": 0, "status": "succeeded",
             "inputs": {"query": "What are the GDPR data retention requirements?"},
             "outputs": {"documents": [
                 {"content": "Under GDPR Article 5(1)(e), data must not be kept longer than necessary...", "score": 0.92},
                 {"content": "Data retention periods vary by purpose and legal basis...", "score": 0.87},
             ]},
             "token_count": 0},
            {"node_id": "n2", "node_type": "llm", "title": "Grader", "superstep": 1, "status": "succeeded",
             "inputs": {"documents": "{{n1.outputs.documents}}", "query": "{{n1.inputs.query}}"},
             "outputs": {"relevant_docs": [0, 1], "relevance_scores": [0.92, 0.87]},
             "token_count": 600},
            {"node_id": "n3", "node_type": "llm", "title": "Generator", "superstep": 2, "status": "succeeded",
             "inputs": {"documents": "{{n1.outputs.documents}}", "query": "{{n1.inputs.query}}"},
             "outputs": {"answer": "Under GDPR Article 5(1)(e), personal data must not be kept longer than necessary for the purposes for which it is processed."},
             "token_count": 1500},
            {"node_id": "n4", "node_type": "llm", "title": "Hallucination Check", "superstep": 3, "status": "succeeded",
             "inputs": {"answer": "{{n3.outputs.answer}}", "documents": "{{n1.outputs.documents}}"},
             "outputs": {"hallucination_score": 0.05, "grounded": True},
             "token_count": 700},
        ],
        "edges": [
            {"source": "__start__", "target": "n1", "edge_type": "fixed"},
            {"source": "n1", "target": "n2", "edge_type": "fixed"},
            {"source": "n2", "target": "n3", "edge_type": "fixed"},
            {"source": "n3", "target": "n4", "edge_type": "fixed"},
            {"source": "n4", "target": "__end__", "edge_type": "fixed"},
        ],
    },
    # T3: Multi-Tool Agent (planner -> tool_executor -> summarizer)
    {
        "graph_id": "graph-t3", "thread_id": "thread-agent-001",
        "graph_type": "StateGraph",
        "status": "completed", "total_tokens": 3500, "total_supersteps": 3,
        "recursion_limit": 30,
        "state_schema": {"keys": ["messages", "plan", "tool_results", "summary"]},
        "nodes": [
            {"node_id": "n1", "node_type": "llm", "title": "Planner", "superstep": 0, "status": "succeeded",
             "inputs": {"query": "Find the weather in Tokyo and convert 100 USD to JPY"},
             "outputs": {"plan": ["search_weather:Tokyo", "convert_currency:USD:JPY:100"]},
             "token_count": 800},
            {"node_id": "n2", "node_type": "tool", "title": "Tool Executor", "superstep": 1, "status": "succeeded",
             "inputs": {"actions": ["search_weather:Tokyo", "convert_currency:USD:JPY:100"]},
             "outputs": {"results": [
                 {"tool": "search_weather", "result": {"temp": 22, "condition": "cloudy"}},
                 {"tool": "convert_currency", "result": {"amount": 15340.50, "rate": 153.405}},
             ]},
             "token_count": 0},
            {"node_id": "n3", "node_type": "llm", "title": "Summarizer", "superstep": 2, "status": "succeeded",
             "inputs": {"tool_results": "{{n2.outputs.results}}"},
             "outputs": {"summary": "Tokyo weather: 22C, cloudy. 100 USD = 15,340.50 JPY (rate: 153.405)."},
             "token_count": 600},
        ],
        "edges": [
            {"source": "__start__", "target": "n1", "edge_type": "fixed"},
            {"source": "n1", "target": "n2", "edge_type": "fixed"},
            {"source": "n2", "target": "n3", "edge_type": "fixed"},
            {"source": "n3", "target": "__end__", "edge_type": "fixed"},
        ],
    },
    # T4: Map-Reduce Analyzer (splitter -> [analyzer_0..N] -> aggregator, Send API)
    {
        "graph_id": "graph-t4", "thread_id": "thread-mapreduce-001",
        "graph_type": "StateGraph",
        "status": "completed", "total_tokens": 6000, "total_supersteps": 3,
        "recursion_limit": 50,
        "state_schema": {"keys": ["messages", "documents", "analyses", "final_report"]},
        "nodes": [
            {"node_id": "n1", "node_type": "llm", "title": "Splitter", "superstep": 0, "status": "succeeded",
             "inputs": {"documents": ["doc_financial.pdf", "doc_legal.pdf", "doc_technical.pdf"]},
             "outputs": {"chunks": [
                 {"id": "chunk_0", "source": "doc_financial.pdf"},
                 {"id": "chunk_1", "source": "doc_legal.pdf"},
                 {"id": "chunk_2", "source": "doc_technical.pdf"},
             ]},
             "token_count": 400},
            {"node_id": "n2_0", "node_type": "map_reduce", "title": "Analyzer 0", "superstep": 1, "status": "succeeded",
             "inputs": {"chunk": {"id": "chunk_0", "source": "doc_financial.pdf"}},
             "outputs": {"analysis": "Financial risk assessment: moderate exposure in Q4..."},
             "token_count": 1200},
            {"node_id": "n2_1", "node_type": "map_reduce", "title": "Analyzer 1", "superstep": 1, "status": "succeeded",
             "inputs": {"chunk": {"id": "chunk_1", "source": "doc_legal.pdf"}},
             "outputs": {"analysis": "Legal compliance: 3 clauses require amendment..."},
             "token_count": 1100},
            {"node_id": "n2_2", "node_type": "map_reduce", "title": "Analyzer 2", "superstep": 1, "status": "succeeded",
             "inputs": {"chunk": {"id": "chunk_2", "source": "doc_technical.pdf"}},
             "outputs": {"analysis": "Technical feasibility: architecture supports 10K RPS..."},
             "token_count": 1000},
            {"node_id": "n3", "node_type": "llm", "title": "Aggregator", "superstep": 2, "status": "succeeded",
             "inputs": {"analyses": ["{{n2_0.outputs.analysis}}", "{{n2_1.outputs.analysis}}", "{{n2_2.outputs.analysis}}"]},
             "outputs": {"final_report": "Cross-document analysis: moderate financial risk, 3 legal amendments needed, architecture is scalable."},
             "token_count": 2300},
        ],
        "edges": [
            {"source": "__start__", "target": "n1", "edge_type": "fixed"},
            {"source": "n1", "target": "n2_0", "edge_type": "send"},
            {"source": "n1", "target": "n2_1", "edge_type": "send"},
            {"source": "n1", "target": "n2_2", "edge_type": "send"},
            {"source": "n2_0", "target": "n3", "edge_type": "fixed"},
            {"source": "n2_1", "target": "n3", "edge_type": "fixed"},
            {"source": "n2_2", "target": "n3", "edge_type": "fixed"},
            {"source": "n3", "target": "__end__", "edge_type": "fixed"},
        ],
    },
    # T5: Human-in-the-Loop (drafter -> reviewer (interrupt) -> editor)
    {
        "graph_id": "graph-t5", "thread_id": "thread-hitl-001",
        "graph_type": "StateGraph",
        "status": "completed", "total_tokens": 3200, "total_supersteps": 3,
        "recursion_limit": 10,
        "state_schema": {"keys": ["messages", "draft", "review_feedback", "final_output"]},
        "nodes": [
            {"node_id": "n1", "node_type": "llm", "title": "Drafter", "superstep": 0, "status": "succeeded",
             "inputs": {"task": "Write a product announcement for our new API versioning feature"},
             "outputs": {"draft": "We are excited to announce API v2.0 with breaking changes..."},
             "token_count": 1200},
            {"node_id": "n2", "node_type": "human", "title": "Reviewer", "superstep": 1, "status": "succeeded",
             "inputs": {"draft": "{{n1.outputs.draft}}"},
             "outputs": {"feedback": "Remove 'breaking changes' phrasing, emphasize backward compatibility", "approved": False},
             "token_count": 0},
            {"node_id": "n3", "node_type": "llm", "title": "Editor", "superstep": 2, "status": "succeeded",
             "inputs": {"draft": "{{n1.outputs.draft}}", "feedback": "{{n2.outputs.feedback}}"},
             "outputs": {"final_output": "We are thrilled to introduce API v2.0, fully backward compatible with v1..."},
             "token_count": 1000},
        ],
        "edges": [
            {"source": "__start__", "target": "n1", "edge_type": "fixed"},
            {"source": "n1", "target": "n2", "edge_type": "fixed"},
            {"source": "n2", "target": "n3", "edge_type": "fixed"},
            {"source": "n3", "target": "__end__", "edge_type": "fixed"},
        ],
        "checkpoints": [
            {"checkpoint_id": "cp-before-review", "superstep": 1, "state": {"draft": "We are excited..."}, "timestamp": "2025-10-15T10:30:00Z"},
        ],
    },
    # T6: Code Review Pipeline (code_parser -> scanner -> reviewer -> fixer, conditional loop)
    {
        "graph_id": "graph-t6", "thread_id": "thread-codereview-001",
        "graph_type": "StateGraph",
        "status": "completed", "total_tokens": 4800, "total_supersteps": 4,
        "recursion_limit": 20,
        "state_schema": {"keys": ["messages", "code", "scan_results", "review", "fixed_code", "iteration"]},
        "nodes": [
            {"node_id": "n1", "node_type": "tool", "title": "Code Parser", "superstep": 0, "status": "succeeded",
             "inputs": {"code": "def process(data):\n    eval(data['cmd'])\n    return data"},
             "outputs": {"ast": {"functions": ["process"], "calls": ["eval"]}, "loc": 3},
             "token_count": 0},
            {"node_id": "n2", "node_type": "tool", "title": "Security Scanner", "superstep": 1, "status": "succeeded",
             "inputs": {"ast": "{{n1.outputs.ast}}"},
             "outputs": {"vulnerabilities": [{"type": "code_injection", "severity": "critical", "line": 2}]},
             "token_count": 0},
            {"node_id": "n3", "node_type": "llm", "title": "Reviewer", "superstep": 2, "status": "succeeded",
             "inputs": {"code": "{{n1.inputs.code}}", "vulnerabilities": "{{n2.outputs.vulnerabilities}}"},
             "outputs": {"review": "Critical: eval() on user input enables arbitrary code execution. Replace with safe parser.", "needs_fix": True},
             "token_count": 1500},
            {"node_id": "n4", "node_type": "llm", "title": "Fixer", "superstep": 3, "status": "succeeded",
             "inputs": {"code": "{{n1.inputs.code}}", "review": "{{n3.outputs.review}}"},
             "outputs": {"fixed_code": "def process(data):\n    cmd = data.get('cmd', '')\n    if cmd in ALLOWED_COMMANDS:\n        return run_safe(cmd, data)\n    raise ValueError('Invalid command')"},
             "token_count": 1200},
        ],
        "edges": [
            {"source": "__start__", "target": "n1", "edge_type": "fixed"},
            {"source": "n1", "target": "n2", "edge_type": "fixed"},
            {"source": "n2", "target": "n3", "edge_type": "fixed"},
            {"source": "n3", "target": "n4", "edge_type": "conditional", "condition": "needs_fix == True"},
            {"source": "n3", "target": "__end__", "edge_type": "conditional", "condition": "needs_fix == False"},
            {"source": "n4", "target": "n1", "edge_type": "conditional", "condition": "iteration < max_iterations"},
            {"source": "n4", "target": "__end__", "edge_type": "conditional", "condition": "iteration >= max_iterations"},
        ],
    },
    # T7: Data Processing (ingester -> validator -> transformer -> loader)
    {
        "graph_id": "graph-t7", "thread_id": "thread-etl-001",
        "graph_type": "StateGraph",
        "status": "completed", "total_tokens": 1800, "total_supersteps": 4,
        "recursion_limit": 10,
        "state_schema": {"keys": ["raw_data", "validated_data", "transformed_data", "load_result"]},
        "nodes": [
            {"node_id": "n1", "node_type": "tool", "title": "Ingester", "superstep": 0, "status": "succeeded",
             "inputs": {"source": "s3://data-lake/raw/users_2025_q4.csv"},
             "outputs": {"records": 15420, "schema": {"columns": ["id", "name", "email", "signup_date"]}},
             "token_count": 0},
            {"node_id": "n2", "node_type": "tool", "title": "Validator", "superstep": 1, "status": "succeeded",
             "inputs": {"records": 15420, "rules": ["email_format", "date_format", "no_duplicates"]},
             "outputs": {"valid": 15380, "invalid": 40, "errors": [{"rule": "email_format", "count": 25}, {"rule": "date_format", "count": 15}]},
             "token_count": 0},
            {"node_id": "n3", "node_type": "llm", "title": "Transformer", "superstep": 2, "status": "succeeded",
             "inputs": {"valid_records": 15380, "transform_rules": "normalize_emails, parse_dates, add_cohort_label"},
             "outputs": {"transformed": 15380, "new_columns": ["normalized_email", "signup_cohort"]},
             "token_count": 800},
            {"node_id": "n4", "node_type": "tool", "title": "Loader", "superstep": 3, "status": "succeeded",
             "inputs": {"destination": "warehouse://analytics.users", "records": 15380},
             "outputs": {"loaded": 15380, "duration_ms": 3420},
             "token_count": 0},
        ],
        "edges": [
            {"source": "__start__", "target": "n1", "edge_type": "fixed"},
            {"source": "n1", "target": "n2", "edge_type": "fixed"},
            {"source": "n2", "target": "n3", "edge_type": "fixed"},
            {"source": "n3", "target": "n4", "edge_type": "fixed"},
            {"source": "n4", "target": "__end__", "edge_type": "fixed"},
        ],
    },
    # T8: Debate System (proposer -> critic -> judge, loop or end)
    {
        "graph_id": "graph-t8", "thread_id": "thread-debate-001",
        "graph_type": "StateGraph",
        "status": "completed", "total_tokens": 5500, "total_supersteps": 4,
        "recursion_limit": 15,
        "state_schema": {"keys": ["messages", "topic", "proposal", "critique", "verdict", "round"]},
        "nodes": [
            {"node_id": "n1", "node_type": "llm", "title": "Proposer", "superstep": 0, "status": "succeeded",
             "inputs": {"topic": "Should AI systems be open-sourced by default?"},
             "outputs": {"proposal": "Yes, open-source AI promotes transparency, reproducibility, and democratizes access..."},
             "token_count": 1200},
            {"node_id": "n2", "node_type": "llm", "title": "Critic", "superstep": 1, "status": "succeeded",
             "inputs": {"proposal": "{{n1.outputs.proposal}}"},
             "outputs": {"critique": "While transparency is valuable, unrestricted open-source of powerful AI creates dual-use risks..."},
             "token_count": 1400},
            {"node_id": "n3", "node_type": "llm", "title": "Judge", "superstep": 2, "status": "succeeded",
             "inputs": {"proposal": "{{n1.outputs.proposal}}", "critique": "{{n2.outputs.critique}}"},
             "outputs": {"verdict": "Both arguments have merit. Recommendation: tiered open-source with safety evaluations.", "converged": True, "score": 0.78},
             "token_count": 1500},
        ],
        "edges": [
            {"source": "__start__", "target": "n1", "edge_type": "fixed"},
            {"source": "n1", "target": "n2", "edge_type": "fixed"},
            {"source": "n2", "target": "n3", "edge_type": "fixed"},
            {"source": "n3", "target": "n1", "edge_type": "conditional", "condition": "converged == False"},
            {"source": "n3", "target": "__end__", "edge_type": "conditional", "condition": "converged == True"},
        ],
    },
    # T9: Hierarchical Subgraph (orchestrator -> subgraph_research -> subgraph_writing -> combiner)
    {
        "graph_id": "graph-t9", "thread_id": "thread-hierarchical-001",
        "graph_type": "CompiledGraph",
        "status": "completed", "total_tokens": 7200, "total_supersteps": 4,
        "recursion_limit": 40,
        "state_schema": {"keys": ["messages", "task", "research_output", "writing_output", "final_document"]},
        "nodes": [
            {"node_id": "n1", "node_type": "llm", "title": "Orchestrator", "superstep": 0, "status": "succeeded",
             "inputs": {"task": "Create a comprehensive report on quantum computing market trends"},
             "outputs": {"research_brief": "Investigate market size, key players, and growth projections", "writing_brief": "Structure as executive summary + 3 sections"},
             "token_count": 600},
            {"node_id": "n2", "node_type": "subgraph", "title": "Research Subgraph", "superstep": 1, "status": "succeeded",
             "inputs": {"brief": "{{n1.outputs.research_brief}}"},
             "outputs": {"research_output": "Quantum computing market: $1.3B in 2025, projected $5.3B by 2030. Key players: IBM, Google, IonQ..."},
             "token_count": 2800,
             "metadata": {"subgraph_id": "sg-research", "subgraph_nodes": 3, "subgraph_supersteps": 2}},
            {"node_id": "n3", "node_type": "subgraph", "title": "Writing Subgraph", "superstep": 2, "status": "succeeded",
             "inputs": {"brief": "{{n1.outputs.writing_brief}}", "research": "{{n2.outputs.research_output}}"},
             "outputs": {"writing_output": "Executive Summary: The quantum computing market is experiencing rapid growth..."},
             "token_count": 2400,
             "metadata": {"subgraph_id": "sg-writing", "subgraph_nodes": 2, "subgraph_supersteps": 2}},
            {"node_id": "n4", "node_type": "llm", "title": "Combiner", "superstep": 3, "status": "succeeded",
             "inputs": {"research": "{{n2.outputs.research_output}}", "writing": "{{n3.outputs.writing_output}}"},
             "outputs": {"final_document": "Quantum Computing Market Trends 2025-2030\n\nExecutive Summary: ..."},
             "token_count": 1400},
        ],
        "edges": [
            {"source": "__start__", "target": "n1", "edge_type": "fixed"},
            {"source": "n1", "target": "n2", "edge_type": "fixed"},
            {"source": "n2", "target": "n3", "edge_type": "fixed"},
            {"source": "n3", "target": "n4", "edge_type": "fixed"},
            {"source": "n4", "target": "__end__", "edge_type": "fixed"},
        ],
    },
]

# Graph type + business domain pairs for scenario diversity
GRAPH_TYPE_DOMAINS = [
    ("StateGraph", "autonomous-agents"), ("StateGraph", "customer-support"),
    ("MessageGraph", "chatbot-pipeline"), ("StateGraph", "data-processing"),
    ("CompiledGraph", "enterprise-rag"), ("StateGraph", "code-review"),
    ("StateGraph", "content-generation"), ("MessageGraph", "healthcare"),
    ("CompiledGraph", "financial-analysis"), ("StateGraph", "devops-automation"),
    ("StateGraph", "legal-review"), ("MessageGraph", "education"),
]


# ---------------------------------------------------------------------------
# Compact output key mapping
# ---------------------------------------------------------------------------

_COMPACT_KEYS = {
    "d": "input_data",
    "e": "expected_detected",
    "mn": "expected_confidence_min",
    "mx": "expected_confidence_max",
    "desc": "description",
    "t": "tags",
}

# Types that use full graph_execution JSON (larger output, smaller batch size)
_GRAPH_EXECUTION_TYPES = {
    "langgraph_recursion", "langgraph_state_corruption", "langgraph_edge_misroute",
    "langgraph_tool_failure", "langgraph_parallel_sync", "langgraph_checkpoint_corruption",
}


def _expand_compact_entry(item: Dict[str, Any]) -> Dict[str, Any]:
    """Expand abbreviated JSON keys to full field names."""
    expanded = {}
    for short, full in _COMPACT_KEYS.items():
        if short in item:
            expanded[full] = item[short]
    # Also accept full keys (in case model ignores compact format)
    for full in _COMPACT_KEYS.values():
        if full in item and full not in expanded:
            expanded[full] = item[full]
    return expanded


def _scenario_hash(entry: GoldenDatasetEntry) -> str:
    """Hash an entry's key characteristics for deduplication."""
    sig = json.dumps({
        "type": entry.detection_type.value,
        "detected": entry.expected_detected,
        "desc": entry.description[:80],
    }, sort_keys=True)
    return hashlib.md5(sig.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------

class LangGraphGoldenDataGenerator(GoldenDataGenerator):
    """Generates LangGraph-native golden dataset entries with token-optimized API calls.

    Optimizations over base class:
    - Prompt caching for LangGraph vocabulary system message (~75% input savings)
    - Tiered model selection: Haiku for easy, Sonnet for medium/hard
    - Compact output format expanded client-side (~30% output savings)
    - Adaptive batch sizing: 3 for graph_execution types, 8 for text types
    - Incremental persistence with resume support
    """

    DIFFICULTY_MODELS = {
        "easy": "claude-haiku-4-5-20251001",
        "medium": "claude-sonnet-4-20250514",
        "hard": "claude-sonnet-4-20250514",
    }
    DIFFICULTY_TEMPERATURES = {
        "easy": 0.7,
        "medium": 0.8,
        "hard": 0.95,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        easy_model: Optional[str] = None,
        hard_model: Optional[str] = None,
        use_cache: bool = True,
        delay_between_calls: float = 1.0,
    ):
        super().__init__(
            model="claude-sonnet-4-20250514",
            api_key=api_key,
            max_tokens=16384,
            temperature=0.8,
        )
        if easy_model:
            self.DIFFICULTY_MODELS["easy"] = easy_model
        if hard_model:
            self.DIFFICULTY_MODELS["medium"] = hard_model
            self.DIFFICULTY_MODELS["hard"] = hard_model
        self._use_cache = use_cache
        self._delay = delay_between_calls
        self._seen_hashes: set = set()
        # Override client with timeout to prevent hanging API calls
        if _HAS_ANTHROPIC and self._api_key:
            import httpx
            self._client = Anthropic(
                api_key=self._api_key,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        self._call_count = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._type_prompts: Optional[Dict] = None

    @property
    def type_prompts(self) -> Dict:
        """Lazy-load LangGraph type prompts to avoid circular imports."""
        if self._type_prompts is None:
            try:
                from app.detection_enterprise.langgraph_type_prompts import LANGGRAPH_TYPE_PROMPTS
                self._type_prompts = LANGGRAPH_TYPE_PROMPTS
            except ImportError:
                logger.warning("langgraph_type_prompts not available, falling back to base TYPE_PROMPTS")
                from app.detection_enterprise.golden_data_generator import TYPE_PROMPTS
                self._type_prompts = TYPE_PROMPTS
        return self._type_prompts

    # ------------------------------------------------------------------
    # Overridden LLM call with caching + tiered models
    # ------------------------------------------------------------------

    def _call_llm_for_difficulty(self, prompt: str, difficulty: str = "medium") -> Tuple[str, Dict[str, int]]:
        """Call LLM with prompt caching and model selection per difficulty."""
        if not self.client:
            logger.error("Anthropic client not available")
            return "", {"input_tokens": 0, "output_tokens": 0}

        model = self.DIFFICULTY_MODELS.get(difficulty, self.model)
        temperature = self.DIFFICULTY_TEMPERATURES.get(difficulty, self.temperature)

        system_blocks = []
        if self._use_cache:
            system_blocks = [{
                "type": "text",
                "text": LANGGRAPH_SYSTEM_MESSAGE,
                "cache_control": {"type": "ephemeral"},
            }]
        else:
            system_blocks = [{
                "type": "text",
                "text": LANGGRAPH_SYSTEM_MESSAGE,
            }]

        try:
            if self._delay > 0 and self._call_count > 0:
                time.sleep(self._delay)

            response = self.client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                temperature=temperature,
                system=system_blocks,
                messages=[{"role": "user", "content": prompt}],
            )

            self._call_count += 1
            usage = {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
            }
            self._total_input_tokens += usage["input_tokens"]
            self._total_output_tokens += usage["output_tokens"]

            text = response.content[0].text

            # Detect truncation
            stop_reason = getattr(response, "stop_reason", None)
            if stop_reason == "max_tokens":
                logger.warning(
                    "Response truncated (max_tokens=%d, output=%d tokens). "
                    "Attempting to salvage partial JSON.",
                    self.max_tokens, usage["output_tokens"],
                )
                text = self._salvage_truncated_json(text)

            return text, usage

        except Exception as exc:
            logger.error("LLM call failed (model=%s): %s", model, exc)
            return "", {"input_tokens": 0, "output_tokens": 0}

    @staticmethod
    def _salvage_truncated_json(text: str) -> str:
        """Attempt to close a truncated JSON array so we can parse partial entries."""
        import re
        stripped = text.rstrip()
        stripped = re.sub(r'^```(?:json)?\s*\n?', '', stripped)
        stripped = re.sub(r'\n?```\s*$', '', stripped)
        stripped = stripped.strip()

        if not stripped.startswith("["):
            return text

        last_brace = stripped.rfind("}")
        if last_brace > 0:
            candidate = stripped[:last_brace + 1] + "]"
            try:
                json.loads(candidate)
                logger.info("Salvaged %d chars of truncated JSON", len(candidate))
                return candidate
            except json.JSONDecodeError:
                for i in range(3):
                    prev_brace = stripped.rfind("}", 0, last_brace)
                    if prev_brace > 0:
                        last_brace = prev_brace
                        candidate = stripped[:last_brace + 1] + "]"
                        try:
                            json.loads(candidate)
                            logger.info("Salvaged %d chars after %d cuts", len(candidate), i + 1)
                            return candidate
                        except json.JSONDecodeError:
                            continue

        return text

    def _call_llm(self, prompt: str) -> str:
        """Override base class -- routes through difficulty-aware call."""
        text, _ = self._call_llm_for_difficulty(prompt, self._current_difficulty)
        return text

    # ------------------------------------------------------------------
    # Overridden prompt builder
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        detection_type: DetectionType,
        count: int,
        n_positive: int,
        n_negative: int,
        examples: List[GoldenDatasetEntry],
        difficulty: str = "easy",
        domain: Optional[str] = None,
    ) -> str:
        """Build LangGraph-specific generation prompt with compact output format."""
        type_key = detection_type.value
        type_info = self.type_prompts.get(type_key)
        if not type_info:
            from app.detection_enterprise.golden_data_generator import TYPE_PROMPTS
            type_info = TYPE_PROMPTS.get(type_key)
            if not type_info:
                raise ValueError(f"No prompt template for detection type: {type_key}")

        # Few-shot examples (compact)
        examples_block = ""
        if examples:
            example_items = []
            for ex in examples[:2]:
                example_items.append(json.dumps({
                    "d": ex.input_data,
                    "e": ex.expected_detected,
                    "mn": ex.expected_confidence_min,
                    "mx": ex.expected_confidence_max,
                    "desc": ex.description,
                    "t": ex.tags[:2],
                }, separators=(",", ":")))
            examples_block = "\n\nExisting examples (create NEW scenarios):\n" + "\n".join(example_items)

        difficulty_instruction = DIFFICULTY_INSTRUCTIONS.get(difficulty, DIFFICULTY_INSTRUCTIONS["easy"])

        # Domain/graph type injection for diversity
        domain_instruction = ""
        if domain:
            parts = domain.split(",") if "," in domain else [domain]
            if len(parts) == 2:
                domain_instruction = f"\nGraph type: {parts[0]}. Business domain: {parts[1]}. Use these for realistic context.\n"
            else:
                domain_instruction = f"\nBusiness domain for these scenarios: {domain}. Use this domain for realistic context.\n"

        # Template reference for graph_execution-heavy types
        template_instruction = ""
        if type_key in _GRAPH_EXECUTION_TYPES:
            template_instruction = (
                "\nYou may base graph_execution structures on the templates from the system message "
                "(modify them -- change node names, add/remove nodes, alter inputs/outputs). "
                "Do NOT copy templates verbatim.\n"
            )

        # LangGraph context from type prompts
        langgraph_context = type_info.get("langgraph_context", "")
        langgraph_context_block = f"\n## LangGraph Context\n{langgraph_context}\n" if langgraph_context else ""

        prompt = f"""## Detection Type: {type_key}

{type_info['description']}

## Difficulty: {difficulty.upper()}
{difficulty_instruction}

## Schema
input_data must match: {type_info['schema']}

## Positive (e=true): {type_info['positive_desc']}
## Negative (e=false): {type_info['negative_desc']}
{langgraph_context_block}{domain_instruction}{template_instruction}{examples_block}

Generate {count} samples ({n_positive} positive, {n_negative} negative).
Positive: mn 0.4-0.85, mx 0.6-0.99. Negative: mn 0.0-0.1, mx 0.15-0.35.
Use compact format: {{"d":..,"e":..,"mn":..,"mx":..,"desc":"..","t":[..]}}
Return ONLY a JSON array."""

        return prompt

    # ------------------------------------------------------------------
    # Fix common LLM generation issues
    # ------------------------------------------------------------------

    @staticmethod
    def _fix_entry(entry_data: Dict[str, Any], detection_type: str) -> Dict[str, Any]:
        """Fix common LLM generation issues in graph_execution entries."""
        # If LangGraph-specific type but missing graph_execution wrapper, add it
        if detection_type in _GRAPH_EXECUTION_TYPES:
            if "graph_execution" not in entry_data and "graph_id" in entry_data:
                entry_data = {"graph_execution": entry_data}

            ge = entry_data.get("graph_execution", {})
            if isinstance(ge, dict):
                # Ensure graph_id exists
                if "graph_id" not in ge:
                    ge["graph_id"] = f"graph-{uuid.uuid4().hex[:8]}"
                # Ensure thread_id exists
                if "thread_id" not in ge:
                    ge["thread_id"] = f"thread-{uuid.uuid4().hex[:8]}"
                # Fix bad timestamps
                for ts_field in ("started_at", "finished_at"):
                    ts = ge.get(ts_field)
                    if ts is not None and isinstance(ts, str):
                        try:
                            if ts.endswith("Z"):
                                datetime.fromisoformat(ts[:-1] + "+00:00")
                            else:
                                datetime.fromisoformat(ts)
                        except (ValueError, TypeError):
                            ge[ts_field] = datetime.now(timezone.utc).isoformat()
                # Fix node timestamps
                for node in ge.get("nodes", []):
                    if isinstance(node, dict):
                        for ts_field in ("started_at", "finished_at"):
                            ts = node.get(ts_field)
                            if ts is not None and isinstance(ts, str):
                                try:
                                    if ts.endswith("Z"):
                                        datetime.fromisoformat(ts[:-1] + "+00:00")
                                    else:
                                        datetime.fromisoformat(ts)
                                except (ValueError, TypeError):
                                    node[ts_field] = datetime.now(timezone.utc).isoformat()

        return entry_data

    # ------------------------------------------------------------------
    # Parse with compact key expansion
    # ------------------------------------------------------------------

    def _parse_entries(
        self,
        raw_response: str,
        detection_type: DetectionType,
    ) -> List[GoldenDatasetEntry]:
        """Parse LLM response, expanding compact keys."""
        parsed = _parse_json(raw_response)
        if parsed is None:
            logger.error(
                "Failed to parse JSON for %s (response length=%d, first 200 chars: %s)",
                detection_type.value, len(raw_response), raw_response[:200],
            )
            return []

        if isinstance(parsed, dict):
            for key in ("entries", "samples", "data", "results"):
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                parsed = [parsed]

        if not isinstance(parsed, list):
            logger.error("Parsed JSON is not a list for %s", detection_type.value)
            return []

        entries: List[GoldenDatasetEntry] = []
        for item in parsed:
            try:
                if not isinstance(item, dict):
                    continue

                expanded = _expand_compact_entry(item)
                input_data = expanded.get("input_data")
                if input_data is None:
                    continue

                # Fix common LLM issues
                input_data = self._fix_entry(input_data, detection_type.value)

                expected_detected = bool(expanded.get("expected_detected", False))
                conf_min = float(expanded.get("expected_confidence_min", 0.0))
                conf_max = float(expanded.get("expected_confidence_max", 1.0))
                conf_min = max(0.0, min(1.0, conf_min))
                conf_max = max(conf_min, min(1.0, conf_max))

                description = str(expanded.get("description", ""))
                tags = expanded.get("tags", [])
                if not isinstance(tags, list):
                    tags = [str(tags)]
                tags = [str(t) for t in tags]
                tags.append("langgraph")  # Mark all as langgraph-native

                entry_id = f"langgraph_{detection_type.value}_gen_{uuid.uuid4().hex[:8]}"

                entry = GoldenDatasetEntry(
                    id=entry_id,
                    detection_type=detection_type,
                    input_data=input_data,
                    expected_detected=expected_detected,
                    expected_confidence_min=conf_min,
                    expected_confidence_max=conf_max,
                    description=description,
                    source="llm_generated",
                    tags=tags,
                    augmentation_method=f"claude_langgraph_{self._current_difficulty}",
                    human_verified=False,
                    difficulty=self._current_difficulty,
                )

                # Deduplication check
                h = _scenario_hash(entry)
                if h in self._seen_hashes:
                    logger.debug("Skipping duplicate entry for %s", detection_type.value)
                    continue
                self._seen_hashes.add(h)

                entries.append(entry)

            except Exception as exc:
                logger.warning("Skipping malformed entry for %s: %s", detection_type.value, exc)
                continue

        return entries

    # ------------------------------------------------------------------
    # Batch generation with incremental save
    # ------------------------------------------------------------------

    def generate_batch(
        self,
        detection_types: Optional[List[DetectionType]] = None,
        target_per_type: int = 100,
        difficulty_distribution: Tuple[float, float, float] = (0.20, 0.45, 0.35),
        output_path: Optional[Path] = None,
        resume: bool = False,
        batch_size: Optional[int] = None,
        db_session=None,
    ) -> Dict[str, Any]:
        """Generate entries for multiple detection types with incremental persistence."""
        if not self.is_available:
            logger.error("Generator not available (missing SDK or API key)")
            return {"error": "not_available"}

        types = detection_types or list(DetectionType)
        e_frac, m_frac, h_frac = difficulty_distribution

        # Load existing dataset for resume
        dataset = GoldenDataset()
        if resume and output_path and output_path.exists():
            dataset.load(output_path)
            for entry in dataset.entries.values():
                self._seen_hashes.add(_scenario_hash(entry))
            logger.info("Resumed: loaded %d existing entries", len(dataset.entries))

        stats: Dict[str, Any] = {}
        total_generated = 0
        domain_idx = 0

        for type_idx, dt in enumerate(types):
            type_key = dt.value

            # Check how many we already have for this type
            existing = dataset.get_entries_by_type(dt)
            existing_langgraph = [e for e in existing if "langgraph" in e.tags]
            current_count = len(existing_langgraph)

            if current_count >= target_per_type:
                logger.info(
                    "[%d/%d] %s: already at %d/%d, skipping",
                    type_idx + 1, len(types), type_key, current_count, target_per_type,
                )
                stats[type_key] = {"skipped": True, "existing": current_count}
                continue

            needed = target_per_type - current_count
            n_easy = max(2, round(needed * e_frac))
            n_hard = max(2, round(needed * h_frac))
            n_medium = needed - n_easy - n_hard

            # Adaptive batch size: smaller for graph_execution types (larger JSON)
            bs = batch_size or (3 if type_key in _GRAPH_EXECUTION_TYPES else 8)

            type_stats = {"generated": 0, "errors": 0, "retries": 0}

            for difficulty, count in [("easy", n_easy), ("medium", n_medium), ("hard", n_hard)]:
                if count <= 0:
                    continue

                self._current_difficulty = difficulty
                remaining = count

                while remaining > 0:
                    batch_count = min(bs, remaining)
                    n_pos = (batch_count + 1) // 2
                    n_neg = batch_count - n_pos

                    # Rotate graph type + business domain
                    graph_type, biz = GRAPH_TYPE_DOMAINS[domain_idx % len(GRAPH_TYPE_DOMAINS)]
                    domain = f"{graph_type},{biz}"
                    domain_idx += 1

                    prompt = self._build_prompt(
                        detection_type=dt,
                        count=batch_count,
                        n_positive=n_pos,
                        n_negative=n_neg,
                        examples=existing[:3],
                        difficulty=difficulty,
                        domain=domain,
                    )

                    logger.info(
                        "[%d/%d] %s %s: generating %d (need %d more)...",
                        type_idx + 1, len(types), type_key, difficulty,
                        batch_count, remaining,
                    )

                    raw, usage = self._call_llm_for_difficulty(prompt, difficulty)
                    if not raw:
                        type_stats["errors"] += 1
                        remaining -= batch_count
                        continue

                    entries = self._parse_entries(raw, dt)

                    # Validate entries (schema validation)
                    valid_entries = []
                    invalid_errors = []
                    try:
                        from app.detection_enterprise.input_schemas import validate_input
                        for entry in entries:
                            ok, err = validate_input(dt.value, entry.input_data)
                            if ok:
                                valid_entries.append(entry)
                            else:
                                invalid_errors.append(err)
                    except ImportError:
                        valid_entries = entries

                    # LangGraph-specific validation
                    try:
                        from app.detection_enterprise.langgraph_graph_validator import validate_langgraph_input_data
                        further_valid = []
                        for entry in valid_entries:
                            ok, err = validate_langgraph_input_data(dt.value, entry.input_data)
                            if ok:
                                further_valid.append(entry)
                            else:
                                invalid_errors.append(f"langgraph: {err}")
                        valid_entries = further_valid
                    except ImportError:
                        pass

                    # Retry invalid entries once
                    if invalid_errors and len(valid_entries) < batch_count:
                        type_stats["retries"] += 1
                        retry_entries = self._retry_with_feedback(
                            dt, batch_count - len(valid_entries),
                            invalid_errors, existing[:2],
                        )
                        valid_entries.extend(retry_entries)

                    # Add to dataset
                    for entry in valid_entries:
                        dataset.add_entry(entry)
                        existing.append(entry)

                    type_stats["generated"] += len(valid_entries)
                    total_generated += len(valid_entries)
                    remaining -= len(valid_entries) if valid_entries else batch_count

                    # Incremental save after each batch
                    if output_path and valid_entries:
                        dataset.save(output_path)
                        logger.debug("Saved %d total entries to %s", len(dataset.entries), output_path)

                    # Write to DB if session provided
                    if db_session and valid_entries:
                        self._save_entries_to_db(db_session, valid_entries)

            stats[type_key] = type_stats
            logger.info(
                "[%d/%d] %s: done -- %d generated, %d errors, %d retries",
                type_idx + 1, len(types), type_key,
                type_stats["generated"], type_stats["errors"], type_stats["retries"],
            )

        # Final save
        if output_path:
            dataset.save(output_path)

        # Token usage summary
        stats["_summary"] = {
            "total_generated": total_generated,
            "total_entries": len(dataset.entries),
            "api_calls": self._call_count,
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
            "estimated_cost_usd": round(
                self._total_input_tokens * 3e-6 + self._total_output_tokens * 15e-6, 2
            ),
        }

        logger.info(
            "Generation complete: %d entries, %d API calls, ~$%.2f estimated cost",
            total_generated, self._call_count, stats["_summary"]["estimated_cost_usd"],
        )
        return stats

    def dry_run(
        self,
        detection_types: Optional[List[DetectionType]] = None,
        target_per_type: int = 100,
        difficulty_distribution: Tuple[float, float, float] = (0.20, 0.45, 0.35),
        existing_dataset: Optional[GoldenDataset] = None,
    ) -> Dict[str, Any]:
        """Estimate what would be generated without calling the API."""
        types = detection_types or list(DetectionType)
        e_frac, m_frac, h_frac = difficulty_distribution

        plan = {}
        total_calls = 0
        total_entries = 0

        for dt in types:
            existing = []
            if existing_dataset:
                existing = [e for e in existing_dataset.get_entries_by_type(dt) if "langgraph" in e.tags]

            current = len(existing)
            if current >= target_per_type:
                plan[dt.value] = {"status": "skip", "existing": current}
                continue

            needed = target_per_type - current
            n_easy = max(2, round(needed * e_frac))
            n_hard = max(2, round(needed * h_frac))
            n_medium = needed - n_easy - n_hard

            bs = 3 if dt.value in _GRAPH_EXECUTION_TYPES else 8
            calls = sum(
                max(1, (n + bs - 1) // bs)
                for n in [n_easy, n_medium, n_hard] if n > 0
            )

            plan[dt.value] = {
                "status": "generate",
                "existing": current,
                "needed": needed,
                "easy": n_easy,
                "medium": n_medium,
                "hard": n_hard,
                "api_calls": calls,
            }
            total_calls += calls
            total_entries += needed

        # Cost estimate
        avg_input_tokens = 2000
        avg_output_tokens = 7000
        total_input = total_calls * avg_input_tokens
        total_output = total_calls * avg_output_tokens
        cost = total_input * 3e-6 + total_output * 15e-6

        plan["_summary"] = {
            "total_entries_to_generate": total_entries,
            "total_api_calls": total_calls,
            "estimated_input_tokens": total_input,
            "estimated_output_tokens": total_output,
            "estimated_cost_usd": round(cost, 2),
        }

        return plan

    @staticmethod
    def _save_entries_to_db(db_session, entries):
        """Save generated entries to database via repository."""
        import asyncio
        from app.storage.golden_dataset_repo import GoldenDatasetRepository, dataclass_to_model

        async def _do_save():
            repo = GoldenDatasetRepository(db_session)
            models = [dataclass_to_model(e) for e in entries]
            inserted = await repo.add_entries_bulk(models)
            await db_session.commit()
            logger.info("Saved %d entries to database", inserted)

        try:
            loop = asyncio.get_running_loop()
            loop.run_until_complete(_do_save())
        except RuntimeError:
            asyncio.run(_do_save())
