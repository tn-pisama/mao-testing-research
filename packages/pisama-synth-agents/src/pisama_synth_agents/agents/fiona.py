"""Fiona — First-time customer onboarding.

Tests the complete new customer journey: create account, get API key,
authenticate, ingest first trace, query results, run evaluation.
Validates that every step a real customer would take actually works.
"""

import asyncio
import logging

from ..base import SyntheticCustomer
from .. import otel_factory

logger = logging.getLogger(__name__)


class FionaAgent(SyntheticCustomer):
    name = "fiona"
    description = "First-time customer — full onboarding journey"

    async def run_scenario(self) -> None:
        tp = self.tenant_path

        # --- 1. Verify we have a working API key and JWT ---
        # (setup() already created tenant + authenticated)
        self.assert_true("has_api_key", self.api_key is not None and self.api_key.startswith("mao_"))
        self.assert_true("has_tenant_id", self.tenant_id is not None)
        self.assert_true("has_jwt", self.jwt is not None)

        # --- 2. Health check — first thing a customer would do ---
        logger.info("[fiona] Checking platform health")
        health = await self.get("/api/v1/health")
        self.assert_eq("health_status", health.get("status"), "healthy")
        self.assert_eq("db_healthy", health.get("database"), "healthy")
        self.assert_eq("redis_healthy", health.get("redis"), "healthy")

        # --- 3. Empty tenant — no traces yet ---
        logger.info("[fiona] Verifying empty tenant state")
        traces = await self.get(tp("/traces"))
        self.assert_eq("no_traces_initially", traces.get("total", -1), 0)

        # --- 4. Ingest first trace (the "hello world" moment) ---
        logger.info("[fiona] Ingesting first trace")
        payload = otel_factory.langgraph_clean(steps=3)
        result = await self.post(tp("/traces/ingest"), json=payload)
        self.assert_true("first_ingest_accepted", result is not None)

        await asyncio.sleep(1)

        # --- 5. Verify trace appears ---
        logger.info("[fiona] Verifying first trace visible")
        traces = await self.get(tp("/traces"))
        self.assert_eq("one_trace_exists", traces.get("total", 0), 1)
        first_trace = traces["traces"][0]
        self.assert_eq("trace_framework", first_trace.get("framework"), "langgraph")
        self.assert_eq("trace_completed", first_trace.get("status"), "completed")
        self.assert_true("trace_has_tokens", first_trace.get("total_tokens", 0) > 0)

        trace_id = first_trace["id"]

        # --- 6. Query trace states ---
        logger.info("[fiona] Querying trace states")
        states = await self.get(tp(f"/traces/{trace_id}/states"))
        self.assert_true("states_returned", isinstance(states, list) and len(states) > 0)

        # --- 7. Run analysis ---
        logger.info("[fiona] Analyzing trace")
        analysis = await self.post(tp(f"/traces/{trace_id}/analyze"))
        self.assert_true("analysis_has_detections_key", "detections" in analysis)
        self.assert_true("analysis_has_states_count", "analyzed_states" in analysis)

        # --- 8. Use the evaluate API ---
        logger.info("[fiona] Testing evaluate API")
        eval_result = await self.post("/api/v1/evaluate", json={
            "specification": {"text": "Explain how to print hello world in Python."},
            "output": {"text": (
                "To print hello world in Python, use the built-in print function: "
                "print('Hello, World!'). This outputs the text to standard output. "
                "Python's print function automatically adds a newline at the end."
            )},
        })
        self.assert_true("eval_has_passed", "passed" in eval_result)
        self.assert_true("eval_has_score", "score" in eval_result)
        self.assert_true("eval_has_detectors", len(eval_result.get("detectors_run", [])) > 0)
        self.assert_true("eval_score_reasonable", eval_result.get("score", 0) >= 0)

        # --- 9. Check detections list (may be empty for clean trace) ---
        logger.info("[fiona] Checking detections")
        detections = await self.get(tp("/detections"))
        self.assert_true("detections_list_works", "items" in detections)

        # --- 10. Check dashboard endpoint ---
        logger.info("[fiona] Checking dashboard data")
        dashboard = await self.get(tp("/dashboard?days=30"))
        self.assert_true("dashboard_has_traces", "traces" in dashboard)
        self.assert_true("dashboard_has_detections", "detections" in dashboard)

        logger.info("[fiona] Onboarding journey complete — all steps passed")
