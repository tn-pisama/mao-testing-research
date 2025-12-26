# Clerk Authentication Integration Plan

## Overview

Add Clerk for user-level authentication while keeping existing API-key auth for SDK/CLI.

**Reviewed by**: backend-architect, security-reviewer, ux-researcher

## Current State

```
┌─────────────┐     API Key      ┌─────────────┐
│   SDK/CLI   │ ───────────────→ │   Backend   │
└─────────────┘                  │  (FastAPI)  │
                                 └─────────────┘
```

- Tenants have API keys (`mao_{token}`)
- API keys exchanged for JWTs
- No user-level auth
- No web dashboard

## Target State

```
┌─────────────┐     API Key      ┌─────────────┐
│   SDK/CLI   │ ───────────────→ │             │
└─────────────┘                  │   Backend   │
                                 │  (FastAPI)  │
┌─────────────┐   Clerk JWT      │             │
│ Web Dashboard│ ───────────────→ │             │
└─────────────┘                  └─────────────┘
        │                              │
        │ OAuth/SSO                    │ Verify JWT
        ↓                              ↓
┌─────────────────────────────────────────────────┐
│                    Clerk                         │
│  - User management                               │
│  - OAuth providers (Google, GitHub, etc.)        │
│  - Session management                            │
│  - Organization/tenant mapping                   │
└─────────────────────────────────────────────────┘
```

## Agent Review Summary

### Backend Architect Findings
- **CRITICAL**: API key lookup is O(n) - must add database index
- **CRITICAL**: Missing JWKS caching - every request hits Clerk
- **CRITICAL**: JWT confusion attack - need proper token discrimination
- **HIGH**: No circuit breaker for Clerk outages
- **Recommendation**: Add index, implement caching, circuit breaker

### Security Reviewer Findings
- **CRITICAL**: Default JWT secret "change-me-in-production"
- **CRITICAL**: Algorithm confusion attack vector (HS256/RS256)
- **HIGH**: CORS overly permissive (allow_methods=["*"])
- **HIGH**: Missing audit logging
- **MEDIUM**: Timing attack on API key verification
- **Recommendation**: Enforce secure secret, fix algorithm validation, add audit log

### UX Researcher Findings
- **P0**: No guidance on which auth method to use
- **P0**: Missing API key management in dashboard
- **P0**: Poor error messaging for auth failures
- **P1**: Team invitation flow missing
- **Recommendation**: Add developer journey docs, API key UI in dashboard

---

## Data Model

### Clerk → Backend Mapping

```
Clerk Organization ←→ MAO Tenant (1:1)
Clerk User ←→ MAO User (1:1, new table)
```

### New Database Tables

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_user_id VARCHAR(255) UNIQUE NOT NULL,
    tenant_id UUID REFERENCES tenants(id),
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'member',  -- 'owner', 'admin', 'member'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_clerk_id ON users(clerk_user_id);
CREATE INDEX idx_users_tenant ON users(tenant_id);

-- Audit log table (security requirement)
CREATE TABLE auth_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    error_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_auth_audit_tenant ON auth_audit(tenant_id);
CREATE INDEX idx_auth_audit_created ON auth_audit(created_at DESC);

-- Fix: Add missing index on tenants (backend-architect finding)
CREATE INDEX idx_tenants_api_key_prefix ON tenants(LEFT(api_key_hash, 10));
```

---

## Authentication Flows

### Flow 1: Web Dashboard (Clerk JWT)

```
1. User visits dashboard
2. Clerk handles login (OAuth, email/password)
3. Clerk issues JWT with claims:
   - sub: clerk_user_id
   - org_id: clerk_org_id (maps to tenant)
   - azp: authorized party (Clerk-specific)
4. Frontend sends JWT in Authorization header
5. Backend checks JWT header for algorithm (must be RS256)
6. Backend verifies JWT signature against cached JWKS
7. Backend looks up user, gets tenant_id
8. Request proceeds with tenant context
9. Audit log entry created
```

### Flow 2: SDK/CLI (API Key - unchanged)

```
1. Developer uses API key in SDK/CLI
2. Backend looks up tenant by API key prefix (indexed)
3. Constant-time comparison of hashed key
4. Issues internal JWT with tenant_id
5. Audit log entry created
```

### Flow 3: Webhook Sync

```
1. User created/updated in Clerk
2. Clerk sends webhook to /api/v1/webhooks/clerk
3. Verify Svix signature + timestamp (prevent replay)
4. Backend syncs user to local database
5. Audit log entry created
```

---

## Project Structure

```
backend/app/
├── core/
│   ├── auth.py          # Existing API-key auth (with fixes)
│   ├── clerk.py         # NEW: Clerk JWT verification + JWKS cache
│   ├── dependencies.py  # NEW: Unified auth dependencies
│   └── audit.py         # NEW: Audit logging
├── api/v1/
│   ├── auth.py          # Existing + API key management endpoints
│   ├── users.py         # NEW: User management
│   └── webhooks.py      # NEW: Clerk webhooks
├── storage/
│   └── models.py        # Add User, AuthAudit models
```

---

## Implementation

### 1. Dependencies

```toml
# pyproject.toml additions
clerk-backend-api = "^1.0.0"
pyjwt = "^2.8.0"
cryptography = "^41.0.0"
svix = "^1.0.0"
pybreaker = "^1.0.0"  # Circuit breaker (backend-architect recommendation)
```

### 2. Configuration (with security fixes)

```python
# config.py - UPDATED per security review
from pydantic import Field, field_validator

class Settings(BaseSettings):
    # Existing - FIXED: No default, must be set
    jwt_secret: str = Field(..., min_length=32, description="JWT signing secret (required)")
    
    # Clerk configuration
    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_webhook_secret: str = ""
    clerk_jwt_issuer: str = ""
    
    # JWKS cache settings (backend-architect recommendation)
    jwks_cache_ttl_seconds: int = 3600  # 1 hour
    
    # Rate limiting for auth (security recommendation)
    auth_rate_limit_requests: int = 10
    auth_rate_limit_window_seconds: int = 60
    
    @field_validator('jwt_secret')
    @classmethod
    def validate_jwt_secret(cls, v):
        if v == "change-me-in-production":
            raise ValueError("JWT secret must be changed from default")
        return v
```

### 3. Clerk JWT Verification (with JWKS caching + circuit breaker)

```python
# core/clerk.py - UPDATED with agent feedback
from datetime import datetime, timedelta
from jose import jwt, JWTError
from jose.exceptions import JWKError
from pybreaker import CircuitBreaker
import httpx
import asyncio

clerk_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)

class ClerkAuth:
    def __init__(self, issuer: str):
        self.issuer = issuer
        self._jwks_cache: dict | None = None
        self._jwks_expires: datetime | None = None
        self._cache_lock = asyncio.Lock()
        self._cache_ttl = timedelta(seconds=settings.jwks_cache_ttl_seconds)
    
    async def get_jwks(self) -> dict:
        """Fetch Clerk's public keys with caching (backend-architect fix)."""
        async with self._cache_lock:
            now = datetime.utcnow()
            if self._jwks_cache and self._jwks_expires and now < self._jwks_expires:
                return self._jwks_cache
            
            self._jwks_cache = await self._fetch_jwks()
            self._jwks_expires = now + self._cache_ttl
            return self._jwks_cache
    
    @clerk_breaker
    async def _fetch_jwks(self) -> dict:
        """Fetch JWKS with circuit breaker protection."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{self.issuer}/.well-known/jwks.json")
            resp.raise_for_status()
            return resp.json()
    
    async def verify_token(self, token: str) -> dict:
        """Verify Clerk JWT with algorithm validation (security fix)."""
        # SECURITY FIX: Validate algorithm before verification
        try:
            header = jwt.get_unverified_header(token)
        except JWTError:
            raise JWTError("Invalid JWT header")
        
        if header.get("alg") != "RS256":
            raise JWTError(f"Invalid algorithm: {header.get('alg')}. Expected RS256")
        
        jwks = await self.get_jwks()
        
        try:
            return jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],  # Only allow RS256
                issuer=self.issuer,
                options={"verify_aud": False}  # Clerk doesn't always set aud
            )
        except JWKError as e:
            raise JWTError(f"Key verification failed: {e}")
```

### 4. Unified Auth Dependency (with proper discrimination)

```python
# core/dependencies.py - UPDATED with agent feedback
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dataclasses import dataclass
from typing import Optional

security = HTTPBearer()

@dataclass
class AuthContext:
    tenant_id: str
    user_id: Optional[str] = None
    source: str = "api_key"  # "api_key" or "clerk"
    email: Optional[str] = None

async def get_current_user_or_tenant(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """
    Unified auth with proper JWT discrimination (backend-architect fix).
    """
    token = credentials.credentials
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")
    
    # BACKEND-ARCHITECT FIX: Check issuer before full verification
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        issuer = unverified.get("iss", "")
    except JWTError:
        issuer = ""
    
    auth_context = None
    error_code = None
    
    # Route based on issuer
    if issuer == settings.clerk_jwt_issuer:
        # Clerk JWT path
        try:
            claims = await clerk_auth.verify_token(token)
            user = await get_or_create_user(db, claims)
            auth_context = AuthContext(
                tenant_id=str(user.tenant_id),
                user_id=str(user.id),
                source="clerk",
                email=user.email
            )
        except JWTError as e:
            error_code = "clerk_jwt_invalid"
            await log_auth_event(db, None, None, "clerk_auth_failed", client_ip, user_agent, False, error_code)
            raise HTTPException(status_code=401, detail=f"Invalid Clerk token: {e}")
    else:
        # Internal API-key JWT path
        try:
            claims = decode_access_token(token)
            auth_context = AuthContext(tenant_id=claims.tenant_id, source="api_key")
        except HTTPException as e:
            error_code = "api_key_jwt_invalid"
            await log_auth_event(db, None, None, "api_key_auth_failed", client_ip, user_agent, False, error_code)
            raise
    
    # Audit log successful auth
    if auth_context:
        await log_auth_event(
            db, auth_context.tenant_id, auth_context.user_id,
            f"auth_success_{auth_context.source}", client_ip, user_agent, True, None
        )
    
    return auth_context
```

### 5. Audit Logging (security requirement)

```python
# core/audit.py - NEW per security review
from sqlalchemy.ext.asyncio import AsyncSession
from app.storage.models import AuthAudit
from uuid import UUID
from typing import Optional

async def log_auth_event(
    db: AsyncSession,
    tenant_id: Optional[str],
    user_id: Optional[str],
    action: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    success: bool,
    error_code: Optional[str] = None
):
    """Log authentication event for audit trail."""
    audit = AuthAudit(
        tenant_id=UUID(tenant_id) if tenant_id else None,
        user_id=UUID(user_id) if user_id else None,
        action=action,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,  # Truncate
        success=success,
        error_code=error_code
    )
    db.add(audit)
    await db.commit()
```

### 6. Webhook Handler (with replay protection)

```python
# api/v1/webhooks.py - UPDATED with security fixes
from fastapi import APIRouter, Request, HTTPException, Depends
from svix.webhooks import Webhook, WebhookVerificationError
from datetime import datetime, timedelta

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()
    headers = {
        "svix-id": request.headers.get("svix-id"),
        "svix-timestamp": request.headers.get("svix-timestamp"),
        "svix-signature": request.headers.get("svix-signature"),
    }
    
    # SECURITY FIX: Validate timestamp to prevent replay attacks
    timestamp_str = headers.get("svix-timestamp")
    if timestamp_str:
        try:
            timestamp = datetime.fromtimestamp(int(timestamp_str))
            if datetime.utcnow() - timestamp > timedelta(minutes=5):
                raise HTTPException(status_code=400, detail="Webhook timestamp too old")
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid webhook timestamp")
    
    # Verify webhook signature
    wh = Webhook(settings.clerk_webhook_secret)
    try:
        event = wh.verify(payload, headers)
    except WebhookVerificationError as e:
        await log_auth_event(db, None, None, "webhook_verification_failed", 
                            request.client.host, None, False, "invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    event_type = event["type"]
    data = event["data"]
    
    if event_type == "user.created":
        await create_user_from_clerk(db, data)
    elif event_type == "user.updated":
        await update_user_from_clerk(db, data)
    elif event_type == "user.deleted":
        await delete_user_from_clerk(db, data)
    elif event_type == "organizationMembership.created":
        await add_user_to_tenant(db, data)
    elif event_type == "organizationMembership.deleted":
        await remove_user_from_tenant(db, data)
    
    await log_auth_event(db, None, None, f"webhook_{event_type}", 
                        request.client.host, None, True, None)
    
    return {"status": "ok"}
```

### 7. API Key Management (UX requirement)

```python
# api/v1/auth.py - ADD endpoints for dashboard users to manage API keys
@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    auth: AuthContext = Depends(get_current_user_or_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List API keys for current tenant (dashboard users only)."""
    if auth.source != "clerk":
        raise HTTPException(status_code=403, detail="Dashboard login required")
    
    result = await db.execute(
        select(ApiKey).where(ApiKey.tenant_id == UUID(auth.tenant_id))
    )
    return result.scalars().all()

@router.post("/api-keys", response_model=ApiKeyCreateResponse)
async def create_api_key(
    request: ApiKeyCreateRequest,
    auth: AuthContext = Depends(get_current_user_or_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create new API key (dashboard users only, owner/admin role)."""
    if auth.source != "clerk":
        raise HTTPException(status_code=403, detail="Dashboard login required")
    
    user = await db.get(User, UUID(auth.user_id))
    if user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin role required")
    
    raw_key = f"mao_{secrets.token_urlsafe(32)}"
    
    api_key = ApiKey(
        tenant_id=UUID(auth.tenant_id),
        created_by=UUID(auth.user_id),
        name=request.name,
        key_hash=hash_api_key(raw_key),
        key_prefix=raw_key[:12],  # For display
    )
    db.add(api_key)
    await db.commit()
    
    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,  # Only shown once
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
    )

@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: UUID,
    auth: AuthContext = Depends(get_current_user_or_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key (dashboard users only, owner/admin role)."""
    # ... similar role check, then soft delete
```

### 8. CORS Fix (security requirement)

```python
# main.py - UPDATED with security fixes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://dashboard.mao-testing.com",  # Specific domain
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicit
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],  # Explicit
)
```

---

## Error Messages (UX requirement)

```python
# core/errors.py - Clear error messages for developers
AUTH_ERRORS = {
    "api_key_invalid": "Invalid API key. Check your key at https://dashboard.mao-testing.com/settings/api-keys",
    "api_key_expired": "API key has been revoked. Generate a new key in the dashboard.",
    "api_key_rate_limited": "Rate limit exceeded. Current limit: {limit} requests per minute.",
    "clerk_jwt_invalid": "Session expired. Please log in again.",
    "clerk_jwt_org_mismatch": "You don't have access to this organization. Contact your team admin.",
    "tenant_not_found": "Organization not found. Please contact support.",
}
```

---

## Environment Variables

```bash
# Required - will fail startup if not set
JWT_SECRET="$(openssl rand -hex 32)"  # Generate: openssl rand -hex 32

# Clerk Configuration
CLERK_PUBLISHABLE_KEY=pk_test_xxx
CLERK_SECRET_KEY=sk_test_xxx
CLERK_WEBHOOK_SECRET=whsec_xxx
CLERK_JWT_ISSUER=https://your-app.clerk.accounts.dev

# Rate limiting
AUTH_RATE_LIMIT_REQUESTS=10
AUTH_RATE_LIMIT_WINDOW_SECONDS=60
```

---

## Testing Strategy

1. **Unit Tests**: Mock Clerk SDK, test JWT verification, algorithm validation
2. **Integration Tests**: Test webhook handling with signed payloads, replay rejection
3. **Security Tests**: Algorithm confusion, timing attacks, tenant isolation
4. **E2E Tests**: Full auth flow with Clerk test keys

---

## Implementation Checklist

### Phase 1: Security Fixes (CRITICAL)
- [ ] Remove default JWT secret, require env var
- [ ] Add algorithm validation in JWT verification
- [ ] Restrict CORS to specific methods/headers
- [ ] Add database index on tenants.api_key_hash

### Phase 2: Clerk Integration
- [ ] Add Clerk configuration
- [ ] Add User and AuthAudit models
- [ ] Implement ClerkAuth with JWKS caching
- [ ] Implement unified auth dependency
- [ ] Add webhook handler with replay protection

### Phase 3: API Key Management (UX)
- [ ] Add list/create/revoke API key endpoints
- [ ] Role-based access (owner/admin only)

### Phase 4: Audit & Monitoring
- [ ] Audit logging on all auth events
- [ ] Circuit breaker for Clerk API
- [ ] Prometheus metrics for auth

---

## Success Criteria

- [ ] Clerk JWTs accepted by API (RS256 only)
- [ ] API-key auth still works (backward compatible)
- [ ] Webhooks sync users to database
- [ ] User → Tenant mapping works
- [ ] Audit log captures all auth events
- [ ] No CRITICAL/HIGH security vulnerabilities
- [ ] Clear error messages for developers
- [ ] Dashboard users can manage API keys
