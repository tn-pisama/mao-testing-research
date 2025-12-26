import pytest
import pytest_asyncio
import time
import hmac
import hashlib
import json
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock

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


@pytest.mark.skip(reason="Requires database - run as integration test")
class TestN8nWebhook:
    async def test_webhook_creates_trace(self, client: AsyncClient, test_tenant):
        payload = {
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
                        "Node1": [{"executionTime": 100}]
                    }
                }
            }
        }
        
        response = await client.post(
            "/api/v1/n8n/webhook",
            json=payload,
            headers={"X-MAO-API-Key": test_tenant["api_key"]},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "trace_id" in data
        assert data["states_created"] == 1
    
    async def test_webhook_invalid_api_key(self, client: AsyncClient):
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
    
    async def test_webhook_missing_api_key(self, client: AsyncClient):
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


@pytest.mark.skip(reason="Requires database - run as integration test")
class TestN8nWorkflowManagement:
    async def test_register_workflow(self, client: AsyncClient, auth_headers):
        response = await client.post(
            "/api/v1/n8n/workflows",
            json={"workflow_id": "wf-test-123", "workflow_name": "Test Workflow"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "wf-test-123"
        assert "webhook_url" in data
    
    async def test_list_workflows(self, client: AsyncClient, auth_headers):
        await client.post(
            "/api/v1/n8n/workflows",
            json={"workflow_id": "wf-list-1"},
            headers=auth_headers,
        )
        
        response = await client.get(
            "/api/v1/n8n/workflows",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(w["workflow_id"] == "wf-list-1" for w in data)
