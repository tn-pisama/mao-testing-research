import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_root_endpoint(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "MAO Testing Platform"


@pytest.mark.asyncio
async def test_create_tenant(client):
    response = await client.post("/api/v1/auth/tenants", json={"name": "Test Tenant"})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "api_key" in data
    assert data["api_key"].startswith("mao_")


@pytest.mark.asyncio
async def test_unauthorized_access(client):
    response = await client.get("/api/v1/tenants/some-id/traces")
    assert response.status_code == 403
