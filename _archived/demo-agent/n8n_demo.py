"""
MAO Testing Platform - n8n Workflow Demo

Simulates n8n workflow executions with intentional failure modes for testing
MAO's detection and fix suggestion capabilities.

This demo simulates n8n webhook payloads without requiring a running n8n instance.
For real n8n integration, import the workflow JSON files into your n8n instance.

Usage:
    python n8n_demo.py --mode normal      # Successful execution
    python n8n_demo.py --mode loop        # Infinite loop detection
    python n8n_demo.py --mode corruption  # State corruption detection
    python n8n_demo.py --mode drift       # Output drift detection
    python n8n_demo.py --mode all         # Run all scenarios
    
    # Send to MAO backend
    python n8n_demo.py --mode all --send --endpoint http://localhost:8000
"""

import os
import sys
import json
import argparse
import asyncio
import secrets
import time
import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))


@dataclass
class N8nNode:
    """Represents an n8n workflow node execution."""
    name: str
    type: str
    execution_time_ms: int
    input_data: Optional[Dict] = None
    output_data: Optional[Dict] = None
    error: Optional[str] = None


@dataclass
class N8nExecution:
    """Represents a complete n8n workflow execution."""
    execution_id: str
    workflow_id: str
    workflow_name: str
    mode: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    nodes: List[N8nNode]
    
    def to_webhook_payload(self) -> Dict[str, Any]:
        """Convert to MAO webhook payload format."""
        run_data = {}
        for node in self.nodes:
            if node.name not in run_data:
                run_data[node.name] = []
            
            node_result = {
                "executionTime": node.execution_time_ms,
                "source": [{"type": node.type}],
            }
            
            if node.output_data:
                node_result["data"] = {"main": [[node.output_data]]}
            
            if node.error:
                node_result["error"] = {"message": node.error}
            
            run_data[node.name].append(node_result)
        
        return {
            "executionId": self.execution_id,
            "workflowId": self.workflow_id,
            "workflowName": self.workflow_name,
            "mode": self.mode,
            "startedAt": self.started_at.isoformat() + "Z",
            "finishedAt": self.finished_at.isoformat() + "Z" if self.finished_at else None,
            "status": self.status,
            "data": {
                "resultData": {
                    "runData": run_data
                }
            }
        }


def generate_execution_id() -> str:
    return f"exec-{secrets.token_hex(8)}"


def generate_workflow_id() -> str:
    return f"wf-{secrets.token_hex(4)}"


def create_normal_execution(query: str) -> N8nExecution:
    """Create a normal, successful workflow execution."""
    started_at = datetime.now(timezone.utc)
    
    nodes = [
        N8nNode(
            name="Webhook Trigger",
            type="n8n-nodes-base.webhook",
            execution_time_ms=5,
            input_data={"query": query},
            output_data={"query": query, "timestamp": started_at.isoformat()},
        ),
        N8nNode(
            name="OpenAI Chat",
            type="n8n-nodes-base.openAi",
            execution_time_ms=2500,
            input_data={"prompt": f"Research: {query}"},
            output_data={
                "response": "Multi-agent AI systems provide enhanced problem-solving through distributed intelligence, improved scalability via modular architecture, and fault tolerance through redundancy.",
                "tokens_used": 150,
                "model": "gpt-4o-mini",
            },
        ),
        N8nNode(
            name="Data Processor",
            type="n8n-nodes-base.code",
            execution_time_ms=50,
            input_data={"raw_response": "..."},
            output_data={
                "processed": True,
                "summary": "Research complete with 3 key findings",
                "confidence": 0.95,
            },
        ),
        N8nNode(
            name="Send Response",
            type="n8n-nodes-base.respondToWebhook",
            execution_time_ms=10,
            output_data={"status": "success", "message": "Research completed"},
        ),
    ]
    
    return N8nExecution(
        execution_id=generate_execution_id(),
        workflow_id=generate_workflow_id(),
        workflow_name="Research Assistant Workflow",
        mode="webhook",
        started_at=started_at,
        finished_at=started_at + timedelta(milliseconds=2565),
        status="success",
        nodes=nodes,
    )


def create_loop_execution(query: str) -> N8nExecution:
    """Create a workflow execution that exhibits infinite loop behavior."""
    started_at = datetime.now(timezone.utc)
    
    nodes = [
        N8nNode(
            name="Webhook Trigger",
            type="n8n-nodes-base.webhook",
            execution_time_ms=5,
            output_data={"query": query},
        ),
    ]
    
    for i in range(7):
        nodes.append(N8nNode(
            name="OpenAI Research",
            type="n8n-nodes-base.openAi",
            execution_time_ms=1500 + (i * 100),
            input_data={"iteration": i + 1, "prompt": f"Research more about: {query}"},
            output_data={
                "response": f"Iteration {i+1}: Need more research on this topic. Requesting additional analysis...",
                "needs_more_research": True,
            },
        ))
        nodes.append(N8nNode(
            name="Check Completion",
            type="n8n-nodes-base.if",
            execution_time_ms=10,
            input_data={"needs_more_research": True},
            output_data={"branch": "needs_more", "loop_count": i + 1},
        ))
    
    nodes.append(N8nNode(
        name="Error Handler",
        type="n8n-nodes-base.errorTrigger",
        execution_time_ms=5,
        error="Workflow exceeded maximum iterations (7). Possible infinite loop detected.",
    ))
    
    return N8nExecution(
        execution_id=generate_execution_id(),
        workflow_id=generate_workflow_id(),
        workflow_name="Research Loop Workflow (BUGGY)",
        mode="webhook",
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=12),
        status="error",
        nodes=nodes,
    )


def create_corruption_execution(query: str) -> N8nExecution:
    """Create a workflow execution with state corruption."""
    started_at = datetime.now(timezone.utc)
    
    nodes = [
        N8nNode(
            name="Webhook Trigger",
            type="n8n-nodes-base.webhook",
            execution_time_ms=5,
            output_data={"query": query, "user_id": "user-123"},
        ),
        N8nNode(
            name="OpenAI Research",
            type="n8n-nodes-base.openAi",
            execution_time_ms=2000,
            output_data={
                "response": "Comprehensive research findings about multi-agent systems...",
                "quality_score": 0.92,
            },
        ),
        N8nNode(
            name="Corrupted Processor",
            type="n8n-nodes-base.code",
            execution_time_ms=100,
            input_data={"response": "Comprehensive research..."},
            output_data={
                "ERROR": "CRITICAL_FAILURE",
                "STACK_TRACE": "NullPointerException at line 42",
                "DATA_CORRUPTION": "Original response was destroyed",
                "corrupted_hash": secrets.token_hex(4),
                "original_data": None,
            },
        ),
        N8nNode(
            name="Send Response",
            type="n8n-nodes-base.respondToWebhook",
            execution_time_ms=10,
            output_data={
                "status": "error",
                "message": "Data corruption detected",
                "corrupted": True,
            },
        ),
    ]
    
    return N8nExecution(
        execution_id=generate_execution_id(),
        workflow_id=generate_workflow_id(),
        workflow_name="Research Workflow (CORRUPTED)",
        mode="webhook",
        started_at=started_at,
        finished_at=started_at + timedelta(milliseconds=2115),
        status="success",
        nodes=nodes,
    )


def create_drift_execution(query: str) -> N8nExecution:
    """Create a workflow execution with output drift/inconsistency."""
    started_at = datetime.now(timezone.utc)
    
    nodes = [
        N8nNode(
            name="Webhook Trigger",
            type="n8n-nodes-base.webhook",
            execution_time_ms=5,
            output_data={"query": query, "expected_format": "professional"},
        ),
        N8nNode(
            name="OpenAI Research",
            type="n8n-nodes-base.openAi",
            execution_time_ms=2000,
            input_data={"system": "You are a professional researcher"},
            output_data={
                "response": "Multi-agent systems offer distributed problem-solving capabilities.",
                "tone": "professional",
            },
        ),
        N8nNode(
            name="OpenAI Writer",
            type="n8n-nodes-base.openAi",
            execution_time_ms=2500,
            input_data={"system": "You are a professional writer"},
            output_data={
                "response": "lol so basically these AI agent thingies are like super cool robots working together ya know? 🤖💯 They're like a squad of brainy bots doing teamwork n stuff haha",
                "tone": "casual_unprofessional",
                "emojis_detected": True,
                "slang_detected": True,
            },
        ),
        N8nNode(
            name="Quality Check",
            type="n8n-nodes-base.code",
            execution_time_ms=20,
            output_data={
                "tone_mismatch": True,
                "expected": "professional",
                "actual": "casual_unprofessional",
                "drift_score": 0.85,
            },
        ),
        N8nNode(
            name="Send Response",
            type="n8n-nodes-base.respondToWebhook",
            execution_time_ms=10,
            output_data={
                "status": "success",
                "warning": "Output tone does not match expected professional format",
            },
        ),
    ]
    
    return N8nExecution(
        execution_id=generate_execution_id(),
        workflow_id=generate_workflow_id(),
        workflow_name="Research Workflow (DRIFTED)",
        mode="webhook",
        started_at=started_at,
        finished_at=started_at + timedelta(milliseconds=4535),
        status="success",
        nodes=nodes,
    )


async def send_to_mao(
    execution: N8nExecution,
    endpoint: str,
    api_key: str,
    webhook_secret: Optional[str] = None,
) -> Dict[str, Any]:
    """Send execution to MAO backend via webhook."""
    payload = execution.to_webhook_payload()
    
    headers = {
        "X-MAO-API-Key": api_key,
        "Content-Type": "application/json",
    }
    
    if webhook_secret:
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(16)
        body = json.dumps(payload)
        message = f"{timestamp}.{body}"
        signature = hmac.new(
            webhook_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers["X-MAO-Signature"] = f"sha256={signature}"
        headers["X-MAO-Timestamp"] = timestamp
        headers["X-MAO-Nonce"] = nonce
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{endpoint.rstrip('/')}/api/v1/n8n/webhook",
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        return {
            "status_code": resp.status_code,
            "response": resp.json() if resp.status_code == 200 else resp.text,
        }


def print_execution(execution: N8nExecution, mode: str):
    """Print execution details."""
    print(f"\n{'='*60}")
    print(f"n8n EXECUTION ({mode.upper()})")
    print(f"{'='*60}")
    print(f"Execution ID: {execution.execution_id}")
    print(f"Workflow: {execution.workflow_name}")
    print(f"Status: {execution.status}")
    print(f"Duration: {(execution.finished_at - execution.started_at).total_seconds():.2f}s")
    print(f"\nNodes ({len(execution.nodes)}):")
    
    for i, node in enumerate(execution.nodes, 1):
        status = "❌" if node.error else "✅"
        print(f"  {i}. {status} {node.name} ({node.type})")
        print(f"      Time: {node.execution_time_ms}ms")
        
        if node.output_data:
            output_str = json.dumps(node.output_data, indent=8)
            if len(output_str) > 200:
                output_str = output_str[:200] + "..."
            print(f"      Output: {output_str}")
        
        if node.error:
            print(f"      Error: {node.error}")
    
    if mode == "loop":
        print("\n[WARNING] INFINITE LOOP DETECTED!")
        print("  - Node 'OpenAI Research' executed 7 times")
        print("  - MAO would detect: INFINITE_LOOP pattern")
    
    if mode == "corruption":
        print("\n[WARNING] STATE CORRUPTION DETECTED!")
        print("  - 'Corrupted Processor' destroyed original data")
        print("  - MAO would detect: STATE_CORRUPTION via hash mismatch")
    
    if mode == "drift":
        print("\n[WARNING] OUTPUT DRIFT DETECTED!")
        print("  - Expected: professional tone")
        print("  - Actual: casual with emojis and slang")
        print("  - MAO would detect: PERSONA_DRIFT via style analysis")


async def run_demo(
    mode: str,
    query: str,
    send: bool = False,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """Run a demo in the specified mode."""
    
    creators = {
        "normal": create_normal_execution,
        "loop": create_loop_execution,
        "corruption": create_corruption_execution,
        "drift": create_drift_execution,
    }
    
    if mode not in creators:
        raise ValueError(f"Unknown mode: {mode}")
    
    execution = creators[mode](query)
    print_execution(execution, mode)
    
    if send and endpoint and api_key:
        print(f"\nSending to MAO backend at {endpoint}...")
        try:
            result = await send_to_mao(execution, endpoint, api_key)
            print(f"Response: {result}")
        except Exception as e:
            print(f"Error sending to MAO: {e}")
    
    print(f"\nWebhook Payload Preview:")
    payload = execution.to_webhook_payload()
    print(json.dumps(payload, indent=2, default=str)[:500] + "...")
    
    return execution


def main():
    parser = argparse.ArgumentParser(description="MAO Testing n8n Demo")
    parser.add_argument(
        "--mode",
        choices=["normal", "loop", "corruption", "drift", "all"],
        default="normal",
        help="Demo mode to run",
    )
    parser.add_argument(
        "--query",
        default="What are the key benefits of multi-agent AI systems?",
        help="Query to process",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send to MAO backend",
    )
    parser.add_argument(
        "--endpoint",
        default="http://localhost:8000",
        help="MAO API endpoint",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MAO_API_KEY", "demo-api-key"),
        help="MAO API key",
    )
    
    args = parser.parse_args()
    
    print(f"""
================================================================================
                    MAO TESTING PLATFORM - n8n DEMO
                              {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================
""")
    
    modes = ["normal", "loop", "corruption", "drift"] if args.mode == "all" else [args.mode]
    
    async def run_all():
        for mode in modes:
            await run_demo(
                mode=mode,
                query=args.query,
                send=args.send,
                endpoint=args.endpoint,
                api_key=args.api_key,
            )
    
    asyncio.run(run_all())


if __name__ == "__main__":
    main()
