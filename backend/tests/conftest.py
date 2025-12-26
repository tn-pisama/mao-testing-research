import pytest
import asyncio
import os
import re
from typing import Any, Dict


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
