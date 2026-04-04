"""Gustav — Load and stress tester.

Ingests many traces rapidly, verifies pagination works under load,
checks response times don't degrade past acceptable thresholds.
"""

import asyncio
import logging
import time

from ..base import SyntheticCustomer
from .. import otel_factory

logger = logging.getLogger(__name__)

BATCH_SIZE = 10  # Traces per batch
BATCHES = 3      # Number of batches
MAX_ACCEPTABLE_MS = 3000  # 3s max for listing


class GustavAgent(SyntheticCustomer):
    name = "gustav"
    description = "Load tester — bulk ingest, pagination, response times"

    async def run_scenario(self) -> None:
        tp = self.tenant_path

        # --- 1. Bulk ingest ---
        total_ingested = 0
        for batch in range(BATCHES):
            logger.info("[gustav] Ingesting batch %d/%d (%d traces)", batch + 1, BATCHES, BATCH_SIZE)
            tasks = []
            for _ in range(BATCH_SIZE):
                payload = otel_factory.langgraph_clean(steps=4)
                tasks.append(self.post(tp("/traces/ingest"), json=payload))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successes = sum(1 for r in results if not isinstance(r, Exception))
            total_ingested += successes
            if batch < BATCHES - 1:
                await asyncio.sleep(1)

        self.assert_gte("bulk_ingest_count", total_ingested, BATCH_SIZE * BATCHES * 0.8)
        logger.info("[gustav] Ingested %d traces", total_ingested)

        await asyncio.sleep(2)

        # --- 2. Verify trace count ---
        traces = await self.get(tp("/traces"))
        self.assert_gte("trace_total", traces.get("total", 0), BATCH_SIZE * BATCHES * 0.8)

        # --- 3. Pagination works ---
        page1 = await self.get(tp("/traces"), params={"page": "1", "per_page": "5"})
        self.assert_eq("page1_size", len(page1.get("traces", [])), 5)
        self.assert_eq("page1_page", page1.get("page"), 1)

        page2 = await self.get(tp("/traces"), params={"page": "2", "per_page": "5"})
        self.assert_eq("page2_size", len(page2.get("traces", [])), 5)
        self.assert_eq("page2_page", page2.get("page"), 2)

        # Pages should have different traces
        p1_ids = {t["id"] for t in page1.get("traces", [])}
        p2_ids = {t["id"] for t in page2.get("traces", [])}
        self.assert_eq("pages_no_overlap", len(p1_ids & p2_ids), 0)

        # --- 4. Response time under load ---
        logger.info("[gustav] Measuring response times")
        times_ms = []
        for _ in range(5):
            start = time.monotonic()
            await self.get(tp("/traces"), params={"per_page": "20"})
            elapsed = (time.monotonic() - start) * 1000
            times_ms.append(elapsed)

        avg_ms = sum(times_ms) / len(times_ms)
        max_ms = max(times_ms)
        logger.info("[gustav] Response times: avg=%.0fms max=%.0fms", avg_ms, max_ms)
        self.assert_lt("avg_response_under_3s", avg_ms, MAX_ACCEPTABLE_MS)

        # --- 5. Analyze one trace and verify it works under load ---
        trace_id = page1["traces"][0]["id"]
        start = time.monotonic()
        analysis = await self.post(tp(f"/traces/{trace_id}/analyze"))
        analyze_ms = (time.monotonic() - start) * 1000
        self.assert_true("analyze_works_under_load", "detections" in analysis)
        logger.info("[gustav] Analyze under load: %.0fms", analyze_ms)

        # --- 6. Dashboard under load ---
        start = time.monotonic()
        dashboard = await self.get(tp("/dashboard?days=30"))
        dashboard_ms = (time.monotonic() - start) * 1000
        self.assert_true("dashboard_under_load", "traces" in dashboard)
        logger.info("[gustav] Dashboard under load: %.0fms", dashboard_ms)

        logger.info("[gustav] Load test complete: %d traces, avg response %.0fms",
                     total_ingested, avg_ms)
