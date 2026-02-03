"""
E2E Test: Free → Startup Billing Upgrade Flow

Tests the complete billing upgrade flow from free plan to startup plan,
including checkout session creation, webhook processing, and plan activation.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.storage.models import Tenant
from app.billing import PlanTier, SubscriptionStatus
from app.billing.service import stripe_service
from app.billing.webhooks import process_webhook_event


@pytest_asyncio.fixture
async def test_tenant(db: AsyncSession):
    """Create a test tenant with free plan."""
    tenant = Tenant(
        id=uuid4(),
        name="test-tenant@example.com",
        plan=PlanTier.FREE,
        span_limit=10000,
        subscription_status=None,
        stripe_customer_id=None,
        stripe_subscription_id=None,
        current_period_end=None,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


class TestBillingUpgradeFlow:
    """Test Free → Startup upgrade flow end-to-end."""

    @pytest.mark.asyncio
    async def test_free_to_startup_upgrade_success(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
    ):
        """
        E2E-BILLING-001: Complete Free → Startup upgrade flow.

        Steps:
        1. Create checkout session for startup plan
        2. Simulate successful payment via webhook
        3. Verify tenant upgraded to startup plan
        4. Verify span_limit increased to 250,000
        5. Verify subscription status is active
        """
        tenant_id = str(test_tenant.id)

        # Step 1: Verify tenant starts on free plan
        assert test_tenant.plan == PlanTier.FREE
        assert test_tenant.span_limit == 10000
        assert test_tenant.stripe_customer_id is None

        # Step 2: Create checkout session (mock Stripe API)
        with patch('stripe.Customer.create') as mock_customer_create, \
             patch('stripe.checkout.Session.create') as mock_checkout_create:

            # Mock Stripe customer creation
            mock_customer_create.return_value = MagicMock(
                id='cus_test123',
            )

            # Mock Stripe checkout session creation
            mock_checkout_create.return_value = MagicMock(
                id='cs_test123',
                url='https://checkout.stripe.com/test/123',
            )

            # Call checkout endpoint
            response = await stripe_service.create_checkout_session(
                db=db,
                tenant_id=tenant_id,
                plan=PlanTier.STARTUP,
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
            )

            # Verify checkout response
            assert response.checkout_url == 'https://checkout.stripe.com/test/123'
            assert response.session_id == 'cs_test123'

            # Verify customer was created
            mock_customer_create.assert_called_once()
            mock_checkout_create.assert_called_once()

        # Step 3: Verify tenant now has Stripe customer ID
        await db.refresh(test_tenant)
        assert test_tenant.stripe_customer_id == 'cus_test123'

        # Step 4: Simulate successful payment webhook
        with patch('stripe.Subscription.retrieve') as mock_subscription_retrieve:
            # Mock Stripe subscription retrieval
            current_period_end = datetime.now() + timedelta(days=30)
            mock_subscription_retrieve.return_value = {
                'id': 'sub_test123',
                'status': 'active',
                'current_period_end': int(current_period_end.timestamp()),
            }

            # Simulate checkout.session.completed webhook event
            event_data = {
                'object': {
                    'id': 'cs_test123',
                    'subscription': 'sub_test123',
                    'metadata': {
                        'tenant_id': tenant_id,
                        'plan': PlanTier.STARTUP,
                    },
                }
            }

            await process_webhook_event(
                db=db,
                event_type='checkout.session.completed',
                event_data=event_data,
            )

        # Step 5: Verify tenant was upgraded
        await db.refresh(test_tenant)

        assert test_tenant.plan == PlanTier.STARTUP, \
            f"Expected plan to be '{PlanTier.STARTUP}', got '{test_tenant.plan}'"

        assert test_tenant.span_limit == 250000, \
            f"Expected span_limit to be 250000, got {test_tenant.span_limit}"

        assert test_tenant.subscription_status == SubscriptionStatus.ACTIVE, \
            f"Expected status to be '{SubscriptionStatus.ACTIVE}', got '{test_tenant.subscription_status}'"

        assert test_tenant.stripe_subscription_id == 'sub_test123', \
            f"Expected subscription_id 'sub_test123', got '{test_tenant.stripe_subscription_id}'"

        assert test_tenant.current_period_end is not None, \
            "Expected current_period_end to be set"

        # Verify period end is approximately 30 days from now (within 1 hour tolerance)
        time_diff = abs((test_tenant.current_period_end - current_period_end).total_seconds())
        assert time_diff < 3600, \
            f"Period end time difference too large: {time_diff} seconds"

    @pytest.mark.asyncio
    async def test_checkout_invalid_plan_rejection(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
    ):
        """
        E2E-BILLING-002: Reject checkout for invalid plans.

        Only startup and growth plans should be allowed for checkout.
        """
        tenant_id = str(test_tenant.id)

        # Try to create checkout for free plan (should fail)
        with pytest.raises(ValueError, match="Invalid plan for checkout"):
            await stripe_service.create_checkout_session(
                db=db,
                tenant_id=tenant_id,
                plan=PlanTier.FREE,
            )

        # Try to create checkout for enterprise plan (should fail)
        with pytest.raises(ValueError, match="Invalid plan for checkout"):
            await stripe_service.create_checkout_session(
                db=db,
                tenant_id=tenant_id,
                plan=PlanTier.ENTERPRISE,
            )

    @pytest.mark.asyncio
    async def test_subscription_cancellation_reverts_to_free(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
    ):
        """
        E2E-BILLING-003: Subscription cancellation reverts tenant to free plan.

        When subscription is cancelled, tenant should:
        - Revert to free plan
        - Have span_limit reset to 10,000
        - Lose stripe_subscription_id
        - Have subscription_status cleared
        """
        tenant_id = str(test_tenant.id)

        # Set up tenant with active startup subscription
        test_tenant.plan = PlanTier.STARTUP
        test_tenant.span_limit = 250000
        test_tenant.stripe_subscription_id = 'sub_test456'
        test_tenant.subscription_status = SubscriptionStatus.ACTIVE
        await db.commit()

        # Simulate subscription deleted webhook
        event_data = {
            'object': {
                'id': 'sub_test456',
            }
        }

        await process_webhook_event(
            db=db,
            event_type='customer.subscription.deleted',
            event_data=event_data,
        )

        # Verify tenant reverted to free plan
        await db.refresh(test_tenant)

        assert test_tenant.plan == PlanTier.FREE, \
            f"Expected plan to revert to '{PlanTier.FREE}', got '{test_tenant.plan}'"

        assert test_tenant.span_limit == 10000, \
            f"Expected span_limit to reset to 10000, got {test_tenant.span_limit}"

        assert test_tenant.stripe_subscription_id is None, \
            "Expected subscription_id to be cleared"

        assert test_tenant.subscription_status is None, \
            "Expected subscription_status to be cleared"

        assert test_tenant.current_period_end is None, \
            "Expected current_period_end to be cleared"
