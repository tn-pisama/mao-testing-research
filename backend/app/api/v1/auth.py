from typing import List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets

from app.storage.database import get_db
from app.storage.models import Tenant, ApiKey, User
from app.core.auth import hash_api_key, verify_api_key, create_access_token
from app.core.dependencies import AuthContext, get_current_user_or_tenant
from app.core.rate_limit import rate_limiter
from app.api.v1.schemas import (
    TenantCreate, TenantResponse, TokenRequest, TokenResponse,
    ApiKeyCreateRequest, ApiKeyResponse, ApiKeyCreateResponse, UserResponse
)

router = APIRouter(prefix="/auth", tags=["auth"])

AUTH_RATE_LIMIT = 10
AUTH_RATE_WINDOW = 60


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreate,
    db: AsyncSession = Depends(get_db),
):
    api_key = f"mao_{secrets.token_urlsafe(32)}"
    api_key_hash = hash_api_key(api_key)
    
    tenant = Tenant(
        name=request.name,
        api_key_hash=api_key_hash,
    )
    
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        api_key=api_key,
        created_at=tenant.created_at,
    )


@router.post("/token", response_model=TokenResponse)
async def get_token(
    request: TokenRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    client_ip = http_request.client.host if http_request.client else "unknown"
    rate_key = f"auth_rate_limit:{client_ip}"
    allowed = await rate_limiter.check_rate_limit(rate_key, AUTH_RATE_LIMIT, AUTH_RATE_WINDOW)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again later."
        )
    key_prefix = request.api_key[:12] if len(request.api_key) >= 12 else ""
    
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == key_prefix,
            ApiKey.revoked_at.is_(None)
        )
    )
    api_key_record = result.scalar_one_or_none()
    
    if api_key_record and verify_api_key(request.api_key, api_key_record.key_hash):
        access_token = create_access_token(str(api_key_record.tenant_id))
        return TokenResponse(access_token=access_token)
    
    result = await db.execute(select(Tenant))
    tenants = result.scalars().all()
    
    for tenant in tenants:
        if verify_api_key(request.api_key, tenant.api_key_hash):
            access_token = create_access_token(str(tenant.id))
            return TokenResponse(access_token=access_token)
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key. Check your key at https://dashboard.mao-testing.com/settings/api-keys",
    )


@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    auth: AuthContext = Depends(get_current_user_or_tenant),
    db: AsyncSession = Depends(get_db),
):
    if auth.source != "clerk":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dashboard login required to manage API keys"
        )
    
    result = await db.execute(
        select(ApiKey).where(ApiKey.tenant_id == UUID(auth.tenant_id))
    )
    api_keys = result.scalars().all()
    
    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            created_at=k.created_at,
            revoked_at=k.revoked_at,
        )
        for k in api_keys
    ]


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: ApiKeyCreateRequest,
    auth: AuthContext = Depends(get_current_user_or_tenant),
    db: AsyncSession = Depends(get_db),
):
    if auth.source != "clerk":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dashboard login required to create API keys"
        )
    
    user_result = await db.execute(
        select(User).where(User.id == UUID(auth.user_id))
    )
    user = user_result.scalar_one_or_none()
    
    if not user or user.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to create API keys"
        )
    
    raw_key = f"mao_{secrets.token_urlsafe(32)}"
    
    api_key = ApiKey(
        tenant_id=UUID(auth.tenant_id),
        created_by=UUID(auth.user_id),
        name=request.name,
        key_hash=hash_api_key(raw_key),
        key_prefix=raw_key[:12],
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    
    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
    )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    auth: AuthContext = Depends(get_current_user_or_tenant),
    db: AsyncSession = Depends(get_db),
):
    if auth.source != "clerk":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dashboard login required to revoke API keys"
        )
    
    user_result = await db.execute(
        select(User).where(User.id == UUID(auth.user_id))
    )
    user = user_result.scalar_one_or_none()
    
    if not user or user.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to revoke API keys"
        )
    
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.tenant_id == UUID(auth.tenant_id)
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key.revoked_at = datetime.utcnow()
    await db.commit()


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    auth: AuthContext = Depends(get_current_user_or_tenant),
    db: AsyncSession = Depends(get_db),
):
    if auth.source != "clerk" or not auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dashboard login required"
        )
    
    result = await db.execute(
        select(User).where(User.id == UUID(auth.user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        created_at=user.created_at,
    )
