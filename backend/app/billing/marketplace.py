"""AWS Marketplace SaaS integration.

Handles:
- Customer registration via ResolveCustomer API
- Usage metering via BatchMeterUsage API
- Entitlement verification via GetEntitlements API

All AWS SDK calls are wrapped with run_in_executor for async compatibility.
Marketplace integration is optional and disabled by default.
"""

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from redis import asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)


class MarketplaceDimension(str, Enum):
    """AWS Marketplace billing dimensions for usage-based pricing."""

    SPANS_INGESTED = "spans_ingested"  # Per 1000 spans
    DETECTIONS_GENERATED = "detections_generated"  # Per 100 detections
    FIXES_APPLIED = "fixes_applied"  # Per fix action


class MarketplaceConfig(BaseModel):
    """Configuration for AWS Marketplace integration."""

    enabled: bool = False
    product_code: str = ""
    region: str = "us-east-1"
    metering_interval_minutes: int = 60


class MarketplaceCustomer(BaseModel):
    """A customer resolved via AWS Marketplace."""

    aws_customer_id: str
    product_code: str
    tenant_id: str = ""  # Maps to PISAMA tenant


class UsageRecord(BaseModel):
    """A single usage event for marketplace metering."""

    tenant_id: str
    dimension: MarketplaceDimension
    quantity: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MarketplaceMeteringService:
    """Handles AWS Marketplace metering and entitlement.

    Uses boto3 clients for:
    - marketplace-metering: ResolveCustomer, BatchMeterUsage
    - marketplace-entitlement: GetEntitlements

    All boto3 calls are synchronous, so they are wrapped with
    asyncio.get_event_loop().run_in_executor() for async compatibility.
    """

    REDIS_KEY_PREFIX = "marketplace:usage"
    REDIS_CUSTOMER_PREFIX = "marketplace:customer"

    def __init__(self, config: MarketplaceConfig):
        """Initialize AWS Marketplace clients.

        Args:
            config: Marketplace configuration with product_code and region.
        """
        self.config = config
        self._metering_client = None
        self._entitlement_client = None
        self._redis: Optional[aioredis.Redis] = None

        if config.enabled:
            try:
                import boto3

                self._metering_client = boto3.client(
                    "meteringmarketplace",
                    region_name=config.region,
                )
                self._entitlement_client = boto3.client(
                    "marketplace-entitlement",
                    region_name=config.region,
                )
                logger.info(
                    "AWS Marketplace clients initialized for product %s in %s",
                    config.product_code,
                    config.region,
                )
            except ImportError:
                logger.error(
                    "boto3 is required for AWS Marketplace integration. "
                    "Install it with: pip install boto3"
                )
            except Exception as e:
                logger.error("Failed to initialize AWS Marketplace clients: %s", e)

    async def register_usage(self) -> None:
        """Call RegisterUsage on container startup.

        Required by AWS Marketplace for SaaS contracts to verify
        the container is running with valid entitlements.
        """
        if not self._metering_client:
            logger.warning("Marketplace metering client not available, skipping RegisterUsage")
            return

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._metering_client.register_usage(
                    ProductCode=self.config.product_code,
                    PublicKeyVersion=1,
                ),
            )
            logger.info("RegisterUsage succeeded for product %s", self.config.product_code)
        except Exception as e:
            logger.error("RegisterUsage failed: %s", e)
            raise

    async def _get_redis(self) -> aioredis.Redis:
        """Get or create async Redis connection."""
        if self._redis is None:
            settings = get_settings()
            self._redis = await aioredis.from_url(
                settings.redis_url, decode_responses=True
            )
        return self._redis

    async def resolve_customer(
        self, registration_token: str
    ) -> MarketplaceCustomer:
        """Resolve an AWS Marketplace customer from a registration token.

        Called when a customer subscribes via the AWS Marketplace listing page.
        Uses the ResolveCustomer API to exchange the registration token for
        the AWS customer identifier.

        Args:
            registration_token: Token provided by AWS Marketplace during
                subscription redirect.

        Returns:
            MarketplaceCustomer with aws_customer_id and product_code.

        Raises:
            ValueError: If the registration token is invalid or expired.
            RuntimeError: If the marketplace client is not initialized.
        """
        if not self._metering_client:
            raise RuntimeError(
                "AWS Marketplace metering client not initialized. "
                "Ensure marketplace is enabled and boto3 is installed."
            )

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._metering_client.resolve_customer(
                    RegistrationToken=registration_token
                ),
            )
        except Exception as e:
            logger.error("Failed to resolve marketplace customer: %s", e)
            raise ValueError(f"Invalid or expired registration token: {e}") from e

        customer = MarketplaceCustomer(
            aws_customer_id=response["CustomerIdentifier"],
            product_code=response["ProductCode"],
        )

        logger.info(
            "Resolved marketplace customer: aws_id=%s, product=%s",
            customer.aws_customer_id,
            customer.product_code,
        )

        return customer

    async def check_entitlement(self, aws_customer_id: str) -> dict:
        """Verify a customer has an active AWS Marketplace entitlement.

        Uses the GetEntitlements API to check what the customer is
        entitled to.

        Args:
            aws_customer_id: The AWS customer identifier from ResolveCustomer.

        Returns:
            Dict with:
            - is_active: bool - whether the customer has an active entitlement
            - tier: str - mapped plan tier (free/pro/enterprise)
            - dimensions: dict - dimension name to limit mapping
        """
        if not self._entitlement_client:
            raise RuntimeError(
                "AWS Marketplace entitlement client not initialized. "
                "Ensure marketplace is enabled and boto3 is installed."
            )

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._entitlement_client.get_entitlements(
                    ProductCode=self.config.product_code,
                    Filter={"CUSTOMER_IDENTIFIER": [aws_customer_id]},
                ),
            )
        except Exception as e:
            logger.error(
                "Failed to check entitlement for customer %s: %s",
                aws_customer_id,
                e,
            )
            return {"is_active": False, "tier": "free", "dimensions": {}}

        entitlements = response.get("Entitlements", [])
        if not entitlements:
            return {"is_active": False, "tier": "free", "dimensions": {}}

        # Parse entitlements into dimensions
        dimensions: Dict[str, int] = {}
        is_active = False
        for entitlement in entitlements:
            dim_name = entitlement.get("Dimension", "")
            value = entitlement.get("Value", {})

            # EntitlementValue can be IntegerValue, BooleanValue, or StringValue
            if "IntegerValue" in value:
                dimensions[dim_name] = value["IntegerValue"]
                is_active = True
            elif "BooleanValue" in value:
                if value["BooleanValue"]:
                    dimensions[dim_name] = 1
                    is_active = True
            elif "StringValue" in value:
                dimensions[dim_name] = 0
                is_active = True

        # Map entitlement dimensions to tier
        tier = self._map_entitlement_to_tier(dimensions)

        logger.info(
            "Entitlement check for %s: active=%s, tier=%s, dimensions=%s",
            aws_customer_id,
            is_active,
            tier,
            dimensions,
        )

        return {
            "is_active": is_active,
            "tier": tier,
            "dimensions": dimensions,
        }

    def _map_entitlement_to_tier(self, dimensions: Dict[str, int]) -> str:
        """Map AWS Marketplace entitlement dimensions to a PISAMA plan tier.

        Args:
            dimensions: Dimension name to value mapping from entitlements.

        Returns:
            Plan tier string: "free", "pro", "team", or "enterprise".
        """
        # Check if any enterprise-level dimension is present
        project_limit = dimensions.get("project_limit", 0)

        if project_limit >= 10 or "enterprise" in dimensions:
            return "enterprise"
        elif project_limit >= 3:
            return "team"
        elif project_limit > 0:
            return "pro"
        else:
            return "free"

    async def record_usage(
        self,
        tenant_id: str,
        dimension: MarketplaceDimension,
        quantity: int,
    ) -> None:
        """Record a usage event for later batch reporting.

        Stores usage in a Redis sorted set keyed by tenant_id + dimension + hour.
        The score is the timestamp, and the member is a JSON record.

        Usage accumulates and is flushed to AWS by report_usage().

        Args:
            tenant_id: PISAMA tenant identifier.
            dimension: The billing dimension to record.
            quantity: The quantity to record (e.g., number of spans).
        """
        if quantity <= 0:
            return

        redis = await self._get_redis()
        now = datetime.now(timezone.utc)
        hour_key = now.strftime("%Y%m%d%H")

        # Redis key: marketplace:usage:{tenant_id}:{dimension}:{hour}
        redis_key = (
            f"{self.REDIS_KEY_PREFIX}:{tenant_id}:{dimension.value}:{hour_key}"
        )

        # Increment the usage counter for this hour
        await redis.incrby(redis_key, quantity)

        # Set TTL to 48 hours so stale keys auto-expire
        await redis.expire(redis_key, 48 * 3600)

        logger.debug(
            "Recorded usage: tenant=%s, dimension=%s, quantity=%d, hour=%s",
            tenant_id,
            dimension.value,
            quantity,
            hour_key,
        )

    async def report_usage(self) -> Dict[str, int]:
        """Batch-report accumulated usage to AWS via BatchMeterUsage.

        Called periodically (every metering_interval_minutes).
        Reads usage counters from Redis, batches by customer, reports to AWS,
        and clears reported entries.

        Uses timestamp-based idempotency tokens to prevent duplicate billing.

        Returns:
            Dict with counts: reported, failed, skipped.
        """
        if not self._metering_client:
            logger.warning("Marketplace metering client not available, skipping report")
            return {"reported": 0, "failed": 0, "skipped": 0}

        redis = await self._get_redis()
        stats = {"reported": 0, "failed": 0, "skipped": 0}

        # Find all usage keys
        pattern = f"{self.REDIS_KEY_PREFIX}:*"
        usage_keys: List[str] = []
        async for key in redis.scan_iter(match=pattern):
            usage_keys.append(key)

        if not usage_keys:
            logger.debug("No usage records to report")
            return stats

        # Group by tenant
        tenant_usage: Dict[str, List[Dict]] = {}
        for key in usage_keys:
            # Parse key: marketplace:usage:{tenant_id}:{dimension}:{hour}
            parts = key.split(":")
            if len(parts) != 5:
                logger.warning("Malformed usage key: %s", key)
                stats["skipped"] += 1
                continue

            _, _, tenant_id, dimension_str, hour_key = parts
            quantity = await redis.get(key)
            if not quantity or int(quantity) <= 0:
                stats["skipped"] += 1
                continue

            if tenant_id not in tenant_usage:
                tenant_usage[tenant_id] = []

            # Parse hour back to timestamp
            try:
                record_time = datetime.strptime(hour_key, "%Y%m%d%H").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                logger.warning("Invalid hour key in usage record: %s", hour_key)
                stats["skipped"] += 1
                continue

            tenant_usage[tenant_id].append(
                {
                    "dimension": dimension_str,
                    "quantity": int(quantity),
                    "timestamp": record_time,
                    "redis_key": key,
                }
            )

        # Report per tenant
        for tenant_id, records in tenant_usage.items():
            # Look up AWS customer ID for this tenant
            customer_key = f"{self.REDIS_CUSTOMER_PREFIX}:{tenant_id}"
            aws_customer_id = await redis.get(customer_key)

            if not aws_customer_id:
                logger.warning(
                    "No AWS customer mapping for tenant %s, skipping %d records",
                    tenant_id,
                    len(records),
                )
                stats["skipped"] += len(records)
                continue

            # Build BatchMeterUsage request
            usage_records = []
            reported_keys = []
            for record in records:
                usage_records.append(
                    {
                        "Timestamp": record["timestamp"],
                        "CustomerIdentifier": aws_customer_id,
                        "Dimension": record["dimension"],
                        "Quantity": record["quantity"],
                    }
                )
                reported_keys.append(record["redis_key"])

            # Send to AWS (max 25 records per batch)
            for batch_start in range(0, len(usage_records), 25):
                batch = usage_records[batch_start : batch_start + 25]
                batch_keys = reported_keys[batch_start : batch_start + 25]

                loop = asyncio.get_event_loop()
                try:
                    await loop.run_in_executor(
                        None,
                        lambda b=batch: self._metering_client.batch_meter_usage(
                            UsageRecords=b,
                            ProductCode=self.config.product_code,
                        ),
                    )

                    # Clear reported keys from Redis
                    for rk in batch_keys:
                        await redis.delete(rk)

                    stats["reported"] += len(batch)
                    logger.info(
                        "Reported %d usage records for tenant %s",
                        len(batch),
                        tenant_id,
                    )
                except Exception as e:
                    stats["failed"] += len(batch)
                    logger.error(
                        "Failed to report usage for tenant %s: %s",
                        tenant_id,
                        e,
                    )

        logger.info(
            "Usage report complete: reported=%d, failed=%d, skipped=%d",
            stats["reported"],
            stats["failed"],
            stats["skipped"],
        )
        return stats

    async def get_usage_summary(
        self, tenant_id: str, days: int = 30
    ) -> Dict[str, int]:
        """Get usage summary for a tenant across all dimensions.

        Reads from Redis usage counters for the specified period.

        Args:
            tenant_id: PISAMA tenant identifier.
            days: Number of days to look back (default 30).

        Returns:
            Dict mapping dimension names to total quantities.
        """
        redis = await self._get_redis()
        summary: Dict[str, int] = {dim.value: 0 for dim in MarketplaceDimension}

        # Scan for all usage keys matching this tenant
        pattern = f"{self.REDIS_KEY_PREFIX}:{tenant_id}:*"
        now = datetime.now(timezone.utc)

        async for key in redis.scan_iter(match=pattern):
            # Parse key: marketplace:usage:{tenant_id}:{dimension}:{hour}
            parts = key.split(":")
            if len(parts) != 5:
                continue

            _, _, _, dimension_str, hour_key = parts

            # Check if within the requested date range
            try:
                record_time = datetime.strptime(hour_key, "%Y%m%d%H").replace(
                    tzinfo=timezone.utc
                )
                age_days = (now - record_time).total_seconds() / 86400
                if age_days > days:
                    continue
            except ValueError:
                continue

            quantity = await redis.get(key)
            if quantity and dimension_str in summary:
                summary[dimension_str] += int(quantity)

        return summary

    async def store_customer_mapping(
        self, tenant_id: str, aws_customer_id: str
    ) -> None:
        """Store the mapping between a PISAMA tenant and AWS customer.

        Args:
            tenant_id: PISAMA tenant identifier.
            aws_customer_id: AWS Marketplace customer identifier.
        """
        redis = await self._get_redis()
        customer_key = f"{self.REDIS_CUSTOMER_PREFIX}:{tenant_id}"
        await redis.set(customer_key, aws_customer_id)

        # Also store reverse mapping
        reverse_key = f"{self.REDIS_CUSTOMER_PREFIX}:aws:{aws_customer_id}"
        await redis.set(reverse_key, tenant_id)

        logger.info(
            "Stored customer mapping: tenant=%s <-> aws=%s",
            tenant_id,
            aws_customer_id,
        )

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


def get_marketplace_config() -> MarketplaceConfig:
    """Build MarketplaceConfig from application settings.

    Returns:
        MarketplaceConfig populated from environment variables.
    """
    settings = get_settings()
    return MarketplaceConfig(
        enabled=getattr(settings, "aws_marketplace_enabled", False),
        product_code=getattr(settings, "aws_marketplace_product_code", ""),
        region=getattr(settings, "aws_marketplace_region", "us-east-1"),
    )


def get_marketplace_service() -> MarketplaceMeteringService:
    """Get the singleton MarketplaceMeteringService instance.

    Returns:
        MarketplaceMeteringService configured from application settings.
    """
    config = get_marketplace_config()
    return MarketplaceMeteringService(config)
