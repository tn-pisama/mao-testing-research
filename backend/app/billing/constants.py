"""
Billing Constants - Plan Definitions

Defines the pricing tiers and their limits for Pisama.
"""

from enum import Enum
from typing import Dict, List


class PlanTier(str, Enum):
    """Available pricing tiers."""
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
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
        "project_limit": 1,
        "retention_days": 7,
        "team_limit": 1,
        "daily_run_limit": 50,
        "alerts_per_day": 5,
        "features": [
            "1 project",
            "All 42 failure detectors",
            "Basic fix suggestions",
            "Email alerts",
            "7-day history",
        ],
    },
    PlanTier.PRO: {
        "display_name": "Pro",
        "price_monthly": 29,
        "project_limit": 3,
        "retention_days": 30,
        "team_limit": 1,
        "daily_run_limit": 500,
        "alerts_per_day": 50,
        "features": [
            "3 projects",
            "Code-level fix suggestions",
            "Slack & webhook alerts",
            "Cost analytics",
            "API access",
            "30-day history",
        ],
    },
    PlanTier.TEAM: {
        "display_name": "Team",
        "price_monthly": 79,
        "project_limit": 10,
        "retention_days": 90,
        "team_limit": 5,
        "daily_run_limit": 5000,
        "alerts_per_day": 500,
        "features": [
            "10 projects",
            "5 team members",
            "AI runbooks",
            "Trend analytics",
            "Custom alert rules",
            "90-day history",
            "Priority support",
        ],
    },
    PlanTier.ENTERPRISE: {
        "display_name": "Enterprise",
        "price_monthly": None,  # Custom pricing
        "project_limit": None,  # Unlimited
        "retention_days": None,  # Custom
        "team_limit": None,  # Unlimited
        "daily_run_limit": None,  # Unlimited
        "alerts_per_day": None,  # Unlimited
        "features": [
            "Unlimited projects",
            "Unlimited team",
            "Self-healing automation",
            "SSO & RBAC",
            "Custom retention",
            "SLA guarantee",
            "Dedicated support",
        ],
    },
}


def get_plan_config(plan: str) -> Dict:
    """Get configuration for a specific plan."""
    return PLANS.get(plan, PLANS[PlanTier.FREE])


def get_project_limit(plan: str) -> int:
    """Get project limit for a plan."""
    config = get_plan_config(plan)
    return config.get("project_limit", 1)


def get_daily_run_limit(plan: str) -> int:
    """Get daily run limit for a plan."""
    config = get_plan_config(plan)
    limit = config.get("daily_run_limit")
    return limit if limit is not None else 999_999_999


# Per-tier rate limits (requests per window)
RATE_LIMITS: Dict[str, Dict[str, int]] = {
    PlanTier.FREE: {"requests_per_minute": 30, "window_seconds": 60},
    PlanTier.PRO: {"requests_per_minute": 200, "window_seconds": 60},
    PlanTier.TEAM: {"requests_per_minute": 1000, "window_seconds": 60},
    PlanTier.ENTERPRISE: {"requests_per_minute": 10000, "window_seconds": 60},
}


def get_rate_limit(plan: str) -> Dict[str, int]:
    """Get rate limit config for a plan tier. Defaults to FREE tier."""
    return RATE_LIMITS.get(plan, RATE_LIMITS[PlanTier.FREE])


def get_stripe_price_id(plan: str, env_vars: Dict[str, str], annual: bool = False) -> str:
    """Get Stripe Price ID for a plan from environment variables."""
    suffix = "_ANNUAL" if annual else "_MONTHLY"
    if plan == PlanTier.PRO:
        return env_vars.get(f"STRIPE_PRICE_ID_PRO{suffix}", "")
    elif plan == PlanTier.TEAM:
        return env_vars.get(f"STRIPE_PRICE_ID_TEAM{suffix}", "")
    else:
        raise ValueError(f"No Stripe price ID configured for plan: {plan}")
