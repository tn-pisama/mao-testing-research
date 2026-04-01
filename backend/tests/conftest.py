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

# Note: No custom event_loop fixture needed - pytest-asyncio auto mode handles it
# (configured in pytest.ini with asyncio_mode = auto)

pytest_plugins = [
    "tests.conftest_http",
    "tests.conftest_auth",
    "tests.conftest_workflows",
    "tests.conftest_datasets",
]

# Re-export make_low_quality_workflow for backward compatibility.
# Some test files import it directly from tests.conftest.
from tests.conftest_workflows import make_low_quality_workflow  # noqa: F401
