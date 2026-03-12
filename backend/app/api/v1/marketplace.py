"""AWS Marketplace API endpoints.

REST API for AWS Marketplace integration:
- Customer subscription handling (registration token resolution)
- Usage reporting dashboard
- SNS webhook processing for subscription lifecycle events
"""

import hashlib
import hmac
import json
import logging
import secrets
from typing import Optional

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.auth import get_current_tenant
from app.storage.database import get_db
from app.storage.models import Tenant
from app.billing.marketplace import (
    MarketplaceConfig,
    MarketplaceCustomer,
    MarketplaceDimension,
    MarketplaceMeteringService,
    get_marketplace_config,
    get_marketplace_service,
)
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


# --- Request/Response schemas ---


class SubscribeRequest(BaseModel):
    """Request from AWS Marketplace subscription redirect."""

    registration_token: str = Field(
        ..., description="AWS Marketplace registration token"
    )


class SubscribeResponse(BaseModel):
    """Response after successful marketplace subscription."""

    tenant_id: str
    aws_customer_id: str
    tier: str
    message: str


class UsageSummaryResponse(BaseModel):
    """Usage summary for marketplace billing dashboard."""

    tenant_id: str
    period_days: int
    spans_ingested: int = Field(
        0, description="Total span units (per 1000 spans)"
    )
    detections_generated: int = Field(
        0, description="Total detection units (per 100 detections)"
    )
    fixes_applied: int = Field(0, description="Total fix actions")


class WebhookResponse(BaseModel):
    """Response for webhook processing."""

    status: str
    message: str = ""


# --- Helper to check marketplace enabled ---


def _require_marketplace_enabled() -> MarketplaceConfig:
    """Check that marketplace integration is enabled.

    Returns:
        MarketplaceConfig if enabled.

    Raises:
        HTTPException 404 if marketplace is not enabled.
    """
    config = get_marketplace_config()
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AWS Marketplace integration is not enabled",
        )
    return config


# --- Endpoints ---


@router.post("/subscribe", response_model=SubscribeResponse)
async def marketplace_subscribe(
    request: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Handle AWS Marketplace subscription redirect.

    Called when a customer clicks "Subscribe" on the AWS Marketplace listing
    and is redirected to the PISAMA fulfillment URL with a registration token.

    Flow:
    1. Resolves customer via AWS ResolveCustomer API
    2. Checks entitlement to determine tier
    3. Creates a new PISAMA tenant (or links to existing one)
    4. Stores the AWS customer <-> tenant mapping
    5. Returns tenant information for dashboard redirect

    Args:
        request: SubscribeRequest with the registration_token from AWS.
        db: Database session.

    Returns:
        SubscribeResponse with tenant_id, tier, and welcome message.

    Raises:
        HTTPException 400: If the registration token is invalid.
        HTTPException 404: If marketplace integration is not enabled.
        HTTPException 500: If tenant creation or AWS API calls fail.
    """
    _require_marketplace_enabled()
    service = get_marketplace_service()

    # Step 1: Resolve customer from registration token
    try:
        customer = await service.resolve_customer(request.registration_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to resolve marketplace customer: {e}",
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Step 2: Check entitlement to determine tier
    try:
        entitlement = await service.check_entitlement(customer.aws_customer_id)
    except Exception as e:
        logger.error("Failed to check entitlement: %s", e)
        entitlement = {"is_active": True, "tier": "startup", "dimensions": {}}

    tier = entitlement.get("tier", "startup")

    # Step 3: Find or create tenant
    # Check if there is already a tenant linked to this AWS customer
    result = await db.execute(
        select(Tenant).where(
            Tenant.settings["aws_marketplace_customer_id"].as_string()
            == customer.aws_customer_id
        )
    )
    tenant = result.scalar_one_or_none()

    if tenant:
        # Existing tenant - update tier if changed
        tenant_id = str(tenant.id)
        if tenant.plan != tier:
            await db.execute(
                update(Tenant)
                .where(Tenant.id == tenant.id)
                .values(plan=tier)
            )
            await db.commit()
            logger.info(
                "Updated existing marketplace tenant %s to tier %s",
                tenant_id,
                tier,
            )
    else:
        # Create new tenant
        tenant_name = f"AWS-{customer.aws_customer_id[:8]}"
        new_tenant = Tenant(
            name=tenant_name,
            plan=tier,
            subscription_status="active",
            settings={
                "aws_marketplace_customer_id": customer.aws_customer_id,
                "aws_marketplace_product_code": customer.product_code,
                "source": "aws_marketplace",
            },
        )
        db.add(new_tenant)
        await db.commit()
        await db.refresh(new_tenant)
        tenant_id = str(new_tenant.id)
        logger.info(
            "Created new marketplace tenant %s for AWS customer %s",
            tenant_id,
            customer.aws_customer_id,
        )

    # Step 4: Store customer <-> tenant mapping in Redis for metering
    await service.store_customer_mapping(tenant_id, customer.aws_customer_id)

    return SubscribeResponse(
        tenant_id=tenant_id,
        aws_customer_id=customer.aws_customer_id,
        tier=tier,
        message=f"Welcome to PISAMA! Your {tier} plan is now active.",
    )


@router.get("/usage", response_model=UsageSummaryResponse)
async def get_usage(
    days: int = Query(default=30, ge=1, le=365, description="Days to look back"),
    tenant_id: str = Depends(get_current_tenant),
):
    """Get current usage summary for the authenticated tenant.

    Returns usage totals across all marketplace billing dimensions
    for the specified period.

    Args:
        days: Number of days to look back (default 30, max 365).
        tenant_id: Current tenant from auth context.

    Returns:
        UsageSummaryResponse with per-dimension totals.

    Raises:
        HTTPException 404: If marketplace integration is not enabled.
        HTTPException 500: If usage data cannot be retrieved.
    """
    _require_marketplace_enabled()
    service = get_marketplace_service()

    try:
        summary = await service.get_usage_summary(tenant_id, days=days)
    except Exception as e:
        logger.error("Failed to get usage summary for tenant %s: %s", tenant_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage data",
        )

    return UsageSummaryResponse(
        tenant_id=tenant_id,
        period_days=days,
        spans_ingested=summary.get(MarketplaceDimension.SPANS_INGESTED.value, 0),
        detections_generated=summary.get(
            MarketplaceDimension.DETECTIONS_GENERATED.value, 0
        ),
        fixes_applied=summary.get(MarketplaceDimension.FIXES_APPLIED.value, 0),
    )


@router.post("/webhook", response_model=WebhookResponse)
async def marketplace_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle AWS Marketplace SNS notifications.

    Processes subscription lifecycle events from AWS Marketplace:
    - subscribe-success: Customer subscription confirmed
    - subscribe-fail: Subscription attempt failed
    - unsubscribe-pending: Customer initiated cancellation
    - unsubscribe-success: Cancellation completed
    - entitlement-updated: Customer's entitlement changed

    The endpoint expects an SNS message body with the event details.

    Args:
        request: Raw HTTP request with SNS payload.
        db: Database session.

    Returns:
        WebhookResponse with processing status.

    Raises:
        HTTPException 400: If the payload is invalid.
        HTTPException 404: If marketplace integration is not enabled.
    """
    _require_marketplace_enabled()

    # Parse request body
    try:
        body = await request.body()
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {e}",
        )

    # Handle SNS subscription confirmation
    message_type = request.headers.get("x-amz-sns-message-type", "")
    if message_type == "SubscriptionConfirmation":
        subscribe_url = payload.get("SubscribeURL")
        if subscribe_url:
            # Validate the URL is from AWS SNS before confirming
            if not subscribe_url.startswith("https://sns.") or ".amazonaws.com/" not in subscribe_url:
                logger.warning("Rejected SNS confirmation with suspicious URL: %s", subscribe_url)
                raise HTTPException(status_code=400, detail="Invalid SubscribeURL")
            logger.info("Auto-confirming SNS subscription: %s", subscribe_url)
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(subscribe_url)
                    resp.raise_for_status()
                logger.info("SNS subscription confirmed successfully")
                return WebhookResponse(
                    status="confirmed",
                    message="SNS subscription confirmed",
                )
            except httpx.HTTPError as e:
                logger.error("Failed to confirm SNS subscription: %s", e)
                raise HTTPException(
                    status_code=502,
                    detail="Failed to confirm SNS subscription",
                )

    # Process notification
    if message_type == "Notification":
        try:
            message = json.loads(payload.get("Message", "{}"))
        except json.JSONDecodeError:
            message = payload

        action = message.get("action", "")
        aws_customer_id = message.get("customer-identifier", "")

        logger.info(
            "Marketplace webhook: action=%s, customer=%s",
            action,
            aws_customer_id,
        )

        if action == "subscribe-success":
            await _handle_subscribe_success(db, aws_customer_id, message)
        elif action == "subscribe-fail":
            logger.warning(
                "Marketplace subscription failed for customer %s",
                aws_customer_id,
            )
        elif action == "unsubscribe-pending":
            await _handle_unsubscribe_pending(db, aws_customer_id)
        elif action == "unsubscribe-success":
            await _handle_unsubscribe_success(db, aws_customer_id)
        elif action == "entitlement-updated":
            await _handle_entitlement_updated(db, aws_customer_id)
        else:
            logger.warning("Unknown marketplace webhook action: %s", action)

        return WebhookResponse(
            status="processed",
            message=f"Processed action: {action}",
        )

    return WebhookResponse(
        status="ignored",
        message=f"Unhandled message type: {message_type}",
    )


# --- Webhook event handlers ---


async def _handle_subscribe_success(
    db: AsyncSession,
    aws_customer_id: str,
    message: dict,
) -> None:
    """Handle successful subscription confirmation.

    Args:
        db: Database session.
        aws_customer_id: AWS customer identifier.
        message: Full SNS message payload.
    """
    # Find tenant by AWS customer ID
    result = await db.execute(
        select(Tenant).where(
            Tenant.settings["aws_marketplace_customer_id"].as_string()
            == aws_customer_id
        )
    )
    tenant = result.scalar_one_or_none()

    if tenant:
        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant.id)
            .values(subscription_status="active")
        )
        await db.commit()
        logger.info(
            "Marketplace subscription confirmed for tenant %s", tenant.id
        )
    else:
        logger.warning(
            "No tenant found for AWS customer %s during subscribe-success",
            aws_customer_id,
        )


async def _handle_unsubscribe_pending(
    db: AsyncSession, aws_customer_id: str
) -> None:
    """Handle pending unsubscription.

    Args:
        db: Database session.
        aws_customer_id: AWS customer identifier.
    """
    result = await db.execute(
        select(Tenant).where(
            Tenant.settings["aws_marketplace_customer_id"].as_string()
            == aws_customer_id
        )
    )
    tenant = result.scalar_one_or_none()

    if tenant:
        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant.id)
            .values(subscription_status="canceling")
        )
        await db.commit()
        logger.info(
            "Marketplace unsubscribe pending for tenant %s", tenant.id
        )


async def _handle_unsubscribe_success(
    db: AsyncSession, aws_customer_id: str
) -> None:
    """Handle completed unsubscription. Revert tenant to free plan.

    Args:
        db: Database session.
        aws_customer_id: AWS customer identifier.
    """
    result = await db.execute(
        select(Tenant).where(
            Tenant.settings["aws_marketplace_customer_id"].as_string()
            == aws_customer_id
        )
    )
    tenant = result.scalar_one_or_none()

    if tenant:
        from app.billing.constants import PlanTier, get_span_limit

        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant.id)
            .values(
                plan=PlanTier.FREE,
                subscription_status=None,
                span_limit=get_span_limit(PlanTier.FREE),
            )
        )
        await db.commit()
        logger.info(
            "Marketplace unsubscribe completed for tenant %s, reverted to free",
            tenant.id,
        )


async def _handle_entitlement_updated(
    db: AsyncSession, aws_customer_id: str
) -> None:
    """Handle entitlement change (upgrade/downgrade).

    Args:
        db: Database session.
        aws_customer_id: AWS customer identifier.
    """
    service = get_marketplace_service()

    try:
        entitlement = await service.check_entitlement(aws_customer_id)
    except Exception as e:
        logger.error(
            "Failed to check updated entitlement for %s: %s",
            aws_customer_id,
            e,
        )
        return

    new_tier = entitlement.get("tier", "free")

    result = await db.execute(
        select(Tenant).where(
            Tenant.settings["aws_marketplace_customer_id"].as_string()
            == aws_customer_id
        )
    )
    tenant = result.scalar_one_or_none()

    if tenant and tenant.plan != new_tier:
        from app.billing.constants import get_span_limit

        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant.id)
            .values(
                plan=new_tier,
                span_limit=get_span_limit(new_tier),
            )
        )
        await db.commit()
        logger.info(
            "Marketplace entitlement updated for tenant %s: %s -> %s",
            tenant.id,
            tenant.plan,
            new_tier,
        )
