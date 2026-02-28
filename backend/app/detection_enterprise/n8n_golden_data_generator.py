"""N8N-native golden dataset generator with token-optimized Claude API calls.

Subclasses GoldenDataGenerator to produce n8n-specific test data using:
- Prompt caching for the shared n8n vocabulary system message
- Tiered model selection (Haiku for easy, Sonnet for medium/hard)
- Compact output format expanded client-side
- Batch generation with incremental persistence and resume support
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
# N8N system message (cached across all API calls)
# ---------------------------------------------------------------------------

N8N_SYSTEM_MESSAGE = """You are a precise test data generator for n8n workflow failure detection.

## n8n Node Types (use these exactly)
Triggers: n8n-nodes-base.webhook, n8n-nodes-base.scheduleTrigger, n8n-nodes-base.manualTrigger
Core: n8n-nodes-base.httpRequest, n8n-nodes-base.code, n8n-nodes-base.set, n8n-nodes-base.if, n8n-nodes-base.switch, n8n-nodes-base.merge, n8n-nodes-base.splitInBatches, n8n-nodes-base.wait, n8n-nodes-base.noOp, n8n-nodes-base.respondToWebhook
AI: @n8n/n8n-nodes-langchain.agent, @n8n/n8n-nodes-langchain.chainLlm, @n8n/n8n-nodes-langchain.toolWorkflow, @n8n/n8n-nodes-langchain.memoryBufferWindow, @n8n/n8n-nodes-langchain.outputParserStructured, @n8n/n8n-nodes-langchain.vectorStoreRetriever
Services: n8n-nodes-base.slack, n8n-nodes-base.gmail, n8n-nodes-base.googleSheets, n8n-nodes-base.postgres, n8n-nodes-base.mysql, n8n-nodes-base.redis, n8n-nodes-base.mongodb, n8n-nodes-base.airtable, n8n-nodes-base.hubspot, n8n-nodes-base.salesforce, n8n-nodes-base.stripe, n8n-nodes-base.telegram, n8n-nodes-base.discord, n8n-nodes-base.openai

## n8n Workflow JSON Format
{"id": "wf-xxx", "name": "...", "nodes": [{"id": "n1", "name": "NodeName", "type": "<node_type>", "position": [x, y], "parameters": {...}, "settings": {}}], "connections": {"SourceNodeName": {"main": [[{"node": "TargetNodeName", "type": "main", "index": 0}]]}}, "settings": {}}

## n8n Execution Trace Format
States use agent_id as n8n node names: {"agent_id": "AI Agent", "content": "Processing customer query about order #1234", "state_delta": {"input": {...}, "output": {...}, "executionTime": 1500}}

## Realism Rules
- Use specific business scenarios: CRM sync, lead enrichment, support chatbot, invoice processing, Slack bot, email automation, data pipeline, API gateway, document processing, scheduled reports
- Use real-looking data: actual API endpoints (api.stripe.com, api.hubspot.com), realistic error messages ("NodeOperationError: The resource 'contact' was not found"), proper HTTP status codes
- Agent systemMessages should be detailed and professional, not generic
- Connection patterns should match real n8n wiring (webhook→code→agent→respond, schedule→HTTP→IF→set)

## Compact Output Format
Return JSON array. Each item: {"d": <input_data>, "e": <bool expected_detected>, "mn": <float confidence_min>, "mx": <float confidence_max>, "desc": <string>, "t": [<tags>]}
Always return valid JSON. No markdown fences."""


# ---------------------------------------------------------------------------
# Workflow templates (referenced by index in prompts to save tokens)
# ---------------------------------------------------------------------------

WORKFLOW_TEMPLATES = [
    # T0: Customer support chatbot
    {"id": "wf-t0", "name": "Customer Support Bot", "nodes": [
        {"id": "n1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {"path": "chat"}, "settings": {}},
        {"id": "n2", "name": "Support Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [450, 300], "parameters": {"systemMessage": "You are a customer support agent for TechCorp. Help with billing, orders, and returns."}, "settings": {}},
        {"id": "n3", "name": "Respond", "type": "n8n-nodes-base.respondToWebhook", "position": [650, 300], "parameters": {}, "settings": {}},
    ], "connections": {"Webhook": {"main": [[{"node": "Support Agent", "type": "main", "index": 0}]]}, "Support Agent": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]}}, "settings": {}},
    # T1: CRM sync pipeline
    {"id": "wf-t1", "name": "CRM Contact Sync", "nodes": [
        {"id": "n1", "name": "Schedule", "type": "n8n-nodes-base.scheduleTrigger", "position": [250, 300], "parameters": {"rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}}, "settings": {}},
        {"id": "n2", "name": "Fetch Contacts", "type": "n8n-nodes-base.httpRequest", "position": [450, 300], "parameters": {"url": "https://api.hubspot.com/crm/v3/objects/contacts", "method": "GET"}, "settings": {}},
        {"id": "n3", "name": "Filter New", "type": "n8n-nodes-base.if", "position": [650, 300], "parameters": {}, "settings": {}},
        {"id": "n4", "name": "Upsert DB", "type": "n8n-nodes-base.postgres", "position": [850, 300], "parameters": {"operation": "upsert"}, "settings": {}},
    ], "connections": {"Schedule": {"main": [[{"node": "Fetch Contacts", "type": "main", "index": 0}]]}, "Fetch Contacts": {"main": [[{"node": "Filter New", "type": "main", "index": 0}]]}, "Filter New": {"main": [[{"node": "Upsert DB", "type": "main", "index": 0}]]}}, "settings": {}},
    # T2: Lead enrichment with AI
    {"id": "wf-t2", "name": "Lead Enrichment", "nodes": [
        {"id": "n1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {"path": "lead"}, "settings": {}},
        {"id": "n2", "name": "Fetch Company", "type": "n8n-nodes-base.httpRequest", "position": [450, 300], "parameters": {"url": "https://api.clearbit.com/v2/companies/find"}, "settings": {}},
        {"id": "n3", "name": "Enrich Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [650, 300], "parameters": {"systemMessage": "Analyze company data and score this lead."}, "settings": {}},
        {"id": "n4", "name": "Update CRM", "type": "n8n-nodes-base.hubspot", "position": [850, 300], "parameters": {"operation": "update", "resource": "contact"}, "settings": {}},
    ], "connections": {"Webhook": {"main": [[{"node": "Fetch Company", "type": "main", "index": 0}]]}, "Fetch Company": {"main": [[{"node": "Enrich Agent", "type": "main", "index": 0}]]}, "Enrich Agent": {"main": [[{"node": "Update CRM", "type": "main", "index": 0}]]}}, "settings": {}},
    # T3: Document processing
    {"id": "wf-t3", "name": "Invoice Processor", "nodes": [
        {"id": "n1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {"path": "invoice"}, "settings": {}},
        {"id": "n2", "name": "Extract Text", "type": "n8n-nodes-base.code", "position": [450, 300], "parameters": {"jsCode": "// OCR extraction"}, "settings": {}},
        {"id": "n3", "name": "Parse Invoice", "type": "@n8n/n8n-nodes-langchain.chainLlm", "position": [650, 300], "parameters": {"prompt": "Extract invoice number, date, total, and line items from this text."}, "settings": {}},
        {"id": "n4", "name": "Save to DB", "type": "n8n-nodes-base.postgres", "position": [850, 300], "parameters": {"operation": "insert", "table": "invoices"}, "settings": {}},
    ], "connections": {"Webhook": {"main": [[{"node": "Extract Text", "type": "main", "index": 0}]]}, "Extract Text": {"main": [[{"node": "Parse Invoice", "type": "main", "index": 0}]]}, "Parse Invoice": {"main": [[{"node": "Save to DB", "type": "main", "index": 0}]]}}, "settings": {}},
    # T4: Slack notification bot
    {"id": "wf-t4", "name": "Alert Bot", "nodes": [
        {"id": "n1", "name": "Schedule", "type": "n8n-nodes-base.scheduleTrigger", "position": [250, 300], "parameters": {"rule": {"interval": [{"field": "minutes", "minutesInterval": 15}]}}, "settings": {}},
        {"id": "n2", "name": "Check Metrics", "type": "n8n-nodes-base.httpRequest", "position": [450, 300], "parameters": {"url": "https://api.datadog.com/api/v1/query", "method": "GET"}, "settings": {}},
        {"id": "n3", "name": "Threshold Check", "type": "n8n-nodes-base.if", "position": [650, 300], "parameters": {}, "settings": {}},
        {"id": "n4", "name": "Send Alert", "type": "n8n-nodes-base.slack", "position": [850, 200], "parameters": {"channel": "#alerts", "text": "Metric threshold exceeded"}, "settings": {}},
    ], "connections": {"Schedule": {"main": [[{"node": "Check Metrics", "type": "main", "index": 0}]]}, "Check Metrics": {"main": [[{"node": "Threshold Check", "type": "main", "index": 0}]]}, "Threshold Check": {"main": [[{"node": "Send Alert", "type": "main", "index": 0}]]}}, "settings": {}},
    # T5: Email responder with AI
    {"id": "wf-t5", "name": "Email Auto-Responder", "nodes": [
        {"id": "n1", "name": "Gmail Trigger", "type": "n8n-nodes-base.gmail", "position": [250, 300], "parameters": {"operation": "getAll", "filters": {"labelIds": ["INBOX"]}}, "settings": {}},
        {"id": "n2", "name": "Classify Intent", "type": "@n8n/n8n-nodes-langchain.chainLlm", "position": [450, 300], "parameters": {"prompt": "Classify this email as: inquiry, complaint, order, spam"}, "settings": {}},
        {"id": "n3", "name": "Route", "type": "n8n-nodes-base.switch", "position": [650, 300], "parameters": {}, "settings": {}},
        {"id": "n4", "name": "Draft Reply", "type": "@n8n/n8n-nodes-langchain.agent", "position": [850, 200], "parameters": {"systemMessage": "Draft professional email replies for customer inquiries."}, "settings": {}},
    ], "connections": {"Gmail Trigger": {"main": [[{"node": "Classify Intent", "type": "main", "index": 0}]]}, "Classify Intent": {"main": [[{"node": "Route", "type": "main", "index": 0}]]}, "Route": {"main": [[{"node": "Draft Reply", "type": "main", "index": 0}]]}}, "settings": {}},
    # T6: Data enrichment pipeline
    {"id": "wf-t6", "name": "Data Enrichment", "nodes": [
        {"id": "n1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {"path": "enrich"}, "settings": {}},
        {"id": "n2", "name": "Lookup DB", "type": "n8n-nodes-base.postgres", "position": [450, 300], "parameters": {"operation": "select"}, "settings": {}},
        {"id": "n3", "name": "Fetch External", "type": "n8n-nodes-base.httpRequest", "position": [650, 300], "parameters": {"url": "https://api.clearbit.com/v2/people/find"}, "settings": {}},
        {"id": "n4", "name": "Merge", "type": "n8n-nodes-base.merge", "position": [850, 300], "parameters": {"mode": "mergeByKey"}, "settings": {}},
        {"id": "n5", "name": "Respond", "type": "n8n-nodes-base.respondToWebhook", "position": [1050, 300], "parameters": {}, "settings": {}},
    ], "connections": {"Webhook": {"main": [[{"node": "Lookup DB", "type": "main", "index": 0}, {"node": "Fetch External", "type": "main", "index": 0}]]}, "Lookup DB": {"main": [[{"node": "Merge", "type": "main", "index": 0}]]}, "Fetch External": {"main": [[{"node": "Merge", "type": "main", "index": 1}]]}, "Merge": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]}}, "settings": {}},
    # T7: Multi-agent RAG
    {"id": "wf-t7", "name": "RAG Knowledge Bot", "nodes": [
        {"id": "n1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {"path": "ask"}, "settings": {}},
        {"id": "n2", "name": "Retriever", "type": "@n8n/n8n-nodes-langchain.vectorStoreRetriever", "position": [450, 300], "parameters": {}, "settings": {}},
        {"id": "n3", "name": "Answer Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [650, 300], "parameters": {"systemMessage": "Answer questions using only the retrieved documents. Cite sources."}, "settings": {}},
        {"id": "n4", "name": "Memory", "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow", "position": [650, 500], "parameters": {"windowSize": 10}, "settings": {}},
        {"id": "n5", "name": "Respond", "type": "n8n-nodes-base.respondToWebhook", "position": [850, 300], "parameters": {}, "settings": {}},
    ], "connections": {"Webhook": {"main": [[{"node": "Retriever", "type": "main", "index": 0}]]}, "Retriever": {"main": [[{"node": "Answer Agent", "type": "main", "index": 0}]]}, "Answer Agent": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]}}, "settings": {}},
    # T8: Scheduled report
    {"id": "wf-t8", "name": "Weekly Report", "nodes": [
        {"id": "n1", "name": "Schedule", "type": "n8n-nodes-base.scheduleTrigger", "position": [250, 300], "parameters": {"rule": {"interval": [{"field": "weeks", "weeksInterval": 1}]}}, "settings": {}},
        {"id": "n2", "name": "Query Sales", "type": "n8n-nodes-base.postgres", "position": [450, 300], "parameters": {"operation": "executeQuery", "query": "SELECT * FROM sales WHERE date > now() - interval '7 days'"}, "settings": {}},
        {"id": "n3", "name": "Summarize", "type": "@n8n/n8n-nodes-langchain.chainLlm", "position": [650, 300], "parameters": {"prompt": "Summarize this sales data into a weekly report."}, "settings": {}},
        {"id": "n4", "name": "Send Email", "type": "n8n-nodes-base.gmail", "position": [850, 300], "parameters": {"operation": "send", "to": "team@company.com", "subject": "Weekly Sales Report"}, "settings": {}},
    ], "connections": {"Schedule": {"main": [[{"node": "Query Sales", "type": "main", "index": 0}]]}, "Query Sales": {"main": [[{"node": "Summarize", "type": "main", "index": 0}]]}, "Summarize": {"main": [[{"node": "Send Email", "type": "main", "index": 0}]]}}, "settings": {}},
    # T9: E-commerce order processor
    {"id": "wf-t9", "name": "Order Processor", "nodes": [
        {"id": "n1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {"path": "order"}, "settings": {}},
        {"id": "n2", "name": "Validate Order", "type": "n8n-nodes-base.code", "position": [450, 300], "parameters": {"jsCode": "// Validate order fields"}, "settings": {}},
        {"id": "n3", "name": "Check Inventory", "type": "n8n-nodes-base.httpRequest", "position": [650, 300], "parameters": {"url": "https://api.shopify.com/admin/api/2024-01/inventory_levels.json"}, "settings": {}},
        {"id": "n4", "name": "Process Payment", "type": "n8n-nodes-base.stripe", "position": [850, 300], "parameters": {"operation": "charge", "resource": "paymentIntent"}, "settings": {}},
        {"id": "n5", "name": "Confirm", "type": "n8n-nodes-base.respondToWebhook", "position": [1050, 300], "parameters": {}, "settings": {}},
    ], "connections": {"Webhook": {"main": [[{"node": "Validate Order", "type": "main", "index": 0}]]}, "Validate Order": {"main": [[{"node": "Check Inventory", "type": "main", "index": 0}]]}, "Check Inventory": {"main": [[{"node": "Process Payment", "type": "main", "index": 0}]]}, "Process Payment": {"main": [[{"node": "Confirm", "type": "main", "index": 0}]]}}, "settings": {}},
]

# Business domains for scenario diversity
BUSINESS_DOMAINS = [
    "e-commerce", "healthcare", "fintech", "hr", "marketing",
    "devops", "legal", "education", "real-estate", "logistics",
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

# Types that use workflow_json (larger output, smaller batch size)
_WORKFLOW_TYPES = {
    "n8n_schema", "n8n_cycle", "n8n_complexity", "n8n_error",
    "n8n_resource", "n8n_timeout", "workflow",
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

class N8nGoldenDataGenerator(GoldenDataGenerator):
    """Generates n8n-native golden dataset entries with token-optimized API calls.

    Optimizations over base class:
    - Prompt caching for n8n vocabulary system message (~75% input savings)
    - Tiered model selection: Haiku for easy, Sonnet for medium/hard
    - Compact output format expanded client-side (~30% output savings)
    - Adaptive batch sizing: 15 for text types, 10 for workflow types
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
            max_tokens=8192,
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
        self._call_count = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._type_prompts: Optional[Dict] = None

    @property
    def type_prompts(self) -> Dict:
        """Lazy-load n8n type prompts to avoid circular imports."""
        if self._type_prompts is None:
            try:
                from app.detection_enterprise.n8n_type_prompts import N8N_TYPE_PROMPTS
                self._type_prompts = N8N_TYPE_PROMPTS
            except ImportError:
                logger.warning("n8n_type_prompts not available, falling back to base TYPE_PROMPTS")
                from app.detection_enterprise.golden_data_generator import TYPE_PROMPTS
                self._type_prompts = TYPE_PROMPTS
        return self._type_prompts

    # ------------------------------------------------------------------
    # Overridden LLM call with caching + tiered models
    # ------------------------------------------------------------------

    def _call_llm_for_difficulty(self, prompt: str, difficulty: str = "medium") -> Tuple[str, Dict[str, int]]:
        """Call LLM with prompt caching and model selection per difficulty.

        Returns:
            Tuple of (response_text, usage_dict)
        """
        if not self.client:
            logger.error("Anthropic client not available")
            return "", {"input_tokens": 0, "output_tokens": 0}

        model = self.DIFFICULTY_MODELS.get(difficulty, self.model)
        temperature = self.DIFFICULTY_TEMPERATURES.get(difficulty, self.temperature)

        system_blocks = []
        if self._use_cache:
            system_blocks = [{
                "type": "text",
                "text": N8N_SYSTEM_MESSAGE,
                "cache_control": {"type": "ephemeral"},
            }]
        else:
            system_blocks = [{
                "type": "text",
                "text": N8N_SYSTEM_MESSAGE,
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
                # Try to close truncated JSON array
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
        # Strip markdown fences if present
        stripped = re.sub(r'^```(?:json)?\s*\n?', '', stripped)
        stripped = re.sub(r'\n?```\s*$', '', stripped)
        stripped = stripped.strip()

        if not stripped.startswith("["):
            return text

        # Find the last complete object (ends with })
        last_brace = stripped.rfind("}")
        if last_brace > 0:
            candidate = stripped[:last_brace + 1] + "]"
            try:
                json.loads(candidate)
                logger.info("Salvaged %d chars of truncated JSON", len(candidate))
                return candidate
            except json.JSONDecodeError:
                # Try progressively shorter cuts
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
        """Build n8n-specific generation prompt with compact output format."""
        type_key = detection_type.value
        type_info = self.type_prompts.get(type_key)
        if not type_info:
            # Fall back to base TYPE_PROMPTS
            from app.detection_enterprise.golden_data_generator import TYPE_PROMPTS
            type_info = TYPE_PROMPTS.get(type_key)
            if not type_info:
                raise ValueError(f"No prompt template for detection type: {type_key}")

        # Few-shot examples (compact)
        examples_block = ""
        if examples:
            example_items = []
            for ex in examples[:2]:  # Max 2 examples to save tokens
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

        # Domain injection for diversity
        domain_instruction = ""
        if domain:
            domain_instruction = f"\nBusiness domain for these scenarios: {domain}. Use this domain for realistic context.\n"

        # Workflow template reference for workflow-heavy types
        template_instruction = ""
        if type_key in _WORKFLOW_TYPES:
            template_instruction = (
                "\nYou may base workflow_json on the templates from the system message "
                "(modify them — change node names, add/remove nodes, alter connections). "
                "Do NOT copy templates verbatim.\n"
            )

        # N8N context from type prompts
        n8n_context = type_info.get("n8n_context", "")
        n8n_context_block = f"\n## n8n Context\n{n8n_context}\n" if n8n_context else ""

        prompt = f"""## Detection Type: {type_key}

{type_info['description']}

## Difficulty: {difficulty.upper()}
{difficulty_instruction}

## Schema
input_data must match: {type_info['schema']}

## Positive (e=true): {type_info['positive_desc']}
## Negative (e=false): {type_info['negative_desc']}
{n8n_context_block}{domain_instruction}{template_instruction}{examples_block}

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
                tags.append("n8n")  # Mark all as n8n-native

                entry_id = f"n8n_{detection_type.value}_gen_{uuid.uuid4().hex[:8]}"

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
                    augmentation_method=f"claude_n8n_{self._current_difficulty}",
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
        """Generate entries for multiple detection types with incremental persistence.

        Args:
            detection_types: Types to generate (default: all DetectionType values).
            target_per_type: Target entries per type.
            difficulty_distribution: (easy, medium, hard) fractions summing to 1.0.
            output_path: Path to save output JSON incrementally.
            resume: If True, load existing output and skip types at target.
            batch_size: Override entries per API call (default: auto).
            db_session: Optional AsyncSession for writing entries directly to DB.

        Returns:
            Stats dict with per-type results and total token usage.
        """
        if not self.is_available:
            logger.error("Generator not available (missing SDK or API key)")
            return {"error": "not_available"}

        types = detection_types or list(DetectionType)
        e_frac, m_frac, h_frac = difficulty_distribution

        # Load existing dataset for resume
        dataset = GoldenDataset()
        if resume and output_path and output_path.exists():
            dataset.load(output_path)
            # Seed dedup hashes from existing entries
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
            existing_n8n = [e for e in existing if "n8n" in e.tags]
            current_count = len(existing_n8n)

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

            # Adaptive batch size — keep small to avoid output truncation
            bs = batch_size or (5 if type_key in _WORKFLOW_TYPES else 8)

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

                    # Rotate business domain
                    domain = BUSINESS_DOMAINS[domain_idx % len(BUSINESS_DOMAINS)]
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
                        remaining -= batch_count  # Don't retry infinitely
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

                    # N8N-specific validation
                    try:
                        from app.detection_enterprise.n8n_workflow_validator import validate_n8n_input_data
                        further_valid = []
                        for entry in valid_entries:
                            ok, err = validate_n8n_input_data(dt.value, entry.input_data)
                            if ok:
                                further_valid.append(entry)
                            else:
                                invalid_errors.append(f"n8n: {err}")
                        valid_entries = further_valid
                    except ImportError:
                        pass  # Validator not yet available

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
                    # Only decrement by actual valid entries produced,
                    # not by batch_count — otherwise parse failures skip entries
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
                existing = [e for e in existing_dataset.get_entries_by_type(dt) if "n8n" in e.tags]

            current = len(existing)
            if current >= target_per_type:
                plan[dt.value] = {"status": "skip", "existing": current}
                continue

            needed = target_per_type - current
            n_easy = max(2, round(needed * e_frac))
            n_hard = max(2, round(needed * h_frac))
            n_medium = needed - n_easy - n_hard

            bs = 10 if dt.value in _WORKFLOW_TYPES else 15
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

        # Cost estimate (rough)
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
