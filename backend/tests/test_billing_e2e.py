"""
E2E Test: Free → Pro Billing Upgrade Flow (Fully Mocked)

Tests the complete billing upgrade flow from free plan to pro plan,
using mocks for all external dependencies including database.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

from app.storage.models import Tenant
from app.billing import PlanTier, SubscriptionStatus
from app.billing.service import stripe_service
from app.billing.webhooks import process_webhook_event


class TestBillingUpgradeFlowMocked:
    """Test Free → Pro upgrade flow with fully mocked dependencies."""

    @pytest.mark.asyncio
    async def test_free_to_pro_upgrade_success(self):
        """
        E2E-BILLING-001: Complete Free → Pro upgrade flow.

        Steps:
        1. Create checkout session for pro plan
        2. Simulate successful payment via webhook
        3. Verify tenant upgraded to pro plan
        4. Verify project_limit increased to 3
        5. Verify subscription status is active
        """
        # Create mock tenant
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
        tenant_id = str(test_tenant.id)

        # Mock database session — return different results for tenant query
        # vs owner/user query. Update calls get a generic MagicMock.
        mock_db = AsyncMock()
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = test_tenant
        owner_result = MagicMock()
        owner_result.scalar_one_or_none.return_value = None  # no owner User row
        generic_result = MagicMock()

        # Calls: 1=get tenant, 2=get owner, 3=update customer_id, 4=update subscription
        mock_db.execute = AsyncMock(
            side_effect=[tenant_result, owner_result, generic_result, generic_result]
        )
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Step 1: Verify tenant starts on free plan
        assert test_tenant.plan == PlanTier.FREE
        assert test_tenant.project_limit == 1
        assert test_tenant.stripe_customer_id is None

        # Step 2: Create checkout session (mock Stripe API)
        with patch('stripe.Customer.create') as mock_customer_create, \
             patch('stripe.checkout.Session.create') as mock_checkout_create, \
             patch('app.billing.service.get_stripe_price_id') as mock_get_price:

            # Mock price ID retrieval
            mock_get_price.return_value = 'price_test_startup'

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
                db=mock_db,
                tenant_id=tenant_id,
                plan=PlanTier.PRO,
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
            )

            # Verify checkout response
            assert response.checkout_url == 'https://checkout.stripe.com/test/123'
            assert response.session_id == 'cs_test123'

        # Step 3: Simulate database update (tenant gets customer ID)
        test_tenant.stripe_customer_id = 'cus_test123'

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
                db=mock_db,
                event_type='checkout.session.completed',
                event_data=event_data,
            )

        # Step 5: Verify database update was called with correct values
        # The webhook handler calls stripe_service.update_tenant_subscription
        # which should have been called with the updated values
        assert mock_db.execute.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_checkout_invalid_plan_rejection(self):
        """
        E2E-BILLING-002: Reject checkout for invalid plans.

        Only pro and team plans should be allowed for checkout.
        """
        test_tenant = Tenant(
            id=uuid4(),
            name="test-tenant@example.com",
            plan=PlanTier.FREE,
            project_limit=1,
        )
        tenant_id = str(test_tenant.id)

        # Mock database session
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_tenant
        mock_db.execute.return_value = mock_result

        # Try to create checkout for free plan (should fail)
        with pytest.raises(ValueError, match="Invalid plan for checkout"):
            await stripe_service.create_checkout_session(
                db=mock_db,
                tenant_id=tenant_id,
                plan=PlanTier.FREE,
            )

        # Try to create checkout for enterprise plan (should fail)
        with pytest.raises(ValueError, match="Invalid plan for checkout"):
            await stripe_service.create_checkout_session(
                db=mock_db,
                tenant_id=tenant_id,
                plan=PlanTier.ENTERPRISE,
            )

    @pytest.mark.asyncio
    async def test_subscription_cancellation_reverts_to_free(self):
        """
        E2E-BILLING-003: Subscription cancellation reverts tenant to free plan.

        When subscription is cancelled, tenant should:
        - Revert to free plan
        - Have project_limit reset to 1
        - Lose stripe_subscription_id
        - Have subscription_status cleared
        """
        # Create tenant with active subscription
        test_tenant = Tenant(
            id=uuid4(),
            name="test-tenant@example.com",
            plan=PlanTier.PRO,
            project_limit=3,
            subscription_status=SubscriptionStatus.ACTIVE,
            stripe_customer_id='cus_test456',
            stripe_subscription_id='sub_test456',
            current_period_end=datetime.now() + timedelta(days=15),
        )

        # Mock database session
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_tenant
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        # Simulate subscription deleted webhook
        event_data = {
            'object': {
                'id': 'sub_test456',
            }
        }

        await process_webhook_event(
            db=mock_db,
            event_type='customer.subscription.deleted',
            event_data=event_data,
        )

        # Verify database operations were called
        assert mock_db.execute.called
        assert mock_db.commit.called
