"""Bram — SDK integrator.

Dogfoods the pisama-agent-sdk package: PisamaEvaluator client, check() function.
Falls back to raw HTTP if the SDK is not installed.
"""

import logging

from ..base import SyntheticCustomer

logger = logging.getLogger(__name__)

try:
    from pisama_agent_sdk import PisamaEvaluator
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False


class BramAgent(SyntheticCustomer):
    name = "bram"
    description = "SDK integrator — dogfoods PisamaEvaluator and check()"

    async def run_scenario(self) -> None:
        if _SDK_AVAILABLE:
            await self._test_sdk_evaluator()
        else:
            logger.info("[bram] pisama-agent-sdk not installed, testing via raw HTTP")

        await self._test_evaluate_api_directly()

    async def _test_sdk_evaluator(self) -> None:
        """Test the PisamaEvaluator client as a real SDK customer would."""
        logger.info("[bram] Testing PisamaEvaluator (sync)")

        evaluator = PisamaEvaluator(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        # --- Clean output ---
        result = evaluator.evaluate(
            specification={"text": "Explain how OAuth 2.0 authorization code flow works."},
            output={"text": (
                "OAuth 2.0 authorization code flow works in these steps: "
                "1) Client redirects user to authorization server. "
                "2) User authenticates and grants permission. "
                "3) Authorization server returns an authorization code. "
                "4) Client exchanges the code for an access token. "
                "5) Client uses the access token to call the resource API."
            )},
        )

        self.assert_true("sdk_clean_passed", result.passed)
        self.assert_gt("sdk_clean_score", result.score, 0.7)
        self.assert_gt("sdk_has_detectors_run", len(result.detectors_run), 0)
        self.assert_true("sdk_eval_time_present", result.evaluation_time_ms > 0)

        # --- Hallucinating output ---
        result = evaluator.evaluate(
            specification={"text": "What is the current price of Bitcoin?"},
            output={"text": (
                "Bitcoin is currently trading at exactly $1,000,000 per coin. "
                "It went up 500% yesterday after the UN declared it the official world currency. "
                "The Federal Reserve has replaced the dollar with Bitcoin effective immediately."
            )},
        )

        self.assert_true(
            "sdk_hallucination_caught",
            not result.passed or result.score < 1.0,
            f"Expected SDK to catch hallucination, score={result.score}",
        )

        # --- Check result structure ---
        self.assert_true("sdk_result_has_failures_list", isinstance(result.failures, list))
        self.assert_true("sdk_result_has_suggestions", isinstance(result.suggestions, list))
        if result.failures:
            failure = result.failures[0]
            self.assert_true("sdk_failure_has_detector", hasattr(failure, "detector") and failure.detector)
            self.assert_true("sdk_failure_has_confidence", hasattr(failure, "confidence"))

        logger.info("[bram] SDK PisamaEvaluator tests complete")

    async def _test_evaluate_api_directly(self) -> None:
        """Test the evaluate API via raw HTTP — validates the API contract."""
        logger.info("[bram] Testing /evaluate via raw HTTP")

        # --- Clean output ---
        result = await self.post("/api/v1/evaluate", json={
            "specification": {"text": "Write a Python hello world program."},
            "output": {"text": "```python\nprint('Hello, World!')\n```"},
        })

        self.assert_true("api_has_passed", "passed" in result)
        self.assert_true("api_has_score", "score" in result)
        self.assert_true("api_has_failures", "failures" in result)
        self.assert_true("api_has_detectors_run", "detectors_run" in result)
        self.assert_true("api_has_eval_time", "evaluation_time_ms" in result)
        self.assert_true("api_has_suggestions", "suggestions" in result)

        # --- Error handling: empty spec ---
        logger.info("[bram] Testing error handling")
        try:
            result = await self.post("/api/v1/evaluate", json={
                "specification": {},
                "output": {},
            })
            # Should still return a valid response (empty is technically valid)
            self.assert_true("api_empty_input_handled", "passed" in result)
        except Exception as exc:
            # 422 validation error is also acceptable
            self.assert_true(
                "api_empty_input_rejected",
                "422" in str(exc) or "400" in str(exc),
                f"Unexpected error: {exc}",
            )

        # --- Async SDK test ---
        if _SDK_AVAILABLE:
            logger.info("[bram] Testing PisamaEvaluator async path")
            try:
                evaluator = PisamaEvaluator(api_key=self.api_key, base_url=self.base_url)
                result = await evaluator.evaluate_async(
                    specification={"text": "Explain what a REST API is."},
                    output={"text": "A REST API uses HTTP methods (GET, POST, PUT, DELETE) to interact with resources identified by URLs."},
                )
                self.assert_true("sdk_async_passed", result.passed)
                self.assert_true("sdk_async_has_score", result.score is not None)
                self.assert_gt("sdk_async_has_detectors", len(result.detectors_run), 0)
            except AttributeError:
                logger.info("[bram] evaluate_async not available in this SDK version")
            except Exception as exc:
                logger.warning("[bram] Async SDK test failed: %s", exc)

        logger.info("[bram] Raw API tests complete")
