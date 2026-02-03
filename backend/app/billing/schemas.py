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
    span_limit: Optional[int]  # None for unlimited
    project_limit: Optional[int]
    retention_days: Optional[int]
    team_limit: Optional[int]
    features: List[str]


class CheckoutRequest(BaseModel):
    """Request to create a Stripe Checkout session."""
    plan: PlanTier = Field(..., description="Plan to subscribe to (startup or growth)")
    success_url: Optional[str] = Field(None, description="URL to redirect after success")
    cancel_url: Optional[str] = Field(None, description="URL to redirect on cancel")

    class Config:
        json_schema_extra = {
            "example": {
                "plan": "startup",
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
    span_count: int = Field(..., description="Spans used in current period")
    span_limit: int = Field(..., description="Span limit for current plan")
    usage_percentage: float = Field(..., description="Percentage of limit used (0-100)")


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
                "plan": "startup",
                "status": "active",
                "current_period_end": "2026-03-01T00:00:00Z",
                "cancel_at_period_end": False,
                "usage": {
                    "span_count": 125000,
                    "span_limit": 250000,
                    "usage_percentage": 50.0
                }
            }
        }


class WebhookEvent(BaseModel):
    """Stripe webhook event payload."""
    type: str = Field(..., description="Event type (e.g., checkout.session.completed)")
    data: dict = Field(..., description="Event data")
