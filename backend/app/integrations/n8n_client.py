"""n8n REST API client for workflow management."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class N8nApiError(Exception):
    """Exception for n8n API errors."""

    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class N8nApiClient:
    """
    Client for n8n REST API to manage workflows.

    n8n API Reference:
    - GET /api/v1/workflows/{id} - Get workflow
    - PUT /api/v1/workflows/{id} - Update workflow
    - POST /api/v1/workflows/{id}/activate - Activate
    - POST /api/v1/workflows/{id}/deactivate - Deactivate
    - GET /api/v1/executions - List executions
    """

    def __init__(
        self,
        instance_url: str,
        api_key: str,
        timeout: float = 30.0,
    ):
        """
        Initialize the n8n API client.

        Args:
            instance_url: Base URL of the n8n instance (e.g., https://my-n8n.example.com)
            api_key: n8n API key for authentication
            timeout: Request timeout in seconds
        """
        self.instance_url = instance_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{self.instance_url}/api/v1",
                headers={
                    "X-N8N-API-KEY": self.api_key,
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
                raise N8nApiError(
                    message=f"n8n API error: {response.status_code}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            return response.json() if response.content else {}

        except httpx.TimeoutException as e:
            raise N8nApiError(f"n8n API request timed out: {e}")
        except httpx.RequestError as e:
            raise N8nApiError(f"n8n API request failed: {e}")

    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get a workflow by ID.

        Args:
            workflow_id: The n8n workflow ID

        Returns:
            Workflow data including nodes, connections, and settings
        """
        logger.info(f"Getting workflow {workflow_id} from n8n")
        return await self._request("GET", f"/workflows/{workflow_id}")

    async def update_workflow(
        self,
        workflow_id: str,
        workflow_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update a workflow.

        Args:
            workflow_id: The n8n workflow ID
            workflow_data: Updated workflow data

        Returns:
            Updated workflow data
        """
        logger.info(f"Updating workflow {workflow_id} in n8n")
        return await self._request("PUT", f"/workflows/{workflow_id}", json_data=workflow_data)

    async def activate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Activate a workflow.

        Args:
            workflow_id: The n8n workflow ID

        Returns:
            Activation result
        """
        logger.info(f"Activating workflow {workflow_id} in n8n")
        return await self._request("POST", f"/workflows/{workflow_id}/activate")

    async def deactivate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Deactivate a workflow.

        Args:
            workflow_id: The n8n workflow ID

        Returns:
            Deactivation result
        """
        logger.info(f"Deactivating workflow {workflow_id} in n8n")
        return await self._request("POST", f"/workflows/{workflow_id}/deactivate")

    async def get_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get workflow executions.

        Args:
            workflow_id: Optional workflow ID to filter by
            status: Optional status filter (success, error, waiting)
            limit: Maximum number of executions to return

        Returns:
            List of execution data
        """
        params = {"limit": limit}
        if workflow_id:
            params["workflowId"] = workflow_id
        if status:
            params["status"] = status

        result = await self._request("GET", "/executions", params=params)
        return result.get("data", [])

    async def list_workflows(
        self,
        active: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List workflows from the n8n instance.

        Args:
            active: Optional filter for active/inactive workflows
            limit: Maximum number of workflows to return

        Returns:
            List of workflow data
        """
        params = {"limit": limit}
        if active is not None:
            params["active"] = str(active).lower()

        result = await self._request("GET", "/workflows", params=params)
        return result.get("data", [])

    async def test_connection(self) -> bool:
        """
        Test the connection to the n8n instance.

        Returns:
            True if connection is successful
        """
        try:
            # Try to list workflows with limit 1
            await self._request("GET", "/workflows", params={"limit": 1})
            return True
        except N8nApiError as e:
            logger.warning(f"n8n connection test failed: {e}")
            return False


class N8nWorkflowDiff:
    """Helper class for generating workflow diffs."""

    @staticmethod
    def generate_diff(
        original: Dict[str, Any],
        modified: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a diff between two workflow versions.

        Args:
            original: Original workflow data
            modified: Modified workflow data

        Returns:
            Diff summary with changes
        """
        changes = []

        # Compare nodes
        original_nodes = {n.get("name"): n for n in original.get("nodes", [])}
        modified_nodes = {n.get("name"): n for n in modified.get("nodes", [])}

        # Added nodes
        for name in modified_nodes:
            if name not in original_nodes:
                changes.append(f"Added node: {name}")

        # Removed nodes
        for name in original_nodes:
            if name not in modified_nodes:
                changes.append(f"Removed node: {name}")

        # Modified nodes
        for name in original_nodes:
            if name in modified_nodes:
                if original_nodes[name] != modified_nodes[name]:
                    changes.append(f"Modified node: {name}")

        # Compare connections
        orig_conn_count = len(original.get("connections", {}))
        mod_conn_count = len(modified.get("connections", {}))
        if orig_conn_count != mod_conn_count:
            changes.append(f"Connections changed: {orig_conn_count} -> {mod_conn_count}")

        # Compare settings
        if original.get("settings") != modified.get("settings"):
            changes.append("Workflow settings modified")

        return {
            "before": {
                "nodes": len(original.get("nodes", [])),
                "connections": orig_conn_count,
            },
            "after": {
                "nodes": len(modified.get("nodes", [])),
                "connections": mod_conn_count,
            },
            "changes": changes,
        }
