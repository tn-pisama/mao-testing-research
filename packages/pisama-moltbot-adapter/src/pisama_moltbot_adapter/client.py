"""WebSocket client for Moltbot Gateway."""

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Optional

import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


class MoltbotClient:
    """WebSocket client for observing Moltbot Gateway events.

    Connects to the Moltbot gateway WebSocket control plane to tap into
    agent execution events, tool calls, and state changes.
    """

    def __init__(self, gateway_url: str = "ws://127.0.0.1:18789"):
        """Initialize the Moltbot client.

        Args:
            gateway_url: WebSocket URL of the Moltbot gateway
        """
        self.gateway_url = gateway_url
        self.ws: Optional[WebSocketClientProtocol] = None
        self._running = False

    async def connect(self) -> None:
        """Establish WebSocket connection to Moltbot gateway."""
        logger.info(f"Connecting to Moltbot gateway at {self.gateway_url}")
        self.ws = await websockets.connect(self.gateway_url)
        self._running = True
        logger.info("Connected to Moltbot gateway")

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        self._running = False
        if self.ws:
            await self.ws.close()
            self.ws = None
        logger.info("Disconnected from Moltbot gateway")

    async def subscribe_to_events(
        self, event_types: Optional[list[str]] = None
    ) -> None:
        """Subscribe to specific event types.

        Args:
            event_types: List of event types to subscribe to.
                        If None, subscribes to all events.
        """
        if not self.ws:
            raise RuntimeError("Not connected. Call connect() first.")

        subscription_msg = {
            "type": "subscribe",
            "events": event_types or ["*"],
        }
        await self.ws.send(json.dumps(subscription_msg))
        logger.info(f"Subscribed to events: {event_types or ['all']}")

    async def listen(self) -> AsyncIterator[dict[str, Any]]:
        """Listen for events from Moltbot gateway.

        Yields:
            Event dictionaries from the gateway
        """
        if not self.ws:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            async for message in self.ws:
                if isinstance(message, bytes):
                    message = message.decode("utf-8")

                try:
                    event = json.loads(message)
                    yield event
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse message: {message}")
                    continue
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed by server")
            self._running = False
        except Exception as e:
            logger.error(f"Error listening to events: {e}")
            raise

    async def run(self) -> AsyncIterator[dict[str, Any]]:
        """Connect, subscribe, and start listening to events.

        Yields:
            Event dictionaries from the gateway
        """
        try:
            await self.connect()
            await self.subscribe_to_events()

            async for event in self.listen():
                yield event
        finally:
            await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if the client is currently connected."""
        return self.ws is not None and self._running
