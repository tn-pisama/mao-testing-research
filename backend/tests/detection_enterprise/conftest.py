"""Shared fixtures for detection_enterprise tests."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.ingestion.universal_trace import (
    UniversalTrace,
    UniversalSpan,
    SpanType,
    SpanStatus,
)


@pytest.fixture
def sample_trace_id():
    """Generate a unique trace ID."""
    return str(uuid4())


@pytest.fixture
def sample_span(sample_trace_id):
    """Create a sample UniversalSpan for testing."""
    now = datetime.utcnow()
    return UniversalSpan(
        id=str(uuid4()),
        trace_id=sample_trace_id,
        name="test_span",
        span_type=SpanType.LLM_CALL,
        status=SpanStatus.OK,
        start_time=now,
        end_time=now + timedelta(milliseconds=100),
        duration_ms=100,
        prompt="What is the capital of France?",
        response="The capital of France is Paris.",
        model="gpt-4o",
        tokens_input=10,
        tokens_output=8,
        agent_id="agent_1",
        agent_name="Test Agent",
    )


@pytest.fixture
def sample_universal_trace(sample_trace_id, sample_span):
    """Create a sample UniversalTrace for testing."""
    return UniversalTrace(
        trace_id=sample_trace_id,
        spans=[sample_span],
        source_format="test",
    )


@pytest.fixture
def multi_span_trace(sample_trace_id):
    """Create a trace with multiple spans of different types."""
    now = datetime.utcnow()
    spans = []

    # LLM call span
    spans.append(UniversalSpan(
        id=str(uuid4()),
        trace_id=sample_trace_id,
        name="llm_call_1",
        span_type=SpanType.LLM_CALL,
        status=SpanStatus.OK,
        start_time=now,
        end_time=now + timedelta(milliseconds=500),
        duration_ms=500,
        prompt="Analyze this document",
        response="Based on my analysis...",
        model="gpt-4o",
        tokens_input=100,
        tokens_output=200,
        agent_id="agent_1",
    ))

    # Tool call span
    spans.append(UniversalSpan(
        id=str(uuid4()),
        trace_id=sample_trace_id,
        name="tool_call_1",
        span_type=SpanType.TOOL_CALL,
        status=SpanStatus.OK,
        start_time=now + timedelta(milliseconds=100),
        end_time=now + timedelta(milliseconds=200),
        duration_ms=100,
        tool_name="search",
        tool_args={"query": "test query"},
        tool_result={"results": ["doc1", "doc2"]},
        agent_id="agent_1",
    ))

    # Retrieval span
    spans.append(UniversalSpan(
        id=str(uuid4()),
        trace_id=sample_trace_id,
        name="retrieval_1",
        span_type=SpanType.RETRIEVAL,
        status=SpanStatus.OK,
        start_time=now + timedelta(milliseconds=200),
        end_time=now + timedelta(milliseconds=300),
        duration_ms=100,
        input_data={"query": "find relevant documents"},
        output_data={"documents": ["doc1", "doc2", "doc3"]},
        agent_id="agent_1",
    ))

    return UniversalTrace(
        trace_id=sample_trace_id,
        spans=spans,
        source_format="test",
    )


@pytest.fixture
def error_trace(sample_trace_id):
    """Create a trace with error spans."""
    now = datetime.utcnow()
    spans = []

    # Successful span
    spans.append(UniversalSpan(
        id=str(uuid4()),
        trace_id=sample_trace_id,
        name="successful_span",
        span_type=SpanType.LLM_CALL,
        status=SpanStatus.OK,
        start_time=now,
        end_time=now + timedelta(milliseconds=100),
        duration_ms=100,
        agent_id="agent_1",
    ))

    # Error span
    spans.append(UniversalSpan(
        id=str(uuid4()),
        trace_id=sample_trace_id,
        name="error_span",
        span_type=SpanType.TOOL_CALL,
        status=SpanStatus.ERROR,
        start_time=now + timedelta(milliseconds=100),
        end_time=now + timedelta(milliseconds=200),
        duration_ms=100,
        error="Connection timeout",
        error_type="TimeoutError",
        agent_id="agent_1",
    ))

    return UniversalTrace(
        trace_id=sample_trace_id,
        spans=spans,
        source_format="test",
    )


@pytest.fixture
def empty_trace(sample_trace_id):
    """Create an empty trace with no spans."""
    return UniversalTrace(
        trace_id=sample_trace_id,
        spans=[],
        source_format="test",
    )


@pytest.fixture
def sample_source_documents():
    """Sample documents for grounding tests."""
    return [
        "In Q3 2024, Acme Corp reported revenue of $45.2M, up 15% year-over-year.",
        "The company's operating margin improved to 23% from 18% in Q2 2024.",
        "CEO John Smith announced expansion into the European market.",
    ]


@pytest.fixture
def sample_output_with_claims():
    """Sample output containing claims to verify against sources."""
    return """
    Based on the financial reports, Acme Corp achieved strong results in Q3 2024:
    - Revenue reached $45.2M, representing 15% growth compared to Q3 2023.
    - Operating margin improved significantly to 23%.
    - CEO John Smith announced European expansion plans.
    - The company expects Q4 revenue to exceed $50M.
    """


@pytest.fixture
def sample_retrieval_context():
    """Sample retrieval context for quality testing."""
    return {
        "query": "What was Acme Corp's revenue in Q3 2024?",
        "retrieved_documents": [
            {
                "id": "doc1",
                "content": "In Q3 2024, Acme Corp reported revenue of $45.2M, up 15% year-over-year.",
                "metadata": {"source": "earnings_report_q3_2024.pdf"},
            },
            {
                "id": "doc2",
                "content": "The weather forecast for tomorrow shows partly cloudy skies.",
                "metadata": {"source": "weather.txt"},
            },
            {
                "id": "doc3",
                "content": "Acme Corp was founded in 1985 and is headquartered in New York.",
                "metadata": {"source": "company_overview.pdf"},
            },
        ],
    }
