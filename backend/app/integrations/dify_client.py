"""Dify API client for workflow and app management."""

import asyncio
import logging
from typing import Dict, Any, List, Optional

import httpx

logger = logging.getLogger(__name__)


class DifyApiError(Exception):
    """Exception for Dify API errors."""

    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class DifyClient:
    """
    Client for Dify API to manage apps and workflows.

    Dify API Reference:
    - GET /apps - List apps
    - GET /apps/{id} - Get app details
    - PUT /apps/{id} - Update app config
    - POST /workflows/run - Run workflow
    - GET /workflows/run/{id} - Get workflow run status
    - GET /workflows/logs - Get workflow execution logs
    """

    def __init__(
        self,
        instance_url: str,
        api_key: str,
        timeout: float = 30.0,
    ):
        self.instance_url = instance_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{self.instance_url}/v1",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an API request."""
        client = await self._get_client()

        try:
            response = await client.request(
                method=method,
                url=path,
                json=json_data,
                params=params,
            )

            if response.status_code >= 400:
                raise DifyApiError(
                    message=f"Dify API error: {response.status_code}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            return response.json() if response.content else {}

        except httpx.TimeoutException as e:
            raise DifyApiError(f"Dify API request timed out: {e}")
        except httpx.RequestError as e:
            raise DifyApiError(f"Dify API request failed: {e}")

    # ── Apps ────────────────────────────────────────────────────────

    async def get_app(self, app_id: str) -> Dict[str, Any]:
        """Get app details and configuration."""
        logger.info(f"Getting app {app_id} from Dify")
        return await self._request("GET", f"/apps/{app_id}")

    async def update_app(
        self,
        app_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update app configuration (workflow nodes, model config, etc.)."""
        logger.info(f"Updating app {app_id} in Dify")
        return await self._request("PUT", f"/apps/{app_id}", json_data=config)

    async def list_apps(self, limit: int = 100, page: int = 1) -> List[Dict[str, Any]]:
        """List apps from the Dify instance."""
        result = await self._request(
            "GET", "/apps", params={"limit": limit, "page": page}
        )
        return result.get("data", [])

    async def get_app_config(self, app_id: str) -> Dict[str, Any]:
        """Get the workflow/chatflow configuration for an app."""
        logger.info(f"Getting config for app {app_id}")
        return await self._request("GET", f"/apps/{app_id}/workflows")

    async def update_app_config(
        self,
        app_id: str,
        workflow_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update the workflow configuration for an app."""
        logger.info(f"Updating workflow config for app {app_id}")
        return await self._request(
            "PUT", f"/apps/{app_id}/workflows", json_data=workflow_config
        )

    # ── Workflow Execution ──────────────────────────────────────────

    async def run_workflow(
        self,
        inputs: Dict[str, Any],
        user: str = "pisama-healing",
    ) -> Dict[str, Any]:
        """
        Trigger a workflow execution.

        Args:
            inputs: Input variables for the workflow
            user: User identifier for the run
        """
        logger.info("Running workflow in Dify")
        return await self._request(
            "POST",
            "/workflows/run",
            json_data={"inputs": inputs, "response_mode": "blocking", "user": user},
        )

    async def get_workflow_run(self, workflow_run_id: str) -> Dict[str, Any]:
        """Get workflow run status and results."""
        return await self._request("GET", f"/workflows/run/{workflow_run_id}")

    async def get_workflow_logs(
        self,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get workflow execution logs."""
        params: Dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        result = await self._request("GET", "/workflows/logs", params=params)
        return result.get("data", [])

    async def stop_workflow_run(self, task_id: str, user: str = "pisama-healing") -> Dict[str, Any]:
        """Stop a running workflow execution."""
        return await self._request(
            "POST",
            f"/workflows/tasks/{task_id}/stop",
            json_data={"user": user},
        )

    async def wait_for_workflow_run(
        self,
        workflow_run_id: str,
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Poll a workflow run until it reaches a terminal status.

        Raises:
            DifyApiError: If run times out
        """
        elapsed = 0.0
        while elapsed < timeout:
            run = await self.get_workflow_run(workflow_run_id)
            status = run.get("workflow_run", {}).get("status", run.get("status", ""))

            if status in ("succeeded", "failed", "stopped"):
                return run

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise DifyApiError(
            f"Workflow run {workflow_run_id} did not complete within {timeout}s"
        )

    # ── Knowledge Base ──────────────────────────────────────────────

    async def list_datasets(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List knowledge base datasets (for RAG poisoning fixes)."""
        result = await self._request(
            "GET", "/datasets", params={"limit": limit}
        )
        return result.get("data", [])

    # ── Combined helpers ────────────────────────────────────────────

    async def run_and_wait(
        self,
        inputs: Dict[str, Any],
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """
        Run a workflow and wait for completion.

        Convenience method for test executions during verification.
        Uses blocking mode which returns when complete.
        """
        return await self.run_workflow(inputs=inputs)

    async def test_connection(self) -> bool:
        """Test the connection to the Dify instance."""
        try:
            await self._request("GET", "/apps", params={"limit": 1})
            return True
        except DifyApiError as e:
            logger.warning(f"Dify connection test failed: {e}")
            return False


class DifyWorkflowDiff:
    """Helper for generating diffs between Dify workflow configurations."""

    @staticmethod
    def generate_diff(
        original: Dict[str, Any],
        modified: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a diff between two Dify workflow configurations."""
        changes = []

        # Compare nodes
        orig_nodes = {n.get("id"): n for n in original.get("nodes", original.get("graph", {}).get("nodes", []))}
        mod_nodes = {n.get("id"): n for n in modified.get("nodes", modified.get("graph", {}).get("nodes", []))}

        for nid in mod_nodes:
            if nid not in orig_nodes:
                changes.append(f"Added node: {mod_nodes[nid].get('data', {}).get('title', nid)}")
        for nid in orig_nodes:
            if nid not in mod_nodes:
                changes.append(f"Removed node: {orig_nodes[nid].get('data', {}).get('title', nid)}")
        for nid in orig_nodes:
            if nid in mod_nodes and orig_nodes[nid] != mod_nodes[nid]:
                changes.append(f"Modified node: {orig_nodes[nid].get('data', {}).get('title', nid)}")

        # Compare edges
        orig_edges = original.get("edges", original.get("graph", {}).get("edges", []))
        mod_edges = modified.get("edges", modified.get("graph", {}).get("edges", []))
        if orig_edges != mod_edges:
            changes.append(f"Edges changed: {len(orig_edges)} -> {len(mod_edges)}")

        # Compare model config
        if original.get("model_config") != modified.get("model_config"):
            changes.append("Model configuration modified")

        return {
            "before": {
                "nodes": len(orig_nodes),
                "edges": len(orig_edges),
            },
            "after": {
                "nodes": len(mod_nodes),
                "edges": len(mod_edges),
            },
            "changes": changes,
        }
