"""
Stripe Service - Stripe API integration

Handles Stripe operations: checkout, customer portal, subscription management.
"""

import stripe
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.storage.models import Tenant, User, State
from app.config import get_settings
from app.core.rate_limit import rate_limiter
from .constants import PlanTier, get_project_limit, get_daily_run_limit, get_stripe_price_id, PLANS
from .schemas import CheckoutResponse, PortalResponse, BillingStatus, UsageInfo

logger = logging.getLogger(__name__)

# Initialize Stripe
settings = get_settings()
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
        annual: bool = False,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> CheckoutResponse:
        """
        Create a Stripe Checkout session for a tenant to upgrade.

        Args:
            db: Database session
            tenant_id: Tenant UUID
            plan: Plan to subscribe to (pro or team)
            annual: Whether to use annual billing
            success_url: URL to redirect to after successful payment
            cancel_url: URL to redirect to if user cancels

        Returns:
            CheckoutResponse with checkout URL and session ID

        Raises:
            ValueError: If plan is invalid or tenant not found
        """
        # Validate plan
        if plan not in [PlanTier.PRO, PlanTier.TEAM]:
            raise ValueError(f"Invalid plan for checkout: {plan}. Must be pro or team.")

        # Get tenant
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")

        # Get Stripe price ID from environment
        suffix = "_ANNUAL" if annual else "_MONTHLY"
        env_vars = {
            f"STRIPE_PRICE_ID_PRO{suffix}": getattr(settings, f'STRIPE_PRICE_ID_PRO{suffix}', ''),
            f"STRIPE_PRICE_ID_TEAM{suffix}": getattr(settings, f'STRIPE_PRICE_ID_TEAM{suffix}', ''),
        }
        price_id = get_stripe_price_id(plan, env_vars, annual=annual)
        if not price_id:
            raise ValueError(f"Stripe price ID not configured for plan: {plan}")

        # Create or retrieve Stripe customer
        if tenant.stripe_customer_id:
            customer_id = tenant.stripe_customer_id
        else:
            # Get owner's email for Stripe customer
            owner_result = await db.execute(
                select(User).where(User.tenant_id == tenant_id, User.role == "owner")
            )
            owner = owner_result.scalar_one_or_none()
            owner_email = owner.email if owner else tenant.name

            # Create new customer
            customer = stripe.Customer.create(
                email=owner_email,
                name=tenant.name,
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

        # Count projects for this tenant
        from app.storage.models import Project
        project_result = await db.execute(
            select(func.count(Project.id))
            .where(Project.tenant_id == tenant_id)
        )
        project_count = project_result.scalar() or 0

        # Count today's runs (states created today)
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        run_result = await db.execute(
            select(func.count(State.id))
            .where(State.tenant_id == tenant_id)
            .where(State.created_at >= today_start)
        )
        daily_runs = run_result.scalar() or 0

        # Get limits from plan config
        project_limit = get_project_limit(tenant.plan)
        daily_run_limit = get_daily_run_limit(tenant.plan)

        return BillingStatus(
            plan=tenant.plan,
            status=tenant.subscription_status or "free",
            current_period_end=tenant.current_period_end,
            cancel_at_period_end=False,  # TODO: Get from Stripe subscription
            usage=UsageInfo(
                project_count=project_count,
                project_limit=project_limit,
                daily_runs=daily_runs,
                daily_run_limit=daily_run_limit,
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
            plan: New plan (pro, team, etc.)
            subscription_id: Stripe subscription ID
            status: Subscription status
            current_period_end: When current period ends
        """
        plan_config = PLANS.get(plan, PLANS[PlanTier.FREE])

        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(
                plan=plan,
                stripe_subscription_id=subscription_id,
                subscription_status=status,
                current_period_end=current_period_end,
                project_limit=plan_config.get("project_limit", 1),
            )
        )
        await db.commit()

        # Invalidate rate limit tier cache so new limits apply immediately
        await rate_limiter.invalidate_tenant_tier(tenant_id)

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
        free_config = PLANS[PlanTier.FREE]

        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(
                plan=PlanTier.FREE,
                subscription_status=None,
                stripe_subscription_id=None,
                current_period_end=None,
                project_limit=free_config["project_limit"],
            )
        )
        await db.commit()

        await rate_limiter.invalidate_tenant_tier(tenant_id)

        logger.info(f"Reverted tenant {tenant_id} to free plan")


# Singleton instance
stripe_service = StripeService()
