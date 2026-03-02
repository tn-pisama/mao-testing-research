"""LangGraph Platform API client for graph management and execution."""

import asyncio
import logging
from typing import Dict, Any, List, Optional

import httpx

logger = logging.getLogger(__name__)


class LangGraphApiError(Exception):
    """Exception for LangGraph API errors."""

    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class LangGraphClient:
    """
    Client for LangGraph Platform API to manage graphs and runs.

    LangGraph Platform API Reference:
    - GET /assistants/{id} - Get assistant (graph config)
    - PUT /assistants/{id} - Update assistant
    - GET /assistants/{id}/graph - Get graph structure
    - POST /threads - Create thread
    - POST /threads/{thread_id}/runs - Create run
    - GET /threads/{thread_id}/runs/{run_id} - Get run status
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
                base_url=self.instance_url,
                headers={
                    "X-Api-Key": self.api_key,
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
                raise LangGraphApiError(
                    message=f"LangGraph API error: {response.status_code}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            return response.json() if response.content else {}

        except httpx.TimeoutException as e:
            raise LangGraphApiError(f"LangGraph API request timed out: {e}")
        except httpx.RequestError as e:
            raise LangGraphApiError(f"LangGraph API request failed: {e}")

    # ── Assistants (graph configs) ──────────────────────────────────

    async def get_assistant(self, assistant_id: str) -> Dict[str, Any]:
        """Get an assistant (graph configuration) by ID."""
        logger.info(f"Getting assistant {assistant_id} from LangGraph")
        return await self._request("GET", f"/assistants/{assistant_id}")

    async def update_assistant(
        self,
        assistant_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an assistant's configuration."""
        logger.info(f"Updating assistant {assistant_id} in LangGraph")
        return await self._request("PUT", f"/assistants/{assistant_id}", json_data=config)

    async def list_assistants(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all assistants."""
        result = await self._request("GET", "/assistants", params={"limit": limit})
        if isinstance(result, list):
            return result
        return result.get("data", result.get("assistants", []))

    async def get_graph(self, assistant_id: str) -> Dict[str, Any]:
        """Get the graph structure for an assistant (nodes, edges, state schema)."""
        logger.info(f"Getting graph structure for assistant {assistant_id}")
        return await self._request("GET", f"/assistants/{assistant_id}/graph")

    # ── Threads ─────────────────────────────────────────────────────

    async def create_thread(self, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new thread for graph execution."""
        json_data = {}
        if metadata:
            json_data["metadata"] = metadata
        return await self._request("POST", "/threads", json_data=json_data or None)

    async def get_thread(self, thread_id: str) -> Dict[str, Any]:
        """Get thread details."""
        return await self._request("GET", f"/threads/{thread_id}")

    async def get_thread_state(self, thread_id: str) -> Dict[str, Any]:
        """Get current state of a thread."""
        return await self._request("GET", f"/threads/{thread_id}/state")

    async def update_thread_state(
        self,
        thread_id: str,
        values: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update thread state (for state correction fixes)."""
        return await self._request(
            "POST", f"/threads/{thread_id}/state", json_data={"values": values}
        )

    # ── Runs (graph execution) ──────────────────────────────────────

    async def create_run(
        self,
        thread_id: str,
        assistant_id: str,
        input_data: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a run (execute the graph).

        Args:
            thread_id: Thread ID to run in
            assistant_id: Assistant/graph to execute
            input_data: Input state for the graph
            config: Runtime config overrides (e.g., recursion_limit)
        """
        logger.info(f"Creating run for assistant {assistant_id} in thread {thread_id}")
        json_data: Dict[str, Any] = {"assistant_id": assistant_id}
        if input_data:
            json_data["input"] = input_data
        if config:
            json_data["config"] = config
        return await self._request(
            "POST", f"/threads/{thread_id}/runs", json_data=json_data
        )

    async def get_run(self, thread_id: str, run_id: str) -> Dict[str, Any]:
        """Get run status and details."""
        return await self._request("GET", f"/threads/{thread_id}/runs/{run_id}")

    async def list_runs(
        self,
        thread_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List runs for a thread."""
        result = await self._request(
            "GET", f"/threads/{thread_id}/runs", params={"limit": limit}
        )
        if isinstance(result, list):
            return result
        return result.get("data", result.get("runs", []))

    async def cancel_run(self, thread_id: str, run_id: str) -> Dict[str, Any]:
        """Cancel a running execution."""
        return await self._request("POST", f"/threads/{thread_id}/runs/{run_id}/cancel")

    async def wait_for_run(
        self,
        thread_id: str,
        run_id: str,
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Poll a run until it reaches a terminal status.

        Returns:
            Final run data

        Raises:
            LangGraphApiError: If run times out
        """
        elapsed = 0.0
        while elapsed < timeout:
            run = await self.get_run(thread_id, run_id)
            status = run.get("status", "")

            if status in ("success", "error", "interrupted", "timeout"):
                return run

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise LangGraphApiError(
            f"Run {run_id} did not complete within {timeout}s"
        )

    # ── Combined helpers ────────────────────────────────────────────

    async def run_graph(
        self,
        assistant_id: str,
        input_data: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """
        Create a thread, run the graph, and wait for completion.

        Convenience method for test executions during verification.
        """
        thread = await self.create_thread(metadata={"source": "pisama_healing"})
        thread_id = thread.get("thread_id", thread.get("id", ""))

        run = await self.create_run(thread_id, assistant_id, input_data, config)
        run_id = run.get("run_id", run.get("id", ""))

        result = await self.wait_for_run(thread_id, run_id, timeout=timeout)
        result["thread_id"] = thread_id
        return result

    async def test_connection(self) -> bool:
        """Test the connection to the LangGraph Platform."""
        try:
            await self._request("GET", "/assistants", params={"limit": 1})
            return True
        except LangGraphApiError as e:
            logger.warning(f"LangGraph connection test failed: {e}")
            return False


class LangGraphConfigDiff:
    """Helper for generating diffs between graph configurations."""

    @staticmethod
    def generate_diff(
        original: Dict[str, Any],
        modified: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a diff between two assistant/graph configurations."""
        changes = []

        # Compare graph nodes
        orig_nodes = {n.get("id"): n for n in original.get("nodes", [])}
        mod_nodes = {n.get("id"): n for n in modified.get("nodes", [])}

        for nid in mod_nodes:
            if nid not in orig_nodes:
                changes.append(f"Added node: {nid}")
        for nid in orig_nodes:
            if nid not in mod_nodes:
                changes.append(f"Removed node: {nid}")
        for nid in orig_nodes:
            if nid in mod_nodes and orig_nodes[nid] != mod_nodes[nid]:
                changes.append(f"Modified node: {nid}")

        # Compare edges
        orig_edges = original.get("edges", [])
        mod_edges = modified.get("edges", [])
        if orig_edges != mod_edges:
            changes.append(f"Edges changed: {len(orig_edges)} -> {len(mod_edges)}")

        # Compare config
        if original.get("config") != modified.get("config"):
            changes.append("Graph config modified")

        # Compare metadata
        if original.get("metadata") != modified.get("metadata"):
            changes.append("Metadata modified")

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
