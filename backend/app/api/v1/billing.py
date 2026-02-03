"""
Billing API Endpoints

REST API for billing operations: plans, checkout, portal, webhooks.
"""

import stripe
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database import get_db
from app.core.auth import get_current_tenant_id
from app.config import settings
from app.billing import (
    PlanInfo,
    CheckoutRequest,
    CheckoutResponse,
    PortalResponse,
    BillingStatus,
    PLANS,
)
from app.billing.service import stripe_service
from app.billing.webhooks import process_webhook_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=List[PlanInfo])
async def list_plans():
    """
    List all available pricing plans.

    Returns:
        List of PlanInfo objects with pricing details
    """
    plans = []
    for plan_name, config in PLANS.items():
        plans.append(
            PlanInfo(
                name=plan_name,
                display_name=config["display_name"],
                price_monthly=config["price_monthly"],
                span_limit=config["span_limit"],
                project_limit=config["project_limit"],
                retention_days=config["retention_days"],
                team_limit=config["team_limit"],
                features=config["features"],
            )
        )
    return plans


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """
    Create a Stripe Checkout session to upgrade to a paid plan.

    Args:
        request: CheckoutRequest with plan and optional URLs
        db: Database session
        tenant_id: Current tenant ID from auth

    Returns:
        CheckoutResponse with Stripe Checkout URL

    Raises:
        HTTPException 400: If plan is invalid
        HTTPException 500: If Stripe API fails
    """
    try:
        response = await stripe_service.create_checkout_session(
            db=db,
            tenant_id=tenant_id,
            plan=request.plan,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.get("/portal", response_model=PortalResponse)
async def get_customer_portal(
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    return_url: str = None,
):
    """
    Get Stripe Customer Portal URL for managing subscription.

    Args:
        db: Database session
        tenant_id: Current tenant ID from auth
        return_url: Optional URL to return to after portal visit

    Returns:
        PortalResponse with Customer Portal URL

    Raises:
        HTTPException 400: If tenant has no Stripe customer
        HTTPException 500: If Stripe API fails
    """
    try:
        response = await stripe_service.create_customer_portal_session(
            db=db,
            tenant_id=tenant_id,
            return_url=return_url,
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create portal session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create portal session")


@router.get("/status", response_model=BillingStatus)
async def get_billing_status(
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """
    Get current billing status for the tenant.

    Args:
        db: Database session
        tenant_id: Current tenant ID from auth

    Returns:
        BillingStatus with plan, subscription status, and usage

    Raises:
        HTTPException 500: If database query fails
    """
    try:
        status = await stripe_service.get_billing_status(
            db=db,
            tenant_id=tenant_id,
        )
        return status
    except Exception as e:
        logger.error(f"Failed to get billing status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get billing status")


@router.post("/webhooks/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    """
    Handle Stripe webhook events.

    Verifies webhook signature and processes events like:
    - checkout.session.completed
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_failed

    Args:
        request: Raw request with webhook payload
        db: Database session
        stripe_signature: Stripe signature header for verification

    Returns:
        Success message

    Raises:
        HTTPException 400: If signature is invalid
        HTTPException 500: If event processing fails
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    # Get raw body
    payload = await request.body()

    # Verify webhook signature
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Process event
    try:
        await process_webhook_event(
            db=db,
            event_type=event['type'],
            event_data=event['data'],
        )
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to process webhook event {event['type']}: {e}")
        # Return 200 to acknowledge receipt even if processing fails
        # Stripe will retry if we return error
        return {"status": "error", "message": str(e)}
