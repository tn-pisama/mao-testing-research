"""Tests for MCP server."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mao.mcp.server import MAOMCPServer, RateLimiter


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.analyze_trace = AsyncMock(return_value={
        "trace_id": "trace-123",
        "framework": "langchain",
        "healthy": False,
        "detections": [
            {"id": "det-1", "type": "infinite_loop", "severity": "high"}
        ],
    })
    client.get_detections = AsyncMock(return_value=[])
    client.get_fix_suggestions = AsyncMock(return_value=[])
    client.get_trace = AsyncMock(return_value={"id": "trace-123"})
    return client


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(self):
        limiter = RateLimiter(requests_per_minute=10)
        
        for _ in range(10):
            assert await limiter.acquire() is True
    
    @pytest.mark.asyncio
    async def test_blocks_requests_over_limit(self):
        limiter = RateLimiter(requests_per_minute=2)
        
        assert await limiter.acquire() is True
        assert await limiter.acquire() is True
        assert await limiter.acquire() is False


class TestMAOMCPServer:
    @pytest.mark.asyncio
    async def test_analyze_trace(self, mock_client):
        with patch("mao.mcp.server.MAOClient", return_value=mock_client):
            server = MAOMCPServer("http://localhost:8000", "test-key")
            server.client = mock_client
            
            result = await server.handle_tool_call(
                "mao_analyze_trace",
                {"trace_id": "trace-123"}
            )
            
            assert "trace_id" in result
            assert result["trace_id"] == "trace-123"
    
    @pytest.mark.asyncio
    async def test_invalid_trace_id(self, mock_client):
        with patch("mao.mcp.server.MAOClient", return_value=mock_client):
            server = MAOMCPServer("http://localhost:8000", "test-key")
            
            result = await server.handle_tool_call(
                "mao_analyze_trace",
                {"trace_id": "invalid;DROP TABLE"}
            )
            
            assert "error" in result
            assert "Validation" in result["error"]
    
    @pytest.mark.asyncio
    async def test_unknown_tool(self, mock_client):
        with patch("mao.mcp.server.MAOClient", return_value=mock_client):
            server = MAOMCPServer("http://localhost:8000", "test-key")
            
            result = await server.handle_tool_call(
                "unknown_tool",
                {}
            )
            
            assert "error" in result
            assert "Unknown tool" in result["error"]
    
    def test_tools_schema(self, mock_client):
        with patch("mao.mcp.server.MAOClient", return_value=mock_client):
            server = MAOMCPServer("http://localhost:8000", "test-key")
            
            tools = server.get_tools_schema()
            
            assert len(tools) == 4
            tool_names = [t["name"] for t in tools]
            assert "mao_analyze_trace" in tool_names
            assert "mao_get_detections" in tool_names
            assert "mao_get_fix_suggestions" in tool_names
            assert "mao_get_trace" in tool_names
    
    def test_resources_schema(self, mock_client):
        with patch("mao.mcp.server.MAOClient", return_value=mock_client):
            server = MAOMCPServer("http://localhost:8000", "test-key")
            
            resources = server.get_resources_schema()
            
            assert len(resources) == 2
            uris = [r["uri"] for r in resources]
            assert "mao://docs/detection-types" in uris
            assert "mao://docs/fix-types" in uris
    
    @pytest.mark.asyncio
    async def test_read_resource(self, mock_client):
        with patch("mao.mcp.server.MAOClient", return_value=mock_client):
            server = MAOMCPServer("http://localhost:8000", "test-key")
            
            content = await server.read_resource("mao://docs/detection-types")
            
            assert "Infinite Loop" in content
            assert "State Corruption" in content
