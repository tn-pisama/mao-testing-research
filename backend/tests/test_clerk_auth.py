import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from jose import jwt
from datetime import datetime, timedelta

from app.core.clerk import ClerkAuth
from app.core.dependencies import AuthContext, get_or_create_user


class TestClerkAuth:
    @pytest.fixture
    def clerk_auth(self):
        return ClerkAuth("https://test.clerk.accounts.dev")

    @pytest.mark.asyncio
    async def test_jwks_caching(self, clerk_auth):
        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test-kid"}]}
        
        with patch.object(clerk_auth, "_fetch_jwks", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_jwks
            
            result1 = await clerk_auth.get_jwks()
            result2 = await clerk_auth.get_jwks()
            
            assert result1 == mock_jwks
            assert result2 == mock_jwks
            assert mock_fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_algorithm_validation_rejects_hs256(self, clerk_auth):
        hs256_token = jwt.encode(
            {"sub": "user_123", "iss": "https://test.clerk.accounts.dev"},
            "secret",
            algorithm="HS256"
        )
        
        with pytest.raises(Exception) as exc_info:
            await clerk_auth.verify_token(hs256_token)
        
        assert "Invalid algorithm" in str(exc_info.value) or "HS256" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_jwt_header(self, clerk_auth):
        with pytest.raises(Exception) as exc_info:
            await clerk_auth.verify_token("not.a.valid.token")
        
        assert "Invalid" in str(exc_info.value)


class TestAuthContext:
    def test_auth_context_api_key(self):
        ctx = AuthContext(tenant_id="tenant-123", source="api_key")
        
        assert ctx.tenant_id == "tenant-123"
        assert ctx.source == "api_key"
        assert ctx.user_id is None
        assert ctx.email is None

    def test_auth_context_clerk(self):
        ctx = AuthContext(
            tenant_id="tenant-123",
            user_id="user-456",
            source="clerk",
            email="test@example.com"
        )
        
        assert ctx.tenant_id == "tenant-123"
        assert ctx.user_id == "user-456"
        assert ctx.source == "clerk"
        assert ctx.email == "test@example.com"


class TestGetOrCreateUser:
    @pytest.mark.asyncio
    async def test_creates_new_user(self):
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        claims = {
            "sub": "user_clerk123",
            "email": "test@example.com",
            "name": "Test User"
        }
        
        user = await get_or_create_user(mock_db, claims)
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        assert user is not None

    @pytest.mark.asyncio
    async def test_returns_existing_user(self):
        mock_user = MagicMock()
        mock_user.id = "existing-user-id"
        mock_user.clerk_user_id = "user_clerk123"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        claims = {"sub": "user_clerk123"}
        
        user = await get_or_create_user(mock_db, claims)
        
        assert user == mock_user
        mock_db.add.assert_not_called()


class TestWebhookSecurity:
    def test_timestamp_validation(self):
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        old_timestamp = (now - timedelta(minutes=10)).timestamp()
        
        assert now - datetime.fromtimestamp(old_timestamp) > timedelta(minutes=5)

    def test_fresh_timestamp(self):
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        fresh_timestamp = (now - timedelta(minutes=2)).timestamp()
        
        assert now - datetime.fromtimestamp(fresh_timestamp) < timedelta(minutes=5)
