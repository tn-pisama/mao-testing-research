from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.storage.database import get_db
from app.storage.models import User, Tenant
from app.core.auth import decode_access_token
from app.core.clerk import get_clerk_auth
from app.core.google_auth import get_google_auth
from app.core.audit import log_auth_event

settings = get_settings()
security = HTTPBearer()


@dataclass
class AuthContext:
    tenant_id: str
    user_id: Optional[str] = None
    source: str = "api_key"
    email: Optional[str] = None


async def get_or_create_user_from_clerk(db: AsyncSession, claims: dict) -> User:
    """Get or create user from Clerk JWT claims."""
    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Missing user ID in token")

    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = result.scalar_one_or_none()

    if user:
        return user

    org_id = claims.get("org_id")
    tenant = None
    if org_id:
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.clerk_org_id == org_id)
        )
        tenant = tenant_result.scalar_one_or_none()

    user = User(
        clerk_user_id=clerk_user_id,
        tenant_id=tenant.id if tenant else None,
        email=claims.get("email", ""),
        name=claims.get("name"),
        role="member"
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def get_or_create_user_from_google(db: AsyncSession, claims: dict) -> User:
    """Get or create user from Google OAuth claims."""
    google_user_id = claims.get("sub")
    if not google_user_id:
        raise HTTPException(status_code=401, detail="Missing user ID in Google token")

    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Missing email in Google token")

    # Email whitelist check
    if settings.allowed_emails:
        allowed = [e.strip() for e in settings.allowed_emails.split(",") if e.strip()]
        if allowed and email not in allowed:
            raise HTTPException(status_code=403, detail="Email not authorized. Contact admin for access.")

    # First try to find by google_user_id (new way)
    result = await db.execute(
        select(User).where(User.google_user_id == google_user_id)
    )
    user = result.scalar_one_or_none()

    # If not found, try to find by email (for migration from Clerk)
    if not user:
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        # If found by email, update with Google ID
        if user:
            user.google_user_id = google_user_id
            await db.commit()
            await db.refresh(user)
            return user

    # If still not found, create new user
    if not user:
        import secrets
        from app.billing.constants import get_plan_defaults
        from app.core.webhook_security import hash_api_key

        # Create a default tenant with plan defaults + auto-generated API key
        raw_key = f"mao_{secrets.token_urlsafe(32)}"
        tenant = Tenant(
            name=f"{email}'s Organization",
            api_key_hash=hash_api_key(raw_key),
            settings=get_plan_defaults("free"),
        )
        db.add(tenant)
        await db.flush()

        # Store the raw key temporarily on the user object for the auth response
        # (one-time display — not persisted after this response)
        tenant._initial_api_key = raw_key

        user = User(
            google_user_id=google_user_id,
            tenant_id=tenant.id,
            email=email,
            name=claims.get("name"),
            role="owner"
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


async def get_current_user_or_tenant(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    token = credentials.credentials
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")

    try:
        unverified = jwt.decode(token, "", options={"verify_signature": False})
        issuer = unverified.get("iss", "")
    except JWTError:
        issuer = ""

    # Check for Google OAuth token
    if issuer in ["https://accounts.google.com", "accounts.google.com"]:
        try:
            google_auth = get_google_auth()
            claims = await google_auth.verify_token(token)
            user = await get_or_create_user_from_google(db, claims)

            if not user.tenant_id:
                await log_auth_event(
                    db, None, str(user.id), "google_auth_no_tenant",
                    client_ip, user_agent, False, "no_tenant"
                )
                raise HTTPException(
                    status_code=403,
                    detail="User not associated with any organization"
                )

            await log_auth_event(
                db, str(user.tenant_id), str(user.id), "auth_success_google",
                client_ip, user_agent, True, None
            )

            return AuthContext(
                tenant_id=str(user.tenant_id),
                user_id=str(user.id),
                source="google",
                email=user.email
            )
        except JWTError as e:
            await log_auth_event(
                db, None, None, "google_auth_failed",
                client_ip, user_agent, False, "google_jwt_invalid"
            )
            raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")

    # Check for Clerk token (backward compatibility)
    clerk_auth = get_clerk_auth()
    if clerk_auth and issuer == settings.clerk_jwt_issuer:
        try:
            claims = await clerk_auth.verify_token(token)
            user = await get_or_create_user_from_clerk(db, claims)

            if not user.tenant_id:
                await log_auth_event(
                    db, None, str(user.id), "clerk_auth_no_tenant",
                    client_ip, user_agent, False, "no_tenant"
                )
                raise HTTPException(
                    status_code=403,
                    detail="User not associated with any organization"
                )

            await log_auth_event(
                db, str(user.tenant_id), str(user.id), "auth_success_clerk",
                client_ip, user_agent, True, None
            )

            return AuthContext(
                tenant_id=str(user.tenant_id),
                user_id=str(user.id),
                source="clerk",
                email=user.email
            )
        except JWTError as e:
            await log_auth_event(
                db, None, None, "clerk_auth_failed",
                client_ip, user_agent, False, "clerk_jwt_invalid"
            )
            raise HTTPException(status_code=401, detail=f"Invalid Clerk token: {e}")

    # Fall back to API key authentication
    try:
        claims = decode_access_token(token)

        await log_auth_event(
            db, claims.tenant_id, None, "auth_success_api_key",
            client_ip, user_agent, True, None
        )

        return AuthContext(tenant_id=claims.tenant_id, source="api_key")
    except HTTPException as e:
        await log_auth_event(
            db, None, None, "api_key_auth_failed",
            client_ip, user_agent, False, "api_key_jwt_invalid"
        )
        raise
