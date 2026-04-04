"""Elin — Multi-framework migrator.

Tests that Pisama correctly auto-detects frameworks from OTEL attributes.
Sends traces styled as CrewAI, Bedrock, and generic Anthropic.
"""

import asyncio
import logging

from ..base import SyntheticCustomer
from .. import otel_factory

logger = logging.getLogger(__name__)


class ElinAgent(SyntheticCustomer):
    name = "elin"
    description = "Multi-framework migrator — tests framework auto-detection"

    async def run_scenario(self) -> None:
        tp = self.tenant_path

        # --- 1. Ingest CrewAI trace ---
        logger.info("[elin] Ingesting CrewAI trace")
        crewai_payload = otel_factory.crewai_trace()
        await self.post(tp("/traces/ingest"), json=crewai_payload)

        # --- 2. Ingest Bedrock trace ---
        logger.info("[elin] Ingesting Bedrock trace")
        bedrock_payload = otel_factory.bedrock_trace()
        await self.post(tp("/traces/ingest"), json=bedrock_payload)

        # --- 3. Ingest generic Anthropic trace ---
        logger.info("[elin] Ingesting generic Anthropic trace")
        anthropic_payload = otel_factory.generic_anthropic_trace()
        await self.post(tp("/traces/ingest"), json=anthropic_payload)

        await asyncio.sleep(2)

        # --- 4. Query all traces ---
        logger.info("[elin] Querying traces")
        traces = await self.get(tp("/traces"))
        trace_list = traces.get("traces", [])
        self.assert_gte("three_traces_ingested", len(trace_list), 3)

        # --- 5. Verify framework detection ---
        frameworks = {t.get("framework", "unknown") for t in trace_list}
        logger.info("[elin] Detected frameworks: %s", frameworks)

        self.assert_true(
            "crewai_framework_detected",
            "crewai" in frameworks,
        )
        self.assert_true(
            "bedrock_framework_detected",
            "bedrock" in frameworks,
        )
        self.assert_true(
            "anthropic_framework_detected",
            "anthropic" in frameworks,
        )

        # --- 6. Verify agent extraction per framework ---
        for trace in trace_list:
            trace_id = trace["id"]
            try:
                states = await self.get(tp(f"/traces/{trace_id}/states"))
                if isinstance(states, list) and len(states) > 0:
                    for state in states:
                        agent_id = state.get("agent_id", "")
                        self.assert_true(
                            f"trace_{trace_id[:8]}_agent_extracted",
                            len(agent_id) > 0,
                        )
            except Exception as exc:
                logger.info("[elin] States query for %s: %s", trace_id[:8], exc)

        # --- 7. Analyze CrewAI trace ---
        crewai_traces = [t for t in trace_list if t.get("framework") == "crewai"]
        if crewai_traces:
            trace_id = crewai_traces[0]["id"]
            logger.info("[elin] Analyzing CrewAI trace %s", trace_id[:8])
            try:
                analysis = await self.post(tp(f"/traces/{trace_id}/analyze"))
                self.assert_true("crewai_analysis_ran", analysis is not None)
            except Exception as exc:
                logger.info("[elin] CrewAI analysis: %s", exc)

        # --- 8. AutoGen trace ---
        logger.info("[elin] Ingesting AutoGen trace")
        autogen_payload = otel_factory.autogen_trace()
        await self.post(tp("/traces/ingest"), json=autogen_payload)

        # --- 9. Dify trace ---
        logger.info("[elin] Ingesting Dify trace")
        dify_payload = otel_factory.dify_trace()
        await self.post(tp("/traces/ingest"), json=dify_payload)

        await asyncio.sleep(1)

        # --- 10. Verify new frameworks detected ---
        traces_v2 = await self.get(tp("/traces"))
        all_frameworks = {t.get("framework", "unknown") for t in traces_v2.get("traces", [])}
        logger.info("[elin] All frameworks after additions: %s", all_frameworks)

        self.assert_true("autogen_detected", "autogen" in all_frameworks)
        self.assert_true("dify_detected", "dify" in all_frameworks)

        # --- 11. Concurrent ingest test ---
        logger.info("[elin] Testing concurrent trace ingestion")
        concurrent_payloads = [
            otel_factory.generic_anthropic_trace(),
            otel_factory.crewai_trace(),
            otel_factory.bedrock_trace(),
        ]
        results = await asyncio.gather(*[
            self.post(tp("/traces/ingest"), json=p)
            for p in concurrent_payloads
        ], return_exceptions=True)
        successes = sum(1 for r in results if not isinstance(r, Exception))
        self.assert_eq("concurrent_ingest_all_succeed", successes, 3)

        logger.info("[elin] Scenario complete: tested %d frameworks, concurrent ingest OK", len(all_frameworks))
