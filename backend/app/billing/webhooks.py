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
from .service import stripe_service
from .constants import SubscriptionStatus

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

    # Determine plan from subscription items
    # TODO: Map Stripe price ID back to plan name
    plan = tenant.plan  # Keep current plan for now

    await stripe_service.update_tenant_subscription(
        db=db,
        tenant_id=str(tenant.id),
        plan=plan,
        subscription_id=subscription_id,
        status=status,
        current_period_end=current_period_end,
    )

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


# Event handler mapping
WEBHOOK_HANDLERS = {
    'checkout.session.completed': handle_checkout_completed,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    'invoice.payment_failed': handle_payment_failed,
}


async def process_webhook_event(
    db: AsyncSession,
    event_type: str,
    event_data: dict,
) -> None:
    """
    Process a Stripe webhook event.

    Args:
        db: Database session
        event_type: Event type (e.g., 'checkout.session.completed')
        event_data: Event data from Stripe

    Raises:
        ValueError: If event type is not supported
    """
    handler = WEBHOOK_HANDLERS.get(event_type)

    if not handler:
        logger.warning(f"No handler for webhook event type: {event_type}")
        return

    await handler(db, event_data)
