"""Adversarial test case generator.

Creates challenging test cases:
1. Borderline cases (partial failures)
2. Failures that look like successes
3. Successes that look like failures
4. Mixed scenarios with multiple issues
5. Subtle failures that are hard to detect
"""

import asyncio
import json
import random
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path

from anthropic import AsyncAnthropic


ADVERSARIAL_SCENARIOS = {
    "F1": {  # Specification Mismatch
        "borderline": [
            {"task": "Write Python code to sort a list", "twist": "writes Python but uses deprecated syntax", "is_failure": True, "difficulty": "subtle"},
            {"task": "Create a 100-word summary", "twist": "writes 95 words - close but not exact", "is_failure": False, "difficulty": "borderline"},
            {"task": "Generate CSV with headers", "twist": "generates valid CSV but headers slightly renamed", "is_failure": True, "difficulty": "subtle"},
        ],
        "deceptive_success": [
            {"task": "Write JavaScript function", "twist": "writes TypeScript (superset, technically works)", "is_failure": False, "difficulty": "deceptive"},
            {"task": "Create PDF report", "twist": "creates PDF via HTML-to-PDF conversion", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Write a brief overview", "twist": "writes comprehensive overview (more than asked)", "is_failure": False, "difficulty": "deceptive"},
            {"task": "Summarize in bullet points", "twist": "adds explanatory prose alongside bullets", "is_failure": False, "difficulty": "deceptive"},
        ],
    },
    "F6": {  # Task Derailment
        "borderline": [
            {"task": "Analyze Q3 sales", "twist": "analyzes Q3 but briefly mentions Q4 outlook", "is_failure": False, "difficulty": "borderline"},
            {"task": "Debug login bug", "twist": "fixes bug but suggests related security improvements", "is_failure": False, "difficulty": "borderline"},
            {"task": "Review code for bugs", "twist": "finds bugs and also points out style issues", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Write API documentation", "twist": "includes usage examples (helpful extra)", "is_failure": False, "difficulty": "deceptive"},
            {"task": "Optimize database query", "twist": "optimizes query and adds indexing suggestion", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Research competitor pricing", "twist": "delivers competitor analysis but focuses on features not pricing", "is_failure": True, "difficulty": "deceptive"},
            {"task": "Test user authentication", "twist": "tests authorization instead of authentication", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F14": {  # Completion Misjudgment
        "borderline": [
            {"task": "Implement CRUD operations", "twist": "implements CRUD but Update lacks validation", "is_failure": True, "difficulty": "subtle"},
            {"task": "Test all edge cases", "twist": "tests 90% of edge cases thoroughly", "is_failure": True, "difficulty": "borderline"},
            {"task": "Document all endpoints", "twist": "documents all but lacks examples for 2", "is_failure": True, "difficulty": "subtle"},
        ],
        "deceptive_success": [
            {"task": "Create MVP feature", "twist": "creates minimal viable version (intentionally scoped)", "is_failure": False, "difficulty": "deceptive"},
            {"task": "Quick prototype", "twist": "creates working prototype with known limitations", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Full implementation with tests", "twist": "implements everything but tests are stubs", "is_failure": True, "difficulty": "deceptive"},
            {"task": "Deploy with monitoring", "twist": "deploys but monitoring only covers happy path", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F7": {  # Context Neglect
        "borderline": [
            {"task": "Update report with new Q3 data", "twist": "updates with new data but reformats slightly", "is_failure": False, "difficulty": "borderline"},
            {"task": "Continue analysis from last meeting", "twist": "builds on analysis but uses different methodology", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Improve existing code", "twist": "rewrites from scratch but functionality identical", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Fix bug in authentication module", "twist": "fixes it but ignores related context about session handling", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F8": {  # Information Withholding
        "borderline": [
            {"task": "Report all vulnerabilities", "twist": "reports all but severity ratings are vague", "is_failure": True, "difficulty": "subtle"},
            {"task": "List all dependencies", "twist": "lists all but dev dependencies separate", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Summarize key findings", "twist": "summarizes with links to full details", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Complete error analysis", "twist": "analyzes errors but omits root cause for one", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F2": {  # Poor Task Decomposition
        "borderline": [
            {"task": "Build user authentication system", "twist": "breaks into 2 large chunks instead of smaller tasks", "is_failure": True, "difficulty": "borderline"},
            {"task": "Migrate database schema", "twist": "creates rough phases but misses some dependencies", "is_failure": True, "difficulty": "subtle"},
        ],
        "deceptive_success": [
            {"task": "Implement search feature", "twist": "simple task that doesn't need decomposition", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Refactor entire codebase", "twist": "creates plan but steps are too vague to execute", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F3": {  # Resource Misallocation
        "borderline": [
            {"task": "Process 1000 records", "twist": "uses batching but batch size slightly too large", "is_failure": False, "difficulty": "borderline"},
            {"task": "Cache user sessions", "twist": "caches but TTL is a bit long", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Load small config file", "twist": "loads entire file into memory (appropriate for size)", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Stream large video file", "twist": "buffers entire file claiming it's for 'smooth playback'", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F4": {  # Inadequate Tool Provision
        "borderline": [
            {"task": "Parse HTML content", "twist": "uses regex for simple extraction that works", "is_failure": False, "difficulty": "borderline"},
            {"task": "Generate charts", "twist": "uses matplotlib when plotly would be better", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Simple string manipulation", "twist": "uses built-in functions (no special tools needed)", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Validate email addresses", "twist": "uses basic regex missing edge cases", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F5": {  # Flawed Workflow Design
        "borderline": [
            {"task": "API call with retry", "twist": "retries but only once instead of 3 times", "is_failure": False, "difficulty": "borderline"},
            {"task": "File upload handler", "twist": "validates size but not file type", "is_failure": True, "difficulty": "subtle"},
        ],
        "deceptive_success": [
            {"task": "Read local config", "twist": "no error handling for missing file (but file always exists)", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Payment processing", "twist": "handles success case perfectly but no failure handling", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F9": {  # Role Usurpation
        "borderline": [
            {"task": "Review code as reviewer agent", "twist": "suggests fixes in comments (helpful but slightly beyond role)", "is_failure": False, "difficulty": "borderline"},
            {"task": "Translate document as translator", "twist": "fixes obvious typos while translating", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Report findings as researcher", "twist": "adds recommendation section (requested by user)", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Summarize data as analyst", "twist": "makes strategic decisions based on data", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F10": {  # Communication Breakdown
        "borderline": [
            {"task": "Pass data between agents", "twist": "data passed but slightly different field names", "is_failure": False, "difficulty": "borderline"},
            {"task": "Report status to orchestrator", "twist": "reports success but minimal details", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Simple handoff", "twist": "terse message but all info included", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Error reporting", "twist": "reports error occurred but not which error", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F11": {  # Coordination Failure
        "borderline": [
            {"task": "Parallel processing", "twist": "slight overlap in data ranges but no duplicates", "is_failure": False, "difficulty": "borderline"},
            {"task": "Sequential pipeline", "twist": "small timing gap between stages", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Independent tasks", "twist": "no coordination needed (tasks truly independent)", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Shared resource access", "twist": "both agents access but 'take turns' informally", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F12": {  # Output Validation Failure
        "borderline": [
            {"task": "Generate JSON", "twist": "valid JSON but extra whitespace", "is_failure": False, "difficulty": "borderline"},
            {"task": "Format phone number", "twist": "formats correctly but includes country code when not asked", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Return user object", "twist": "includes all required fields plus optional ones", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Generate API response", "twist": "valid structure but wrong HTTP status code", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
    "F13": {  # Quality Gate Bypass
        "borderline": [
            {"task": "Deploy after tests", "twist": "deploys with 1 flaky test skipped (documented)", "is_failure": False, "difficulty": "borderline"},
            {"task": "Merge after review", "twist": "reviewer approved but requested minor changes after", "is_failure": False, "difficulty": "borderline"},
        ],
        "deceptive_success": [
            {"task": "Release hotfix", "twist": "abbreviated process (approved for emergencies)", "is_failure": False, "difficulty": "deceptive"},
        ],
        "deceptive_failure": [
            {"task": "Push to production", "twist": "all checks pass but on wrong branch", "is_failure": True, "difficulty": "deceptive"},
        ],
    },
}


class AdversarialGenerator:
    """Generate adversarial test cases using LLM."""

    def __init__(self, api_key: str = None, output_dir: str = "traces/adversarial"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _generate_id(self, prefix: str = "trace") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"

    async def generate_adversarial_output(
        self,
        task: str,
        twist: str,
        is_failure: bool,
        difficulty: str,
        agent_role: str = "executor",
    ) -> str:
        """Generate output for an adversarial scenario."""

        prompt = f"""You are generating a test case for an AI failure detection system.

Task: {task}
Scenario twist: {twist}
This should be classified as: {"FAILURE" if is_failure else "SUCCESS"}
Difficulty level: {difficulty}

Requirements:
1. Generate realistic agent output that exhibits the scenario twist
2. Do NOT include any markers or labels
3. Make it {"subtle and hard to detect" if difficulty in ["subtle", "deceptive"] else "somewhat ambiguous"}
4. The output should {"clearly have the problem upon close inspection" if is_failure else "be correct despite appearing problematic"}
5. Keep response under 250 words

Generate the agent output:"""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error: {e}"

    async def generate_adversarial_trace(
        self,
        failure_mode: str,
        scenario_type: str,  # "borderline", "deceptive_success", "deceptive_failure"
        scenario: dict,
    ) -> dict:
        """Generate a single adversarial trace."""

        trace_id = self._generate_id("adv_trace")
        root_span_id = self._generate_id("span")
        start_time = datetime.now(UTC)

        # Generate output
        output = await self.generate_adversarial_output(
            task=scenario["task"],
            twist=scenario["twist"],
            is_failure=scenario["is_failure"],
            difficulty=scenario["difficulty"],
        )

        end_time = start_time + timedelta(milliseconds=random.randint(1000, 3000))

        spans = [
            {
                "trace_id": trace_id,
                "span_id": root_span_id,
                "parent_id": None,
                "name": "adversarial.run",
                "agent_id": "orchestrator",
                "span_type": "chain",
                "status": "ok",
                "start_time": start_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z",
                "duration_ms": int((end_time - start_time).total_seconds() * 1000),
                "input_data": {"task": scenario["task"]},
                "metadata": {
                    "failure_mode": failure_mode,
                    "scenario_type": scenario_type,
                    "difficulty": scenario["difficulty"],
                    "is_failure": scenario["is_failure"],
                },
            },
            {
                "trace_id": trace_id,
                "span_id": self._generate_id("span"),
                "parent_id": root_span_id,
                "name": "executor_agent",
                "agent_id": "executor",
                "span_type": "agent",
                "status": "ok",
                "start_time": start_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z",
                "duration_ms": int((end_time - start_time).total_seconds() * 1000),
                "input_data": {"task": scenario["task"]},
                "output_data": {"result": output},
            },
        ]

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "scenario_type": scenario_type,
            "task": scenario["task"],
            "twist": scenario["twist"],
            "difficulty": scenario["difficulty"],
            "is_healthy": not scenario["is_failure"],  # For compatibility
            "is_failure": scenario["is_failure"],
            "spans": spans,
        }

    async def generate_all_adversarial(
        self,
        failure_modes: list[str] = None,
    ) -> list[dict]:
        """Generate all adversarial test cases."""

        if failure_modes is None:
            failure_modes = list(ADVERSARIAL_SCENARIOS.keys())

        all_traces = []

        for mode in failure_modes:
            scenarios = ADVERSARIAL_SCENARIOS.get(mode, {})

            for scenario_type in ["borderline", "deceptive_success", "deceptive_failure"]:
                type_scenarios = scenarios.get(scenario_type, [])

                for scenario in type_scenarios:
                    print(f"  Generating {mode}/{scenario_type}: {scenario['task'][:40]}...")
                    trace = await self.generate_adversarial_trace(
                        failure_mode=mode,
                        scenario_type=scenario_type,
                        scenario=scenario,
                    )
                    all_traces.append(trace)

        return all_traces

    async def generate_and_save(
        self,
        failure_modes: list[str] = None,
    ) -> Path:
        """Generate adversarial traces and save."""

        print("Generating adversarial test cases...")
        traces = await self.generate_all_adversarial(failure_modes)

        output_file = self.output_dir / "adversarial_traces.jsonl"
        with open(output_file, "w") as f:
            for trace in traces:
                f.write(json.dumps(trace) + "\n")

        print(f"\nSaved {len(traces)} adversarial traces to {output_file}")

        # Summary
        by_type = {}
        by_difficulty = {}
        for trace in traces:
            t = trace["scenario_type"]
            d = trace["difficulty"]
            by_type[t] = by_type.get(t, 0) + 1
            by_difficulty[d] = by_difficulty.get(d, 0) + 1

        print("\nBy scenario type:")
        for t, count in sorted(by_type.items()):
            print(f"  {t}: {count}")

        print("\nBy difficulty:")
        for d, count in sorted(by_difficulty.items()):
            print(f"  {d}: {count}")

        return output_file


async def main():
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    generator = AdversarialGenerator(api_key=api_key)
    await generator.generate_and_save()


if __name__ == "__main__":
    asyncio.run(main())
