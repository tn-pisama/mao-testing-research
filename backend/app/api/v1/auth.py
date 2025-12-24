from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets

from app.storage.database import get_db
from app.storage.models import Tenant
from app.core.auth import hash_api_key, verify_api_key, create_access_token
from app.api.v1.schemas import TenantCreate, TenantResponse, TokenRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


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
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tenant))
    tenants = result.scalars().all()
    
    for tenant in tenants:
        if verify_api_key(request.api_key, tenant.api_key_hash):
            access_token = create_access_token(str(tenant.id))
            return TokenResponse(access_token=access_token)
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )
