"""Tests for Google OAuth token verification (google_auth.py).

Covers: token verification, audience validation, expiry, HTTP errors,
singleton factory, email_verified parsing.
"""
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from jose import JWTError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token_info(
    sub="google-uid-123",
    email="user@example.com",
    email_verified="true",
    name="Test User",
    picture="https://photo.example.com/pic.jpg",
    aud="test-client-id",
    exp=None,
):
    """Build a Google tokeninfo response dict."""
    info = {
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "picture": picture,
        "aud": aud,
    }
    if exp is not None:
        info["exp"] = str(exp)
    else:
        # Default: expires 1 hour from now
        info["exp"] = str(int(time.time()) + 3600)
    return info


def _mock_httpx_response(json_data, status_code=200, text=""):
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = text or str(json_data)
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGoogleAuthVerifyToken:
    """Tests for GoogleAuth.verify_token()."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        """Reset the module-level singleton before each test."""
        import app.core.google_auth as mod
        mod.google_auth = None
        yield
        mod.google_auth = None

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.google_client_id = "test-client-id"
        return settings

    def _build_auth(self, mock_settings):
        """Create a GoogleAuth instance with patched settings."""
        with patch("app.core.google_auth.settings", mock_settings):
            from app.core.google_auth import GoogleAuth
            return GoogleAuth()

    # 1. Successful verification -----------------------------------------
    @pytest.mark.asyncio
    async def test_verify_token_success(self, mock_settings):
        token_info = _make_token_info()
        response = _mock_httpx_response(token_info)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.google_auth.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            from app.core.google_auth import GoogleAuth
            auth = GoogleAuth()
            # Call the unwrapped function to bypass circuit breaker
            result = await auth.verify_token.__wrapped__(auth, "valid-token")

        assert result["sub"] == "google-uid-123"
        assert result["email"] == "user@example.com"
        assert result["email_verified"] is True
        assert result["name"] == "Test User"
        assert result["picture"] == "https://photo.example.com/pic.jpg"

    # 2. Wrong audience ---------------------------------------------------
    @pytest.mark.asyncio
    async def test_verify_token_wrong_audience(self, mock_settings):
        token_info = _make_token_info(aud="wrong-client-id")
        response = _mock_httpx_response(token_info)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.google_auth.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            from app.core.google_auth import GoogleAuth
            auth = GoogleAuth()
            with pytest.raises(JWTError, match="audience"):
                await auth.verify_token.__wrapped__(auth, "bad-aud-token")

    # 3. Expired token ----------------------------------------------------
    @pytest.mark.asyncio
    async def test_verify_token_expired(self, mock_settings):
        expired_exp = int(time.time()) - 3600  # 1 hour ago
        token_info = _make_token_info(exp=expired_exp)
        response = _mock_httpx_response(token_info)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.google_auth.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            from app.core.google_auth import GoogleAuth
            auth = GoogleAuth()
            with pytest.raises(JWTError, match="expired"):
                await auth.verify_token.__wrapped__(auth, "expired-token")

    # 4. HTTP error from Google -------------------------------------------
    @pytest.mark.asyncio
    async def test_verify_token_http_error(self, mock_settings):
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.google_auth.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            from app.core.google_auth import GoogleAuth
            auth = GoogleAuth()
            with pytest.raises(JWTError, match="Failed to verify"):
                await auth.verify_token.__wrapped__(auth, "fail-token")

    # 5. Non-200 status code ----------------------------------------------
    @pytest.mark.asyncio
    async def test_verify_token_non_200_status(self, mock_settings):
        response = _mock_httpx_response({}, status_code=400, text="Bad Request")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.google_auth.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            from app.core.google_auth import GoogleAuth
            auth = GoogleAuth()
            with pytest.raises(JWTError, match="verification failed"):
                await auth.verify_token.__wrapped__(auth, "bad-status-token")

    # 6. Singleton – same instance returned twice -------------------------
    def test_get_google_auth_singleton(self, mock_settings):
        with patch("app.core.google_auth.settings", mock_settings):
            from app.core.google_auth import get_google_auth
            first = get_google_auth()
            second = get_google_auth()
            assert first is second

    # 7. Singleton – creates new instance on first call -------------------
    def test_get_google_auth_creates_instance(self, mock_settings):
        import app.core.google_auth as mod
        assert mod.google_auth is None
        with patch("app.core.google_auth.settings", mock_settings):
            instance = mod.get_google_auth()
            assert instance is not None
            assert isinstance(instance, mod.GoogleAuth)

    # 8. Missing email field still returns result -------------------------
    @pytest.mark.asyncio
    async def test_verify_token_missing_email(self, mock_settings):
        token_info = _make_token_info()
        del token_info["email"]
        response = _mock_httpx_response(token_info)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.google_auth.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            from app.core.google_auth import GoogleAuth
            auth = GoogleAuth()
            result = await auth.verify_token.__wrapped__(auth, "no-email-token")

        assert result["email"] is None
        assert result["sub"] == "google-uid-123"

    # 9. email_verified "true" string → True boolean ----------------------
    @pytest.mark.asyncio
    async def test_email_verified_true_string(self, mock_settings):
        token_info = _make_token_info(email_verified="true")
        response = _mock_httpx_response(token_info)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.google_auth.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            from app.core.google_auth import GoogleAuth
            auth = GoogleAuth()
            result = await auth.verify_token.__wrapped__(auth, "verified-token")

        assert result["email_verified"] is True

    # 10. email_verified non-"true" → False --------------------------------
    @pytest.mark.asyncio
    async def test_email_verified_false_values(self, mock_settings):
        for value in ["false", "0", "", "FALSE", None]:
            token_info = _make_token_info(email_verified=value)
            response = _mock_httpx_response(token_info)

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            with patch("app.core.google_auth.settings", mock_settings), \
                 patch("httpx.AsyncClient", return_value=mock_client):
                from app.core.google_auth import GoogleAuth
                auth = GoogleAuth()
                result = await auth.verify_token.__wrapped__(auth, "unverified-token")

            assert result["email_verified"] is False, (
                f"Expected False for email_verified={value!r}"
            )
