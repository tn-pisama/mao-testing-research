"""Tests for the feature gate decorator and utilities (feature_gate.py).

Covers: require_enterprise decorator (async + sync, enabled + disabled),
is_feature_enabled, is_enterprise_enabled, FeatureNotEnabledError.
"""
import pytest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.core.feature_gate import (
    require_enterprise,
    is_feature_enabled,
    is_enterprise_enabled,
    FeatureNotEnabledError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_settings(enterprise_enabled: bool = False, **feature_flags):
    """Build a mock settings object with controlled feature flags."""
    features = MagicMock()
    features.enterprise_enabled = enterprise_enabled

    def _is_enabled(feature: str) -> bool:
        if not enterprise_enabled:
            return False
        return feature_flags.get(feature, False)

    features.is_enabled = MagicMock(side_effect=_is_enabled)

    settings = MagicMock()
    settings.features = features
    return settings


# ---------------------------------------------------------------------------
# require_enterprise decorator
# ---------------------------------------------------------------------------

class TestRequireEnterprise:

    # 1. Blocks disabled feature → 402 -----------------------------------
    def test_blocks_disabled_feature(self):
        settings = _mock_settings(enterprise_enabled=False)

        with patch("app.core.feature_gate.get_settings", return_value=settings):
            @require_enterprise("ml_detection")
            def my_sync_func():
                return "should not reach"

            with pytest.raises(HTTPException) as exc_info:
                my_sync_func()

            assert exc_info.value.status_code == 402

    # 2. Allows enabled feature ------------------------------------------
    def test_allows_enabled_feature(self):
        settings = _mock_settings(enterprise_enabled=True, ml_detection=True)

        with patch("app.core.feature_gate.get_settings", return_value=settings):
            @require_enterprise("ml_detection")
            def my_func():
                return "ok"

            result = my_func()
            assert result == "ok"

    # 3. Works with async function ----------------------------------------
    @pytest.mark.asyncio
    async def test_works_with_async_enabled(self):
        settings = _mock_settings(enterprise_enabled=True, chaos_engineering=True)

        with patch("app.core.feature_gate.get_settings", return_value=settings):
            @require_enterprise("chaos_engineering")
            async def my_async_func():
                return "async-ok"

            result = await my_async_func()
            assert result == "async-ok"

    # 4. Async function blocked when disabled -----------------------------
    @pytest.mark.asyncio
    async def test_async_blocked_when_disabled(self):
        settings = _mock_settings(enterprise_enabled=False)

        with patch("app.core.feature_gate.get_settings", return_value=settings):
            @require_enterprise("chaos_engineering")
            async def my_async_func():
                return "should not reach"

            with pytest.raises(HTTPException) as exc_info:
                await my_async_func()

            assert exc_info.value.status_code == 402


# ---------------------------------------------------------------------------
# is_feature_enabled
# ---------------------------------------------------------------------------

class TestIsFeatureEnabled:

    # 5. Returns False when enterprise is off ----------------------------
    def test_returns_false_when_enterprise_off(self):
        settings = _mock_settings(enterprise_enabled=False, ml_detection=True)

        with patch("app.core.feature_gate.get_settings", return_value=settings):
            assert is_feature_enabled("ml_detection") is False

    # 6. Returns True when enterprise + flag on --------------------------
    def test_returns_true_when_enabled(self):
        settings = _mock_settings(enterprise_enabled=True, ml_detection=True)

        with patch("app.core.feature_gate.get_settings", return_value=settings):
            assert is_feature_enabled("ml_detection") is True


# ---------------------------------------------------------------------------
# is_enterprise_enabled
# ---------------------------------------------------------------------------

class TestIsEnterpriseEnabled:

    # 7. Returns False by default ----------------------------------------
    def test_returns_false_by_default(self):
        settings = _mock_settings(enterprise_enabled=False)

        with patch("app.core.feature_gate.get_settings", return_value=settings):
            assert is_enterprise_enabled() is False

    # 8. Returns True when set -------------------------------------------
    def test_returns_true_when_set(self):
        settings = _mock_settings(enterprise_enabled=True)

        with patch("app.core.feature_gate.get_settings", return_value=settings):
            assert is_enterprise_enabled() is True


# ---------------------------------------------------------------------------
# FeatureNotEnabledError
# ---------------------------------------------------------------------------

class TestFeatureNotEnabledError:

    # 9. Has correct status code and detail structure --------------------
    def test_status_code_and_detail(self):
        error = FeatureNotEnabledError("ml_detection")

        assert error.status_code == 402
        assert error.detail["error"] == "feature_not_enabled"
        assert error.detail["feature"] == "ml_detection"
        assert "enterprise" in error.detail["message"].lower()
        assert error.detail["upgrade_url"] == "https://pisama.io/pricing"

    def test_inherits_from_http_exception(self):
        error = FeatureNotEnabledError("chaos_engineering")
        assert isinstance(error, HTTPException)
