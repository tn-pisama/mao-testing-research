"""MAO MCP Server implementation.

A secure MCP server for AI assistants to analyze agent traces and get fix suggestions.

Security notes:
- All tools are READ-ONLY (no apply_fix exposed)
- Rate limiting prevents abuse
- All inputs are validated
- Audit logging for all operations
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from mao.core.client import MAOClient
from mao.core.security import validate_trace_id, validate_detection_id, get_config_dir
from mao.core.errors import MAOError, ValidationError

logger = logging.getLogger("mao.mcp")


class RateLimiter:
    """Simple rate limiter."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: List[datetime] = []
    
    async def acquire(self) -> bool:
        """Acquire rate limit token."""
        now = datetime.utcnow()
        
        self.requests = [
            r for r in self.requests
            if (now - r).total_seconds() < 60
        ]
        
        if len(self.requests) >= self.requests_per_minute:
            return False
        
        self.requests.append(now)
        return True


class AuditLogger:
    """Audit logger for MCP operations."""
    
    def __init__(self):
        self.log_path = get_config_dir() / "mcp_audit.log"
    
    def log(self, action: str, data: Dict[str, Any]) -> None:
        """Log an action."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "data": data,
        }
        
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


class MAOMCPServer:
    """MCP server for MAO agent testing platform."""
    
    def __init__(self, endpoint: str, api_key: str, tenant_id: str = "default"):
        self.client = MAOClient(endpoint, api_key, tenant_id)
        self.rate_limiter = RateLimiter(requests_per_minute=60)
        self.audit = AuditLogger()
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an MCP tool call."""
        if not await self.rate_limiter.acquire():
            return {"error": "Rate limit exceeded. Try again in a minute."}
        
        self.audit.log(tool_name, arguments)
        
        try:
            if tool_name == "mao_analyze_trace":
                return await self._analyze_trace(arguments)
            elif tool_name == "mao_get_detections":
                return await self._get_detections(arguments)
            elif tool_name == "mao_get_fix_suggestions":
                return await self._get_fix_suggestions(arguments)
            elif tool_name == "mao_get_trace":
                return await self._get_trace(arguments)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except ValidationError as e:
            return {"error": f"Validation error: {e}"}
        except MAOError as e:
            return {"error": str(e)}
        except Exception as e:
            logger.exception(f"Error in {tool_name}")
            return {"error": f"Internal error: {type(e).__name__}"}
    
    async def _analyze_trace(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a trace for agent failures."""
        trace_id = validate_trace_id(args.get("trace_id", ""))
        result = await self.client.analyze_trace(trace_id)
        return self._format_analysis(result)
    
    async def _get_detections(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detections for a trace or time range."""
        trace_id = args.get("trace_id")
        if trace_id:
            trace_id = validate_trace_id(trace_id)
        
        detections = await self.client.get_detections(
            trace_id=trace_id,
            severity=args.get("severity"),
            detection_type=args.get("type"),
        )
        return {"detections": detections, "count": len(detections)}
    
    async def _get_fix_suggestions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get fix suggestions for a detection."""
        detection_id = validate_detection_id(args.get("detection_id", ""))
        level = args.get("level")
        
        fixes = await self.client.get_fix_suggestions(detection_id, level)
        return {"fixes": fixes, "count": len(fixes)}
    
    async def _get_trace(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get trace details."""
        trace_id = validate_trace_id(args.get("trace_id", ""))
        return await self.client.get_trace(trace_id)
    
    def _format_analysis(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format analysis result for AI consumption."""
        detections = result.get("detections", [])
        
        summary = f"Trace {result.get('trace_id', 'unknown')}: "
        if detections:
            high = sum(1 for d in detections if d.get("severity") == "high")
            medium = sum(1 for d in detections if d.get("severity") == "medium")
            summary += f"{len(detections)} issues found ({high} high, {medium} medium)"
        else:
            summary += "No issues detected"
        
        return {
            "summary": summary,
            "trace_id": result.get("trace_id"),
            "framework": result.get("framework"),
            "healthy": result.get("healthy", True),
            "detections": detections,
            "next_steps": self._get_next_steps(detections),
        }
    
    def _get_next_steps(self, detections: List[Dict[str, Any]]) -> List[str]:
        """Get recommended next steps."""
        if not detections:
            return ["No action needed - trace is healthy"]
        
        steps = []
        for det in detections[:3]:
            det_id = det.get("id", "")
            det_type = det.get("type", "unknown")
            steps.append(f"Get fix suggestions: mao_get_fix_suggestions(detection_id='{det_id}')")
        
        return steps
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """Get MCP tools schema."""
        return [
            {
                "name": "mao_analyze_trace",
                "description": "Analyze an agent trace for failures (loops, state corruption, persona drift, deadlock). Returns detected issues with severity and recommended fixes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "trace_id": {
                            "type": "string",
                            "description": "The trace ID to analyze",
                        },
                    },
                    "required": ["trace_id"],
                },
            },
            {
                "name": "mao_get_detections",
                "description": "Get all detections, optionally filtered by trace, severity, or type.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "trace_id": {
                            "type": "string",
                            "description": "Filter by trace ID",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Filter by severity",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["infinite_loop", "state_corruption", "persona_drift", "deadlock"],
                            "description": "Filter by detection type",
                        },
                    },
                },
            },
            {
                "name": "mao_get_fix_suggestions",
                "description": "Get code fix suggestions for a detected issue. Returns ready-to-apply code changes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "detection_id": {
                            "type": "string",
                            "description": "The detection ID",
                        },
                        "level": {
                            "type": "string",
                            "enum": ["light", "moderate", "aggressive"],
                            "description": "Reinforcement level for persona fixes",
                        },
                    },
                    "required": ["detection_id"],
                },
            },
            {
                "name": "mao_get_trace",
                "description": "Get full trace details including all spans and events.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "trace_id": {
                            "type": "string",
                            "description": "The trace ID",
                        },
                    },
                    "required": ["trace_id"],
                },
            },
        ]
    
    def get_resources_schema(self) -> List[Dict[str, Any]]:
        """Get MCP resources schema."""
        return [
            {
                "uri": "mao://docs/detection-types",
                "name": "Detection Types Documentation",
                "description": "Documentation for all detection types (loop, corruption, drift, deadlock)",
                "mimeType": "text/markdown",
            },
            {
                "uri": "mao://docs/fix-types",
                "name": "Fix Types Documentation",
                "description": "Documentation for available fix suggestion types",
                "mimeType": "text/markdown",
            },
        ]
    
    async def read_resource(self, uri: str) -> str:
        """Read an MCP resource."""
        if uri == "mao://docs/detection-types":
            return DETECTION_TYPES_DOC
        elif uri == "mao://docs/fix-types":
            return FIX_TYPES_DOC
        else:
            return f"Unknown resource: {uri}"


DETECTION_TYPES_DOC = """# MAO Detection Types

## Infinite Loop
Detects when agents get stuck in repetitive patterns:
- Tool calls with identical inputs
- Conversation loops between agents
- Structural repetition in execution

**Severity indicators:**
- HIGH: >10 iterations, identical outputs
- MEDIUM: 5-10 iterations, similar outputs
- LOW: 3-5 iterations, related outputs

## State Corruption
Detects inconsistent or invalid state changes:
- Schema violations
- Impossible value transitions
- Cross-field inconsistencies

## Persona Drift
Detects when agents deviate from their assigned roles:
- Tone changes
- Capability expansion beyond role
- Role abandonment

## Deadlock
Detects circular waits in multi-agent systems:
- Agent A waiting for Agent B, Agent B waiting for Agent A
- Resource contention
- Infinite delegation chains
"""

FIX_TYPES_DOC = """# MAO Fix Types

## For Infinite Loops
- **max_iterations**: Add iteration limits
- **exponential_backoff**: Slow down repeated operations
- **circuit_breaker**: Stop calling failing components

## For State Corruption
- **state_validation**: Add Pydantic validators
- **schema_enforcement**: Add JSON schema checks
- **cross_field_validation**: Add consistency checks

## For Persona Drift
- **prompt_reinforcement**: Strengthen system prompts
- **role_boundary**: Add output validation
- **periodic_reset**: Reset context periodically

## For Deadlock
- **timeout**: Add operation timeouts
- **priority**: Add resource priority ordering
- **async_handoff**: Convert to async patterns
"""


async def run_server(endpoint: str, api_key: str, tenant_id: str = "default"):
    """Run the MCP server using stdio transport."""
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        import mcp.types as types
    except ImportError:
        print("MCP SDK not installed. Install with: pip install mcp")
        return
    
    server = Server("mao-agent-testing")
    mao = MAOMCPServer(endpoint, api_key, tenant_id)
    
    @server.list_tools()
    async def list_tools() -> List[types.Tool]:
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in mao.get_tools_schema()
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> List[types.TextContent]:
        result = await mao.handle_tool_call(name, arguments)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    
    @server.list_resources()
    async def list_resources() -> List[types.Resource]:
        return [
            types.Resource(
                uri=r["uri"],
                name=r["name"],
                description=r["description"],
                mimeType=r["mimeType"],
            )
            for r in mao.get_resources_schema()
        ]
    
    @server.read_resource()
    async def read_resource(uri: str) -> str:
        return await mao.read_resource(uri)
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python -m mao.mcp.server <endpoint> <api_key> [tenant_id]")
        sys.exit(1)
    
    endpoint = sys.argv[1]
    api_key = sys.argv[2]
    tenant_id = sys.argv[3] if len(sys.argv) > 3 else "default"
    
    asyncio.run(run_server(endpoint, api_key, tenant_id))
