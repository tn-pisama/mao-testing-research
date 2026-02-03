"""
Billing Module - Stripe Integration for PISAMA

Handles subscription management, payment processing, and webhook events.
"""

from .constants import PlanTier, SubscriptionStatus, PLANS, get_plan_config, get_span_limit
from .schemas import (
    PlanInfo,
    CheckoutRequest,
    CheckoutResponse,
    PortalResponse,
    BillingStatus,
    UsageInfo,
    WebhookEvent,
)

from .service import stripe_service

__all__ = [
    # Constants
    "PlanTier",
    "SubscriptionStatus",
    "PLANS",
    "get_plan_config",
    "get_span_limit",
    # Schemas
    "PlanInfo",
    "CheckoutRequest",
    "CheckoutResponse",
    "PortalResponse",
    "BillingStatus",
    "UsageInfo",
    "WebhookEvent",
    # Service
    "stripe_service",
]
