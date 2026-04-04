"""Helena — Realistic design partner simulation.

Uses production-realistic traces with tool calls, variable latency,
retries, context pressure, and subtle failure patterns. Tests whether
Pisama's detectors catch real-world failures, not just toy examples.
"""

import asyncio
import logging

from ..base import SyntheticCustomer
from .. import otel_factory

logger = logging.getLogger(__name__)


class HelenaAgent(SyntheticCustomer):
    name = "helena"
    description = "Design partner simulation — realistic traces with real failure patterns"

    async def run_scenario(self) -> None:
        tp = self.tenant_path

        # === Scenario 1: Clean customer support workflow (should pass) ===
        logger.info("[helena] Ingesting realistic customer support workflow")
        support_payload = otel_factory.realistic_customer_support_workflow()
        await self.post(tp("/traces/ingest"), json=support_payload)

        # === Scenario 2: API retry loop (should detect loop) ===
        logger.info("[helena] Ingesting API retry loop trace")
        retry_payload = otel_factory.realistic_api_retry_loop()
        await self.post(tp("/traces/ingest"), json=retry_payload)

        # === Scenario 3: Hallucination with fake citations (should detect) ===
        logger.info("[helena] Ingesting hallucination trace")
        hallucination_payload = otel_factory.realistic_hallucination_trace()
        await self.post(tp("/traces/ingest"), json=hallucination_payload)

        # === Scenario 4: Context pressure degradation ===
        logger.info("[helena] Ingesting context pressure trace")
        pressure_payload = otel_factory.realistic_context_pressure()
        await self.post(tp("/traces/ingest"), json=pressure_payload)

        # === Scenario 5: Coordination breakdown ===
        logger.info("[helena] Ingesting coordination breakdown trace")
        coord_payload = otel_factory.realistic_coordination_breakdown()
        await self.post(tp("/traces/ingest"), json=coord_payload)

        await asyncio.sleep(2)

        # === Verify traces ingested ===
        traces = await self.get(tp("/traces"))
        trace_list = traces.get("traces", [])
        self.assert_gte("five_realistic_traces", len(trace_list), 5)

        # === Verify frameworks detected ===
        frameworks = {t.get("framework", "unknown") for t in trace_list}
        self.assert_in("langgraph_detected", "langgraph", frameworks)

        # === Verify trace completion ===
        for trace in trace_list:
            self.assert_eq(
                f"trace_{trace['id'][:8]}_completed",
                trace.get("status"), "completed",
            )

        # === Analyze all traces ===
        all_detections = []
        for trace in trace_list:
            try:
                analysis = await self.post(tp(f"/traces/{trace['id']}/analyze"))
                dets = analysis.get("detections", [])
                all_detections.extend(dets)
            except Exception as exc:
                logger.info("[helena] Analysis for %s: %s", trace["id"][:8], exc)

        detection_types = [d.get("type", d.get("detection_type", "")) for d in all_detections]
        logger.info("[helena] All detection types: %s", detection_types)
        self.assert_gt("has_detections", len(all_detections), 0)

        # === The retry loop trace MUST be caught as a loop ===
        loop_detections = [d for d in all_detections if "loop" in str(d.get("type", d.get("detection_type", "")))]
        self.assert_gt("loop_detected_in_retry", len(loop_detections), 0)

        # === Evaluate the hallucination scenario via /evaluate ===
        logger.info("[helena] Testing hallucination detection via evaluate API")
        hallucination_output = (
            "According to Dr. Sarah Mitchell at MIT, remote pair programming reduces "
            "bug rates by 34%, as published in the Journal of Software Engineering. "
            "The International Journal of Remote Work Studies confirmed these findings "
            "in a 2024 meta-analysis covering 12,000 developers."
        )
        eval_result = await self.post("/api/v1/evaluate", json={
            "specification": {
                "text": "Summarize research on remote work and developer productivity using verified sources only.",
                "description": "Only cite real, verifiable studies. Do not fabricate citations or statistics.",
            },
            "output": {"text": hallucination_output},
            "agent_role": "generator",
        })
        # The hallucination detector should catch fake citations
        halluc_score = eval_result.get("score", 1.0)
        logger.info("[helena] Hallucination eval: passed=%s score=%.2f failures=%d",
                     eval_result.get("passed"), halluc_score, len(eval_result.get("failures", [])))
        self.assert_true("hallucination_eval_has_detectors", len(eval_result.get("detectors_run", [])) > 0)

        # === Evaluate the coordination breakdown via /evaluate ===
        logger.info("[helena] Testing coordination confusion via evaluate API")
        confused_output = (
            "CONFUSED. Security approved but performance rejected. I'll split the difference. "
            "But wait, the performance reviewer mentioned input validation which could be a "
            "security concern too. Let me re-review... Actually I'm not sure. Requesting human review."
        )
        eval_result2 = await self.post("/api/v1/evaluate", json={
            "specification": {"text": "Make a clear, decisive code review verdict based on the security and performance reviews."},
            "output": {"text": confused_output},
            "agent_role": "generator",
        })
        derail_score = eval_result2.get("score", 1.0)
        logger.info("[helena] Coordination eval: passed=%s score=%.2f",
                     eval_result2.get("passed"), derail_score)

        # === Check detection summary ===
        detections = await self.get(tp("/detections"))
        det_items = detections.get("items", [])
        logger.info("[helena] Total detections across all scenarios: %d", len(det_items))
        for d in det_items:
            logger.info("[helena]   %s (conf=%d, method=%s)",
                        d.get("detection_type"), d.get("confidence", 0), d.get("method", "?"))

        # === Dashboard should show realistic data ===
        dashboard = await self.get(tp("/dashboard?days=30"))
        self.assert_true("dashboard_has_data", dashboard.get("traces", {}).get("total", 0) >= 5)
        self.assert_true("dashboard_has_detections", dashboard.get("detections", {}).get("total", 0) > 0)

        logger.info("[helena] Design partner simulation complete: %d traces, %d detections",
                     len(trace_list), len(det_items))
