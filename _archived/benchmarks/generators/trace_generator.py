"""Generate traces for all 16 MAST failure modes.

Produces 50 unique traces per failure mode (800 total) for mao-testing evaluation.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

# MAST Failure Mode Definitions
FAILURE_MODES = {
    "F1": {
        "name": "Specification Mismatch",
        "description": "Task doesn't match user intent",
        "scenarios": [
            "User asks for Python code but agent writes JavaScript",
            "User wants a summary but agent writes full article",
            "User requests data analysis but agent does visualization only",
            "User asks for REST API but agent builds GraphQL",
            "User wants unit tests but agent writes integration tests",
        ]
    },
    "F2": {
        "name": "Poor Task Decomposition",
        "description": "Subtasks ill-defined or impossible",
        "scenarios": [
            "Agent creates circular task dependencies",
            "Agent skips critical prerequisite steps",
            "Agent creates tasks that cannot be completed with available tools",
            "Agent over-decomposes simple tasks into too many steps",
            "Agent under-decomposes complex tasks",
        ]
    },
    "F3": {
        "name": "Resource Misallocation",
        "description": "Wrong agents assigned to tasks",
        "scenarios": [
            "Research agent assigned to write code",
            "Writer agent assigned to do data analysis",
            "Junior agent assigned to architecture decisions",
            "Specialist agent assigned to general tasks",
            "Agent with wrong tools assigned to task",
        ]
    },
    "F4": {
        "name": "Inadequate Tool Provision",
        "description": "Missing or wrong tools available",
        "scenarios": [
            "Agent needs database access but only has file tools",
            "Agent needs web search but only has local search",
            "Agent needs code execution but only has text generation",
            "Agent needs API access but has no HTTP tools",
            "Agent needs image processing but only has text tools",
        ]
    },
    "F5": {
        "name": "Flawed Workflow Design",
        "description": "Process has structural problems",
        "scenarios": [
            "Missing validation step before deployment",
            "No error handling branch in workflow",
            "Workflow allows skipping mandatory review",
            "Parallel tasks with unhandled race conditions",
            "Missing rollback capability in workflow",
        ]
    },
    "F6": {
        "name": "Task Derailment",
        "description": "Agent goes off-topic",
        "scenarios": [
            "Agent starts discussing unrelated topics",
            "Agent focuses on minor details instead of main task",
            "Agent pursues tangential research",
            "Agent optimizes wrong objective",
            "Agent gets distracted by edge cases",
        ]
    },
    "F7": {
        "name": "Context Neglect",
        "description": "Agent ignores upstream context",
        "scenarios": [
            "Agent ignores previous research findings",
            "Agent doesn't use provided constraints",
            "Agent repeats already completed work",
            "Agent contradicts earlier decisions",
            "Agent ignores user preferences stated earlier",
        ]
    },
    "F8": {
        "name": "Information Withholding",
        "description": "Agent doesn't share needed info",
        "scenarios": [
            "Research agent doesn't pass key findings to writer",
            "Agent keeps error details private",
            "Agent summarizes too aggressively losing details",
            "Agent filters out relevant information",
            "Agent doesn't share intermediate results",
        ]
    },
    "F9": {
        "name": "Role Usurpation",
        "description": "Agent does another agent's job",
        "scenarios": [
            "Writer agent starts doing research",
            "Reviewer agent rewrites instead of reviewing",
            "Planner agent starts executing tasks",
            "Executor agent changes the plan",
            "Support agent makes business decisions",
        ]
    },
    "F10": {
        "name": "Communication Breakdown",
        "description": "Message misunderstood",
        "scenarios": [
            "Agent misinterprets technical jargon",
            "Agent takes sarcasm literally",
            "Agent misunderstands negation",
            "Agent conflates similar but different concepts",
            "Agent misses implicit requirements",
        ]
    },
    "F11": {
        "name": "Coordination Failure",
        "description": "Timing/sequencing errors",
        "scenarios": [
            "Agents work on same task simultaneously",
            "Agent starts before dependency is complete",
            "Agents deadlock waiting for each other",
            "Agent misses handoff signal",
            "Agents overwrite each other's work",
        ]
    },
    "F12": {
        "name": "Output Validation Failure",
        "description": "Output doesn't match spec",
        "scenarios": [
            "JSON output has wrong schema",
            "Code doesn't compile",
            "Output exceeds length limits",
            "Output missing required fields",
            "Output format doesn't match template",
        ]
    },
    "F13": {
        "name": "Quality Gate Bypass",
        "description": "Verification checkpoints skipped",
        "scenarios": [
            "Code review step skipped",
            "Testing phase bypassed",
            "Security scan not performed",
            "Approval not obtained",
            "Validation checks disabled",
        ]
    },
    "F14": {
        "name": "Completion Misjudgment",
        "description": "Task marked done when incomplete",
        "scenarios": [
            "Agent declares success with partial implementation",
            "Agent marks done but tests failing",
            "Agent completes wrong version of task",
            "Agent finishes draft as final",
            "Agent stops at first working solution",
        ]
    },
    "F15": {
        "name": "Grounding Failure",
        "description": "Output not supported by source documents",
        "scenarios": [
            "Agent extracts $45M revenue when source says $42M",
            "Agent claims Q3 data but sources only contain Q2",
            "Agent attributes quote to wrong person in document",
            "Agent cites source but misrepresents its actual content",
            "Agent invents statistics not present in any source document",
        ]
    },
    "F16": {
        "name": "Retrieval Quality Failure",
        "description": "Wrong or insufficient documents retrieved",
        "scenarios": [
            "Query about 2024 financials retrieves 2019 reports instead",
            "Query about product features retrieves HR policies",
            "Query needs multiple docs but agent only retrieves one",
            "Retrieval returns competitor info instead of company info",
            "Critical regulatory document missed in retrieval results",
        ]
    },
}


class TraceGenerator:
    """Generates traces for MAST failure mode evaluation."""

    def __init__(self, api_key: str, output_dir: str = "traces"):
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.model = ChatAnthropic(
            model="claude-3-5-haiku-20241022",  # Faster model for trace generation
            max_tokens=1024,
            api_key=api_key,
        )

    def _generate_trace_id(self) -> str:
        return f"trace_{uuid.uuid4().hex[:16]}"

    def _generate_span_id(self) -> str:
        return f"span_{uuid.uuid4().hex[:12]}"

    def _now(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    async def generate_failure_trace(
        self,
        failure_mode: str,
        scenario_idx: int,
        trace_num: int,
    ) -> dict:
        """Generate a single trace exhibiting a specific failure mode."""

        mode_info = FAILURE_MODES[failure_mode]
        scenario = mode_info["scenarios"][scenario_idx % len(mode_info["scenarios"])]

        trace_id = self._generate_trace_id()
        start_time = datetime.utcnow()

        # Generate the multi-agent interaction
        spans = []

        # Root span - workflow
        root_span_id = self._generate_span_id()
        root_start = start_time

        # Research agent span
        research_span_id = self._generate_span_id()
        research_start = start_time + timedelta(milliseconds=100)

        research_prompt = f"""You are simulating a RESEARCH AGENT in a multi-agent system.
Generate a realistic research output that will lead to failure mode: {mode_info['name']}
Scenario: {scenario}
Failure description: {mode_info['description']}

Generate research notes that would cause this failure when passed to a writer agent.
Be subtle - make it realistic, not obviously broken. Include specific details."""

        try:
            research_response = await self.model.ainvoke([
                SystemMessage(content="You are a research agent in a multi-agent system."),
                HumanMessage(content=research_prompt),
            ])
            research_output = research_response.content
            research_tokens = getattr(research_response, 'usage_metadata', {})
        except Exception as e:
            research_output = f"Research error: {str(e)}"
            research_tokens = {}

        research_end = datetime.utcnow()

        # Add research span
        spans.append({
            "trace_id": trace_id,
            "span_id": research_span_id,
            "parent_id": root_span_id,
            "name": "research_agent",
            "agent_id": "researcher",
            "span_type": "agent",
            "status": "ok",
            "start_time": research_start.isoformat() + "Z",
            "end_time": research_end.isoformat() + "Z",
            "duration_ms": int((research_end - research_start).total_seconds() * 1000),
            "input_data": {"task": f"Research for: {scenario}"},
            "output_data": {"research": research_output[:500]},
            "prompt": research_prompt,
            "response": research_output,
            "model": "claude-3-5-haiku-20241022",
            "tokens_input": research_tokens.get('input_tokens', 0),
            "tokens_output": research_tokens.get('output_tokens', 0),
            "metadata": {
                "failure_mode": failure_mode,
                "failure_name": mode_info["name"],
                "scenario": scenario,
            }
        })

        # Writer agent span
        writer_span_id = self._generate_span_id()
        writer_start = research_end + timedelta(milliseconds=50)

        writer_prompt = f"""You are simulating a WRITER AGENT in a multi-agent system.
You received this research from the research agent:

{research_output[:1000]}

Now generate content that exhibits this failure mode: {mode_info['name']}
Scenario: {scenario}

Generate output that demonstrates this failure - make it realistic and subtle."""

        try:
            writer_response = await self.model.ainvoke([
                SystemMessage(content="You are a writer agent in a multi-agent system."),
                HumanMessage(content=writer_prompt),
            ])
            writer_output = writer_response.content
            writer_tokens = getattr(writer_response, 'usage_metadata', {})
        except Exception as e:
            writer_output = f"Writer error: {str(e)}"
            writer_tokens = {}

        writer_end = datetime.utcnow()

        # Add writer span
        spans.append({
            "trace_id": trace_id,
            "span_id": writer_span_id,
            "parent_id": root_span_id,
            "name": "writer_agent",
            "agent_id": "writer",
            "span_type": "agent",
            "status": "ok",
            "start_time": writer_start.isoformat() + "Z",
            "end_time": writer_end.isoformat() + "Z",
            "duration_ms": int((writer_end - writer_start).total_seconds() * 1000),
            "input_data": {"research": research_output[:200]},
            "output_data": {"content": writer_output[:500]},
            "prompt": writer_prompt,
            "response": writer_output,
            "model": "claude-3-5-haiku-20241022",
            "tokens_input": writer_tokens.get('input_tokens', 0),
            "tokens_output": writer_tokens.get('output_tokens', 0),
            "metadata": {
                "failure_mode": failure_mode,
                "failure_name": mode_info["name"],
                "scenario": scenario,
            }
        })

        # Root span
        root_end = writer_end + timedelta(milliseconds=50)
        spans.insert(0, {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "workflow.research_and_write",
            "agent_id": "orchestrator",
            "span_type": "chain",
            "status": "ok",
            "start_time": root_start.isoformat() + "Z",
            "end_time": root_end.isoformat() + "Z",
            "duration_ms": int((root_end - root_start).total_seconds() * 1000),
            "input_data": {"task": scenario},
            "output_data": {"result": "completed"},
            "metadata": {
                "failure_mode": failure_mode,
                "failure_name": mode_info["name"],
                "scenario": scenario,
                "trace_num": trace_num,
            }
        })

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "failure_name": mode_info["name"],
            "scenario": scenario,
            "spans": spans,
            "source_format": "langgraph",
            "total_duration_ms": int((root_end - root_start).total_seconds() * 1000),
            "total_tokens": sum(s.get("tokens_input", 0) + s.get("tokens_output", 0) for s in spans),
        }

    async def generate_all_traces(self, traces_per_mode: int = 50, concurrency: int = 10):
        """Generate traces for all failure modes in parallel."""

        all_traces = []
        total = len(FAILURE_MODES) * traces_per_mode
        completed = [0]  # Use list for mutable counter in closure
        semaphore = asyncio.Semaphore(concurrency)

        async def generate_with_semaphore(failure_mode: str, scenario_idx: int, trace_num: int):
            async with semaphore:
                try:
                    trace = await self.generate_failure_trace(
                        failure_mode=failure_mode,
                        scenario_idx=scenario_idx,
                        trace_num=trace_num,
                    )
                    completed[0] += 1
                    print(f"  [{completed[0]}/{total}] {failure_mode} #{trace_num} ✓ ({trace['total_duration_ms']}ms)", flush=True)
                    return trace
                except Exception as e:
                    completed[0] += 1
                    print(f"  [{completed[0]}/{total}] {failure_mode} #{trace_num} ✗ {e}")
                    return None

        for failure_mode in FAILURE_MODES:
            print(f"\n{'='*60}")
            print(f"Generating {traces_per_mode} traces for {failure_mode}: {FAILURE_MODES[failure_mode]['name']}")
            print(f"{'='*60}")

            # Generate all traces for this mode in parallel
            tasks = [
                generate_with_semaphore(failure_mode, i, i+1)
                for i in range(traces_per_mode)
            ]
            results = await asyncio.gather(*tasks)
            mode_traces = [t for t in results if t is not None]
            all_traces.extend(mode_traces)

            # Save traces for this failure mode
            mode_file = self.output_dir / f"{failure_mode}_traces.jsonl"
            with open(mode_file, "w") as f:
                for trace in mode_traces:
                    for span in trace["spans"]:
                        span["_trace_metadata"] = {
                            "failure_mode": trace["failure_mode"],
                            "failure_name": trace["failure_name"],
                            "scenario": trace["scenario"],
                        }
                        f.write(json.dumps(span) + "\n")

            print(f"  Saved {len(mode_traces)} traces to {mode_file}")

        # Save combined traces
        combined_file = self.output_dir / "all_traces.jsonl"
        with open(combined_file, "w") as f:
            for trace in all_traces:
                for span in trace["spans"]:
                    f.write(json.dumps(span) + "\n")

        print(f"\n{'='*60}")
        print(f"COMPLETE: Generated {len(all_traces)} traces")
        print(f"Saved to {combined_file}")
        print(f"{'='*60}")

        return all_traces


async def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    generator = TraceGenerator(
        api_key=api_key,
        output_dir="traces"
    )

    traces = await generator.generate_all_traces(traces_per_mode=50)

    # Summary
    print("\n" + "="*60)
    print("TRACE GENERATION SUMMARY")
    print("="*60)
    for fm in FAILURE_MODES:
        count = len([t for t in traces if t["failure_mode"] == fm])
        print(f"  {fm}: {FAILURE_MODES[fm]['name']:<30} - {count} traces")
    print(f"\nTotal: {len(traces)} traces generated")


if __name__ == "__main__":
    asyncio.run(main())
