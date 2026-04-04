"""Ava — LangGraph team lead.

Tests the core pipeline: ingest OTEL traces, trigger detection, query results.
Sends clean traces, loop failures, and coordination failures.
"""

import asyncio
import logging

from ..base import SyntheticCustomer
from .. import otel_factory

logger = logging.getLogger(__name__)


class AvaAgent(SyntheticCustomer):
    name = "ava"
    description = "LangGraph team lead — core ingest/detect/query pipeline"

    async def run_scenario(self) -> None:
        tp = self.tenant_path

        # --- 1. Ingest a clean trace ---
        logger.info("[ava] Ingesting clean LangGraph trace")
        clean_payload = otel_factory.langgraph_clean()
        clean_result = await self.post(tp("/traces/ingest"), json=clean_payload)
        self.assert_true("clean_ingest_accepted", clean_result is not None)

        # --- 2. Ingest a loop trace ---
        logger.info("[ava] Ingesting loop failure trace")
        loop_payload = otel_factory.langgraph_loop(repeat_count=6)
        loop_result = await self.post(tp("/traces/ingest"), json=loop_payload)
        self.assert_true("loop_ingest_accepted", loop_result is not None)

        # --- 3. Ingest a coordination failure trace ---
        logger.info("[ava] Ingesting coordination failure trace")
        coord_payload = otel_factory.langgraph_coordination_failure()
        coord_result = await self.post(tp("/traces/ingest"), json=coord_payload)
        self.assert_true("coord_ingest_accepted", coord_result is not None)

        # Brief pause for async processing
        await asyncio.sleep(2)

        # --- 4. List traces and verify all 3 exist ---
        logger.info("[ava] Querying traces")
        traces = await self.get(tp("/traces"))
        trace_list = traces.get("traces", [])
        self.assert_gte("traces_created", len(trace_list), 3)

        # --- 5. Check frameworks detected ---
        frameworks = [t.get("framework", "unknown") for t in trace_list]
        self.assert_in("langgraph_detected", "langgraph", frameworks)

        # --- 6. Analyze traces for detections ---
        for trace in trace_list:
            trace_id = trace["id"]
            state_count = trace.get("state_count", 0)

            # All traces should have states
            if state_count > 0:
                states = await self.get(tp(f"/traces/{trace_id}/states"))
                self.assert_gt(
                    f"trace_{trace_id[:8]}_has_states",
                    len(states),
                    0,
                )

            # Try to trigger analysis
            try:
                analysis = await self.post(tp(f"/traces/{trace_id}/analyze"))
                detections = analysis.get("detections", [])
                detection_count = len(detections)

                # The loop trace should have detections
                if state_count >= 6:
                    self.assert_gt(
                        f"trace_{trace_id[:8]}_has_detections",
                        detection_count,
                        0,
                    )

                    det_types = [d.get("detection_type", "") for d in detections]
                    logger.info("[ava] Detection types for %s: %s", trace_id[:8], det_types)
            except Exception as exc:
                logger.info("[ava] Analysis response for %s: %s", trace_id[:8], exc)

        # --- 7. Check detection_count on trace list ---
        traces_after = await self.get(tp("/traces"))
        traces_with_detections = [
            t for t in traces_after.get("traces", [])
            if t.get("detection_count", 0) > 0
        ]
        self.assert_gt(
            "some_traces_have_detections",
            len(traces_with_detections),
            0,
        )

        # --- 8. Trace lifecycle: status should be "completed" ---
        for trace in traces_after.get("traces", []):
            self.assert_eq(
                f"trace_{trace['id'][:8]}_status_completed",
                trace.get("status"),
                "completed",
            )
            self.assert_true(
                f"trace_{trace['id'][:8]}_has_completed_at",
                trace.get("completed_at") is not None,
            )

        # --- 9. Tenant isolation: accessing another tenant's path should fail ---
        logger.info("[ava] Testing tenant isolation")
        fake_tenant_id = "00000000-0000-0000-0000-000000000000"
        client = await self._ensure_client()
        resp = await client.get(f"/api/v1/tenants/{fake_tenant_id}/traces")
        self.assert_true(
            "tenant_isolation_returns_403",
            resp.status_code == 403,
        )

        # --- 10. Rate limit probe: rapid requests ---
        logger.info("[ava] Testing rate limiting")
        ok_count = 0
        limited_count = 0
        for _ in range(30):
            r = await client.get(tp("/traces"))
            if r.status_code == 200:
                ok_count += 1
            elif r.status_code == 429:
                limited_count += 1
                break
        self.assert_true("rate_limit_probed", ok_count > 0)
        if limited_count > 0:
            logger.info("[ava] Rate limit hit after %d requests", ok_count)
        else:
            logger.info("[ava] No rate limit on GET /traces after %d requests", ok_count)

        logger.info("[ava] Scenario complete: %d traces, %d with detections",
                     len(trace_list), len(traces_with_detections))
