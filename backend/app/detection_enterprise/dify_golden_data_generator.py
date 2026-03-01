"""Dify-native golden dataset generator with token-optimized Claude API calls.

Subclasses GoldenDataGenerator to produce Dify-specific test data using:
- Prompt caching for the shared Dify vocabulary system message
- Tiered model selection (Haiku for easy, Sonnet for medium/hard)
- Compact output format expanded client-side
- Batch generation with incremental persistence and resume support
- Workflow run templates covering all Dify app types
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
# Dify system message (cached across all API calls)
# ---------------------------------------------------------------------------

DIFY_SYSTEM_MESSAGE = """You are a precise test data generator for Dify workflow failure detection.

## Dify Node Types (use these exactly)
LLM: llm
Tools: tool, http_request, code
Retrieval: knowledge_retrieval
Routing: question_classifier, if_else
Transform: template_transform, variable_aggregator, parameter_extractor
Iteration: iteration, loop

## Dify App Types
chatbot, agent, workflow, chatflow

## Dify Node Status Values
running, succeeded, failed, stopped

## Dify Workflow Run JSON Format
{"workflow_run_id": "wfr-xxx", "app_id": "app-xxx", "app_name": "...", "app_type": "<chatbot|agent|workflow|chatflow>", "started_at": "ISO8601", "finished_at": "ISO8601", "status": "<succeeded|failed|stopped>", "total_tokens": N, "total_steps": N, "nodes": [{"node_id": "n1", "node_type": "<type>", "title": "NodeTitle", "status": "<status>", "inputs": {...}, "outputs": {...}, "token_count": N, "error": null, "metadata": {}, "iteration_index": null, "parent_node_id": null}]}

## Iteration/Loop Structure
Container node has node_type "iteration" or "loop".
Child nodes have parent_node_id set to the container node_id and sequential iteration_index values (0, 1, 2, ...).

## Compact Output Format
Return entries as: {"d": <input_data>, "e": <bool>, "mn": <float>, "mx": <float>, "desc": "<string>", "t": [<tags>]}
Where: d=input_data, e=expected_detected, mn=expected_confidence_min, mx=expected_confidence_max, desc=description, t=tags.
Always return a JSON array of these objects.

## Data Quality Rules
- Use unique, realistic workflow_run_id values (wfr-xxx format)
- Use unique app_id values (app-xxx format)
- Node IDs should be sequential (n1, n2, n3...)
- token_count must be non-negative integers (0 for non-LLM nodes)
- total_tokens should roughly equal sum of node token_counts
- total_steps should roughly equal number of nodes
- For Dify-specific types, wrap input_data in {"workflow_run": {...}}
- For universal types (loop, corruption, etc.), use the type's native schema
- All timestamps must be valid ISO 8601

## Model Names (use these)
Claude: claude-sonnet-4-20250514, claude-haiku-4-5-20251001
OpenAI: gpt-4o, gpt-4o-mini
"""


# ---------------------------------------------------------------------------
# Workflow Run Templates (T0-T9)
# ---------------------------------------------------------------------------

WORKFLOW_RUN_TEMPLATES = [
    # T0: Customer support chatbot (chatbot app, LLM + knowledge_retrieval)
    {
        "workflow_run_id": "wfr-t0", "app_id": "app-support",
        "app_name": "Customer Support Bot", "app_type": "chatbot",
        "status": "succeeded", "total_tokens": 2500, "total_steps": 3,
        "nodes": [
            {"node_id": "n1", "node_type": "knowledge_retrieval", "title": "Search FAQ", "status": "succeeded",
             "inputs": {"query": "How do I reset my password?"},
             "outputs": {"documents": [{"title": "Password Reset Guide", "content": "Go to Settings > Security > Reset Password", "score": 0.95}]},
             "token_count": 0},
            {"node_id": "n2", "node_type": "llm", "title": "Generate Answer", "status": "succeeded",
             "inputs": {"context": "{{n1.outputs.documents}}", "system": "You are a helpful customer support agent."},
             "outputs": {"text": "To reset your password, go to Settings > Security > Reset Password."},
             "token_count": 500},
        ],
    },
    # T1: Lead qualification workflow (workflow app, question_classifier + if_else)
    {
        "workflow_run_id": "wfr-t1", "app_id": "app-leads",
        "app_name": "Lead Qualifier", "app_type": "workflow",
        "status": "succeeded", "total_tokens": 1800, "total_steps": 4,
        "nodes": [
            {"node_id": "n1", "node_type": "question_classifier", "title": "Classify Intent", "status": "succeeded",
             "inputs": {"query": "I'm interested in your enterprise plan for 500 users"},
             "outputs": {"category": "enterprise_lead", "confidence": 0.92},
             "token_count": 200},
            {"node_id": "n2", "node_type": "if_else", "title": "Check Lead Quality", "status": "succeeded",
             "inputs": {"condition": "confidence > 0.8"},
             "outputs": {"branch": "high_quality"},
             "token_count": 0},
            {"node_id": "n3", "node_type": "llm", "title": "Draft Response", "status": "succeeded",
             "inputs": {"lead_type": "enterprise", "user_count": 500},
             "outputs": {"text": "Thank you for your interest! I'd love to schedule a demo for your team of 500."},
             "token_count": 600},
            {"node_id": "n4", "node_type": "tool", "title": "Create CRM Lead", "status": "succeeded",
             "inputs": {"name": "Enterprise Lead", "size": 500, "priority": "high"},
             "outputs": {"lead_id": "LEAD-789"},
             "token_count": 0},
        ],
    },
    # T2: RAG-powered knowledge base (chatflow app, knowledge_retrieval + LLM)
    {
        "workflow_run_id": "wfr-t2", "app_id": "app-kb",
        "app_name": "Knowledge Assistant", "app_type": "chatflow",
        "status": "succeeded", "total_tokens": 3200, "total_steps": 4,
        "nodes": [
            {"node_id": "n1", "node_type": "knowledge_retrieval", "title": "Retrieve Docs", "status": "succeeded",
             "inputs": {"query": "GDPR data retention requirements"},
             "outputs": {"documents": [
                 {"title": "GDPR Compliance Guide", "content": "Data must be deleted within 30 days of request...", "score": 0.91},
                 {"title": "Data Retention Policy", "content": "Customer data retained for 3 years after last activity...", "score": 0.87},
             ]},
             "token_count": 0},
            {"node_id": "n2", "node_type": "llm", "title": "Synthesize Answer", "status": "succeeded",
             "inputs": {"context": "{{n1.outputs.documents}}"},
             "outputs": {"text": "Under GDPR, data must be deleted within 30 days of a deletion request. Our policy retains customer data for 3 years after last activity."},
             "token_count": 1200},
        ],
    },
    # T3: Content generation pipeline (workflow app, LLM chain + template_transform)
    {
        "workflow_run_id": "wfr-t3", "app_id": "app-content",
        "app_name": "Content Pipeline", "app_type": "workflow",
        "status": "succeeded", "total_tokens": 4500, "total_steps": 5,
        "nodes": [
            {"node_id": "n1", "node_type": "llm", "title": "Generate Draft", "status": "succeeded",
             "inputs": {"topic": "AI in healthcare", "length": "500 words"},
             "outputs": {"text": "AI is revolutionizing healthcare..."},
             "token_count": 1500},
            {"node_id": "n2", "node_type": "llm", "title": "Review & Edit", "status": "succeeded",
             "inputs": {"draft": "{{n1.outputs.text}}"},
             "outputs": {"text": "Revised: AI is transforming healthcare delivery..."},
             "token_count": 1200},
            {"node_id": "n3", "node_type": "template_transform", "title": "Format Output", "status": "succeeded",
             "inputs": {"content": "{{n2.outputs.text}}", "template": "blog_post"},
             "outputs": {"result": "<article>AI is transforming healthcare delivery...</article>"},
             "token_count": 0},
            {"node_id": "n4", "node_type": "code", "title": "Word Count Check", "status": "succeeded",
             "inputs": {"text": "{{n3.outputs.result}}"},
             "outputs": {"word_count": 487, "meets_requirement": True},
             "token_count": 0},
        ],
    },
    # T4: Data extraction agent (agent app, tool + http_request + parameter_extractor)
    {
        "workflow_run_id": "wfr-t4", "app_id": "app-extract",
        "app_name": "Data Extractor Agent", "app_type": "agent",
        "status": "succeeded", "total_tokens": 2800, "total_steps": 5,
        "nodes": [
            {"node_id": "n1", "node_type": "parameter_extractor", "title": "Extract Params", "status": "succeeded",
             "inputs": {"text": "Find revenue data for Acme Corp Q4 2025"},
             "outputs": {"company": "Acme Corp", "period": "Q4 2025", "metric": "revenue"},
             "token_count": 300},
            {"node_id": "n2", "node_type": "http_request", "title": "Fetch Financial Data", "status": "succeeded",
             "inputs": {"url": "https://api.financial.com/v2/companies/acme/revenue?period=Q4-2025"},
             "outputs": {"revenue": 12500000, "currency": "USD", "growth_yoy": 0.15},
             "token_count": 0},
            {"node_id": "n3", "node_type": "llm", "title": "Analyze Results", "status": "succeeded",
             "inputs": {"data": "{{n2.outputs}}"},
             "outputs": {"text": "Acme Corp reported $12.5M revenue in Q4 2025, a 15% YoY increase."},
             "token_count": 800},
        ],
    },
    # T5: Multi-step research workflow (workflow app, iteration + LLM + code)
    {
        "workflow_run_id": "wfr-t5", "app_id": "app-research",
        "app_name": "Research Pipeline", "app_type": "workflow",
        "status": "succeeded", "total_tokens": 8000, "total_steps": 8,
        "nodes": [
            {"node_id": "n1", "node_type": "code", "title": "Split Topics", "status": "succeeded",
             "inputs": {"query": "Compare AI platforms: Dify, LangChain, LlamaIndex"},
             "outputs": {"topics": ["Dify", "LangChain", "LlamaIndex"]},
             "token_count": 0},
            {"node_id": "n2", "node_type": "iteration", "title": "Research Each", "status": "succeeded",
             "inputs": {"items": ["Dify", "LangChain", "LlamaIndex"]},
             "outputs": {"completed_iterations": 3},
             "token_count": 0},
            {"node_id": "n2-c0", "node_type": "llm", "title": "Research Topic", "status": "succeeded",
             "inputs": {"topic": "Dify"}, "outputs": {"summary": "Dify is an open-source LLM app platform..."}, "token_count": 1500, "iteration_index": 0, "parent_node_id": "n2"},
            {"node_id": "n2-c1", "node_type": "llm", "title": "Research Topic", "status": "succeeded",
             "inputs": {"topic": "LangChain"}, "outputs": {"summary": "LangChain is a framework for LLM applications..."}, "token_count": 1500, "iteration_index": 1, "parent_node_id": "n2"},
            {"node_id": "n2-c2", "node_type": "llm", "title": "Research Topic", "status": "succeeded",
             "inputs": {"topic": "LlamaIndex"}, "outputs": {"summary": "LlamaIndex specializes in data indexing..."}, "token_count": 1500, "iteration_index": 2, "parent_node_id": "n2"},
            {"node_id": "n3", "node_type": "variable_aggregator", "title": "Combine Results", "status": "succeeded",
             "inputs": {"sources": ["n2-c0", "n2-c1", "n2-c2"]},
             "outputs": {"combined": "Dify: open-source... LangChain: framework... LlamaIndex: data indexing..."},
             "token_count": 0},
            {"node_id": "n4", "node_type": "llm", "title": "Final Comparison", "status": "succeeded",
             "inputs": {"data": "{{n3.outputs.combined}}"},
             "outputs": {"text": "Comparison: Dify excels in visual workflow building..."},
             "token_count": 2000},
        ],
    },
    # T6: Automated email responder (chatbot app, LLM + tool + variable_aggregator)
    {
        "workflow_run_id": "wfr-t6", "app_id": "app-email",
        "app_name": "Email Responder", "app_type": "chatbot",
        "status": "succeeded", "total_tokens": 2200, "total_steps": 4,
        "nodes": [
            {"node_id": "n1", "node_type": "question_classifier", "title": "Classify Email", "status": "succeeded",
             "inputs": {"query": "Hi, I'd like to schedule a product demo for next week"},
             "outputs": {"category": "demo_request", "confidence": 0.89},
             "token_count": 150},
            {"node_id": "n2", "node_type": "tool", "title": "Check Calendar", "status": "succeeded",
             "inputs": {"action": "get_availability", "week": "next"},
             "outputs": {"slots": ["Mon 2pm", "Wed 10am", "Fri 3pm"]},
             "token_count": 0},
            {"node_id": "n3", "node_type": "llm", "title": "Draft Reply", "status": "succeeded",
             "inputs": {"email_type": "demo_request", "available_slots": "{{n2.outputs.slots}}"},
             "outputs": {"text": "Thank you for your interest! We have demo slots available: Mon 2pm, Wed 10am, or Fri 3pm."},
             "token_count": 600},
        ],
    },
    # T7: Document analysis pipeline (workflow app, knowledge_retrieval + LLM + code)
    {
        "workflow_run_id": "wfr-t7", "app_id": "app-docs",
        "app_name": "Doc Analyzer", "app_type": "workflow",
        "status": "succeeded", "total_tokens": 5000, "total_steps": 5,
        "nodes": [
            {"node_id": "n1", "node_type": "knowledge_retrieval", "title": "Load Document", "status": "succeeded",
             "inputs": {"query": "contract terms and conditions"},
             "outputs": {"documents": [{"title": "Service Agreement v2.3", "content": "This agreement governs the use of...", "score": 0.94}]},
             "token_count": 0},
            {"node_id": "n2", "node_type": "llm", "title": "Extract Key Terms", "status": "succeeded",
             "inputs": {"document": "{{n1.outputs.documents}}", "task": "Extract key contractual terms"},
             "outputs": {"text": "{\"terms\": [{\"name\": \"Liability Cap\", \"value\": \"$1M\"}, {\"name\": \"Term Length\", \"value\": \"2 years\"}]}"},
             "token_count": 1800},
            {"node_id": "n3", "node_type": "code", "title": "Parse & Validate", "status": "succeeded",
             "inputs": {"json_str": "{{n2.outputs.text}}"},
             "outputs": {"terms": [{"name": "Liability Cap", "value": "$1M"}, {"name": "Term Length", "value": "2 years"}], "valid": True},
             "token_count": 0},
            {"node_id": "n4", "node_type": "llm", "title": "Risk Assessment", "status": "succeeded",
             "inputs": {"terms": "{{n3.outputs.terms}}"},
             "outputs": {"text": "Risk Assessment: Liability cap at $1M is standard. 2-year term is favorable."},
             "token_count": 1500},
        ],
    },
    # T8: API integration hub (workflow app, http_request + code + if_else)
    {
        "workflow_run_id": "wfr-t8", "app_id": "app-api-hub",
        "app_name": "API Hub", "app_type": "workflow",
        "status": "succeeded", "total_tokens": 800, "total_steps": 5,
        "nodes": [
            {"node_id": "n1", "node_type": "http_request", "title": "Fetch Data", "status": "succeeded",
             "inputs": {"url": "https://api.example.com/orders/recent", "method": "GET"},
             "outputs": {"status_code": 200, "data": [{"id": 1, "amount": 99.99}, {"id": 2, "amount": 249.99}]},
             "token_count": 0},
            {"node_id": "n2", "node_type": "code", "title": "Calculate Totals", "status": "succeeded",
             "inputs": {"orders": "{{n1.outputs.data}}"},
             "outputs": {"total_amount": 349.98, "order_count": 2},
             "token_count": 0},
            {"node_id": "n3", "node_type": "if_else", "title": "Check Threshold", "status": "succeeded",
             "inputs": {"condition": "total_amount > 100"},
             "outputs": {"branch": "notify"},
             "token_count": 0},
            {"node_id": "n4", "node_type": "http_request", "title": "Send Notification", "status": "succeeded",
             "inputs": {"url": "https://api.slack.com/webhook", "method": "POST", "body": {"text": "Order total: $349.98"}},
             "outputs": {"status_code": 200},
             "token_count": 0},
        ],
    },
    # T9: Multi-model comparison (workflow app, multiple LLM nodes + variable_aggregator)
    {
        "workflow_run_id": "wfr-t9", "app_id": "app-compare",
        "app_name": "Model Comparator", "app_type": "workflow",
        "status": "succeeded", "total_tokens": 6000, "total_steps": 5,
        "nodes": [
            {"node_id": "n1", "node_type": "llm", "title": "Sonnet Response", "status": "succeeded",
             "inputs": {"prompt": "Explain quantum computing", "model_config": {"model": "claude-sonnet-4-20250514"}},
             "outputs": {"text": "Quantum computing leverages quantum mechanical phenomena..."},
             "token_count": 2000, "metadata": {"model": "claude-sonnet-4-20250514"}},
            {"node_id": "n2", "node_type": "llm", "title": "Haiku Response", "status": "succeeded",
             "inputs": {"prompt": "Explain quantum computing", "model_config": {"model": "claude-haiku-4-5-20251001"}},
             "outputs": {"text": "Quantum computing uses qubits instead of classical bits..."},
             "token_count": 800, "metadata": {"model": "claude-haiku-4-5-20251001"}},
            {"node_id": "n3", "node_type": "variable_aggregator", "title": "Combine Responses", "status": "succeeded",
             "inputs": {"sources": ["n1", "n2"]},
             "outputs": {"sonnet": "Quantum computing leverages...", "haiku": "Quantum computing uses qubits..."},
             "token_count": 0},
            {"node_id": "n4", "node_type": "llm", "title": "Evaluate Quality", "status": "succeeded",
             "inputs": {"responses": "{{n3.outputs}}"},
             "outputs": {"text": "Sonnet provides more depth, Haiku is more concise. Both accurate."},
             "token_count": 1500, "metadata": {"model": "claude-sonnet-4-20250514"}},
        ],
    },
]

# App type + business domain pairs for scenario diversity
APP_TYPE_DOMAINS = [
    ("chatbot", "customer-support"), ("workflow", "data-processing"),
    ("chatflow", "enterprise-rag"), ("agent", "sales-automation"),
    ("workflow", "content-generation"), ("chatbot", "healthcare"),
    ("chatflow", "legal-review"), ("workflow", "fintech"),
    ("agent", "devops"), ("chatbot", "education"),
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

# Types that use full workflow_run JSON (larger output, smaller batch size)
_WORKFLOW_RUN_TYPES = {
    "dify_rag_poisoning", "dify_iteration_escape", "dify_model_fallback",
    "dify_variable_leak", "dify_classifier_drift", "dify_tool_schema_mismatch",
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

class DifyGoldenDataGenerator(GoldenDataGenerator):
    """Generates Dify-native golden dataset entries with token-optimized API calls.

    Optimizations over base class:
    - Prompt caching for Dify vocabulary system message (~75% input savings)
    - Tiered model selection: Haiku for easy, Sonnet for medium/hard
    - Compact output format expanded client-side (~30% output savings)
    - Adaptive batch sizing: 8 for text types, 5 for workflow_run types
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
        """Lazy-load Dify type prompts to avoid circular imports."""
        if self._type_prompts is None:
            try:
                from app.detection_enterprise.dify_type_prompts import DIFY_TYPE_PROMPTS
                self._type_prompts = DIFY_TYPE_PROMPTS
            except ImportError:
                logger.warning("dify_type_prompts not available, falling back to base TYPE_PROMPTS")
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
                "text": DIFY_SYSTEM_MESSAGE,
                "cache_control": {"type": "ephemeral"},
            }]
        else:
            system_blocks = [{
                "type": "text",
                "text": DIFY_SYSTEM_MESSAGE,
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
        """Override base class — routes through difficulty-aware call."""
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
        """Build Dify-specific generation prompt with compact output format."""
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

        # Domain/app type injection for diversity
        domain_instruction = ""
        if domain:
            parts = domain.split(",") if "," in domain else [domain]
            if len(parts) == 2:
                domain_instruction = f"\nApp type: {parts[0]}. Business domain: {parts[1]}. Use these for realistic context.\n"
            else:
                domain_instruction = f"\nBusiness domain for these scenarios: {domain}. Use this domain for realistic context.\n"

        # Template reference for workflow_run-heavy types
        template_instruction = ""
        if type_key in _WORKFLOW_RUN_TYPES:
            template_instruction = (
                "\nYou may base workflow_run structures on the templates from the system message "
                "(modify them — change node names, add/remove nodes, alter inputs/outputs). "
                "Do NOT copy templates verbatim.\n"
            )

        # Dify context from type prompts
        dify_context = type_info.get("dify_context", "")
        dify_context_block = f"\n## Dify Context\n{dify_context}\n" if dify_context else ""

        prompt = f"""## Detection Type: {type_key}

{type_info['description']}

## Difficulty: {difficulty.upper()}
{difficulty_instruction}

## Schema
input_data must match: {type_info['schema']}

## Positive (e=true): {type_info['positive_desc']}
## Negative (e=false): {type_info['negative_desc']}
{dify_context_block}{domain_instruction}{template_instruction}{examples_block}

Generate {count} samples ({n_positive} positive, {n_negative} negative).
Positive: mn 0.4-0.85, mx 0.6-0.99. Negative: mn 0.0-0.1, mx 0.15-0.35.
Use compact format: {{"d":..,"e":..,"mn":..,"mx":..,"desc":"..","t":[..]}}
Return ONLY a JSON array."""

        return prompt

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
                tags.append("dify")  # Mark all as dify-native

                entry_id = f"dify_{detection_type.value}_gen_{uuid.uuid4().hex[:8]}"

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
                    augmentation_method=f"claude_dify_{self._current_difficulty}",
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
            existing_dify = [e for e in existing if "dify" in e.tags]
            current_count = len(existing_dify)

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

            # Adaptive batch size
            bs = batch_size or (3 if type_key in _WORKFLOW_RUN_TYPES else 8)

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

                    # Rotate app type + business domain
                    app_type, biz = APP_TYPE_DOMAINS[domain_idx % len(APP_TYPE_DOMAINS)]
                    domain = f"{app_type},{biz}"
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

                    # Validate entries
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

                    # Dify-specific validation
                    try:
                        from app.detection_enterprise.dify_workflow_validator import validate_dify_input_data
                        further_valid = []
                        for entry in valid_entries:
                            ok, err = validate_dify_input_data(dt.value, entry.input_data)
                            if ok:
                                further_valid.append(entry)
                            else:
                                invalid_errors.append(f"dify: {err}")
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
                "[%d/%d] %s: done — %d generated, %d errors, %d retries",
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
                existing = [e for e in existing_dataset.get_entries_by_type(dt) if "dify" in e.tags]

            current = len(existing)
            if current >= target_per_type:
                plan[dt.value] = {"status": "skip", "existing": current}
                continue

            needed = target_per_type - current
            n_easy = max(2, round(needed * e_frac))
            n_hard = max(2, round(needed * h_frac))
            n_medium = needed - n_easy - n_hard

            bs = 5 if dt.value in _WORKFLOW_RUN_TYPES else 8
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
