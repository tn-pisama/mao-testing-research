"""OpenClaw API client for agent session management."""

import asyncio
import logging
from typing import Dict, Any, List, Optional

import httpx

logger = logging.getLogger(__name__)


class OpenClawApiError(Exception):
    """Exception for OpenClaw API errors."""

    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class OpenClawClient:
    """
    Client for OpenClaw API to manage agents and sessions.

    OpenClaw API Reference:
    - GET /agents - List agents
    - GET /agents/{id} - Get agent config
    - PUT /agents/{id} - Update agent config
    - POST /sessions - Create session
    - GET /sessions/{id} - Get session status
    - POST /sessions/{id}/message - Send message to session
    - GET /sessions/{id}/events - Get session events
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
                base_url=f"{self.instance_url}/api/v1",
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
                raise OpenClawApiError(
                    message=f"OpenClaw API error: {response.status_code}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            return response.json() if response.content else {}

        except httpx.TimeoutException as e:
            raise OpenClawApiError(f"OpenClaw API request timed out: {e}")
        except httpx.RequestError as e:
            raise OpenClawApiError(f"OpenClaw API request failed: {e}")

    # ── Agents ──────────────────────────────────────────────────────

    async def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """Get agent configuration."""
        logger.info(f"Getting agent {agent_id} from OpenClaw")
        return await self._request("GET", f"/agents/{agent_id}")

    async def update_agent(
        self,
        agent_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update agent configuration (tools, permissions, limits)."""
        logger.info(f"Updating agent {agent_id} in OpenClaw")
        return await self._request("PUT", f"/agents/{agent_id}", json_data=config)

    async def list_agents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List agents."""
        result = await self._request("GET", "/agents", params={"limit": limit})
        if isinstance(result, list):
            return result
        return result.get("data", result.get("agents", []))

    async def get_agent_tools(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get tools configured for an agent."""
        result = await self._request("GET", f"/agents/{agent_id}/tools")
        if isinstance(result, list):
            return result
        return result.get("tools", [])

    async def update_agent_tools(
        self,
        agent_id: str,
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Update tools for an agent (for tool abuse/sandbox fixes)."""
        return await self._request(
            "PUT", f"/agents/{agent_id}/tools", json_data={"tools": tools}
        )

    # ── Sessions ────────────────────────────────────────────────────

    async def create_session(
        self,
        agent_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new agent session."""
        logger.info(f"Creating session for agent {agent_id}")
        json_data: Dict[str, Any] = {"agent_id": agent_id}
        if metadata:
            json_data["metadata"] = metadata
        return await self._request("POST", "/sessions", json_data=json_data)

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session status and details."""
        return await self._request("GET", f"/sessions/{session_id}")

    async def send_message(
        self,
        session_id: str,
        message: str,
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a message to an active session."""
        json_data: Dict[str, Any] = {"message": message}
        if channel:
            json_data["channel"] = channel
        return await self._request(
            "POST", f"/sessions/{session_id}/message", json_data=json_data
        )

    async def get_session_events(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get events from a session (for re-detection after healing)."""
        result = await self._request(
            "GET", f"/sessions/{session_id}/events", params={"limit": limit}
        )
        if isinstance(result, list):
            return result
        return result.get("events", [])

    async def stop_session(self, session_id: str) -> Dict[str, Any]:
        """Stop a running session."""
        return await self._request("POST", f"/sessions/{session_id}/stop")

    async def wait_for_session(
        self,
        session_id: str,
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Poll a session until it reaches a terminal status.

        Raises:
            OpenClawApiError: If session times out
        """
        elapsed = 0.0
        while elapsed < timeout:
            session = await self.get_session(session_id)
            status = session.get("status", "")

            if status in ("completed", "failed", "stopped", "error"):
                return session

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise OpenClawApiError(
            f"Session {session_id} did not complete within {timeout}s"
        )

    # ── Combined helpers ────────────────────────────────────────────

    async def run_session(
        self,
        agent_id: str,
        message: str,
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """
        Create a session, send a message, and wait for completion.

        Convenience method for test executions during verification.
        """
        session = await self.create_session(
            agent_id=agent_id,
            metadata={"source": "pisama_healing"},
        )
        session_id = session.get("session_id", session.get("id", ""))

        await self.send_message(session_id, message)
        result = await self.wait_for_session(session_id, timeout=timeout)
        return result

    async def test_connection(self) -> bool:
        """Test the connection to the OpenClaw instance."""
        try:
            await self._request("GET", "/agents", params={"limit": 1})
            return True
        except OpenClawApiError as e:
            logger.warning(f"OpenClaw connection test failed: {e}")
            return False


class OpenClawConfigDiff:
    """Helper for generating diffs between agent configurations."""

    @staticmethod
    def generate_diff(
        original: Dict[str, Any],
        modified: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a diff between two agent configurations."""
        changes = []

        # Compare tools
        orig_tools = {t.get("name"): t for t in original.get("tools", [])}
        mod_tools = {t.get("name"): t for t in modified.get("tools", [])}

        for name in mod_tools:
            if name not in orig_tools:
                changes.append(f"Added tool: {name}")
        for name in orig_tools:
            if name not in mod_tools:
                changes.append(f"Removed tool: {name}")
        for name in orig_tools:
            if name in mod_tools and orig_tools[name] != mod_tools[name]:
                changes.append(f"Modified tool: {name}")

        # Compare permissions
        if original.get("permissions") != modified.get("permissions"):
            changes.append("Permissions modified")

        # Compare limits
        if original.get("limits") != modified.get("limits"):
            changes.append("Limits modified")

        # Compare sandbox settings
        if original.get("sandbox") != modified.get("sandbox"):
            changes.append("Sandbox settings modified")

        return {
            "before": {
                "tools": len(orig_tools),
                "permissions": len(original.get("permissions", {})),
            },
            "after": {
                "tools": len(mod_tools),
                "permissions": len(modified.get("permissions", {})),
            },
            "changes": changes,
        }
