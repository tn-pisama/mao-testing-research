"""Unit tests for N8nApiClient."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import Response, TimeoutException, RequestError

from app.integrations.n8n_client import (
    N8nApiClient,
    N8nApiError,
    N8nWorkflowDiff,
)


class TestN8nApiClient:
    """Tests for N8nApiClient."""

    @pytest.fixture
    def client(self):
        """Create a test client instance."""
        return N8nApiClient(
            instance_url="https://test-n8n.example.com",
            api_key="test-api-key",
            timeout=10.0,
        )

    @pytest.fixture
    def sample_workflow(self):
        """Sample workflow data."""
        return {
            "id": "wf-test-001",
            "name": "Test Workflow",
            "active": True,
            "versionId": 1,
            "nodes": [
                {
                    "name": "Start",
                    "type": "n8n-nodes-base.start",
                    "position": [250, 300],
                    "parameters": {}
                },
                {
                    "name": "Loop",
                    "type": "n8n-nodes-base.loop",
                    "position": [450, 300],
                    "parameters": {"batchSize": 10}
                }
            ],
            "connections": {
                "Start": {"main": [[{"node": "Loop", "type": "main", "index": 0}]]}
            },
            "settings": {}
        }

    @pytest.mark.asyncio
    async def test_client_initialization(self, client):
        """Test client initializes with correct properties."""
        assert client.instance_url == "https://test-n8n.example.com"
        assert client.api_key == "test-api-key"
        assert client.timeout == 10.0

    @pytest.mark.asyncio
    async def test_client_url_trailing_slash_stripped(self):
        """Test that trailing slash is stripped from URL."""
        client = N8nApiClient(
            instance_url="https://test-n8n.example.com/",
            api_key="test-key"
        )
        assert client.instance_url == "https://test-n8n.example.com"

    @pytest.mark.asyncio
    async def test_get_workflow_success(self, client, sample_workflow):
        """Test successful workflow fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "wf-test-001"}'
        mock_response.json.return_value = sample_workflow

        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.get_workflow("wf-test-001")

            mock_http_client.request.assert_called_once_with(
                method="GET",
                url="/workflows/wf-test-001",
                json=None,
                params=None,
            )
            assert result["id"] == "wf-test-001"
            assert result["name"] == "Test Workflow"

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(self, client):
        """Test workflow not found returns N8nApiError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Workflow not found"

        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            with pytest.raises(N8nApiError) as exc_info:
                await client.get_workflow("nonexistent")

            assert exc_info.value.status_code == 404
            assert "404" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_update_workflow_success(self, client, sample_workflow):
        """Test successful workflow update."""
        updated_workflow = {**sample_workflow, "versionId": 2}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": "wf-test-001", "versionId": 2}'
        mock_response.json.return_value = updated_workflow

        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.update_workflow("wf-test-001", sample_workflow)

            mock_http_client.request.assert_called_once_with(
                method="PUT",
                url="/workflows/wf-test-001",
                json=sample_workflow,
                params=None,
            )
            assert result["versionId"] == 2

    @pytest.mark.asyncio
    async def test_update_workflow_error(self, client, sample_workflow):
        """Test workflow update error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid workflow data"

        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            with pytest.raises(N8nApiError) as exc_info:
                await client.update_workflow("wf-test-001", sample_workflow)

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_activate_workflow(self, client):
        """Test workflow activation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"success": true}'
        mock_response.json.return_value = {"success": True}

        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.activate_workflow("wf-test-001")

            mock_http_client.request.assert_called_once_with(
                method="POST",
                url="/workflows/wf-test-001/activate",
                json=None,
                params=None,
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_deactivate_workflow(self, client):
        """Test workflow deactivation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"success": true}'
        mock_response.json.return_value = {"success": True}

        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.deactivate_workflow("wf-test-001")

            mock_http_client.request.assert_called_once_with(
                method="POST",
                url="/workflows/wf-test-001/deactivate",
                json=None,
                params=None,
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_executions(self, client):
        """Test getting workflow executions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"data": [{"id": "exec-1"}]}'
        mock_response.json.return_value = {
            "data": [
                {"id": "exec-1", "status": "success"},
                {"id": "exec-2", "status": "error"}
            ]
        }

        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.get_executions(
                workflow_id="wf-test-001",
                status="success",
                limit=10
            )

            mock_http_client.request.assert_called_once_with(
                method="GET",
                url="/executions",
                json=None,
                params={"limit": 10, "workflowId": "wf-test-001", "status": "success"},
            )
            assert len(result) == 2
            assert result[0]["id"] == "exec-1"

    @pytest.mark.asyncio
    async def test_connection_timeout(self, client):
        """Test timeout error handling."""
        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(
                side_effect=TimeoutException("Request timed out")
            )
            mock_get_client.return_value = mock_http_client

            with pytest.raises(N8nApiError) as exc_info:
                await client.get_workflow("wf-test-001")

            assert "timed out" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_connection_error(self, client):
        """Test connection error handling."""
        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(
                side_effect=RequestError("Connection refused")
            )
            mock_get_client.return_value = mock_http_client

            with pytest.raises(N8nApiError) as exc_info:
                await client.get_workflow("wf-test-001")

            assert "failed" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_test_connection_success(self, client):
        """Test connection test success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"data": []}'
        mock_response.json.return_value = {"data": []}

        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.test_connection()

            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, client):
        """Test connection test failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.test_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager behavior."""
        async with N8nApiClient(
            instance_url="https://test.example.com",
            api_key="test-key"
        ) as client:
            assert client is not None
            assert client.instance_url == "https://test.example.com"


class TestN8nWorkflowDiff:
    """Tests for N8nWorkflowDiff."""

    def test_no_changes(self):
        """Test diff with identical workflows."""
        workflow = {
            "nodes": [{"name": "Node1"}, {"name": "Node2"}],
            "connections": {"Node1": {}},
            "settings": {}
        }

        diff = N8nWorkflowDiff.generate_diff(workflow, workflow)

        assert diff["changes"] == []
        assert diff["before"]["nodes"] == 2
        assert diff["after"]["nodes"] == 2

    def test_added_node(self):
        """Test diff detects added nodes."""
        original = {
            "nodes": [{"name": "Node1"}],
            "connections": {},
            "settings": {}
        }
        modified = {
            "nodes": [{"name": "Node1"}, {"name": "Node2"}],
            "connections": {},
            "settings": {}
        }

        diff = N8nWorkflowDiff.generate_diff(original, modified)

        assert "Added node: Node2" in diff["changes"]
        assert diff["before"]["nodes"] == 1
        assert diff["after"]["nodes"] == 2

    def test_removed_node(self):
        """Test diff detects removed nodes."""
        original = {
            "nodes": [{"name": "Node1"}, {"name": "Node2"}],
            "connections": {},
            "settings": {}
        }
        modified = {
            "nodes": [{"name": "Node1"}],
            "connections": {},
            "settings": {}
        }

        diff = N8nWorkflowDiff.generate_diff(original, modified)

        assert "Removed node: Node2" in diff["changes"]
        assert diff["before"]["nodes"] == 2
        assert diff["after"]["nodes"] == 1

    def test_modified_node(self):
        """Test diff detects modified nodes."""
        original = {
            "nodes": [{"name": "Node1", "parameters": {"value": 1}}],
            "connections": {},
            "settings": {}
        }
        modified = {
            "nodes": [{"name": "Node1", "parameters": {"value": 2}}],
            "connections": {},
            "settings": {}
        }

        diff = N8nWorkflowDiff.generate_diff(original, modified)

        assert "Modified node: Node1" in diff["changes"]

    def test_connection_change(self):
        """Test diff detects connection changes."""
        original = {
            "nodes": [{"name": "Node1"}],
            "connections": {"Node1": {}},
            "settings": {}
        }
        modified = {
            "nodes": [{"name": "Node1"}],
            "connections": {"Node1": {}, "Node2": {}},
            "settings": {}
        }

        diff = N8nWorkflowDiff.generate_diff(original, modified)

        assert any("Connections changed" in change for change in diff["changes"])

    def test_settings_change(self):
        """Test diff detects settings changes."""
        original = {
            "nodes": [],
            "connections": {},
            "settings": {"timeout": 10}
        }
        modified = {
            "nodes": [],
            "connections": {},
            "settings": {"timeout": 30}
        }

        diff = N8nWorkflowDiff.generate_diff(original, modified)

        assert "Workflow settings modified" in diff["changes"]

    def test_empty_workflows(self):
        """Test diff with empty workflows."""
        original = {"nodes": [], "connections": {}, "settings": {}}
        modified = {"nodes": [], "connections": {}, "settings": {}}

        diff = N8nWorkflowDiff.generate_diff(original, modified)

        assert diff["changes"] == []
        assert diff["before"]["nodes"] == 0
        assert diff["after"]["nodes"] == 0

    def test_multiple_changes(self):
        """Test diff with multiple types of changes."""
        original = {
            "nodes": [
                {"name": "Node1", "parameters": {}},
                {"name": "Node2", "parameters": {}}
            ],
            "connections": {"Node1": {}},
            "settings": {"timeout": 10}
        }
        modified = {
            "nodes": [
                {"name": "Node1", "parameters": {"maxIterations": 100}},
                {"name": "Node3", "parameters": {}}
            ],
            "connections": {"Node1": {}, "Node3": {}},
            "settings": {"timeout": 30}
        }

        diff = N8nWorkflowDiff.generate_diff(original, modified)

        assert "Modified node: Node1" in diff["changes"]
        assert "Added node: Node3" in diff["changes"]
        assert "Removed node: Node2" in diff["changes"]
        assert any("Connections changed" in c for c in diff["changes"])
        assert "Workflow settings modified" in diff["changes"]


class TestN8nApiError:
    """Tests for N8nApiError exception."""

    def test_error_with_status_code(self):
        """Test error includes status code."""
        error = N8nApiError(
            message="Not found",
            status_code=404,
            response_body="Resource not found"
        )

        assert error.message == "Not found"
        assert error.status_code == 404
        assert error.response_body == "Resource not found"
        assert str(error) == "Not found"

    def test_error_without_status_code(self):
        """Test error without status code."""
        error = N8nApiError(message="Connection failed")

        assert error.message == "Connection failed"
        assert error.status_code is None
        assert error.response_body is None
