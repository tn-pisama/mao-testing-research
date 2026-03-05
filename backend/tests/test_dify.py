"""Tests for Dify integration: parser and webhook endpoint."""

import pytest
import pytest_asyncio
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.ingestion.dify_parser import dify_parser, DifyWorkflowRun, DifyNodeEvent


class TestDifyParser:
    """Tests for DifyParser parsing and state extraction."""

    def test_parse_workflow_run_basic(self):
        raw_data = {
            "workflow_run_id": "run-123",
            "app_id": "app-456",
            "app_name": "Test App",
            "app_type": "workflow",
            "started_at": "2024-01-01T00:00:00Z",
            "finished_at": "2024-01-01T00:00:05Z",
            "status": "succeeded",
            "total_tokens": 500,
            "total_steps": 3,
            "nodes": [
                {
                    "node_id": "node-1",
                    "node_type": "llm",
                    "title": "Generate Response",
                    "status": "succeeded",
                    "inputs": {"query": "hello"},
                    "outputs": {"text": "Hi there"},
                    "token_count": 200,
                }
            ],
        }

        run = dify_parser.parse_workflow_run(raw_data)

        assert run.workflow_run_id == "run-123"
        assert run.app_id == "app-456"
        assert run.app_name == "Test App"
        assert run.app_type == "workflow"
        assert run.status == "succeeded"
        assert run.total_tokens == 500
        assert run.total_steps == 3
        assert len(run.nodes) == 1
        assert run.nodes[0].node_type == "llm"
        assert run.nodes[0].title == "Generate Response"
        assert run.nodes[0].token_count == 200

    def test_parse_to_states(self):
        run = DifyWorkflowRun(
            workflow_run_id="run-123",
            app_id="app-456",
            app_name="Test App",
            app_type="workflow",
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            status="succeeded",
            nodes=[
                DifyNodeEvent(
                    node_id="n1", node_type="llm", title="LLM Node",
                    status="succeeded", token_count=100,
                ),
                DifyNodeEvent(
                    node_id="n2", node_type="tool", title="Search Tool",
                    status="succeeded", token_count=0,
                ),
                DifyNodeEvent(
                    node_id="n3", node_type="knowledge_retrieval",
                    title="RAG Lookup", status="succeeded", token_count=50,
                ),
            ],
        )

        states = dify_parser.parse_to_states(run, "tenant-123")

        assert len(states) == 3
        assert states[0].agent_id == "LLM Node"
        assert states[0].sequence_num == 0
        assert states[0].token_count == 100
        assert states[1].agent_id == "Search Tool"
        assert states[1].sequence_num == 1
        assert states[2].agent_id == "RAG Lookup"
        assert states[2].sequence_num == 2

    def test_node_type_mapping(self):
        """Verify node_type is preserved in state_delta."""
        run = DifyWorkflowRun(
            workflow_run_id="run-1",
            app_id="app-1",
            app_name="Test",
            app_type="workflow",
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            status="succeeded",
            nodes=[
                DifyNodeEvent(
                    node_id="n1", node_type="knowledge_retrieval",
                    title="RAG", status="succeeded",
                ),
            ],
        )

        states = dify_parser.parse_to_states(run, "tenant-1")
        assert states[0].node_type == "knowledge_retrieval"

    def test_iteration_child_detection(self):
        """Nodes with parent_node_id should be marked as iteration children."""
        run = DifyWorkflowRun(
            workflow_run_id="run-1",
            app_id="app-1",
            app_name="Test",
            app_type="workflow",
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            status="succeeded",
            nodes=[
                DifyNodeEvent(
                    node_id="n1", node_type="iteration",
                    title="Loop Block", status="succeeded",
                ),
                DifyNodeEvent(
                    node_id="n2", node_type="llm",
                    title="Inner LLM", status="succeeded",
                    parent_node_id="n1", iteration_index=0,
                ),
            ],
        )

        states = dify_parser.parse_to_states(run, "tenant-1")
        assert states[0].is_iteration_child is False
        assert states[1].is_iteration_child is True


@pytest_asyncio.fixture
async def dify_webhook_client():
    """Async client for Dify webhook tests with mocked DB."""
    from app.storage.database import get_db
    from app.core.auth import get_current_tenant

    mock_tenant = MagicMock()
    mock_tenant.id = uuid4()
    mock_tenant.name = "Test Tenant"

    mock_api_key = MagicMock()
    mock_api_key.key_prefix = "mao_testkey1"
    mock_api_key.key_hash = "hashed_key"
    mock_api_key.tenant_id = mock_tenant.id
    mock_api_key.revoked_at = None

    call_count = [0]

    def create_mock_result():
        call_count[0] += 1
        mock_result = MagicMock()
        if call_count[0] == 1:
            # API key lookup (verify_api_key_and_get_tenant step 1)
            mock_result.scalar_one_or_none.return_value = mock_api_key
        elif call_count[0] == 2:
            # Tenant lookup (verify_api_key_and_get_tenant step 2)
            mock_result.scalar_one_or_none.return_value = mock_tenant
        elif call_count[0] == 3:
            # set_tenant_context (verify_api_key_and_get_tenant step 3)
            return mock_result
        elif call_count[0] == 4:
            # DifyApp lookup
            mock_result.scalar_one_or_none.return_value = None
        else:
            mock_result.scalar_one_or_none.return_value = None
            mock_result.scalars.return_value.all.return_value = []
        return mock_result

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(side_effect=lambda *a, **k: create_mock_result())
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    def override_get_db():
        return mock_db

    def override_get_tenant():
        return str(mock_tenant.id)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_tenant] = override_get_tenant

    mock_rate_limiter = MagicMock()
    mock_rate_limiter.check_rate_limit = AsyncMock(return_value=True)
    mock_rate_limiter.get_remaining = AsyncMock(return_value=1000)
    mock_rate_limiter.close = AsyncMock()

    try:
        with patch('app.main.rate_limiter', mock_rate_limiter):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client, mock_db, mock_tenant
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_tenant, None)


class TestDifyWebhook:
    """Tests for POST /api/v1/dify/webhook."""

    @pytest.mark.asyncio
    async def test_webhook_creates_trace(self, dify_webhook_client):
        """Dify webhook should create a trace successfully."""
        client, mock_db, mock_tenant = dify_webhook_client

        with patch('app.core.auth.verify_api_key', return_value=True), \
             patch('app.api.v1.dify.verify_webhook_if_configured', new_callable=AsyncMock):
            payload = {
                "workflow_run_id": "run-123",
                "app_id": "app-456",
                "app_name": "Test App",
                "app_type": "workflow",
                "started_at": "2024-01-01T00:00:00Z",
                "finished_at": "2024-01-01T00:00:05Z",
                "status": "succeeded",
                "total_tokens": 500,
                "total_steps": 2,
                "nodes": [
                    {
                        "node_id": "n1",
                        "node_type": "llm",
                        "title": "Generate",
                        "status": "succeeded",
                    }
                ],
            }

            response = await client.post(
                "/api/v1/dify/webhook",
                json=payload,
                headers={"X-MAO-API-Key": "mao_testkey123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "trace_id" in data

    @pytest.mark.asyncio
    async def test_webhook_missing_api_key(self, dify_webhook_client):
        """Missing API key should return 422."""
        client, _, _ = dify_webhook_client

        payload = {
            "workflow_run_id": "run-123",
            "app_id": "app-456",
            "app_name": "Test",
            "app_type": "workflow",
            "started_at": "2024-01-01T00:00:00Z",
            "status": "succeeded",
            "nodes": [],
        }

        response = await client.post(
            "/api/v1/dify/webhook",
            json=payload,
        )

        assert response.status_code == 422
