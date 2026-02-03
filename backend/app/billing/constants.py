"""
Billing Constants - Plan Definitions

Defines the pricing tiers and their limits for PISAMA.
"""

from enum import Enum
from typing import Dict, List


class PlanTier(str, Enum):
    """Available pricing tiers."""
    FREE = "free"
    STARTUP = "startup"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Stripe subscription statuses."""
    ACTIVE = "active"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"


# Plan configurations
PLANS: Dict[str, Dict] = {
    PlanTier.FREE: {
        "display_name": "Free",
        "price_monthly": 0,
        "span_limit": 10_000,
        "project_limit": 1,
        "retention_days": 7,
        "team_limit": 1,
        "features": [
            "10K spans/month",
            "1 project",
            "7-day retention",
            "Community support",
            "Basic detectors",
        ],
    },
    PlanTier.STARTUP: {
        "display_name": "Startup",
        "price_monthly": 49,
        "span_limit": 250_000,
        "project_limit": 5,
        "retention_days": 30,
        "team_limit": 3,
        "features": [
            "250K spans/month",
            "5 projects",
            "30-day retention",
            "Slack & API alerts",
            "All detectors",
            "Email support",
        ],
    },
    PlanTier.GROWTH: {
        "display_name": "Growth",
        "price_monthly": 199,
        "span_limit": 2_500_000,
        "project_limit": 25,
        "retention_days": 90,
        "team_limit": 10,
        "features": [
            "2.5M spans/month",
            "25 projects",
            "90-day retention",
            "PagerDuty integration",
            "All detectors + ML",
            "Priority support",
            "Custom rules",
        ],
    },
    PlanTier.ENTERPRISE: {
        "display_name": "Enterprise",
        "price_monthly": None,  # Custom pricing
        "span_limit": None,  # Unlimited
        "project_limit": None,  # Unlimited
        "retention_days": None,  # Custom
        "team_limit": None,  # Unlimited
        "features": [
            "Unlimited spans",
            "Unlimited projects",
            "Custom retention",
            "SSO & RBAC",
            "SLA guarantee",
            "Dedicated support",
            "Custom integrations",
            "Self-hosted option",
        ],
    },
}


def get_plan_config(plan: str) -> Dict:
    """Get configuration for a specific plan."""
    return PLANS.get(plan, PLANS[PlanTier.FREE])


def get_span_limit(plan: str) -> int:
    """Get span limit for a plan."""
    config = get_plan_config(plan)
    return config.get("span_limit", 10_000)


def get_stripe_price_id(plan: str, env_vars: Dict[str, str]) -> str:
    """Get Stripe Price ID for a plan from environment variables."""
    if plan == PlanTier.STARTUP:
        return env_vars.get("STRIPE_PRICE_ID_STARTUP", "")
    elif plan == PlanTier.GROWTH:
        return env_vars.get("STRIPE_PRICE_ID_GROWTH", "")
    else:
        raise ValueError(f"No Stripe price ID configured for plan: {plan}")
