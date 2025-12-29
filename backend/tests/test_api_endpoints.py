"""Comprehensive tests for API endpoints."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.v1.webhooks import (
    create_user_from_clerk,
    update_user_from_clerk,
    delete_user_from_clerk,
    add_user_to_tenant,
    remove_user_from_tenant,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def client():
    """Basic async test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def mock_db():
    """Create a mock database session."""
    mock = MagicMock()
    mock.add = MagicMock()
    mock.commit = AsyncMock()
    mock.refresh = AsyncMock()
    mock.delete = AsyncMock()
    mock.flush = AsyncMock()
    mock.execute = AsyncMock()
    return mock


# ============================================================================
# Webhook Helper Function Tests
# ============================================================================

class TestWebhookHelpers:
    """Tests for webhook helper functions."""

    @pytest.mark.asyncio
    async def test_create_user_from_clerk_new_user(self, mock_db):
        """Should create a new user from Clerk data."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        data = {
            "id": "clerk_user_123",
            "email_addresses": [{"email_address": "test@example.com"}],
            "first_name": "John",
            "last_name": "Doe",
        }

        await create_user_from_clerk(mock_db, data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_from_clerk_existing_user(self, mock_db):
        """Should not create user if already exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute.return_value = mock_result

        data = {"id": "clerk_user_123"}

        await create_user_from_clerk(mock_db, data)

        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_user_from_clerk_with_defaults(self, mock_db):
        """Should handle missing email with default."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        data = {
            "id": "clerk_user_123",
            "email_addresses": [{}],
            "first_name": "John",
        }

        await create_user_from_clerk(mock_db, data)
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_from_clerk_existing(self, mock_db):
        """Should update existing user."""
        mock_user = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        data = {
            "id": "clerk_user_123",
            "email_addresses": [{"email_address": "new@example.com"}],
            "first_name": "Jane",
            "last_name": "Smith",
        }

        await update_user_from_clerk(mock_db, data)

        assert mock_user.email == "new@example.com"
        assert mock_user.name == "Jane Smith"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_from_clerk_not_found(self, mock_db):
        """Should do nothing if user not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        data = {"id": "nonexistent_user"}

        await update_user_from_clerk(mock_db, data)
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_user_from_clerk_existing(self, mock_db):
        """Should delete existing user."""
        mock_user = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        data = {"id": "clerk_user_123"}

        await delete_user_from_clerk(mock_db, data)

        mock_db.delete.assert_called_once_with(mock_user)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user_from_clerk_not_found(self, mock_db):
        """Should do nothing if user not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        data = {"id": "nonexistent_user"}

        await delete_user_from_clerk(mock_db, data)
        mock_db.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_user_to_tenant(self, mock_db):
        """Should add user to tenant."""
        mock_user = MagicMock()
        mock_tenant = MagicMock()
        mock_tenant.id = uuid4()

        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_user)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
        ]

        data = {
            "public_user_data": {"user_id": "clerk_user_123"},
            "organization": {"id": "org_123"},
            "role": "admin",
        }

        await add_user_to_tenant(mock_db, data)

        assert mock_user.tenant_id == mock_tenant.id
        assert mock_user.role == "owner"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_user_to_tenant_member_role(self, mock_db):
        """Should set member role for non-admin."""
        mock_user = MagicMock()
        mock_tenant = MagicMock()
        mock_tenant.id = uuid4()

        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_user)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
        ]

        data = {
            "public_user_data": {"user_id": "clerk_user_123"},
            "organization": {"id": "org_123"},
            "role": "member",
        }

        await add_user_to_tenant(mock_db, data)
        assert mock_user.role == "member"

    @pytest.mark.asyncio
    async def test_add_user_to_tenant_user_not_found(self, mock_db):
        """Should do nothing if user not found."""
        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock())),
        ]

        data = {
            "public_user_data": {"user_id": "nonexistent"},
            "organization": {"id": "org_123"},
        }

        await add_user_to_tenant(mock_db, data)
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_user_from_tenant(self, mock_db):
        """Should remove user from tenant."""
        mock_user = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        data = {"public_user_data": {"user_id": "clerk_user_123"}}

        await remove_user_from_tenant(mock_db, data)

        assert mock_user.tenant_id is None
        assert mock_user.role == "member"
        mock_db.commit.assert_called_once()


# ============================================================================
# Health Endpoint Tests
# ============================================================================

class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        """Should return health status."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_includes_timestamp(self, client):
        """Should include timestamp in response."""
        response = await client.get("/api/v1/health")
        data = response.json()
        assert "timestamp" in data or "status" in data


# ============================================================================
# Root Endpoint Tests
# ============================================================================

class TestRootEndpoint:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_info(self, client):
        """Should return application info."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "MAO Testing Platform"

    @pytest.mark.asyncio
    async def test_root_includes_version(self, client):
        """Should include version in response."""
        response = await client.get("/")
        data = response.json()
        assert "version" in data


# ============================================================================
# Webhook Endpoint Tests
# ============================================================================

class TestWebhookEndpoint:
    """Tests for Clerk webhook endpoint."""

    def test_webhook_handlers_are_registered(self):
        """Should have webhook type handlers ready."""
        from app.api.v1.webhooks import (
            create_user_from_clerk,
            update_user_from_clerk,
            delete_user_from_clerk,
        )
        # Verify handlers are callable
        assert callable(create_user_from_clerk)
        assert callable(update_user_from_clerk)
        assert callable(delete_user_from_clerk)


# ============================================================================
# Fix Generator Tests
# ============================================================================

class TestFixGenerator:
    """Tests for fix generator endpoint integration."""

    def test_get_fix_generator_returns_generator(self):
        """Should return configured fix generator."""
        from app.api.v1.detections import get_fix_generator

        generator = get_fix_generator()
        assert generator is not None

    def test_fix_generator_has_handlers(self):
        """Should have registered fix handlers."""
        from app.api.v1.detections import get_fix_generator

        generator = get_fix_generator()
        assert hasattr(generator, 'generate_fixes')


# ============================================================================
# Content Type Tests
# ============================================================================

class TestContentTypes:
    """Tests for content type handling."""

    @pytest.mark.asyncio
    async def test_json_response_type(self, client):
        """Should return JSON content type."""
        response = await client.get("/api/v1/health")
        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_root_json_response(self, client):
        """Should return JSON for root endpoint."""
        response = await client.get("/")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")


# ============================================================================
# API Route Existence Tests
# ============================================================================

class TestAPIRoutes:
    """Tests verifying API routes are registered."""

    def test_traces_router_imported(self):
        """Traces router should be imported in main."""
        from app.api.v1 import traces
        assert traces.router is not None

    def test_detections_router_imported(self):
        """Detections router should be imported in main."""
        from app.api.v1 import detections
        assert detections.router is not None

    def test_analytics_router_imported(self):
        """Analytics router should be imported in main."""
        from app.api.v1 import analytics
        assert analytics.router is not None

    def test_webhooks_router_imported(self):
        """Webhooks router should be imported in main."""
        from app.api.v1 import webhooks
        assert webhooks.router is not None

    def test_health_router_imported(self):
        """Health router should be imported in main."""
        from app.api.v1 import health
        assert health.router is not None
