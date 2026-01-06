"""Semantic trace generator using LLM for realistic agent outputs.

Generates traces where:
1. Outputs semantically match the scenarios (no artificial markers)
2. Failures are implicit in the content, not labeled
3. Healthy traces actually complete the task correctly
4. Failure traces exhibit real failure patterns
"""

import asyncio
import json
import random
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Literal

from anthropic import AsyncAnthropic

# Realistic scenarios for each failure mode
SCENARIOS = {
    "F1": [  # Specification Mismatch
        {"task": "Write a Python function to sort a list", "failure": "writes JavaScript instead", "success": "writes correct Python"},
        {"task": "Create a 100-word summary of the article", "failure": "writes 500+ word essay", "success": "writes concise 100-word summary"},
        {"task": "Generate a CSV file with user data", "failure": "generates JSON instead", "success": "generates proper CSV format"},
        {"task": "Write unit tests using pytest", "failure": "writes tests using unittest", "success": "writes pytest tests"},
        {"task": "Create a REST API endpoint", "failure": "creates GraphQL endpoint", "success": "creates REST endpoint"},
    ],
    "F6": [  # Task Derailment
        {"task": "Analyze Q3 sales performance", "failure": "discusses marketing strategy instead", "success": "focuses on Q3 sales metrics"},
        {"task": "Debug the login authentication bug", "failure": "starts refactoring unrelated code", "success": "identifies and fixes auth bug"},
        {"task": "Write documentation for the API", "failure": "starts implementing new features", "success": "documents existing API"},
        {"task": "Review the security audit findings", "failure": "discusses performance optimization", "success": "addresses security findings"},
        {"task": "Optimize database queries", "failure": "redesigns the entire schema", "success": "optimizes specific slow queries"},
    ],
    "F14": [  # Completion Misjudgment
        {"task": "Implement full CRUD operations", "failure": "implements only Create and Read", "success": "implements all CRUD operations"},
        {"task": "Test all edge cases", "failure": "tests only happy path", "success": "tests edge cases comprehensively"},
        {"task": "Deploy to production with rollback plan", "failure": "deploys without rollback plan", "success": "deploys with full rollback capability"},
        {"task": "Migrate all user data", "failure": "migrates only active users", "success": "migrates all user data"},
        {"task": "Document all API endpoints", "failure": "documents only main endpoints", "success": "documents all endpoints"},
    ],
    "F3": [  # Resource Misallocation
        {"task": "Process 10,000 records efficiently", "failure": "loads all into memory causing OOM", "success": "uses streaming/batching"},
        {"task": "Handle concurrent API requests", "failure": "creates unlimited threads", "success": "uses thread pool with limits"},
        {"task": "Cache frequently accessed data", "failure": "caches everything indefinitely", "success": "caches with appropriate TTL"},
        {"task": "Query large dataset", "failure": "fetches all columns when only 2 needed", "success": "selects only required columns"},
        {"task": "Process uploaded files", "failure": "holds files in memory", "success": "streams to disk"},
    ],
    "F7": [  # Context Neglect
        {"task": "Continue the analysis from previous meeting notes", "failure": "starts fresh ignoring prior context", "success": "builds on previous analysis"},
        {"task": "Update the existing report with new data", "failure": "creates new report ignoring old one", "success": "integrates new data with existing"},
        {"task": "Fix the bug mentioned in ticket #1234", "failure": "asks what the bug is", "success": "references ticket details"},
        {"task": "Follow up on client's specific requirements", "failure": "provides generic solution", "success": "addresses specific requirements"},
        {"task": "Implement feature per the approved design doc", "failure": "proposes different design", "success": "follows approved design"},
    ],
    "F8": [  # Information Withholding
        {"task": "Report all security vulnerabilities found", "failure": "reports only critical ones", "success": "reports all severities"},
        {"task": "Summarize meeting with all action items", "failure": "omits some action items", "success": "includes all action items"},
        {"task": "Provide complete error logs", "failure": "provides truncated logs", "success": "provides full logs"},
        {"task": "List all dependencies", "failure": "lists only direct dependencies", "success": "lists all including transitive"},
        {"task": "Document all configuration options", "failure": "documents only common ones", "success": "documents all options"},
    ],
}

# Add more failure modes
SCENARIOS["F2"] = [  # Poor Task Decomposition
    {"task": "Build a complete e-commerce site", "failure": "treats as single monolithic task", "success": "breaks into frontend, backend, db, auth, etc."},
    {"task": "Migrate legacy system", "failure": "attempts big-bang migration", "success": "plans incremental migration phases"},
    {"task": "Implement search functionality", "failure": "jumps to implementation without planning", "success": "decomposes into indexing, query, ranking"},
    {"task": "Set up CI/CD pipeline", "failure": "configures everything at once", "success": "sets up build, test, deploy stages separately"},
    {"task": "Refactor payment module", "failure": "rewrites entire module at once", "success": "identifies and refactors components incrementally"},
]

SCENARIOS["F4"] = [  # Inadequate Tool Provision
    {"task": "Analyze data with statistical tests", "failure": "lacks scipy, does manual calculations", "success": "uses appropriate statistical library"},
    {"task": "Parse complex XML documents", "failure": "uses regex instead of XML parser", "success": "uses proper XML parsing library"},
    {"task": "Process images for ML pipeline", "failure": "no image processing tools available", "success": "uses PIL/OpenCV appropriately"},
    {"task": "Connect to PostgreSQL database", "failure": "driver not available, uses raw sockets", "success": "uses psycopg2/asyncpg"},
    {"task": "Generate PDF reports", "failure": "creates HTML and tells user to print", "success": "uses PDF generation library"},
]

SCENARIOS["F5"] = [  # Flawed Workflow Design
    {"task": "Handle user registration with email verification", "failure": "no handling for invalid emails", "success": "validates email and handles failures"},
    {"task": "Process payments with retry logic", "failure": "no retry on transient failures", "success": "implements exponential backoff"},
    {"task": "Import data with validation", "failure": "fails completely on first error", "success": "logs errors and continues processing"},
    {"task": "Deploy with health checks", "failure": "no rollback on failed health check", "success": "automatic rollback on failure"},
    {"task": "Sync data between systems", "failure": "no conflict resolution", "success": "handles conflicts gracefully"},
]

SCENARIOS["F9"] = [  # Role Usurpation
    {"task": "Research and report findings (research agent)", "failure": "starts making business decisions", "success": "reports findings for human decision"},
    {"task": "Validate data format (validator agent)", "failure": "modifies data to make it valid", "success": "reports validation errors"},
    {"task": "Review code for issues (reviewer agent)", "failure": "rewrites the code instead", "success": "provides review comments"},
    {"task": "Translate document (translator agent)", "failure": "edits content for 'improvement'", "success": "translates accurately"},
    {"task": "Summarize article (summarizer agent)", "failure": "adds own opinions and analysis", "success": "objectively summarizes content"},
]

SCENARIOS["F10"] = [  # Communication Breakdown
    {"task": "Researcher passes findings to writer", "failure": "sends unstructured data dump", "success": "sends structured findings with context"},
    {"task": "Validator reports issues to fixer", "failure": "reports 'found problems' with no details", "success": "reports specific issues with locations"},
    {"task": "Planner delegates to executors", "failure": "vague task descriptions", "success": "clear tasks with acceptance criteria"},
    {"task": "Aggregator combines results", "failure": "can't parse inconsistent formats", "success": "receives standardized outputs"},
    {"task": "Monitor alerts on issues", "failure": "sends cryptic error codes", "success": "sends actionable alerts with context"},
]

SCENARIOS["F11"] = [  # Coordination Failure
    {"task": "Parallel agents process data partitions", "failure": "agents process overlapping data", "success": "clean partition with no overlap"},
    {"task": "Sequential pipeline processing", "failure": "next agent starts before previous finishes", "success": "proper handoff between stages"},
    {"task": "Distributed task execution", "failure": "multiple agents claim same task", "success": "proper task locking"},
    {"task": "Concurrent resource access", "failure": "race condition on shared state", "success": "proper synchronization"},
    {"task": "Multi-agent negotiation", "failure": "deadlock waiting for each other", "success": "proper turn-taking protocol"},
]

SCENARIOS["F12"] = [  # Output Validation Failure
    {"task": "Generate JSON response", "failure": "produces invalid JSON syntax", "success": "produces valid JSON"},
    {"task": "Create SQL query", "failure": "generates vulnerable SQL", "success": "generates parameterized query"},
    {"task": "Format date as ISO 8601", "failure": "outputs MM/DD/YYYY format", "success": "outputs YYYY-MM-DD format"},
    {"task": "Return paginated results with metadata", "failure": "returns data without pagination info", "success": "includes page, total, hasNext"},
    {"task": "Produce API response with required fields", "failure": "missing required 'id' field", "success": "all required fields present"},
]

SCENARIOS["F13"] = [  # Quality Gate Bypass
    {"task": "Deploy after all tests pass", "failure": "deploys with failing tests", "success": "waits for green tests"},
    {"task": "Merge after code review approval", "failure": "merges without approval", "success": "waits for reviewer approval"},
    {"task": "Release after security scan", "failure": "skips security scan for speed", "success": "completes security scan"},
    {"task": "Publish after QA sign-off", "failure": "publishes without QA", "success": "gets QA sign-off first"},
    {"task": "Process after data validation", "failure": "processes invalid data", "success": "validates before processing"},
]


class SemanticTraceGenerator:
    """Generate traces with semantically meaningful content using LLM."""

    def __init__(self, api_key: str = None, output_dir: str = "traces/semantic"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _generate_id(self, prefix: str = "trace") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"

    async def generate_agent_output(
        self,
        task: str,
        agent_role: str,
        failure_mode: str,
        is_failure: bool,
        failure_description: str = "",
        success_description: str = "",
        previous_output: str = "",
    ) -> str:
        """Generate realistic agent output using LLM."""

        if is_failure:
            prompt = f"""You are a {agent_role} agent in a multi-agent system.
Generate a realistic but FLAWED output for this task.

Task: {task}
Your role: {agent_role}
Failure to exhibit: {failure_description}

Requirements:
1. Your output should ACTUALLY exhibit the failure, not just mention it
2. Do NOT include any markers like [Failure:] or [Note:]
3. Write as if you're genuinely completing the task (but doing it wrong)
4. Be subtle - real failures aren't obvious
5. Keep response under 200 words

{f"Previous agent output: {previous_output[:300]}" if previous_output else ""}

Generate the flawed output:"""
        else:
            prompt = f"""You are a {agent_role} agent in a multi-agent system.
Generate a realistic and CORRECT output for this task.

Task: {task}
Your role: {agent_role}
Expected behavior: {success_description}

Requirements:
1. Your output should correctly complete the task
2. Do NOT include any markers like [Success:] or [Completed:]
3. Write naturally as if genuinely completing the task
4. Keep response under 200 words

{f"Previous agent output: {previous_output[:300]}" if previous_output else ""}

Generate the correct output:"""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error generating output: {e}"

    async def generate_trace(
        self,
        failure_mode: str,
        is_healthy: bool,
        framework: str = "langchain",
    ) -> dict:
        """Generate a single trace with semantic content."""

        scenarios = SCENARIOS.get(failure_mode, SCENARIOS["F1"])
        scenario = random.choice(scenarios)

        trace_id = self._generate_id("trace")
        root_span_id = self._generate_id("span")
        start_time = datetime.now(UTC)
        spans = []

        # Generate researcher output
        researcher_output = await self.generate_agent_output(
            task=scenario["task"],
            agent_role="researcher",
            failure_mode=failure_mode,
            is_failure=not is_healthy,
            failure_description=scenario["failure"],
            success_description=scenario["success"],
        )

        researcher_end = start_time + timedelta(milliseconds=random.randint(800, 2000))
        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_id("span"),
            "parent_id": root_span_id,
            "name": "researcher_agent",
            "agent_id": "researcher",
            "span_type": "agent",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": researcher_end.isoformat() + "Z",
            "duration_ms": int((researcher_end - start_time).total_seconds() * 1000),
            "input_data": {"task": scenario["task"]},
            "output_data": {"result": researcher_output},
        })

        # Generate writer output
        writer_output = await self.generate_agent_output(
            task=scenario["task"],
            agent_role="writer",
            failure_mode=failure_mode,
            is_failure=not is_healthy,
            failure_description=scenario["failure"],
            success_description=scenario["success"],
            previous_output=researcher_output,
        )

        writer_end = researcher_end + timedelta(milliseconds=random.randint(600, 1500))
        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_id("span"),
            "parent_id": root_span_id,
            "name": "writer_agent",
            "agent_id": "writer",
            "span_type": "agent",
            "status": "ok",
            "start_time": researcher_end.isoformat() + "Z",
            "end_time": writer_end.isoformat() + "Z",
            "duration_ms": int((writer_end - researcher_end).total_seconds() * 1000),
            "input_data": {"research": researcher_output[:200]},
            "output_data": {"document": writer_output},
        })

        # Root span
        root_end = writer_end + timedelta(milliseconds=50)
        spans.insert(0, {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": f"{framework}.run",
            "agent_id": "orchestrator",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": root_end.isoformat() + "Z",
            "duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "input_data": {"task": scenario["task"]},
            "metadata": {
                "framework": framework,
                "failure_mode": failure_mode,
                "is_healthy": is_healthy,
                "scenario": scenario,
            },
        })

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "scenario": scenario["task"],
            "expected_failure": scenario["failure"] if not is_healthy else None,
            "expected_success": scenario["success"] if is_healthy else None,
            "is_healthy": is_healthy,
            "framework": framework,
            "spans": spans,
        }

    async def generate_batch(
        self,
        failure_modes: list[str],
        traces_per_mode: int = 10,
        framework: str = "langchain",
    ) -> list[dict]:
        """Generate a batch of traces."""

        all_traces = []

        for mode in failure_modes:
            print(f"  Generating {mode}...")

            # Generate failure traces
            for i in range(traces_per_mode):
                trace = await self.generate_trace(mode, is_healthy=False, framework=framework)
                all_traces.append(trace)

            # Generate healthy traces
            for i in range(traces_per_mode):
                trace = await self.generate_trace(mode, is_healthy=True, framework=framework)
                all_traces.append(trace)

        return all_traces

    async def generate_and_save(
        self,
        failure_modes: list[str] = None,
        traces_per_mode: int = 10,
        framework: str = "langchain",
    ) -> Path:
        """Generate traces and save to file."""

        if failure_modes is None:
            failure_modes = list(SCENARIOS.keys())

        print(f"Generating semantic traces for {len(failure_modes)} failure modes...")
        traces = await self.generate_batch(failure_modes, traces_per_mode, framework)

        # Save to file
        output_file = self.output_dir / f"{framework}_semantic_traces.jsonl"
        with open(output_file, "w") as f:
            for trace in traces:
                f.write(json.dumps(trace) + "\n")

        print(f"Saved {len(traces)} traces to {output_file}")

        # Also save separate files for failure and healthy
        failure_traces = [t for t in traces if not t["is_healthy"]]
        healthy_traces = [t for t in traces if t["is_healthy"]]

        with open(self.output_dir / f"{framework}_semantic_failure.jsonl", "w") as f:
            for trace in failure_traces:
                f.write(json.dumps(trace) + "\n")

        with open(self.output_dir / f"{framework}_semantic_healthy.jsonl", "w") as f:
            for trace in healthy_traces:
                f.write(json.dumps(trace) + "\n")

        return output_file


async def main():
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    generator = SemanticTraceGenerator(api_key=api_key)

    # Generate traces for key failure modes
    key_modes = ["F1", "F6", "F14", "F7", "F8"]  # Start with 5 modes

    await generator.generate_and_save(
        failure_modes=key_modes,
        traces_per_mode=5,  # 5 failure + 5 healthy per mode = 50 traces
        framework="langchain",
    )


if __name__ == "__main__":
    asyncio.run(main())
