import pytest
import pytest_asyncio
import time
import hmac
import hashlib
import json
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.storage.models import Tenant, Trace, State, N8nWorkflow
from app.core.n8n_security import (
    verify_webhook_signature,
    validate_n8n_url,
    redact_sensitive_data,
    compute_state_hash,
)
from app.ingestion.n8n_parser import n8n_parser, N8nExecution, N8nNode


class TestN8nSecurity:
    def test_verify_signature_valid(self):
        secret = "test-secret-key"
        timestamp = str(int(time.time()))
        payload = b'{"test": "data"}'
        
        message = f"{timestamp}.{payload.decode()}"
        signature = "sha256=" + hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        result = verify_webhook_signature(payload, signature, secret, timestamp)
        assert result is True
    
    def test_verify_signature_expired(self):
        secret = "test-secret-key"
        timestamp = str(int(time.time()) - 400)
        payload = b'{"test": "data"}'
        
        message = f"{timestamp}.{payload.decode()}"
        signature = "sha256=" + hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            verify_webhook_signature(payload, signature, secret, timestamp)
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()
    
    def test_verify_signature_invalid(self):
        secret = "test-secret-key"
        timestamp = str(int(time.time()))
        payload = b'{"test": "data"}'
        signature = "sha256=invalid"
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            verify_webhook_signature(payload, signature, secret, timestamp)
        assert exc.value.status_code == 401
    
    def test_validate_url_https(self):
        url = "https://n8n.example.com"
        result = validate_n8n_url(url)
        assert result == url
    
    def test_validate_url_blocks_localhost(self):
        with pytest.raises(ValueError, match="Internal hosts"):
            validate_n8n_url("https://localhost/api")
    
    def test_validate_url_blocks_private_ip(self):
        with pytest.raises(ValueError, match="Private"):
            validate_n8n_url("https://192.168.1.1/api")
    
    def test_validate_url_blocks_internal_domains(self):
        with pytest.raises(ValueError, match="Internal domains"):
            validate_n8n_url("https://service.internal/api")
    
    def test_redact_sensitive_data_emails(self):
        data = {"email": "user@example.com", "name": "Test"}
        result = redact_sensitive_data(data)
        assert "[REDACTED]" in result["email"]
        assert result["name"] == "Test"
    
    def test_redact_sensitive_data_api_keys(self):
        data = {"key": "sk-1234567890abcdefghijklmnopqrstuvwxyz", "safe": "value"}
        result = redact_sensitive_data(data)
        assert "[REDACTED]" in result["key"]
        assert result["safe"] == "value"
    
    def test_redact_nested_data(self):
        data = {
            "outer": {
                "email": "test@test.com",
                "inner": {"key": "sk-abcdefghijklmnopqrstuvwxyz1234567890"}
            }
        }
        result = redact_sensitive_data(data)
        assert "[REDACTED]" in result["outer"]["email"]
        assert "[REDACTED]" in result["outer"]["inner"]["key"]
    
    def test_compute_state_hash_deterministic(self):
        state1 = {"a": 1, "b": 2}
        state2 = {"b": 2, "a": 1}
        
        hash1 = compute_state_hash(state1)
        hash2 = compute_state_hash(state2)
        
        assert hash1 == hash2
        assert len(hash1) == 16


class TestN8nParser:
    def test_parse_execution_basic(self):
        raw_data = {
            "executionId": "exec-123",
            "workflowId": "wf-456",
            "workflowName": "Test Workflow",
            "mode": "manual",
            "startedAt": "2024-01-01T00:00:00Z",
            "finishedAt": "2024-01-01T00:00:05Z",
            "status": "success",
            "data": {
                "resultData": {
                    "runData": {
                        "OpenAI": [
                            {
                                "executionTime": 1500,
                                "source": [{"type": "n8n-nodes-base.openAi"}],
                                "data": {"main": [[{"response": "Hello"}]]},
                            }
                        ]
                    }
                }
            }
        }
        
        execution = n8n_parser.parse_execution(raw_data)
        
        assert execution.id == "exec-123"
        assert execution.workflow_id == "wf-456"
        assert execution.workflow_name == "Test Workflow"
        assert execution.status == "success"
        assert len(execution.nodes) == 1
        assert execution.nodes[0].name == "OpenAI"
        assert execution.nodes[0].execution_time_ms == 1500
    
    def test_parse_to_states(self):
        execution = N8nExecution(
            id="exec-123",
            workflow_id="wf-456",
            workflow_name="Test",
            mode="manual",
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            status="success",
            nodes=[
                N8nNode(name="OpenAI", type="n8n-nodes-base.openAi", execution_time_ms=1500),
                N8nNode(name="Process", type="n8n-nodes-base.code", execution_time_ms=50),
            ]
        )
        
        states = n8n_parser.parse_to_states(execution, "tenant-123")
        
        assert len(states) == 2
        assert states[0].agent_id == "OpenAI"
        assert states[0].is_ai_node is True
        assert states[0].sequence_num == 0
        assert states[1].agent_id == "Process"
        assert states[1].is_ai_node is False
        assert states[1].sequence_num == 1
    
    def test_ai_node_detection(self):
        ai_types = [
            "n8n-nodes-base.openAi",
            "n8n-nodes-base.anthropic",
            "@n8n/n8n-nodes-langchain.lmChatOpenAi",
        ]
        
        for ai_type in ai_types:
            node = N8nNode(name="Test", type=ai_type)
            assert n8n_parser._is_ai_node(node) is True
        
        non_ai_node = N8nNode(name="HTTP", type="n8n-nodes-base.httpRequest")
        assert n8n_parser._is_ai_node(non_ai_node) is True


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def mock_db_n8n_client():
    from app.storage.database import get_db
    from app.core.auth import get_current_tenant
    
    mock_tenant = MagicMock()
    mock_tenant.id = uuid4()
    mock_tenant.name = "Test Tenant"
    
    mock_api_key = MagicMock()
    mock_api_key.key_prefix = "mao_testkey1"
    mock_api_key.key_hash = "hashed_key"
    mock_api_key.tenant_id = mock_tenant.id
    
    call_count = [0]
    def create_mock_result():
        call_count[0] += 1
        mock_result = MagicMock()
        if call_count[0] == 1:
            mock_result.scalar_one_or_none.return_value = mock_api_key
        elif call_count[0] == 2:
            mock_result.scalar_one_or_none.return_value = mock_tenant
        else:
            mock_result.scalar_one_or_none.return_value = None
            mock_result.scalar_one.return_value = mock_tenant
            mock_result.scalars.return_value.all.return_value = []
        return mock_result
    
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(side_effect=lambda *a, **k: create_mock_result())
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    
    async def override_get_db():
        yield mock_db
    
    async def override_get_tenant():
        return str(mock_tenant.id)
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_tenant] = override_get_tenant
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, mock_db, mock_tenant
    
    app.dependency_overrides.clear()


class TestN8nWebhook:
    @pytest.mark.asyncio
    async def test_webhook_creates_trace(self, n8n_test_client):
        """Test that n8n webhook creates a trace successfully."""
        client, mock_db, mock_tenant = n8n_test_client

        with patch('app.core.auth.verify_api_key', return_value=True):
            payload = {
                "executionId": "exec-123",
                "workflowId": "wf-456",
                "workflowName": "Test Workflow",
                "mode": "manual",
                "startedAt": "2024-01-01T00:00:00Z",
                "finishedAt": "2024-01-01T00:00:05Z",
                "status": "success",
                "data": {"resultData": {"runData": {"Node1": [{"executionTime": 100}]}}}
            }

            response = await client.post(
                "/api/v1/n8n/webhook",
                json=payload,
                headers={"X-MAO-API-Key": "mao_testkey123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "trace_id" in data

    @pytest.mark.asyncio
    async def test_webhook_invalid_api_key(self, n8n_test_client):
        """Test that invalid API key returns 401."""
        client, _, _ = n8n_test_client

        payload = {
            "executionId": "exec-123",
            "workflowId": "wf-456",
            "workflowName": "Test",
            "startedAt": "2024-01-01T00:00:00Z",
            "status": "success",
        }

        response = await client.post(
            "/api/v1/n8n/webhook",
            json=payload,
            headers={"X-MAO-API-Key": "invalid-key"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_missing_api_key(self, n8n_test_client):
        """Test that missing API key returns 422."""
        client, _, _ = n8n_test_client

        payload = {
            "executionId": "exec-123",
            "workflowId": "wf-456",
            "startedAt": "2024-01-01T00:00:00Z",
        }

        response = await client.post(
            "/api/v1/n8n/webhook",
            json=payload,
        )

        assert response.status_code == 422


class TestN8nWorkflowManagement:
    @pytest.mark.asyncio
    async def test_register_workflow(self, n8n_workflow_client):
        """Test that workflow registration succeeds."""
        client, mock_db, mock_workflow = n8n_workflow_client

        response = await client.post(
            "/api/v1/n8n/workflows",
            json={"workflow_id": "wf-test-123", "workflow_name": "Test Workflow"},
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "wf-test-123"
        assert "webhook_url" in data

    @pytest.mark.asyncio
    async def test_list_workflows(self, n8n_workflow_client):
        """Test that workflow listing returns a list."""
        client, mock_db, mock_workflow = n8n_workflow_client

        response = await client.get(
            "/api/v1/n8n/workflows",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
