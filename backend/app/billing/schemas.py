"""
Billing Schemas - Pydantic models for billing API

Defines request/response models for billing endpoints.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from .constants import PlanTier, SubscriptionStatus


class PlanInfo(BaseModel):
    """Information about a pricing plan."""
    name: PlanTier
    display_name: str
    price_monthly: Optional[int]  # None for Enterprise
    project_limit: Optional[int]  # None for unlimited
    retention_days: Optional[int]
    team_limit: Optional[int]
    daily_run_limit: Optional[int]
    alerts_per_day: Optional[int]
    features: List[str]


class CheckoutRequest(BaseModel):
    """Request to create a Stripe Checkout session."""
    plan: PlanTier = Field(..., description="Plan to subscribe to (pro or team)")
    annual: bool = Field(False, description="Whether to use annual billing")
    success_url: Optional[str] = Field(None, description="URL to redirect after success")
    cancel_url: Optional[str] = Field(None, description="URL to redirect on cancel")

    class Config:
        json_schema_extra = {
            "example": {
                "plan": "pro",
                "annual": False,
                "success_url": "https://app.pisama.ai/billing/success",
                "cancel_url": "https://app.pisama.ai/billing/cancel"
            }
        }


class CheckoutResponse(BaseModel):
    """Response with Stripe Checkout session URL."""
    checkout_url: str = Field(..., description="Stripe Checkout URL to redirect user to")
    session_id: str = Field(..., description="Stripe Checkout session ID")


class PortalResponse(BaseModel):
    """Response with Stripe Customer Portal URL."""
    portal_url: str = Field(..., description="Stripe Customer Portal URL")


class UsageInfo(BaseModel):
    """Current usage statistics."""
    project_count: int = Field(..., description="Projects used")
    project_limit: int = Field(..., description="Project limit for current plan")
    daily_runs: int = Field(..., description="Agent runs today")
    daily_run_limit: int = Field(..., description="Daily run limit for current plan")


class BillingStatus(BaseModel):
    """Complete billing status for a tenant."""
    plan: PlanTier
    status: SubscriptionStatus = Field(..., description="Subscription status")
    current_period_end: Optional[datetime] = Field(None, description="When current billing period ends")
    cancel_at_period_end: bool = Field(False, description="Whether subscription will cancel at period end")
    usage: UsageInfo

    class Config:
        json_schema_extra = {
            "example": {
                "plan": "pro",
                "status": "active",
                "current_period_end": "2026-04-01T00:00:00Z",
                "cancel_at_period_end": False,
                "usage": {
                    "project_count": 2,
                    "project_limit": 3,
                    "daily_runs": 120,
                    "daily_run_limit": 500
                }
            }
        }


class WebhookEvent(BaseModel):
    """Stripe webhook event payload."""
    type: str = Field(..., description="Event type (e.g., checkout.session.completed)")
    data: dict = Field(..., description="Event data")
