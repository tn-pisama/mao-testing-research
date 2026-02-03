"""
Stripe Service - Stripe API integration

Handles Stripe operations: checkout, customer portal, subscription management.
"""

import stripe
import logging
from typing import Optional, Dict
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.storage.models import Tenant
from app.config import settings
from .constants import PlanTier, get_span_limit, get_stripe_price_id, PLANS
from .schemas import CheckoutResponse, PortalResponse, BillingStatus, UsageInfo

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY if hasattr(settings, 'STRIPE_SECRET_KEY') else None


class StripeService:
    """Service for Stripe operations."""

    def __init__(self):
        """Initialize Stripe service."""
        if not stripe.api_key:
            logger.warning("Stripe API key not configured")

    async def create_checkout_session(
        self,
        db: AsyncSession,
        tenant_id: str,
        plan: str,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> CheckoutResponse:
        """
        Create a Stripe Checkout session for a tenant to upgrade.

        Args:
            db: Database session
            tenant_id: Tenant UUID
            plan: Plan to subscribe to (startup or growth)
            success_url: URL to redirect to after successful payment
            cancel_url: URL to redirect to if user cancels

        Returns:
            CheckoutResponse with checkout URL and session ID

        Raises:
            ValueError: If plan is invalid or tenant not found
        """
        # Validate plan
        if plan not in [PlanTier.STARTUP, PlanTier.GROWTH]:
            raise ValueError(f"Invalid plan for checkout: {plan}. Must be startup or growth.")

        # Get tenant
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")

        # Get Stripe price ID from environment
        env_vars = {
            "STRIPE_PRICE_ID_STARTUP": getattr(settings, 'STRIPE_PRICE_ID_STARTUP', ''),
            "STRIPE_PRICE_ID_GROWTH": getattr(settings, 'STRIPE_PRICE_ID_GROWTH', ''),
        }
        price_id = get_stripe_price_id(plan, env_vars)
        if not price_id:
            raise ValueError(f"Stripe price ID not configured for plan: {plan}")

        # Create or retrieve Stripe customer
        if tenant.stripe_customer_id:
            customer_id = tenant.stripe_customer_id
        else:
            # Create new customer
            customer = stripe.Customer.create(
                email=tenant.name,  # TODO: Use actual tenant email when available
                metadata={"tenant_id": str(tenant_id)},
            )
            customer_id = customer.id

            # Update tenant with customer ID
            await db.execute(
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(stripe_customer_id=customer_id)
            )
            await db.commit()

        # Create Checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url or f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=cancel_url or f"{settings.FRONTEND_URL}/billing/cancel",
            metadata={
                "tenant_id": str(tenant_id),
                "plan": plan,
            },
        )

        logger.info(f"Created Stripe checkout session for tenant {tenant_id}, plan {plan}")

        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id,
        )

    async def create_customer_portal_session(
        self,
        db: AsyncSession,
        tenant_id: str,
        return_url: Optional[str] = None,
    ) -> PortalResponse:
        """
        Create a Stripe Customer Portal session.

        Args:
            db: Database session
            tenant_id: Tenant UUID
            return_url: URL to return to after portal visit

        Returns:
            PortalResponse with portal URL

        Raises:
            ValueError: If tenant not found or no Stripe customer
        """
        # Get tenant
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")

        if not tenant.stripe_customer_id:
            raise ValueError(f"Tenant has no Stripe customer ID: {tenant_id}")

        # Create portal session
        session = stripe.billing_portal.Session.create(
            customer=tenant.stripe_customer_id,
            return_url=return_url or f"{settings.FRONTEND_URL}/settings/billing",
        )

        logger.info(f"Created Stripe portal session for tenant {tenant_id}")

        return PortalResponse(portal_url=session.url)

    async def get_billing_status(
        self,
        db: AsyncSession,
        tenant_id: str,
    ) -> BillingStatus:
        """
        Get current billing status for a tenant.

        Args:
            db: Database session
            tenant_id: Tenant UUID

        Returns:
            BillingStatus with plan, status, and usage info

        Raises:
            ValueError: If tenant not found
        """
        # Get tenant
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")

        # Get current span usage (TODO: Implement actual usage tracking)
        # For now, return 0
        span_count = 0

        # Calculate usage percentage
        span_limit = tenant.span_limit or get_span_limit(tenant.plan)
        usage_percentage = (span_count / span_limit * 100) if span_limit > 0 else 0

        return BillingStatus(
            plan=tenant.plan,
            status=tenant.subscription_status or "free",
            current_period_end=tenant.current_period_end,
            cancel_at_period_end=False,  # TODO: Get from Stripe subscription
            usage=UsageInfo(
                span_count=span_count,
                span_limit=span_limit,
                usage_percentage=round(usage_percentage, 2),
            ),
        )

    async def update_tenant_subscription(
        self,
        db: AsyncSession,
        tenant_id: str,
        plan: str,
        subscription_id: str,
        status: str,
        current_period_end: Optional[datetime] = None,
    ) -> None:
        """
        Update tenant subscription info after Stripe webhook.

        Args:
            db: Database session
            tenant_id: Tenant UUID
            plan: New plan (startup, growth, etc.)
            subscription_id: Stripe subscription ID
            status: Subscription status
            current_period_end: When current period ends
        """
        span_limit = get_span_limit(plan)

        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(
                plan=plan,
                stripe_subscription_id=subscription_id,
                subscription_status=status,
                current_period_end=current_period_end,
                span_limit=span_limit,
            )
        )
        await db.commit()

        logger.info(f"Updated tenant {tenant_id} subscription: plan={plan}, status={status}")

    async def cancel_subscription(
        self,
        db: AsyncSession,
        tenant_id: str,
    ) -> None:
        """
        Revert tenant to free plan after subscription cancellation.

        Args:
            db: Database session
            tenant_id: Tenant UUID
        """
        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(
                plan=PlanTier.FREE,
                subscription_status=None,
                stripe_subscription_id=None,
                current_period_end=None,
                span_limit=get_span_limit(PlanTier.FREE),
            )
        )
        await db.commit()

        logger.info(f"Reverted tenant {tenant_id} to free plan")


# Singleton instance
stripe_service = StripeService()
