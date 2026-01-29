"""Redis Pub/Sub utilities for real-time events."""

import json
import logging
from typing import Any, Dict, AsyncGenerator, Optional
from redis import asyncio as aioredis
from redis.exceptions import RedisError
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


async def get_redis_connection() -> aioredis.Redis:
    """
    Get an async Redis connection.

    Returns:
        Redis connection instance
    """
    return await aioredis.from_url(settings.redis_url, decode_responses=True)


async def publish_event(channel: str, data: Dict[str, Any]) -> bool:
    """
    Publish an event to a Redis channel.

    Args:
        channel: Redis channel name (e.g., "execution:tenant123")
        data: Event data to publish (will be JSON serialized)

    Returns:
        True if published successfully, False otherwise
    """
    try:
        redis = await get_redis_connection()
        message = json.dumps(data)
        await redis.publish(channel, message)
        await redis.close()
        logger.debug(f"Published event to {channel}: {data}")
        return True
    except RedisError as e:
        logger.error(f"Failed to publish event to {channel}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error publishing event: {e}")
        return False


async def subscribe_events(channel: str) -> AsyncGenerator[str, None]:
    """
    Subscribe to a Redis channel and yield events as SSE-formatted strings.

    Args:
        channel: Redis channel name to subscribe to

    Yields:
        SSE-formatted event strings (e.g., "data: {...}\n\n")
    """
    redis: Optional[aioredis.Redis] = None
    pubsub: Optional[aioredis.client.PubSub] = None

    try:
        redis = await get_redis_connection()
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        logger.info(f"Subscribed to Redis channel: {channel}")

        # Yield initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'channel': channel})}\n\n"

        # Listen for messages
        async for message in pubsub.listen():
            if message["type"] == "message":
                # Format as SSE event
                yield f"data: {message['data']}\n\n"

    except RedisError as e:
        logger.error(f"Redis error in subscribe_events: {e}")
        error_event = json.dumps({"type": "error", "message": str(e)})
        yield f"data: {error_event}\n\n"

    except Exception as e:
        logger.error(f"Unexpected error in subscribe_events: {e}")
        error_event = json.dumps({"type": "error", "message": "Internal server error"})
        yield f"data: {error_event}\n\n"

    finally:
        # Cleanup
        if pubsub:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
                logger.info(f"Unsubscribed from Redis channel: {channel}")
            except Exception as e:
                logger.error(f"Error during pubsub cleanup: {e}")

        if redis:
            try:
                await redis.close()
            except Exception as e:
                logger.error(f"Error during redis cleanup: {e}")
