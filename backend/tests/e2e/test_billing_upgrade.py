"""
E2E Test: Free → Pro Billing Upgrade Flow

Tests the complete billing upgrade flow from free plan to pro plan,
including checkout session creation, webhook processing, and plan activation.

NOTE: These tests require a real PostgreSQL database (async_db_session fixture).
For mocked versions, see tests/test_billing_e2e.py.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import Tenant
from app.billing import PlanTier, SubscriptionStatus
from app.billing.service import stripe_service
from app.billing.webhooks import process_webhook_event

# Skip entire module — these tests require a real database connection.
# The mocked equivalents live in tests/test_billing_e2e.py.
pytestmark = pytest.mark.skip(reason="Requires real PostgreSQL (async_db_session fixture)")


class TestBillingUpgradeFlow:
    """Test Free → Pro upgrade flow end-to-end."""

    @pytest.mark.asyncio
    async def test_free_to_pro_upgrade_success(
        self,
        async_db_session: AsyncSession,
    ):
        """
        E2E-BILLING-001: Complete Free → Pro upgrade flow.

        Steps:
        1. Create checkout session for pro plan
        2. Simulate successful payment via webhook
        3. Verify tenant upgraded to pro plan
        4. Verify project_limit increased to 3
        5. Verify subscription status is active
        """
        # Create test tenant
        test_tenant = Tenant(
            id=uuid4(),
            name="test-tenant@example.com",
            plan=PlanTier.FREE,
            project_limit=1,
            subscription_status=None,
            stripe_customer_id=None,
            stripe_subscription_id=None,
            current_period_end=None,
        )
        async_db_session.add(test_tenant)
        await async_db_session.commit()
        await async_db_session.refresh(test_tenant)

        tenant_id = str(test_tenant.id)

        # Step 1: Verify tenant starts on free plan
        assert test_tenant.plan == PlanTier.FREE
        assert test_tenant.project_limit == 1
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
                db=async_db_session,
                tenant_id=tenant_id,
                plan=PlanTier.PRO,
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
            )

            # Verify checkout response
            assert response.checkout_url == 'https://checkout.stripe.com/test/123'
            assert response.session_id == 'cs_test123'

        # Step 3: Verify tenant now has Stripe customer ID
        await async_db_session.refresh(test_tenant)
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
                        'plan': PlanTier.PRO,
                    },
                }
            }

            await process_webhook_event(
                db=async_db_session,
                event_type='checkout.session.completed',
                event_data=event_data,
            )

        # Step 5: Verify tenant was upgraded
        await async_db_session.refresh(test_tenant)

        assert test_tenant.plan == PlanTier.PRO, \
            f"Expected plan to be '{PlanTier.PRO}', got '{test_tenant.plan}'"

        assert test_tenant.project_limit == 3, \
            f"Expected project_limit to be 3, got {test_tenant.project_limit}"

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
        async_db_session: AsyncSession,
    ):
        """
        E2E-BILLING-002: Reject checkout for invalid plans.

        Only pro and team plans should be allowed for checkout.
        """
        # Create test tenant
        test_tenant = Tenant(
            id=uuid4(),
            name="test-tenant@example.com",
            plan=PlanTier.FREE,
            project_limit=1,
            subscription_status=None,
            stripe_customer_id=None,
            stripe_subscription_id=None,
            current_period_end=None,
        )
        async_db_session.add(test_tenant)
        await async_db_session.commit()
        await async_db_session.refresh(test_tenant)

        tenant_id = str(test_tenant.id)

        # Try to create checkout for free plan (should fail)
        with pytest.raises(ValueError, match="Invalid plan for checkout"):
            await stripe_service.create_checkout_session(
                db=async_db_session,
                tenant_id=tenant_id,
                plan=PlanTier.FREE,
            )

        # Try to create checkout for enterprise plan (should fail)
        with pytest.raises(ValueError, match="Invalid plan for checkout"):
            await stripe_service.create_checkout_session(
                db=async_db_session,
                tenant_id=tenant_id,
                plan=PlanTier.ENTERPRISE,
            )

    @pytest.mark.asyncio
    async def test_subscription_cancellation_reverts_to_free(
        self,
        async_db_session: AsyncSession,
    ):
        """
        E2E-BILLING-003: Subscription cancellation reverts tenant to free plan.

        When subscription is cancelled, tenant should:
        - Revert to free plan
        - Have project_limit reset to 1
        - Lose stripe_subscription_id
        - Have subscription_status cleared
        """
        # Create test tenant with active subscription
        test_tenant = Tenant(
            id=uuid4(),
            name="test-tenant@example.com",
            plan=PlanTier.FREE,
            project_limit=1,
            subscription_status=None,
            stripe_customer_id=None,
            stripe_subscription_id=None,
            current_period_end=None,
        )
        async_db_session.add(test_tenant)
        await async_db_session.commit()
        await async_db_session.refresh(test_tenant)

        tenant_id = str(test_tenant.id)

        # Set up tenant with active pro subscription
        test_tenant.plan = PlanTier.PRO
        test_tenant.project_limit = 3
        test_tenant.stripe_subscription_id = 'sub_test456'
        test_tenant.subscription_status = SubscriptionStatus.ACTIVE
        await async_db_session.commit()

        # Simulate subscription deleted webhook
        event_data = {
            'object': {
                'id': 'sub_test456',
            }
        }

        await process_webhook_event(
            db=async_db_session,
            event_type='customer.subscription.deleted',
            event_data=event_data,
        )

        # Verify tenant reverted to free plan
        await async_db_session.refresh(test_tenant)

        assert test_tenant.plan == PlanTier.FREE, \
            f"Expected plan to revert to '{PlanTier.FREE}', got '{test_tenant.plan}'"

        assert test_tenant.project_limit == 1, \
            f"Expected project_limit to reset to 1, got {test_tenant.project_limit}"

        assert test_tenant.stripe_subscription_id is None, \
            "Expected subscription_id to be cleared"

        assert test_tenant.subscription_status is None, \
            "Expected subscription_status to be cleared"

        assert test_tenant.current_period_end is None, \
            "Expected current_period_end to be cleared"
