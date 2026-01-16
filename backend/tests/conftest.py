import os
os.environ["TESTING"] = "1"
os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://mao:mao@localhost:5432/mao")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

import pytest
import pytest_asyncio
import re
from typing import Any, Dict
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4


# Note: No custom event_loop fixture needed - pytest-asyncio auto mode handles it
# (configured in pytest.ini with asyncio_mode = auto)


SENSITIVE_PATTERNS = [
    (r'sk-[a-zA-Z0-9]{20,}', '[OPENAI_KEY_REDACTED]'),
    (r'sk-proj-[a-zA-Z0-9\-_]{20,}', '[OPENAI_PROJECT_KEY_REDACTED]'),
    (r'xai-[a-zA-Z0-9]{20,}', '[GROK_KEY_REDACTED]'),
    (r'AIza[0-9A-Za-z\-_]{35}', '[GOOGLE_KEY_REDACTED]'),
    (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]'),
    (r'api[_-]?key["\']?\s*[:=]\s*["\']?[a-zA-Z0-9\-_]{20,}', 'api_key: [REDACTED]'),
]


def scrub_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive data from recorded responses."""
    if 'body' not in response or 'string' not in response['body']:
        return response
    
    body = response['body']['string']
    if isinstance(body, bytes):
        try:
            body = body.decode('utf-8', errors='ignore')
        except Exception:
            return response
    
    for pattern, replacement in SENSITIVE_PATTERNS:
        body = re.sub(pattern, replacement, body, flags=re.IGNORECASE)
    
    if isinstance(response['body']['string'], bytes):
        response['body']['string'] = body.encode('utf-8')
    else:
        response['body']['string'] = body
    
    return response


def scrub_request(request: Any) -> Any:
    """Remove sensitive data from recorded requests."""
    if hasattr(request, 'body') and request.body:
        body = request.body
        if isinstance(body, bytes):
            try:
                body = body.decode('utf-8', errors='ignore')
            except Exception:
                return request
        
        for pattern, replacement in SENSITIVE_PATTERNS:
            body = re.sub(pattern, replacement, body, flags=re.IGNORECASE)
        
        if isinstance(request.body, bytes):
            request.body = body.encode('utf-8')
        else:
            request.body = body
    
    return request


@pytest.fixture(scope="module")
def vcr_config():
    """VCR configuration for recording/replaying HTTP interactions."""
    return {
        "cassette_library_dir": os.path.join(os.path.dirname(__file__), "cassettes"),
        "record_mode": os.getenv("MAO_RECORD_MODE", "none"),
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        "filter_headers": [
            "authorization",
            "x-api-key",
            "openai-api-key",
            "api-key",
            "x-goog-api-key",
        ],
        "before_record_response": scrub_response,
        "before_record_request": scrub_request,
        "decode_compressed_response": True,
    }


@pytest.fixture
def mao_test_endpoint():
    """MAO backend endpoint for testing."""
    return os.getenv("MAO_TEST_ENDPOINT", "http://localhost:8000")


@pytest.fixture
def test_trace_id():
    """Generate a unique trace ID for testing."""
    import uuid
    return str(uuid.uuid4())


# =============================================================================
# N8n and API Test Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def n8n_test_client():
    """
    Async client with mocked database for n8n webhook tests.

    Provides proper setup/teardown to avoid event loop cleanup issues.
    Yields (client, mock_db, mock_tenant) tuple.
    """
    from unittest.mock import patch
    from httpx import AsyncClient, ASGITransport
    from app.main import app
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

    # Use sync lambda returns instead of async generators to avoid event loop issues
    def override_get_db():
        return mock_db

    def override_get_tenant():
        return str(mock_tenant.id)

    # Apply test overrides
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_tenant] = override_get_tenant

    # Mock rate limiter to avoid Redis connection issues
    mock_rate_limiter = MagicMock()
    mock_rate_limiter.check_rate_limit = AsyncMock(return_value=True)
    mock_rate_limiter.get_remaining = AsyncMock(return_value=1000)
    mock_rate_limiter.close = AsyncMock()

    try:
        with patch('app.main.rate_limiter', mock_rate_limiter):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                yield client, mock_db, mock_tenant
    finally:
        # Remove only the overrides we added (not the whole dict)
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_tenant, None)


@pytest_asyncio.fixture
async def n8n_workflow_client():
    """
    Async client for n8n workflow management tests (register, list workflows).

    Uses separate mock setup for workflow-related endpoints.
    """
    from unittest.mock import patch
    from httpx import AsyncClient, ASGITransport
    from datetime import datetime, timezone
    from app.main import app
    from app.storage.database import get_db
    from app.core.auth import get_current_tenant

    mock_tenant_id = str(uuid4())

    mock_workflow = MagicMock()
    mock_workflow.id = uuid4()
    mock_workflow.workflow_id = "wf-test-123"
    mock_workflow.workflow_name = "Test Workflow"
    mock_workflow.registered_at = datetime.now(timezone.utc)
    mock_workflow.webhook_secret = "test_secret"

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = mock_workflow
    mock_result.scalars.return_value.all.return_value = [mock_workflow]

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    # Use sync returns instead of async generators
    def override_get_db():
        return mock_db

    def override_get_tenant():
        return mock_tenant_id

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_tenant] = override_get_tenant

    # Mock rate limiter to avoid Redis connection issues
    mock_rate_limiter = MagicMock()
    mock_rate_limiter.check_rate_limit = AsyncMock(return_value=True)
    mock_rate_limiter.get_remaining = AsyncMock(return_value=1000)
    mock_rate_limiter.close = AsyncMock()

    try:
        with patch('app.main.rate_limiter', mock_rate_limiter):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                yield client, mock_db, mock_workflow
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_tenant, None)


@pytest_asyncio.fixture
async def api_test_client():
    """
    Async client for general API tests with mocked database.
    """
    from unittest.mock import patch
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.storage.database import get_db

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    # Use sync return instead of async generator
    def override_get_db():
        return mock_db

    app.dependency_overrides[get_db] = override_get_db

    # Mock rate limiter to avoid Redis connection issues
    mock_rate_limiter = MagicMock()
    mock_rate_limiter.check_rate_limit = AsyncMock(return_value=True)
    mock_rate_limiter.get_remaining = AsyncMock(return_value=1000)
    mock_rate_limiter.close = AsyncMock()

    try:
        with patch('app.main.rate_limiter', mock_rate_limiter):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                yield client, mock_db
    finally:
        app.dependency_overrides.pop(get_db, None)
