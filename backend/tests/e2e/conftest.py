"""E2E test configuration and fixtures."""

import pytest
import pytest_asyncio
from typing import Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.healing import SelfHealingEngine

from .fixtures import (
    WorkflowFactory,
    DetectionFactory,
    MockLLMResponses,
)
from .utils import WorkflowRunner, MetricsCollector


# Note: No custom event_loop fixture needed - pytest-asyncio auto mode handles it
# For session-scoped async fixtures, use @pytest.fixture(scope="session") with loop_scope="session"
# marker on the test class if needed.


@pytest_asyncio.fixture
async def async_db_session():
    """Create a real async database session for E2E tests."""
    from app.config import get_settings
    settings = get_settings()

    engine = create_async_engine(settings.database_url, echo=False)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()  # Rollback any changes after test


@pytest.fixture
def healing_engine():
    """Auto-apply healing engine for E2E tests."""
    return SelfHealingEngine(
        auto_apply=True,
        max_fix_attempts=3,
        validation_timeout=30.0,
    )


@pytest.fixture
def healing_engine_manual():
    """Manual approval healing engine."""
    return SelfHealingEngine(
        auto_apply=False,
        max_fix_attempts=3,
    )


@pytest.fixture
def workflow_factory():
    """Workflow factory for creating test workflows."""
    return WorkflowFactory()


@pytest.fixture
def detection_factory():
    """Detection factory for creating test detections."""
    return DetectionFactory()


@pytest.fixture
def mock_responses():
    """Mock LLM responses."""
    return MockLLMResponses()


@pytest.fixture
def workflow_runner(healing_engine):
    """Workflow runner for E2E tests."""
    return WorkflowRunner(healing_engine)


@pytest.fixture(scope="module")
def metrics_collector():
    """Metrics collector for test module."""
    collector = MetricsCollector()
    yield collector
    collector.print_report()


@pytest.fixture
def langgraph_workflow(workflow_factory):
    """Standard LangGraph workflow."""
    return workflow_factory.create_workflow("langgraph", "normal")


@pytest.fixture
def crewai_workflow(workflow_factory):
    """Standard CrewAI workflow."""
    return workflow_factory.create_workflow("crewai", "normal")


@pytest.fixture
def n8n_workflow(workflow_factory):
    """Standard n8n workflow."""
    return workflow_factory.create_workflow("n8n", "normal")


@pytest.fixture
def loop_detection(detection_factory):
    """Infinite loop detection."""
    return detection_factory.infinite_loop()


@pytest.fixture
def corruption_detection(detection_factory):
    """State corruption detection."""
    return detection_factory.state_corruption()


@pytest.fixture
def drift_detection(detection_factory):
    """Persona drift detection."""
    return detection_factory.persona_drift()
