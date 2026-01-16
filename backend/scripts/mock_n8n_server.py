#!/usr/bin/env python3
"""
Mock n8n API server for testing the self-healing pipeline.

This simulates the n8n REST API endpoints needed for testing:
- GET /api/v1/workflows - List workflows
- GET /api/v1/workflows/{id} - Get workflow
- PUT /api/v1/workflows/{id} - Update workflow
- POST /api/v1/workflows/{id}/activate - Activate workflow
- POST /api/v1/workflows/{id}/deactivate - Deactivate workflow

Usage:
    python mock_n8n_server.py --port 8001
"""

import argparse
import json
import logging
from datetime import datetime
from typing import Dict, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock n8n API", version="1.0.0")

# In-memory workflow storage
WORKFLOWS: Dict[str, Dict[str, Any]] = {}

# Sample workflow with a loop that could cause infinite loops
SAMPLE_LOOP_WORKFLOW = {
    "id": "wf-loop-test-001",
    "name": "Loop Test Workflow",
    "active": True,
    "versionId": 1,
    "nodes": [
        {
            "name": "Start",
            "type": "n8n-nodes-base.start",
            "typeVersion": 1,
            "position": [250, 300],
            "parameters": {}
        },
        {
            "name": "Loop",
            "type": "n8n-nodes-base.loop",
            "typeVersion": 1,
            "position": [450, 300],
            "parameters": {
                "batchSize": 10,
                # Missing maxIterations - potential infinite loop
            }
        },
        {
            "name": "AI Agent",
            "type": "n8n-nodes-base.openAi",
            "typeVersion": 1,
            "position": [650, 300],
            "parameters": {
                "operation": "chat",
                "model": "gpt-4"
            }
        }
    ],
    "connections": {
        "Start": {
            "main": [[{"node": "Loop", "type": "main", "index": 0}]]
        },
        "Loop": {
            "main": [[{"node": "AI Agent", "type": "main", "index": 0}]]
        }
    },
    "settings": {},
    "createdAt": "2025-01-15T10:00:00.000Z",
    "updatedAt": "2025-01-15T10:00:00.000Z"
}

# Initialize with sample workflow
WORKFLOWS["wf-loop-test-001"] = SAMPLE_LOOP_WORKFLOW.copy()


def verify_api_key(x_n8n_api_key: str = Header(None, alias="X-N8N-API-KEY")):
    """Verify the n8n API key."""
    if not x_n8n_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    # Accept any key for mock server
    return x_n8n_api_key


@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "service": "mock-n8n-api"}


@app.get("/api/v1/workflows")
async def list_workflows(
    limit: int = 20,
    x_n8n_api_key: str = Header(None, alias="X-N8N-API-KEY")
):
    """List all workflows."""
    verify_api_key(x_n8n_api_key)
    workflows = list(WORKFLOWS.values())[:limit]
    return {"data": workflows}


@app.get("/api/v1/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    x_n8n_api_key: str = Header(None, alias="X-N8N-API-KEY")
):
    """Get a specific workflow."""
    verify_api_key(x_n8n_api_key)

    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    logger.info(f"GET workflow: {workflow_id}")
    return WORKFLOWS[workflow_id]


@app.put("/api/v1/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    request: Request,
    x_n8n_api_key: str = Header(None, alias="X-N8N-API-KEY")
):
    """Update a workflow."""
    verify_api_key(x_n8n_api_key)

    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    body = await request.json()

    # Update workflow
    old_version = WORKFLOWS[workflow_id].get("versionId", 1)
    body["versionId"] = old_version + 1
    body["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    body["id"] = workflow_id

    WORKFLOWS[workflow_id] = body

    logger.info(f"PUT workflow: {workflow_id} (version {old_version} -> {body['versionId']})")
    logger.info(f"Updated nodes: {len(body.get('nodes', []))}")

    return body


@app.post("/api/v1/workflows/{workflow_id}/activate")
async def activate_workflow(
    workflow_id: str,
    x_n8n_api_key: str = Header(None, alias="X-N8N-API-KEY")
):
    """Activate a workflow."""
    verify_api_key(x_n8n_api_key)

    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    WORKFLOWS[workflow_id]["active"] = True
    logger.info(f"ACTIVATE workflow: {workflow_id}")
    return {"success": True}


@app.post("/api/v1/workflows/{workflow_id}/deactivate")
async def deactivate_workflow(
    workflow_id: str,
    x_n8n_api_key: str = Header(None, alias="X-N8N-API-KEY")
):
    """Deactivate a workflow."""
    verify_api_key(x_n8n_api_key)

    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    WORKFLOWS[workflow_id]["active"] = False
    logger.info(f"DEACTIVATE workflow: {workflow_id}")
    return {"success": True}


@app.get("/api/v1/executions")
async def list_executions(
    workflowId: str = None,
    status: str = None,
    limit: int = 20,
    x_n8n_api_key: str = Header(None, alias="X-N8N-API-KEY")
):
    """List workflow executions (returns mock data)."""
    verify_api_key(x_n8n_api_key)

    # Return mock executions
    executions = [
        {
            "id": str(uuid4()),
            "workflowId": workflowId or "wf-loop-test-001",
            "status": status or "success",
            "startedAt": "2025-01-16T10:00:00.000Z",
            "stoppedAt": "2025-01-16T10:00:05.000Z",
            "mode": "manual"
        }
    ]

    return {"data": executions[:limit]}


@app.post("/api/v1/workflows/{workflow_id}/reset")
async def reset_workflow(
    workflow_id: str,
    x_n8n_api_key: str = Header(None, alias="X-N8N-API-KEY")
):
    """Reset workflow to original state (test helper)."""
    verify_api_key(x_n8n_api_key)

    if workflow_id == "wf-loop-test-001":
        WORKFLOWS[workflow_id] = SAMPLE_LOOP_WORKFLOW.copy()
        logger.info(f"RESET workflow: {workflow_id}")
        return {"success": True, "message": "Workflow reset to original state"}

    raise HTTPException(status_code=404, detail="Cannot reset unknown workflow")


@app.get("/api/v1/workflows/{workflow_id}/diff")
async def get_workflow_diff(
    workflow_id: str,
    x_n8n_api_key: str = Header(None, alias="X-N8N-API-KEY")
):
    """Get diff between current and original state (test helper)."""
    verify_api_key(x_n8n_api_key)

    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    current = WORKFLOWS[workflow_id]
    original = SAMPLE_LOOP_WORKFLOW

    changes = []

    # Compare nodes
    current_nodes = {n.get("name"): n for n in current.get("nodes", [])}
    original_nodes = {n.get("name"): n for n in original.get("nodes", [])}

    for name, node in current_nodes.items():
        if name in original_nodes:
            if node != original_nodes[name]:
                changes.append(f"Modified: {name}")
        else:
            changes.append(f"Added: {name}")

    for name in original_nodes:
        if name not in current_nodes:
            changes.append(f"Removed: {name}")

    return {
        "workflow_id": workflow_id,
        "original_version": 1,
        "current_version": current.get("versionId", 1),
        "changes": changes,
        "has_changes": len(changes) > 0
    }


def main():
    parser = argparse.ArgumentParser(description="Mock n8n API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to listen on")
    args = parser.parse_args()

    logger.info(f"Starting mock n8n server on {args.host}:{args.port}")
    logger.info(f"Sample workflow ID: wf-loop-test-001")

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
