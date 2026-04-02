"""
Stripe Webhook Handlers

Processes Stripe webhook events for subscription lifecycle management.
"""

import stripe
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.storage.models import Tenant, User
from app.notifications.email import EmailNotifier
from app.config import get_settings
from app.core.rate_limit import rate_limiter
from .service import stripe_service
from .constants import SubscriptionStatus, get_plan_from_price_id

logger = logging.getLogger(__name__)


async def handle_checkout_completed(
    db: AsyncSession,
    event_data: dict,
) -> None:
    """
    Handle checkout.session.completed event.

    Activates subscription after successful payment.

    Args:
        db: Database session
        event_data: Stripe event data
    """
    session = event_data['object']
    tenant_id = session['metadata'].get('tenant_id')
    plan = session['metadata'].get('plan')
    subscription_id = session.get('subscription')

    if not tenant_id or not plan:
        logger.error(f"Missing metadata in checkout session: {session['id']}")
        return

    # Get subscription details from Stripe
    if subscription_id:
        subscription = stripe.Subscription.retrieve(subscription_id)
        status = subscription['status']
        current_period_end = datetime.fromtimestamp(subscription['current_period_end'])
    else:
        status = SubscriptionStatus.ACTIVE
        current_period_end = None

    # Update tenant
    await stripe_service.update_tenant_subscription(
        db=db,
        tenant_id=tenant_id,
        plan=plan,
        subscription_id=subscription_id,
        status=status,
        current_period_end=current_period_end,
    )

    # Invalidate rate limit tier cache so new limits take effect immediately
    await rate_limiter.invalidate_tenant_tier(tenant_id)

    logger.info(f"Checkout completed for tenant {tenant_id}, plan {plan}")


async def handle_subscription_updated(
    db: AsyncSession,
    event_data: dict,
) -> None:
    """
    Handle customer.subscription.updated event.

    Updates subscription status when changed (upgrade, downgrade, etc.).

    Args:
        db: Database session
        event_data: Stripe event data
    """
    subscription = event_data['object']
    subscription_id = subscription['id']
    status = subscription['status']
    current_period_end = datetime.fromtimestamp(subscription['current_period_end'])

    # Find tenant by subscription_id
    result = await db.execute(
        select(Tenant).where(Tenant.stripe_subscription_id == subscription_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        logger.warning(f"Tenant not found for subscription {subscription_id}")
        return

    # Determine plan from subscription's current price
    items = subscription.get('items', {}).get('data', [])
    if items:
        price_id = items[0].get('price', {}).get('id', '')
        plan = get_plan_from_price_id(price_id) or tenant.plan
    else:
        plan = tenant.plan

    await stripe_service.update_tenant_subscription(
        db=db,
        tenant_id=str(tenant.id),
        plan=plan,
        subscription_id=subscription_id,
        status=status,
        current_period_end=current_period_end,
    )

    await rate_limiter.invalidate_tenant_tier(str(tenant.id))

    logger.info(f"Subscription updated for tenant {tenant.id}: status={status}")


async def handle_subscription_deleted(
    db: AsyncSession,
    event_data: dict,
) -> None:
    """
    Handle customer.subscription.deleted event.

    Reverts tenant to free plan when subscription is cancelled.

    Args:
        db: Database session
        event_data: Stripe event data
    """
    subscription = event_data['object']
    subscription_id = subscription['id']

    # Find tenant by subscription_id
    result = await db.execute(
        select(Tenant).where(Tenant.stripe_subscription_id == subscription_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        logger.warning(f"Tenant not found for subscription {subscription_id}")
        return

    # Revert to free plan
    await stripe_service.cancel_subscription(
        db=db,
        tenant_id=str(tenant.id),
    )

    await rate_limiter.invalidate_tenant_tier(str(tenant.id))

    logger.info(f"Subscription deleted for tenant {tenant.id}, reverted to free plan")


async def handle_payment_failed(
    db: AsyncSession,
    event_data: dict,
) -> None:
    """
    Handle invoice.payment_failed event.

    Marks subscription as past_due when payment fails.

    Args:
        db: Database session
        event_data: Stripe event data
    """
    invoice = event_data['object']
    subscription_id = invoice.get('subscription')

    if not subscription_id:
        return

    # Find tenant by subscription_id
    result = await db.execute(
        select(Tenant).where(Tenant.stripe_subscription_id == subscription_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        logger.warning(f"Tenant not found for subscription {subscription_id}")
        return

    # Update subscription status to past_due
    await stripe_service.update_tenant_subscription(
        db=db,
        tenant_id=str(tenant.id),
        plan=tenant.plan,
        subscription_id=subscription_id,
        status=SubscriptionStatus.PAST_DUE,
        current_period_end=tenant.current_period_end,
    )

    logger.warning(f"Payment failed for tenant {tenant.id}, marked as past_due")

    # Send notification email to owner
    settings = get_settings()
    owner_result = await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.role == "owner")
    )
    owner = owner_result.scalar_one_or_none()
    if owner and owner.email:
        notifier = EmailNotifier()
        try:
            await notifier.send(
                to=owner.email,
                subject="PISAMA: Payment Failed - Action Required",
                body=f"""Your payment for PISAMA {tenant.plan} plan has failed.

Please update your payment method to avoid service interruption.

Update payment: {settings.FRONTEND_URL}/billing

If you have questions, reply to this email.
""",
            )
            logger.info(f"Sent payment failure notification to {owner.email}")
        except Exception as e:
            logger.error(f"Failed to send payment notification: {e}")


async def handle_trial_will_end(
    db: AsyncSession,
    event_data: dict,
) -> None:
    """Handle customer.subscription.trial_will_end event.

    Sends email notification ~3 days before trial expires.
    """
    subscription = event_data['object']
    subscription_id = subscription['id']

    result = await db.execute(
        select(Tenant).where(Tenant.stripe_subscription_id == subscription_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.warning(f"Tenant not found for subscription {subscription_id}")
        return

    owner_result = await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.role == "owner")
    )
    owner = owner_result.scalar_one_or_none()
    if owner and owner.email:
        settings = get_settings()
        notifier = EmailNotifier()
        try:
            await notifier.send(
                to=owner.email,
                subject="Pisama: Your trial ends soon",
                body=f"""Your Pisama {tenant.plan} trial is ending in 3 days.

Add a payment method to continue using {tenant.plan} features without interruption.

Manage subscription: {settings.FRONTEND_URL}/billing

If you have questions, reply to this email.
""",
            )
        except Exception as e:
            logger.error(f"Failed to send trial ending notification: {e}")

    logger.info(f"Trial ending soon for tenant {tenant.id}")


async def handle_payment_action_required(
    db: AsyncSession,
    event_data: dict,
) -> None:
    """Handle invoice.payment_action_required event.

    Notifies user when payment needs additional authentication (e.g., 3D Secure).
    """
    invoice = event_data['object']
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return

    result = await db.execute(
        select(Tenant).where(Tenant.stripe_subscription_id == subscription_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        return

    hosted_invoice_url = invoice.get('hosted_invoice_url', '')

    owner_result = await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.role == "owner")
    )
    owner = owner_result.scalar_one_or_none()
    if owner and owner.email:
        notifier = EmailNotifier()
        try:
            await notifier.send(
                to=owner.email,
                subject="Pisama: Payment action required",
                body=f"""Your payment for Pisama {tenant.plan} requires additional authentication.

Complete payment: {hosted_invoice_url}

Your subscription will remain active while you complete this step.
""",
            )
        except Exception as e:
            logger.error(f"Failed to send payment action notification: {e}")

    logger.info(f"Payment action required for tenant {tenant.id}")


async def handle_dispute_created(
    db: AsyncSession,
    event_data: dict,
) -> None:
    """Handle charge.dispute.created event.

    Logs the dispute and notifies the tenant owner.
    """
    dispute = event_data['object']
    charge_id = dispute.get('charge', '')
    amount = dispute.get('amount', 0)
    reason = dispute.get('reason', 'unknown')

    # Try to find tenant via the charge's customer
    customer_id = dispute.get('customer', '') or (
        dispute.get('charge_object', {}).get('customer', '')
    )

    tenant = None
    if customer_id:
        result = await db.execute(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        )
        tenant = result.scalar_one_or_none()

    logger.warning(
        f"Dispute created: charge={charge_id}, amount={amount}, reason={reason}, "
        f"tenant={tenant.id if tenant else 'unknown'}"
    )

    if tenant:
        owner_result = await db.execute(
            select(User).where(User.tenant_id == tenant.id, User.role == "owner")
        )
        owner = owner_result.scalar_one_or_none()
        if owner and owner.email:
            notifier = EmailNotifier()
            try:
                await notifier.send(
                    to=owner.email,
                    subject="Pisama: Payment dispute received",
                    body=f"""A payment dispute has been filed for your Pisama account.

Reason: {reason}
Amount: ${amount / 100:.2f}

Please contact support if you believe this is an error.
""",
                )
            except Exception as e:
                logger.error(f"Failed to send dispute notification: {e}")


# Event handler mapping
WEBHOOK_HANDLERS = {
    'checkout.session.completed': handle_checkout_completed,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    'customer.subscription.trial_will_end': handle_trial_will_end,
    'invoice.payment_failed': handle_payment_failed,
    'invoice.payment_action_required': handle_payment_action_required,
    'charge.dispute.created': handle_dispute_created,
}


async def process_webhook_event(
    db: AsyncSession,
    event_type: str,
    event_data: dict,
    event_id: str = "",
) -> None:
    """
    Process a Stripe webhook event with idempotency.

    Args:
        db: Database session
        event_type: Event type (e.g., 'checkout.session.completed')
        event_data: Event data from Stripe
        event_id: Stripe event ID for deduplication
    """
    # Idempotency: skip if this event was already processed
    if event_id:
        try:
            redis = rate_limiter.redis
            key = f"stripe_webhook:{event_id}"
            if await redis.get(key):
                logger.info(f"Skipping duplicate webhook event: {event_id}")
                return
            # Mark as processed with 72h TTL (matches Stripe retry window)
            await redis.setex(key, 259200, "1")
        except Exception as e:
            # If Redis is down, process anyway (better to double-process than miss)
            logger.warning(f"Redis idempotency check failed, processing anyway: {e}")

    handler = WEBHOOK_HANDLERS.get(event_type)

    if not handler:
        logger.warning(f"No handler for webhook event type: {event_type}")
        return

    await handler(db, event_data)
