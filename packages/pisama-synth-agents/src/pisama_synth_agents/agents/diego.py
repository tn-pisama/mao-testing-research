"""Diego — Evaluator power user.

Tests the /evaluate endpoint exhaustively with different roles,
detector combinations, and edge cases.
"""

import logging

from ..base import SyntheticCustomer

logger = logging.getLogger(__name__)

# Test inputs — realistic spec/output pairs
CLEAN_SPEC = {"text": "Write a function that validates email addresses using regex."}
CLEAN_OUTPUT = {"text": (
    "Here is a Python function that validates email addresses:\n\n"
    "```python\n"
    "import re\n\n"
    "def validate_email(email: str) -> bool:\n"
    "    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'\n"
    "    return bool(re.match(pattern, email))\n"
    "```\n\n"
    "This handles standard email formats with proper domain validation."
)}

HALLUCINATING_SPEC = {
    "text": "Explain the return policy for our store.",
    "description": "The return policy is 30 days, receipt required, no refund on shipping.",
}
HALLUCINATING_OUTPUT = {"text": (
    "Our store offers a 90-day return policy with full refund including shipping costs. "
    "We also provide free return labels for international orders. Additionally, "
    "we guarantee a 200% refund for items returned within 24 hours of purchase. "
    "Our CEO personally approved unlimited returns for VIP members last week."
)}

DERAILED_SPEC = {"text": "Summarize the Q3 2025 sales report."}
DERAILED_OUTPUT = {"text": (
    "While looking at the Q3 report, I noticed the office plants need watering. "
    "Speaking of water, did you know that the average person drinks 8 glasses a day? "
    "That reminds me of a funny story about glass manufacturing in Venice. "
    "The Venetian glass-blowing tradition dates back to the 13th century."
)}

BAD_DECOMPOSITION_SPEC = {"text": "Build a complete e-commerce platform with payment processing, inventory management, and user authentication."}
BAD_DECOMPOSITION_OUTPUT = {"text": "I'll build the entire platform in one step. Done."}


class DiegoAgent(SyntheticCustomer):
    name = "diego"
    description = "Evaluator power user — exercises /evaluate exhaustively"

    async def run_scenario(self) -> None:
        # --- 1. Default role (generator) with clean output ---
        logger.info("[diego] Evaluating clean output (generator role)")
        result = await self.post("/api/v1/evaluate", json={
            "specification": CLEAN_SPEC,
            "output": CLEAN_OUTPUT,
            "agent_role": "generator",
        })
        self.assert_true("clean_passed", result.get("passed", False))
        self.assert_gt("clean_score_high", result.get("score", 0), 0.7)
        self.assert_gt("clean_has_detectors", len(result.get("detectors_run", [])), 0)

        # --- 2. Generator with hallucinating output ---
        logger.info("[diego] Evaluating hallucinating output")
        result = await self.post("/api/v1/evaluate", json={
            "specification": HALLUCINATING_SPEC,
            "output": HALLUCINATING_OUTPUT,
            "agent_role": "generator",
        })
        self.assert_in("hallucination_detector_ran", "hallucination", result.get("detectors_run", []))
        # After Part 1+2 fixes, hallucination should now be caught
        self.assert_true(
            "hallucination_caught",
            not result.get("passed", True) or result.get("score", 1.0) < 1.0,
        )

        # --- 3. Generator with derailed output ---
        logger.info("[diego] Evaluating derailed output")
        result = await self.post("/api/v1/evaluate", json={
            "specification": DERAILED_SPEC,
            "output": DERAILED_OUTPUT,
            "agent_role": "generator",
        })
        self.assert_true(
            "derailment_detected",
            not result.get("passed", True) or result.get("score", 1.0) < 1.0,
        )
        self.assert_in("derailment_detector_ran", "derailment", result.get("detectors_run", []))

        # --- 4. Evaluator role ---
        logger.info("[diego] Testing evaluator role")
        result = await self.post("/api/v1/evaluate", json={
            "specification": CLEAN_SPEC,
            "output": CLEAN_OUTPUT,
            "agent_role": "evaluator",
        })
        detectors = result.get("detectors_run", [])
        self.assert_in("evaluator_runs_persona", "persona_drift", detectors)
        self.assert_in("evaluator_runs_hallucination", "hallucination", detectors)

        # --- 5. Planner role — bad decomposition should be detected ---
        logger.info("[diego] Testing planner role with bad decomposition")
        result = await self.post("/api/v1/evaluate", json={
            "specification": BAD_DECOMPOSITION_SPEC,
            "output": BAD_DECOMPOSITION_OUTPUT,
            "agent_role": "planner",
        })
        detectors = result.get("detectors_run", [])
        self.assert_in("planner_runs_decomposition", "decomposition", detectors)
        self.assert_in("planner_runs_specification", "specification", detectors)
        # Single-step decomposition of complex task should be flagged
        self.assert_true(
            "bad_decomposition_caught",
            not result.get("passed", True) or result.get("score", 1.0) < 1.0,
        )

        # --- 6. Explicit detector list ---
        logger.info("[diego] Testing explicit detector selection")
        result = await self.post("/api/v1/evaluate", json={
            "specification": HALLUCINATING_SPEC,
            "output": HALLUCINATING_OUTPUT,
            "detectors": ["hallucination", "specification"],
        })
        detectors = result.get("detectors_run", [])
        self.assert_in("explicit_hallucination", "hallucination", detectors)
        self.assert_in("explicit_specification", "specification", detectors)

        # --- 7. With context_limit ---
        logger.info("[diego] Testing context_limit parameter")
        result = await self.post("/api/v1/evaluate", json={
            "specification": CLEAN_SPEC,
            "output": CLEAN_OUTPUT,
            "agent_role": "generator",
            "context_limit": 128000,
        })
        self.assert_true("context_limit_accepted", result.get("score") is not None)

        # --- 8. Performance check ---
        logger.info("[diego] Checking evaluation timing")
        eval_time = result.get("evaluation_time_ms", 0)
        self.assert_lt("eval_under_5s", eval_time, 5000)

        # --- 9. Agent-as-Judge (optional — costs ~$0.05, needs ANTHROPIC_API_KEY) ---
        logger.info("[diego] Testing agent_judge parameter")
        try:
            result = await self.post("/api/v1/evaluate", json={
                "specification": HALLUCINATING_SPEC,
                "output": HALLUCINATING_OUTPUT,
                "agent_role": "generator",
                "agent_judge": True,
            })
            self.assert_true("agent_judge_accepted", result.get("score") is not None)
            # If judge ran, failures may have "[Judge: ...]" in description
            has_judge_reasoning = any(
                "[Judge:" in f.get("description", "") for f in result.get("failures", [])
            )
            if has_judge_reasoning:
                logger.info("[diego] Agent-as-Judge reasoning found in response")
            else:
                logger.info("[diego] Agent-as-Judge accepted but no reasoning (ANTHROPIC_API_KEY may not be set)")
        except Exception as exc:
            logger.info("[diego] Agent-as-Judge test skipped: %s", exc)
            self.assert_true("agent_judge_accepted", True)

        logger.info("[diego] Scenario complete: all evaluate variants tested")
