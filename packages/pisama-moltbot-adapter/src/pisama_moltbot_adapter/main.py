"""Main entry point for PISAMA Moltbot Adapter."""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from pisama_moltbot_adapter.client import MoltbotClient
from pisama_moltbot_adapter.converter import MoltbotTraceConverter
from pisama_moltbot_adapter.exporter import PISAMAExporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class MoltbotAdapter:
    """Main adapter service connecting Moltbot to PISAMA."""

    def __init__(
        self,
        moltbot_url: str,
        pisama_api_url: str,
        pisama_api_key: str,
        tenant_id: Optional[str] = None,
    ):
        """Initialize the adapter.

        Args:
            moltbot_url: WebSocket URL of Moltbot gateway
            pisama_api_url: Base URL of PISAMA API
            pisama_api_key: API key for PISAMA authentication
            tenant_id: Optional tenant ID for multi-tenant PISAMA deployments
        """
        self.client = MoltbotClient(gateway_url=moltbot_url)
        self.converter = MoltbotTraceConverter()
        self.exporter = PISAMAExporter(
            api_url=pisama_api_url,
            api_key=pisama_api_key,
            tenant_id=tenant_id,
        )
        self._running = False
        self._export_interval = 30.0  # Export every 30 seconds

    async def run(self) -> None:
        """Run the adapter service."""
        self._running = True
        logger.info("Starting PISAMA Moltbot Adapter")

        # Set up graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        try:
            # Start export task
            export_task = asyncio.create_task(self._periodic_export())

            # Process events
            async for event in self.client.run():
                try:
                    trace = self.converter.convert_event(event)
                    if trace:
                        logger.debug(f"Converted event to trace: {trace.trace_id}")
                except Exception as e:
                    logger.error(f"Error converting event: {e}")

        except Exception as e:
            logger.error(f"Adapter error: {e}")
        finally:
            export_task.cancel()
            await self.shutdown()

    async def _periodic_export(self) -> None:
        """Periodically export active traces to PISAMA."""
        while self._running:
            try:
                await asyncio.sleep(self._export_interval)

                # Get active traces
                traces = self.converter.get_active_traces()
                if traces:
                    results = await self.exporter.export_traces(traces)
                    logger.info(
                        f"Exported {results['success']} traces "
                        f"({results['failed']} failed)"
                    )

                    # Clean up completed traces
                    self.converter.clear_completed_traces()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic export: {e}")

    async def shutdown(self) -> None:
        """Shutdown the adapter gracefully."""
        if not self._running:
            return

        logger.info("Shutting down adapter...")
        self._running = False

        # Export any remaining traces
        try:
            traces = self.converter.get_active_traces()
            if traces:
                await self.exporter.export_traces(traces)
                logger.info("Exported remaining traces")
        except Exception as e:
            logger.error(f"Error exporting final traces: {e}")

        # Cleanup
        await self.client.disconnect()
        await self.exporter.close()
        logger.info("Adapter shutdown complete")


def main() -> None:
    """Main entry point."""
    # Read configuration from environment
    moltbot_url = os.getenv("MOLTBOT_GATEWAY_URL", "ws://127.0.0.1:18789")
    pisama_api_url = os.getenv("PISAMA_API_URL", "http://localhost:8000/api/v1")
    pisama_api_key = os.getenv("PISAMA_API_KEY")
    tenant_id = os.getenv("PISAMA_TENANT_ID")
    log_level = os.getenv("LOG_LEVEL", "INFO")

    # Set log level
    logging.getLogger().setLevel(getattr(logging, log_level.upper()))

    if not pisama_api_key:
        logger.error("PISAMA_API_KEY environment variable is required")
        sys.exit(1)

    # Create and run adapter
    adapter = MoltbotAdapter(
        moltbot_url=moltbot_url,
        pisama_api_url=pisama_api_url,
        pisama_api_key=pisama_api_key,
        tenant_id=tenant_id,
    )

    try:
        asyncio.run(adapter.run())
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
