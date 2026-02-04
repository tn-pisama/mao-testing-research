from datetime import datetime, timedelta
from typing import Optional
import asyncio
import httpx
from jose import jwt, JWTError
from jose.exceptions import JWKError
from pybreaker import CircuitBreaker

from app.config import get_settings

settings = get_settings()

clerk_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)


class ClerkAuth:
    def __init__(self, issuer: str):
        self.issuer = issuer
        self._jwks_cache: Optional[dict] = None
        self._jwks_expires: Optional[datetime] = None
        self._cache_lock = asyncio.Lock()
        self._cache_ttl = timedelta(seconds=settings.jwks_cache_ttl_seconds)
    
    async def get_jwks(self) -> dict:
        async with self._cache_lock:
            now = datetime.utcnow()
            if self._jwks_cache and self._jwks_expires and now < self._jwks_expires:
                return self._jwks_cache
            
            self._jwks_cache = await self._fetch_jwks()
            self._jwks_expires = now + self._cache_ttl
            return self._jwks_cache
    
    @clerk_breaker
    async def _fetch_jwks(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{self.issuer}/.well-known/jwks.json")
            resp.raise_for_status()
            return resp.json()
    
    async def verify_token(self, token: str) -> dict:
        try:
            header = jwt.get_unverified_header(token)
        except JWTError:
            raise JWTError("Invalid JWT header")
        
        if header.get("alg") != "RS256":
            raise JWTError(f"Invalid algorithm: {header.get('alg')}. Expected RS256")
        
        jwks = await self.get_jwks()
        
        try:
            # Conditionally verify audience if configured
            decode_options = {"verify_aud": bool(settings.clerk_jwt_audience)}
            return jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=settings.clerk_jwt_audience if settings.clerk_jwt_audience else None,
                options=decode_options
            )
        except JWKError as e:
            raise JWTError(f"Key verification failed: {e}")


clerk_auth: Optional[ClerkAuth] = None


def get_clerk_auth() -> Optional[ClerkAuth]:
    global clerk_auth
    if clerk_auth is None and settings.clerk_jwt_issuer:
        clerk_auth = ClerkAuth(settings.clerk_jwt_issuer)
    return clerk_auth
