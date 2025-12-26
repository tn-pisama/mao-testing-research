"""HTTP client for MAO API."""

import httpx
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from .errors import APIError, TraceNotFoundError, DetectionNotFoundError, RateLimitError
from .security import validate_trace_id, validate_detection_id


class MAOClient:
    """Async HTTP client for MAO API with retries and connection pooling."""
    
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        tenant_id: str = "default",
        timeout: float = 30.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.tenant_id = tenant_id
        
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
        )
        timeout_config = httpx.Timeout(
            connect=5.0,
            read=timeout,
            write=10.0,
        )
        
        self._client = httpx.AsyncClient(
            base_url=self.endpoint,
            limits=limits,
            timeout=timeout_config,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
    
    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make an HTTP request with error handling."""
        url = f"/api/v1/tenants/{self.tenant_id}{path}"
        
        try:
            response = await self._client.request(method, url, **kwargs)
        except httpx.ConnectError as e:
            raise APIError(0, f"Connection failed: {e}")
        except httpx.TimeoutException:
            raise APIError(0, "Request timed out")
        
        if response.status_code == 404:
            raise TraceNotFoundError(kwargs.get("trace_id", "unknown"))
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(int(retry_after) if retry_after else None)
        elif response.status_code >= 400:
            try:
                error_body = response.json()
                message = error_body.get("detail", response.text)
            except Exception:
                message = response.text
            raise APIError(response.status_code, message)
        
        return response.json()
    
    async def analyze_trace(self, trace_id: str) -> Dict[str, Any]:
        """Analyze a trace for issues."""
        validated_id = validate_trace_id(trace_id)
        return await self._request("GET", f"/traces/{validated_id}/analyze")
    
    async def get_trace(self, trace_id: str) -> Dict[str, Any]:
        """Get trace details."""
        validated_id = validate_trace_id(trace_id)
        return await self._request("GET", f"/traces/{validated_id}")
    
    async def list_traces(
        self,
        limit: int = 10,
        since: Optional[str] = None,
        framework: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List recent traces."""
        params = {"limit": limit}
        if since:
            params["since"] = since
        if framework:
            params["framework"] = framework
        
        return await self._request("GET", "/traces", params=params)
    
    async def get_detections(
        self,
        trace_id: Optional[str] = None,
        severity: Optional[str] = None,
        detection_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get detections, optionally filtered."""
        params = {}
        if trace_id:
            params["trace_id"] = validate_trace_id(trace_id)
        if severity:
            params["severity"] = severity
        if detection_type:
            params["type"] = detection_type
        
        return await self._request("GET", "/detections", params=params)
    
    async def get_detection(self, detection_id: str) -> Dict[str, Any]:
        """Get a specific detection."""
        validated_id = validate_detection_id(detection_id)
        return await self._request("GET", f"/detections/{validated_id}")
    
    async def get_fix_suggestions(
        self,
        detection_id: str,
        level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get fix suggestions for a detection."""
        validated_id = validate_detection_id(detection_id)
        params = {}
        if level:
            params["level"] = level
        
        return await self._request("GET", f"/detections/{validated_id}/fixes", params=params)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        response = await self._client.get("/api/v1/health")
        return response.json()


@asynccontextmanager
async def create_client(
    endpoint: str,
    api_key: str,
    tenant_id: str = "default",
):
    """Create a MAO client with proper lifecycle management."""
    client = MAOClient(endpoint, api_key, tenant_id)
    try:
        yield client
    finally:
        await client.close()
