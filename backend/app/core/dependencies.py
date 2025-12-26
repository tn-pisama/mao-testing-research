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
from app.core.audit import log_auth_event

settings = get_settings()
security = HTTPBearer()


@dataclass
class AuthContext:
    tenant_id: str
    user_id: Optional[str] = None
    source: str = "api_key"
    email: Optional[str] = None


async def get_or_create_user(db: AsyncSession, claims: dict) -> User:
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


async def get_current_user_or_tenant(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    token = credentials.credentials
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")
    
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        issuer = unverified.get("iss", "")
    except JWTError:
        issuer = ""
    
    clerk_auth = get_clerk_auth()
    
    if clerk_auth and issuer == settings.clerk_jwt_issuer:
        try:
            claims = await clerk_auth.verify_token(token)
            user = await get_or_create_user(db, claims)
            
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
    else:
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
