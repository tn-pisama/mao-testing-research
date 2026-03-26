import os
os.environ["TESTING"] = "1"
os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://mao:mao@localhost:5432/mao")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("FEATURE_ENTERPRISE_ENABLED", "true")
os.environ.setdefault("FEATURE_QUALITY_ASSESSMENT", "true")
os.environ.setdefault("STRIPE_PRICE_ID_PRO_MONTHLY", "price_test_pro")
os.environ.setdefault("STRIPE_PRICE_ID_TEAM_MONTHLY", "price_test_team")
os.environ.setdefault("FRONTEND_URL", "https://app.example.com")

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
    mock_workflow.ingestion_mode = "webhook"

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


# =============================================================================
# Standalone Fixtures for Phase 5 API Tests
# =============================================================================


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


# =============================================================================
# Quality Assessment Test Fixtures
# =============================================================================


@pytest.fixture
def sample_workflow():
    """Sample n8n workflow JSON for quality testing."""
    return {
        "id": "wf-test-quality",
        "name": "Test Quality Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook Trigger",
                "type": "n8n-nodes-base.webhook",
                "parameters": {}
            },
            {
                "id": "2",
                "name": "Data Analyst",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "continueOnFail": True,
                "parameters": {
                    "systemMessage": "You are a data analyst. Analyze input and return JSON.",
                    "options": {
                        "temperature": 0.3,
                        "timeout": 30000,
                        "retryOnFail": True
                    }
                }
            },
            {
                "id": "3",
                "name": "Output",
                "type": "n8n-nodes-base.respond",
                "parameters": {}
            }
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Data Analyst"}]]},
            "Data Analyst": {"main": [[{"node": "Output"}]]}
        }
    }


@pytest.fixture
def sample_agent_node():
    """Sample agent node JSON for quality testing."""
    return {
        "id": "agent-test",
        "name": "Test Agent",
        "type": "@n8n/n8n-nodes-langchain.agent",
        "continueOnFail": True,
        "parameters": {
            "systemMessage": "You are a helpful assistant. Always respond in JSON format.",
            "options": {
                "temperature": 0.5,
                "timeout": 30000
            }
        }
    }


@pytest.fixture
def minimal_workflow():
    """Minimal workflow for testing low-quality scenarios."""
    return {
        "id": "wf-minimal",
        "name": "Minimal Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {}
            }
        ],
        "connections": {}
    }


def make_low_quality_workflow():
    """Factory: deliberately low-quality 3-node n8n workflow.

    Has: trigger + bare AI agent + output (with connections).
    Missing: system prompt, error handling, pinData, error trigger.
    Shared across healing test suites — do not modify without running
    test_quality_healing_*.py tests.
    """
    return {
        "id": "low-quality-shared",
        "name": "Low Quality Workflow",
        "nodes": [
            {
                "id": "trigger-1",
                "name": "Webhook Trigger",
                "type": "n8n-nodes-base.webhook",
                "parameters": {"path": "/test"},
                "position": [0, 0],
            },
            {
                "id": "agent-1",
                "name": "AI Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "parameters": {},
                "position": [200, 0],
            },
            {
                "id": "output-1",
                "name": "Output",
                "type": "n8n-nodes-base.respondToWebhook",
                "parameters": {},
                "position": [400, 0],
            },
        ],
        "connections": {
            "Webhook Trigger": {
                "main": [[{"node": "AI Agent", "type": "main", "index": 0}]]
            },
            "AI Agent": {
                "main": [[{"node": "Output", "type": "main", "index": 0}]]
            },
        },
        "settings": {},
    }


@pytest.fixture
def low_quality_workflow():
    """Fixture wrapper around make_low_quality_workflow()."""
    return make_low_quality_workflow()


@pytest.fixture
def well_configured_workflow():
    """Well-configured workflow for testing high-quality scenarios."""
    return {
        "id": "wf-excellent",
        "name": "Excellent Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Webhook Trigger",
                "type": "n8n-nodes-base.webhook",
                "parameters": {}
            },
            {
                "id": "2",
                "name": "Senior Data Analyst",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "continueOnFail": True,
                "alwaysOutputData": True,
                "parameters": {
                    "systemMessage": """You are a senior data analyst specializing in business intelligence.
Your role is to analyze data and provide actionable insights.
Your task is to examine the provided dataset and identify trends.

You must respond with a JSON object in this format:
{
  "summary": "Brief analysis summary",
  "insights": ["insight 1", "insight 2"],
  "confidence": 0.0-1.0
}

Do not make assumptions about missing data.
Only respond to data analysis requests.""",
                    "options": {
                        "temperature": 0.2,
                        "timeout": 60000,
                        "retryOnFail": True,
                        "maxRetries": 3
                    },
                    "tools": [
                        {
                            "name": "search_data",
                            "description": "Search the data warehouse",
                            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}
                        }
                    ]
                }
            },
            {
                "id": "3",
                "name": "Checkpoint",
                "type": "n8n-nodes-base.set",
                "parameters": {}
            },
            {
                "id": "4",
                "name": "Send Response",
                "type": "n8n-nodes-base.respond",
                "parameters": {}
            },
            {
                "id": "5",
                "name": "Error Handler",
                "type": "n8n-nodes-base.errorTrigger",
                "parameters": {}
            }
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "Senior Data Analyst"}]]},
            "Senior Data Analyst": {"main": [[{"node": "Checkpoint"}]]},
            "Checkpoint": {"main": [[{"node": "Send Response"}]]}
        },
        "settings": {
            "saveManualExecutions": True,
            "saveDataErrorExecution": "all"
        }
    }


@pytest.fixture
def execution_history_consistent():
    """Consistent execution history for output consistency testing."""
    return [
        {"output": {"result": "A", "confidence": 0.9}},
        {"output": {"result": "B", "confidence": 0.8}},
        {"output": {"result": "C", "confidence": 0.95}},
    ]


@pytest.fixture
def execution_history_inconsistent():
    """Inconsistent execution history for output consistency testing."""
    return [
        {"output": {"result": "A", "confidence": 0.9}},
        {"output": {"answer": "B", "score": 0.8}},
        {"output": {"data": "C"}},
    ]


# =============================================================================
# Dataset Loading Fixtures
# =============================================================================


@pytest.fixture
def n8n_workflow_files():
    """Load all 4 n8n workflow JSON files from _archived/demo-agent/n8n-workflows/."""
    import json
    from pathlib import Path

    base_path = Path(__file__).parent.parent.parent / "_archived" / "demo-agent" / "n8n-workflows"

    workflows = {}
    for filename in ["research-assistant-normal.json", "research-loop-buggy.json",
                     "research-corruption.json", "research-drift.json"]:
        filepath = base_path / filename
        if filepath.exists():
            with open(filepath) as f:
                workflows[filename.replace(".json", "")] = json.load(f)

    return workflows


@pytest.fixture
def golden_traces():
    """Load golden_traces.jsonl (420 traces)."""
    import json
    from pathlib import Path

    filepath = Path(__file__).parent.parent / "fixtures" / "golden" / "golden_traces.jsonl"

    traces = []
    if filepath.exists():
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    traces.append(json.loads(line))

    return traces


@pytest.fixture
def golden_traces_by_type(golden_traces):
    """Group golden traces by detection type."""
    by_type = {}

    for trace in golden_traces:
        # Detection type is nested in _golden_metadata
        metadata = trace.get("_golden_metadata", {})
        detection_type = metadata.get("detection_type", "unknown")

        if detection_type not in by_type:
            by_type[detection_type] = []
        by_type[detection_type].append(trace)

    return by_type


@pytest.fixture
def archived_traces():
    """Load 4,142 archived traces from all_traces.jsonl."""
    import json
    from pathlib import Path

    filepath = Path(__file__).parent.parent.parent / "_archived" / "traces" / "all_traces.jsonl"

    traces = []
    if filepath.exists():
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    traces.append(json.loads(line))

    return traces


@pytest.fixture
def archived_traces_by_framework(archived_traces):
    """Group archived traces by framework (langchain, autogen, crewai, etc.)."""
    by_framework = {}

    for trace in archived_traces:
        framework = trace.get("framework", "unknown")
        if framework not in by_framework:
            by_framework[framework] = []
        by_framework[framework].append(trace)

    return by_framework


@pytest.fixture
def mast_traces():
    """Load 10 MAST benchmark traces with F1-F14 labels."""
    import json
    from pathlib import Path

    filepath = Path(__file__).parent.parent / "fixtures" / "mast" / "sample_mast.jsonl"

    traces = []
    if filepath.exists():
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    traces.append(json.loads(line))

    return traces


@pytest.fixture
def external_n8n_workflows():
    """Load external n8n workflow templates (sample of 100)."""
    import json
    from pathlib import Path

    base = Path(__file__).parent.parent / "fixtures" / "external" / "n8n"
    workflows = []

    if not base.exists():
        return workflows

    for repo in ["zengfr-templates", "ai-templates"]:
        repo_path = base / repo
        if repo_path.exists():
            for json_file in repo_path.rglob("*.json"):
                if len(workflows) >= 100:
                    break
                try:
                    workflows.append(json.loads(json_file.read_text()))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Skip invalid JSON files
                    continue

    return workflows
