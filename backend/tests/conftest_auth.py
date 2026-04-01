"""Auth and database mock fixtures."""

import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4


@pytest_asyncio.fixture
async def test_tenant():
    """Test tenant with valid UUID."""
    from app.storage.models import Tenant
    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid4()
    tenant.name = "Test Tenant"
    tenant.api_key_hash = "test_hash"
    return tenant


@pytest_asyncio.fixture
async def db_session(test_tenant):
    """Mocked async database session."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.storage.database import get_db

    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.scalar_one_or_none = AsyncMock(return_value=None)

    # Storage for added objects
    added_objects = []

    def track_add(obj):
        added_objects.append(obj)

    mock_session.add.side_effect = track_add

    # Override get_db to return mock session
    def override_db():
        return mock_session

    app.dependency_overrides[get_db] = override_db
    yield mock_session
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def client(test_tenant, db_session):
    """HTTP client with auth overridden to use test_tenant."""
    from unittest.mock import patch
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.auth import get_current_tenant

    def override_tenant():
        return str(test_tenant.id)

    app.dependency_overrides[get_current_tenant] = override_tenant

    # Mock rate limiter to avoid Redis connection issues
    mock_rate_limiter = MagicMock()
    mock_rate_limiter.check_rate_limit = AsyncMock(return_value=True)
    mock_rate_limiter.get_remaining = AsyncMock(return_value=1000)
    mock_rate_limiter.close = AsyncMock()

    try:
        with patch('app.main.rate_limiter', mock_rate_limiter):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                yield ac
    finally:
        app.dependency_overrides.pop(get_current_tenant, None)


@pytest_asyncio.fixture
async def mock_tenant_context():
    """Mock set_tenant_context for tests that need it."""
    from unittest.mock import patch, AsyncMock

    # Mock set_tenant_context without importing the module
    with patch('app.storage.database.set_tenant_context', new_callable=AsyncMock) as mock:
        yield mock
