"""PISAMA MCP Server for coding agent integration.

Exposes PISAMA's detection, scoring, and healing capabilities as MCP tools
for use by Claude Code, Codex, Gemini CLI, and other coding assistants.

Usage:
    python -m app.mcp.server --base-url http://localhost:8000 --api-key KEY --tenant-id ID

Configure in Claude Code settings.json:
    {
        "mcpServers": {
            "pisama": {
                "command": "python",
                "args": ["-m", "app.mcp.server", "--base-url", "...", "--api-key", "...", "--tenant-id", "..."]
            }
        }
    }
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

logger = logging.getLogger("pisama-mcp")


# ---------------------------------------------------------------------------
# Detection & fix type reference data
# ---------------------------------------------------------------------------

DETECTION_TYPES: Dict[str, str] = {
    "loop": "Exact, structural, and semantic infinite loop detection in agent state sequences",
    "corruption": "State corruption and invalid state transitions between agent steps",
    "persona_drift": "Agent persona drift and role confusion across interactions",
    "coordination": "Agent handoff and inter-agent communication failures",
    "hallucination": "Factual inaccuracy and unsupported claim detection",
    "injection": "Prompt injection attempts and adversarial input detection",
    "overflow": "Context window exhaustion and token budget overruns",
    "derailment": "Task focus deviation and goal abandonment mid-execution",
    "context": "Context neglect -- failure to use relevant prior context in responses",
    "communication": "Inter-agent communication breakdown and message loss",
    "specification": "Output versus specification mismatch in task completion",
    "decomposition": "Task breakdown failures -- poor subtask structure or missing dependencies",
    "workflow": "Workflow execution issues including node failures and ordering errors",
    "withholding": "Information withholding -- agent omits critical data from output",
    "completion": "Premature or delayed task completion signaling",
    "retrieval_quality": "Poor retrieval quality in RAG pipelines -- low relevance or missing docs",
    "grounding": "Grounding failures -- agent output not supported by source documents",
}

FIX_CATEGORIES: Dict[str, List[Dict[str, str]]] = {
    "Runtime Fixes": [
        {"type": "retry_with_backoff", "description": "Retry the failed operation with exponential backoff"},
        {"type": "state_rollback", "description": "Roll back to the last known good agent state"},
        {"type": "context_injection", "description": "Inject missing context into the agent prompt"},
        {"type": "agent_restart", "description": "Restart the failed agent with a clean state"},
        {"type": "escalate_to_human", "description": "Escalate the issue to a human operator"},
    ],
    "Configuration Fixes": [
        {"type": "adjust_threshold", "description": "Adjust detection thresholds based on feedback"},
        {"type": "update_persona", "description": "Update the agent persona/system prompt to prevent drift"},
        {"type": "token_budget", "description": "Adjust token budget or context window limits"},
        {"type": "loop_breaker", "description": "Add loop-breaking conditions to the workflow"},
    ],
    "Source Code Fixes": [
        {"type": "code_patch", "description": "Generate a code patch to fix the root cause in application source"},
        {"type": "guardrail_addition", "description": "Add input/output guardrails to the agent pipeline"},
        {"type": "validation_layer", "description": "Insert validation between agent steps"},
        {"type": "error_handler", "description": "Add or improve error handling in the agent code"},
    ],
    "Workflow Fixes": [
        {"type": "node_reorder", "description": "Reorder workflow nodes to fix dependency issues"},
        {"type": "add_checkpoint", "description": "Add checkpoints for state persistence and rollback"},
        {"type": "split_workflow", "description": "Split a complex workflow into smaller, safer sub-workflows"},
    ],
}


def _build_detection_types_markdown() -> str:
    """Return a Markdown document listing all 17 ICP detection types."""
    lines = [
        "# PISAMA Detection Types",
        "",
        "PISAMA monitors multi-agent orchestration traces for the following failure modes.",
        "Each detector runs at up to five escalation tiers (hash -> state delta -> embeddings -> LLM -> human).",
        "",
        "| # | Type | Description |",
        "|---|------|-------------|",
    ]
    for idx, (dtype, desc) in enumerate(DETECTION_TYPES.items(), start=1):
        lines.append(f"| {idx} | `{dtype}` | {desc} |")

    lines.extend([
        "",
        "## Tiered Escalation",
        "",
        "- **Tier 1 (Hash):** O(1) exact-match checks on state hashes",
        "- **Tier 2 (State Delta):** Structural comparison of state deltas",
        "- **Tier 3 (Embeddings):** Semantic similarity via pgvector embeddings",
        "- **Tier 4 (LLM Judge):** Claude-based reasoning for ambiguous cases",
        "- **Tier 5 (Human):** Escalate to human review when confidence is low",
        "",
        "## Confidence Scoring",
        "",
        "All detections report a confidence score from 0 to 100:",
        "- **80-100:** High confidence -- likely a real issue",
        "- **50-79:** Medium confidence -- review recommended",
        "- **0-49:** Low confidence -- may be a false positive",
    ])
    return "\n".join(lines)


def _build_fix_types_markdown() -> str:
    """Return a Markdown document listing available fix types by category."""
    lines = [
        "# PISAMA Fix Types",
        "",
        "Fixes are organized by category. Each detection may suggest one or more applicable fixes.",
        "",
    ]
    for category, fixes in FIX_CATEGORIES.items():
        lines.append(f"## {category}")
        lines.append("")
        lines.append("| Type | Description |")
        lines.append("|------|-------------|")
        for fix in fixes:
            lines.append(f"| `{fix['type']}` | {fix['description']} |")
        lines.append("")

    lines.extend([
        "## Fix Lifecycle",
        "",
        "1. **Generated** -- PISAMA produces a fix suggestion with confidence score",
        "2. **Reviewed** -- The fix is reviewed (automatic or human approval)",
        "3. **Applied** -- The fix is applied to the runtime, config, or source",
        "4. **Validated** -- Post-apply validation confirms the fix resolved the issue",
        "5. **Rolled back** -- If validation fails, the fix is rolled back automatically",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PISAMA API Client
# ---------------------------------------------------------------------------

class PISAMAMCPClient:
    """Async HTTP client that wraps the PISAMA backend REST API."""

    def __init__(self, base_url: str, api_key: str, tenant_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Tenant-ID": self.tenant_id,
                    "Content-Type": "application/json",
                    "User-Agent": "pisama-mcp-server/1.0",
                },
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # -- helpers --

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        client = await self._ensure_client()
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        client = await self._ensure_client()
        resp = await client.post(path, json=json_body or {})
        resp.raise_for_status()
        return resp.json()

    # -- traces --

    async def query_traces(
        self,
        *,
        framework: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "per_page": per_page}
        if framework:
            params["framework"] = framework
        if status:
            params["status"] = status
        if since:
            params["since"] = since
        return await self._get("/api/v1/traces", params=params)

    async def get_trace_detail(self, trace_id: str) -> Dict[str, Any]:
        return await self._get(f"/api/v1/traces/{trace_id}")

    # -- detections --

    async def query_detections(
        self,
        *,
        detection_type: Optional[str] = None,
        min_confidence: Optional[int] = None,
        since: Optional[str] = None,
        trace_id: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "per_page": per_page}
        if detection_type:
            params["type"] = detection_type
        if min_confidence is not None:
            params["min_confidence"] = min_confidence
        if since:
            params["since"] = since
        if trace_id:
            params["trace_id"] = trace_id
        return await self._get("/api/v1/detections", params=params)

    async def get_detection_detail(self, detection_id: str) -> Dict[str, Any]:
        return await self._get(f"/api/v1/detections/{detection_id}")

    # -- fixes --

    async def get_fix_suggestions(self, detection_id: str) -> Dict[str, Any]:
        return await self._get(f"/api/v1/healing/detections/{detection_id}/fixes")

    async def apply_fix(self, detection_id: str, fix_id: str) -> Dict[str, Any]:
        return await self._post(
            f"/api/v1/healing/detections/{detection_id}/heal",
            json_body={"fix_id": fix_id},
        )

    # -- feedback --

    async def submit_feedback(
        self,
        detection_id: str,
        is_correct: bool,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "detection_id": detection_id,
            "is_correct": is_correct,
        }
        if reason:
            body["reason"] = reason
        return await self._post("/api/v1/feedback", json_body=body)

    # -- scorers --

    async def create_scorer(
        self,
        name: str,
        description: str,
        framework: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"name": name, "description": description}
        if framework:
            body["framework"] = framework
        return await self._post("/api/v1/scorers", json_body=body)

    async def run_scorer(
        self,
        scorer_id: str,
        *,
        latest_n: Optional[int] = None,
        trace_ids: Optional[List[str]] = None,
        framework: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if latest_n is not None:
            body["latest_n"] = latest_n
        if trace_ids:
            body["trace_ids"] = trace_ids
        if framework:
            body["framework"] = framework
        return await self._post(f"/api/v1/scorers/{scorer_id}/run", json_body=body)

    async def list_scorers(self) -> Dict[str, Any]:
        return await self._get("/api/v1/scorers")

    # -- conversation evaluation --

    async def evaluate_conversation(self, trace_id: str) -> Dict[str, Any]:
        return await self._post(f"/api/v1/conversations/{trace_id}/analyze")

    # -- source fixes --

    async def generate_source_fix(
        self,
        detection_id: str,
        file_path: str,
        file_content: str,
        language: str,
    ) -> Dict[str, Any]:
        return await self._post(
            f"/api/v1/source-fixes/detections/{detection_id}/source-fix",
            json_body={
                "language": language,
                "context": {
                    "file_path": file_path,
                    "file_content": file_content,
                },
            },
        )

    # -- health --

    async def get_health(self) -> Dict[str, Any]:
        return await self._get("/health")


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: List[Tool] = [
    Tool(
        name="pisama_query_traces",
        description=(
            "Search PISAMA traces with optional filters. Returns paginated trace "
            "summaries including framework, status, token counts, and timestamps."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "framework": {
                    "type": "string",
                    "description": "Filter by agent framework (langgraph, crewai, autogen, n8n, claude-code)",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by trace status (active, completed, failed)",
                },
                "since": {
                    "type": "string",
                    "description": "ISO-8601 datetime -- only return traces created after this timestamp",
                },
                "page": {
                    "type": "integer",
                    "description": "Page number for pagination (default: 1)",
                    "default": 1,
                    "minimum": 1,
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (default: 20, max: 100)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="pisama_query_detections",
        description=(
            "Search PISAMA detections (failure mode alerts) with optional filters. "
            "Returns detection type, confidence, method, and associated trace."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": (
                        "Detection type to filter by. One of: "
                        + ", ".join(sorted(DETECTION_TYPES.keys()))
                    ),
                },
                "min_confidence": {
                    "type": "integer",
                    "description": "Minimum confidence score (0-100) to include",
                    "minimum": 0,
                    "maximum": 100,
                },
                "since": {
                    "type": "string",
                    "description": "ISO-8601 datetime -- only return detections after this timestamp",
                },
                "trace_id": {
                    "type": "string",
                    "description": "Filter detections to a specific trace ID (UUID)",
                },
                "page": {
                    "type": "integer",
                    "description": "Page number (default: 1)",
                    "default": 1,
                    "minimum": 1,
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (default: 20, max: 100)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="pisama_get_trace_detail",
        description=(
            "Get full detail for a single trace including all agent states, "
            "detections, token usage, and timeline."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "trace_id": {
                    "type": "string",
                    "description": "UUID of the trace to retrieve",
                },
            },
            "required": ["trace_id"],
        },
    ),
    Tool(
        name="pisama_get_detection_detail",
        description=(
            "Get full detail for a single detection including explanation, "
            "evidence, confidence breakdown, and suggested fixes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "detection_id": {
                    "type": "string",
                    "description": "UUID of the detection to retrieve",
                },
            },
            "required": ["detection_id"],
        },
    ),
    Tool(
        name="pisama_get_fix_suggestions",
        description=(
            "Get fix suggestions for a specific detection. Returns a list of "
            "applicable fixes with descriptions, confidence, and risk assessment."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "detection_id": {
                    "type": "string",
                    "description": "UUID of the detection to get fixes for",
                },
            },
            "required": ["detection_id"],
        },
    ),
    Tool(
        name="pisama_apply_fix",
        description=(
            "Apply a specific fix to resolve a detection. The fix must have been "
            "previously suggested via pisama_get_fix_suggestions."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "detection_id": {
                    "type": "string",
                    "description": "UUID of the detection the fix belongs to",
                },
                "fix_id": {
                    "type": "string",
                    "description": "ID of the fix to apply (from fix suggestions)",
                },
            },
            "required": ["detection_id", "fix_id"],
        },
    ),
    Tool(
        name="pisama_submit_feedback",
        description=(
            "Submit feedback on whether a detection was a true positive (correct) "
            "or false positive (incorrect). Used to improve detection accuracy."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "detection_id": {
                    "type": "string",
                    "description": "UUID of the detection to submit feedback for",
                },
                "is_correct": {
                    "type": "boolean",
                    "description": "True if the detection was correct (true positive), false if incorrect (false positive)",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional explanation of why the detection is correct or incorrect",
                },
            },
            "required": ["detection_id", "is_correct"],
        },
    ),
    Tool(
        name="pisama_create_scorer",
        description=(
            "Create a custom scorer from a natural-language description. "
            "PISAMA generates an LLM prompt template that can be run against traces."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Short name for the scorer (e.g., 'tool-use-efficiency')",
                },
                "description": {
                    "type": "string",
                    "description": (
                        "Natural-language description of what to score. "
                        "Be specific: 'Rate how efficiently the agent uses tools -- "
                        "penalize redundant tool calls and reward minimal-step solutions.'"
                    ),
                },
                "framework": {
                    "type": "string",
                    "description": "Optional framework filter (langgraph, crewai, n8n)",
                },
            },
            "required": ["name", "description"],
        },
    ),
    Tool(
        name="pisama_run_scorer",
        description=(
            "Run an existing custom scorer against traces. Returns per-trace scores, "
            "letter grades (A+ through F), and aggregate statistics."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "scorer_id": {
                    "type": "string",
                    "description": "UUID of the scorer to run",
                },
                "latest_n": {
                    "type": "integer",
                    "description": "Score the N most recent traces (default: 10)",
                    "minimum": 1,
                    "maximum": 500,
                },
                "trace_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific trace UUIDs to score (alternative to latest_n)",
                },
                "framework": {
                    "type": "string",
                    "description": "Filter traces by framework before scoring",
                },
            },
            "required": ["scorer_id"],
        },
    ),
    Tool(
        name="pisama_list_scorers",
        description="List all custom scorers configured for this tenant.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="pisama_evaluate_conversation",
        description=(
            "Run turn-aware evaluation on a conversation trace. Detects context neglect, "
            "task derailment, repetitive loops, and other conversation-level failures."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "trace_id": {
                    "type": "string",
                    "description": "UUID of the conversation trace to evaluate",
                },
            },
            "required": ["trace_id"],
        },
    ),
    Tool(
        name="pisama_generate_source_fix",
        description=(
            "Generate a source-level code fix for a detection. Provide the relevant file "
            "and PISAMA will produce a diff patch, description, and confidence score."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "detection_id": {
                    "type": "string",
                    "description": "UUID of the detection to generate a source fix for",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the source file containing the code to fix",
                },
                "file_content": {
                    "type": "string",
                    "description": "Full content of the source file",
                },
                "language": {
                    "type": "string",
                    "description": "Programming language (python, typescript, javascript, go, rust)",
                },
            },
            "required": ["detection_id", "file_path", "file_content", "language"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Resource definitions
# ---------------------------------------------------------------------------

RESOURCES: List[Resource] = [
    Resource(
        uri="pisama://docs/detection-types",
        name="PISAMA Detection Types Reference",
        description="Complete reference of all 17 ICP detection types with descriptions and tier info",
        mimeType="text/markdown",
    ),
    Resource(
        uri="pisama://docs/fix-types",
        name="PISAMA Fix Types Reference",
        description="Reference of all fix types organized by category with lifecycle documentation",
        mimeType="text/markdown",
    ),
    Resource(
        uri="pisama://status/summary",
        name="PISAMA System Status",
        description="Current health and status summary of the PISAMA platform",
        mimeType="application/json",
    ),
]


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

_UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _validate_uuid(value: str, field_name: str) -> str:
    """Validate that a string looks like a UUID and return it stripped."""
    import re

    value = value.strip()
    if not re.match(_UUID_PATTERN, value):
        raise ValueError(f"{field_name} must be a valid UUID, got: {value!r}")
    return value


def _validate_int_range(
    value: Any,
    field_name: str,
    min_val: int,
    max_val: int,
    default: int,
) -> int:
    """Validate an optional integer parameter falls within range."""
    if value is None:
        return default
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer, got: {value!r}")
    if v < min_val or v > max_val:
        raise ValueError(f"{field_name} must be between {min_val} and {max_val}, got: {v}")
    return v


def _validate_iso_datetime(value: Optional[str], field_name: str) -> Optional[str]:
    """Validate an optional ISO-8601 datetime string."""
    if value is None:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} must be a valid ISO-8601 datetime, got: {value!r}")
    return value


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

def create_server(api_client: PISAMAMCPClient) -> Server:
    """Create and configure the MCP server with all tools and resources."""

    server = Server("pisama")

    # -- List tools --

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return TOOLS

    # -- List resources --

    @server.list_resources()
    async def list_resources() -> List[Resource]:
        return RESOURCES

    # -- Read resource --

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        if uri == "pisama://docs/detection-types":
            return _build_detection_types_markdown()

        if uri == "pisama://docs/fix-types":
            return _build_fix_types_markdown()

        if uri == "pisama://status/summary":
            try:
                health = await api_client.get_health()
            except Exception as exc:
                health = {
                    "status": "unreachable",
                    "error": str(exc),
                }
            summary = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "health": health,
                "detection_types_count": len(DETECTION_TYPES),
                "fix_categories_count": len(FIX_CATEGORIES),
                "mcp_server_version": "1.0.0",
            }
            return json.dumps(summary, indent=2, default=str)

        raise ValueError(f"Unknown resource URI: {uri}")

    # -- Call tool --

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            result = await _dispatch_tool(api_client, name, arguments or {})
            text = json.dumps(result, indent=2, default=str) if isinstance(result, (dict, list)) else str(result)
            return [TextContent(type="text", text=text)]
        except ValueError as exc:
            return [TextContent(type="text", text=f"Validation error: {exc}")]
        except httpx.HTTPStatusError as exc:
            error_body = ""
            try:
                error_body = exc.response.json()
            except Exception:
                error_body = exc.response.text
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": f"PISAMA API returned {exc.response.status_code}",
                            "detail": error_body,
                        },
                        indent=2,
                        default=str,
                    ),
                )
            ]
        except httpx.RequestError as exc:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": "Failed to reach PISAMA API",
                            "detail": str(exc),
                        },
                        indent=2,
                    ),
                )
            ]
        except Exception as exc:
            logger.exception("Unexpected error in tool %s", name)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": "Internal MCP server error",
                            "detail": str(exc),
                        },
                        indent=2,
                    ),
                )
            ]

    return server


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

async def _dispatch_tool(
    client: PISAMAMCPClient,
    name: str,
    args: Dict[str, Any],
) -> Any:
    """Route a tool call to the correct API client method with validation."""

    if name == "pisama_query_traces":
        page = _validate_int_range(args.get("page"), "page", 1, 10_000, 1)
        per_page = _validate_int_range(args.get("per_page"), "per_page", 1, 100, 20)
        since = _validate_iso_datetime(args.get("since"), "since")
        return await client.query_traces(
            framework=args.get("framework"),
            status=args.get("status"),
            since=since,
            page=page,
            per_page=per_page,
        )

    if name == "pisama_query_detections":
        page = _validate_int_range(args.get("page"), "page", 1, 10_000, 1)
        per_page = _validate_int_range(args.get("per_page"), "per_page", 1, 100, 20)
        min_confidence = args.get("min_confidence")
        if min_confidence is not None:
            min_confidence = _validate_int_range(min_confidence, "min_confidence", 0, 100, 0)
        since = _validate_iso_datetime(args.get("since"), "since")
        dtype = args.get("type")
        if dtype and dtype not in DETECTION_TYPES:
            raise ValueError(
                f"Unknown detection type: {dtype!r}. "
                f"Valid types: {', '.join(sorted(DETECTION_TYPES.keys()))}"
            )
        trace_id = args.get("trace_id")
        if trace_id:
            trace_id = _validate_uuid(trace_id, "trace_id")
        return await client.query_detections(
            detection_type=dtype,
            min_confidence=min_confidence,
            since=since,
            trace_id=trace_id,
            page=page,
            per_page=per_page,
        )

    if name == "pisama_get_trace_detail":
        trace_id = _validate_uuid(args["trace_id"], "trace_id")
        return await client.get_trace_detail(trace_id)

    if name == "pisama_get_detection_detail":
        detection_id = _validate_uuid(args["detection_id"], "detection_id")
        return await client.get_detection_detail(detection_id)

    if name == "pisama_get_fix_suggestions":
        detection_id = _validate_uuid(args["detection_id"], "detection_id")
        return await client.get_fix_suggestions(detection_id)

    if name == "pisama_apply_fix":
        detection_id = _validate_uuid(args["detection_id"], "detection_id")
        fix_id = args.get("fix_id", "").strip()
        if not fix_id:
            raise ValueError("fix_id is required")
        return await client.apply_fix(detection_id, fix_id)

    if name == "pisama_submit_feedback":
        detection_id = _validate_uuid(args["detection_id"], "detection_id")
        is_correct = args.get("is_correct")
        if is_correct is None:
            raise ValueError("is_correct is required (true or false)")
        if not isinstance(is_correct, bool):
            raise ValueError(f"is_correct must be a boolean, got: {type(is_correct).__name__}")
        return await client.submit_feedback(
            detection_id=detection_id,
            is_correct=is_correct,
            reason=args.get("reason"),
        )

    if name == "pisama_create_scorer":
        name_val = (args.get("name") or "").strip()
        description = (args.get("description") or "").strip()
        if not name_val:
            raise ValueError("name is required")
        if len(description) < 10:
            raise ValueError("description must be at least 10 characters")
        return await client.create_scorer(
            name=name_val,
            description=description,
            framework=args.get("framework"),
        )

    if name == "pisama_run_scorer":
        scorer_id = _validate_uuid(args["scorer_id"], "scorer_id")
        latest_n = args.get("latest_n")
        trace_ids = args.get("trace_ids")
        if latest_n is not None:
            latest_n = _validate_int_range(latest_n, "latest_n", 1, 500, 10)
        if trace_ids:
            trace_ids = [_validate_uuid(tid, "trace_ids[]") for tid in trace_ids]
        if latest_n is None and not trace_ids:
            latest_n = 10  # sensible default
        return await client.run_scorer(
            scorer_id=scorer_id,
            latest_n=latest_n,
            trace_ids=trace_ids,
            framework=args.get("framework"),
        )

    if name == "pisama_list_scorers":
        return await client.list_scorers()

    if name == "pisama_evaluate_conversation":
        trace_id = _validate_uuid(args["trace_id"], "trace_id")
        return await client.evaluate_conversation(trace_id)

    if name == "pisama_generate_source_fix":
        detection_id = _validate_uuid(args["detection_id"], "detection_id")
        file_path = (args.get("file_path") or "").strip()
        file_content = args.get("file_content", "")
        language = (args.get("language") or "").strip().lower()
        if not file_path:
            raise ValueError("file_path is required")
        if not file_content:
            raise ValueError("file_content is required (provide the full file content)")
        supported_languages = {"python", "typescript", "javascript", "go", "rust", "java", "ruby"}
        if language not in supported_languages:
            raise ValueError(
                f"Unsupported language: {language!r}. "
                f"Supported: {', '.join(sorted(supported_languages))}"
            )
        return await client.generate_source_fix(
            detection_id=detection_id,
            file_path=file_path,
            file_content=file_content,
            language=language,
        )

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for the MCP server."""
    parser = argparse.ArgumentParser(
        prog="pisama-mcp-server",
        description="PISAMA MCP Server -- expose detection, scoring, and healing tools to coding agents",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="PISAMA backend API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="API key for authenticating with the PISAMA backend",
    )
    parser.add_argument(
        "--tenant-id",
        required=True,
        help="Tenant ID for multi-tenant isolation",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: WARNING -- keep stdio clean for MCP transport)",
    )
    return parser.parse_args(argv)


async def main(argv: Optional[List[str]] = None) -> None:
    """Async entry point: create client, server, and run stdio transport."""
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,  # MCP uses stdout for JSON-RPC; logs go to stderr
    )

    api_client = PISAMAMCPClient(
        base_url=args.base_url,
        api_key=args.api_key,
        tenant_id=args.tenant_id,
    )

    server = create_server(api_client)

    logger.info(
        "Starting PISAMA MCP server (base_url=%s, tenant=%s)",
        args.base_url,
        args.tenant_id,
    )

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await api_client.close()
        logger.info("PISAMA MCP server shut down")


if __name__ == "__main__":
    asyncio.run(main())
