"""n8n integration for MAO Testing SDK."""

from __future__ import annotations
import hashlib
import hmac
import time
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from ..tracer import MAOTracer
from ..config import MAOConfig


@dataclass
class N8nNode:
    name: str
    type: str
    execution_time_ms: int = 0
    output: Any = None
    error: Optional[str] = None


@dataclass
class N8nExecution:
    id: str
    workflow_id: str
    workflow_name: str
    mode: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    nodes: List[N8nNode] = field(default_factory=list)


class N8nTracer(MAOTracer):
    """Tracer for n8n workflow executions."""
    
    FRAMEWORK_NAME = "n8n"
    FRAMEWORK_VERSION = "1.x"
    
    def __init__(
        self,
        n8n_url: Optional[str] = None,
        n8n_api_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.n8n_url = n8n_url
        self.n8n_api_key = n8n_api_key
        self.webhook_secret = webhook_secret
    
    async def poll_executions(
        self,
        since: Optional[datetime] = None,
        workflow_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[N8nExecution]:
        """Poll n8n API for recent executions."""
        if not self.n8n_url or not self.n8n_api_key:
            raise ValueError("n8n_url and n8n_api_key required for polling")
        
        params: Dict[str, Any] = {"limit": limit}
        if since:
            params["startedAfter"] = since.isoformat()
        if workflow_id:
            params["workflowId"] = workflow_id
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.n8n_url.rstrip('/')}/api/v1/executions",
                headers={"X-N8N-API-KEY": self.n8n_api_key},
                params=params,
                timeout=30.0,
            )
            resp.raise_for_status()
            
            data = resp.json()
            executions = []
            
            for e in data.get("data", []):
                executions.append(self._parse_execution(e))
            
            return executions
    
    async def get_execution(self, execution_id: str) -> N8nExecution:
        """Get a specific execution by ID."""
        if not self.n8n_url or not self.n8n_api_key:
            raise ValueError("n8n_url and n8n_api_key required for polling")
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.n8n_url.rstrip('/')}/api/v1/executions/{execution_id}",
                headers={"X-N8N-API-KEY": self.n8n_api_key},
                timeout=30.0,
            )
            resp.raise_for_status()
            return self._parse_execution(resp.json())
    
    async def send_to_mao(
        self,
        execution: N8nExecution,
        mao_endpoint: Optional[str] = None,
        mao_api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an execution to MAO Testing Platform."""
        endpoint = mao_endpoint or self.config.endpoint if hasattr(self, 'config') else None
        api_key = mao_api_key or self.config.api_key if hasattr(self, 'config') else None
        
        if not endpoint or not api_key:
            raise ValueError("MAO endpoint and API key required")
        
        payload = self._execution_to_payload(execution)
        headers = {
            "X-MAO-API-Key": api_key,
            "Content-Type": "application/json",
        }
        
        if self.webhook_secret:
            timestamp = str(int(time.time()))
            nonce = secrets.token_urlsafe(16)
            
            import json
            body = json.dumps(payload)
            message = f"{timestamp}.{body}"
            signature = hmac.new(
                self.webhook_secret.encode(),
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
            resp.raise_for_status()
            return resp.json()
    
    async def sync_executions(
        self,
        since: Optional[datetime] = None,
        workflow_id: Optional[str] = None,
        mao_endpoint: Optional[str] = None,
        mao_api_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Poll n8n and send all executions to MAO."""
        executions = await self.poll_executions(since=since, workflow_id=workflow_id)
        
        results = []
        for execution in executions:
            try:
                result = await self.send_to_mao(
                    execution,
                    mao_endpoint=mao_endpoint,
                    mao_api_key=mao_api_key,
                )
                results.append({"execution_id": execution.id, "success": True, **result})
            except Exception as e:
                results.append({"execution_id": execution.id, "success": False, "error": str(e)})
        
        return results
    
    def _parse_execution(self, data: Dict[str, Any]) -> N8nExecution:
        """Parse n8n API response into N8nExecution."""
        nodes = []
        run_data = data.get("data", {}).get("resultData", {}).get("runData", {})
        
        for node_name, node_runs in run_data.items():
            if not node_runs:
                continue
            for run in node_runs:
                nodes.append(N8nNode(
                    name=node_name,
                    type=run.get("source", [{}])[0].get("type", "unknown") if run.get("source") else "unknown",
                    execution_time_ms=run.get("executionTime", 0),
                    output=run.get("data", {}).get("main", [[]])[0] if run.get("data") else None,
                    error=run.get("error", {}).get("message") if run.get("error") else None,
                ))
        
        return N8nExecution(
            id=data.get("id", ""),
            workflow_id=data.get("workflowId", ""),
            workflow_name=data.get("workflowData", {}).get("name", ""),
            mode=data.get("mode", "manual"),
            started_at=self._parse_datetime(data.get("startedAt")),
            finished_at=self._parse_datetime(data.get("stoppedAt")),
            status=data.get("status", "unknown"),
            nodes=nodes,
        )
    
    def _execution_to_payload(self, execution: N8nExecution) -> Dict[str, Any]:
        """Convert N8nExecution to webhook payload."""
        run_data = {}
        for node in execution.nodes:
            if node.name not in run_data:
                run_data[node.name] = []
            run_data[node.name].append({
                "executionTime": node.execution_time_ms,
                "source": [{"type": node.type}],
                "data": {"main": [[node.output]]} if node.output else {},
                "error": {"message": node.error} if node.error else None,
            })
        
        return {
            "executionId": execution.id,
            "workflowId": execution.workflow_id,
            "workflowName": execution.workflow_name,
            "mode": execution.mode,
            "startedAt": execution.started_at.isoformat(),
            "finishedAt": execution.finished_at.isoformat() if execution.finished_at else None,
            "status": execution.status,
            "data": {
                "resultData": {
                    "runData": run_data
                }
            }
        }
    
    def _parse_datetime(self, dt_str: Optional[str]) -> datetime:
        if not dt_str:
            return datetime.utcnow()
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError):
            return datetime.utcnow()
