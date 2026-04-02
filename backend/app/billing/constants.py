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
        "price_annual_monthly": None,
        "project_limit": 1,
        "retention_days": 7,
        "team_limit": 1,
        "daily_run_limit": 100,
        "alerts_per_day": 5,
        "features": [
            "1 project",
            "100 daily runs",
            "Core detectors",
            "Basic fix suggestions",
            "7-day retention",
            "Community support",
        ],
    },
    PlanTier.PRO: {
        "display_name": "Pro",
        "price_monthly": 29,
        "price_annual_monthly": 24,
        "project_limit": 10,
        "retention_days": 30,
        "team_limit": 1,
        "daily_run_limit": 5000,
        "alerts_per_day": 50,
        "features": [
            "10 projects",
            "5,000 daily runs",
            "All detectors",
            "API access",
            "Webhooks & Slack alerts",
            "30-day retention",
            "Email support",
        ],
    },
    PlanTier.TEAM: {
        "display_name": "Team",
        "price_monthly": 79,
        "price_annual_monthly": 66,
        "project_limit": 50,
        "retention_days": 90,
        "team_limit": 5,
        "daily_run_limit": 25000,
        "alerts_per_day": 500,
        "features": [
            "50 projects",
            "25,000 daily runs",
            "All detectors + ML tier",
            "5 team members",
            "SSO & RBAC",
            "Custom webhooks",
            "90-day retention",
            "Priority support",
        ],
    },
    PlanTier.ENTERPRISE: {
        "display_name": "Enterprise",
        "price_monthly": None,  # Custom pricing
        "price_annual_monthly": None,
        "project_limit": None,  # Unlimited
        "retention_days": None,  # Custom
        "team_limit": None,  # Unlimited
        "daily_run_limit": None,  # Unlimited
        "alerts_per_day": None,  # Unlimited
        "features": [
            "Unlimited projects",
            "Unlimited runs",
            "All detectors + ML + custom",
            "Unlimited team",
            "Self-healing automation",
            "SSO & RBAC",
            "SLA guarantee",
            "Dedicated support",
            "On-prem option",
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


# Default tenant settings per plan — persisted to Tenant.settings at creation
PLAN_DEFAULTS: Dict[str, Dict] = {
    PlanTier.FREE: {
        "retention_days": 7,
        "rate_limit_rpm": 30,
        "max_traces_daily": 100,
        "ml_detection": False,
        "advanced_evals": False,
        "auto_detection": True,
    },
    PlanTier.PRO: {
        "retention_days": 30,
        "rate_limit_rpm": 200,
        "max_traces_daily": 5000,
        "ml_detection": True,
        "advanced_evals": False,
        "auto_detection": True,
    },
    PlanTier.TEAM: {
        "retention_days": 90,
        "rate_limit_rpm": 1000,
        "max_traces_daily": 25000,
        "ml_detection": True,
        "advanced_evals": True,
        "auto_detection": True,
    },
}


def get_plan_defaults(plan: str) -> Dict:
    """Get default tenant settings for a plan tier."""
    return PLAN_DEFAULTS.get(plan, PLAN_DEFAULTS[PlanTier.FREE])


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


def get_plan_from_price_id(price_id: str) -> str:
    """Reverse-map a Stripe price ID to a plan name.

    Returns empty string if price ID is not recognized.
    """
    from app.config import get_settings
    settings = get_settings()
    mapping = {
        settings.stripe_price_id_pro_monthly: PlanTier.PRO,
        settings.stripe_price_id_pro_annual: PlanTier.PRO,
        settings.stripe_price_id_team_monthly: PlanTier.TEAM,
        settings.stripe_price_id_team_annual: PlanTier.TEAM,
    }
    # Filter out empty string keys (unconfigured price IDs)
    return mapping.get(price_id, "") if price_id else ""
