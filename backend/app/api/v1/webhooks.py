from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from svix.webhooks import Webhook, WebhookVerificationError

from app.config import get_settings
from app.storage.database import get_db
from app.storage.models import User, Tenant
from app.core.audit import log_auth_event

settings = get_settings()
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def create_user_from_clerk(db: AsyncSession, data: dict):
    clerk_user_id = data.get("id")
    email = data.get("email_addresses", [{}])[0].get("email_address", "")
    name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
    
    existing = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    if existing.scalar_one_or_none():
        return
    
    user = User(
        clerk_user_id=clerk_user_id,
        email=email,
        name=name or None,
        role="member"
    )
    db.add(user)
    await db.commit()


async def update_user_from_clerk(db: AsyncSession, data: dict):
    clerk_user_id = data.get("id")
    
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return
    
    email = data.get("email_addresses", [{}])[0].get("email_address", "")
    name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
    
    user.email = email
    user.name = name or None
    await db.commit()


async def delete_user_from_clerk(db: AsyncSession, data: dict):
    clerk_user_id = data.get("id")
    
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = result.scalar_one_or_none()
    
    if user:
        await db.delete(user)
        await db.commit()


async def add_user_to_tenant(db: AsyncSession, data: dict):
    clerk_user_id = data.get("public_user_data", {}).get("user_id")
    clerk_org_id = data.get("organization", {}).get("id")
    role = data.get("role", "member")
    
    user_result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = user_result.scalar_one_or_none()
    
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.clerk_org_id == clerk_org_id)
    )
    tenant = tenant_result.scalar_one_or_none()
    
    if user and tenant:
        user.tenant_id = tenant.id
        user.role = "owner" if role == "admin" else role
        await db.commit()


async def remove_user_from_tenant(db: AsyncSession, data: dict):
    clerk_user_id = data.get("public_user_data", {}).get("user_id")
    
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = result.scalar_one_or_none()
    
    if user:
        user.tenant_id = None
        user.role = "member"
        await db.commit()


@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not settings.clerk_webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    
    payload = await request.body()
    headers = {
        "svix-id": request.headers.get("svix-id"),
        "svix-timestamp": request.headers.get("svix-timestamp"),
        "svix-signature": request.headers.get("svix-signature"),
    }
    
    timestamp_str = headers.get("svix-timestamp")
    if timestamp_str:
        try:
            timestamp = datetime.fromtimestamp(int(timestamp_str))
            if datetime.utcnow() - timestamp > timedelta(minutes=5):
                raise HTTPException(status_code=400, detail="Webhook timestamp too old")
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid webhook timestamp")
    
    wh = Webhook(settings.clerk_webhook_secret)
    try:
        event = wh.verify(payload, headers)
    except WebhookVerificationError:
        client_ip = request.client.host if request.client else None
        await log_auth_event(
            db, None, None, "webhook_verification_failed",
            client_ip, None, False, "invalid_signature"
        )
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    event_type = event.get("type", "")
    data = event.get("data", {})
    
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
    
    client_ip = request.client.host if request.client else None
    await log_auth_event(
        db, None, None, f"webhook_{event_type}",
        client_ip, None, True, None
    )
    
    return {"status": "ok"}
