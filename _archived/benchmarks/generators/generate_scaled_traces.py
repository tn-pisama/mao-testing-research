"""Scaled trace generation system for 2000 traces per framework.

Generates traces at 3 complexity levels across 4 frameworks:
- LangChain/LangGraph: Primary framework with full complexity
- AutoGen: Microsoft's multi-agent conversation patterns
- CrewAI: Role-based crew orchestration
- n8n: Workflow automation patterns

Target: 2000 traces per framework = 8000 total traces
Distribution: ~143 traces per mode per framework
Complexity split: 40% simple, 35% medium, 25% complex
"""

import asyncio
import functools
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any, Literal

# Force unbuffered output
print = functools.partial(print, flush=True)

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.trace_generator import FAILURE_MODES


class ScaledTraceGenerator:
    """Generate large-scale traces across multiple frameworks."""

    FRAMEWORKS = {
        "langchain": {
            "prefix": "trace",
            "span_prefix": "span",
            "root_name": "langgraph.workflow",
            "agent_format": "{role}_agent",
        },
        "autogen": {
            "prefix": "autogen_trace",
            "span_prefix": "ag_span",
            "root_name": "autogen.conversation",
            "agent_format": "{role}",
        },
        "crewai": {
            "prefix": "crewai_trace",
            "span_prefix": "crew_span",
            "root_name": "crewai.crew.kickoff",
            "agent_format": "{role}",
        },
        "n8n": {
            "prefix": "n8n_exec",
            "span_prefix": "n8n_node",
            "root_name": "n8n.workflow.execute",
            "agent_format": "{role}_node",
        },
    }

    AGENT_ROLES = [
        "researcher", "writer", "reviewer", "planner", "validator",
        "executor", "aggregator", "supervisor", "analyst", "editor"
    ]

    TOOLS = [
        "web_search", "code_execute", "database_query", "file_read",
        "file_write", "api_call", "email_send", "http_request"
    ]

    def __init__(self, api_key: str, output_dir: str = "traces"):
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.model = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            api_key=api_key,
        )
        self.stats = {"generated": 0, "failed": 0}

    def _generate_id(self, framework: str, id_type: str = "trace") -> str:
        """Generate framework-specific ID."""
        fw = self.FRAMEWORKS[framework]
        prefix = fw["prefix"] if id_type == "trace" else fw["span_prefix"]
        return f"{prefix}_{uuid.uuid4().hex[:16 if id_type == 'trace' else 12]}"

    async def _generate_content(
        self,
        role: str,
        task: str,
        failure_mode: str,
        scenario: str,
        framework: str,
        context: str = "",
    ) -> tuple[str, str]:
        """Generate realistic agent content using LLM."""

        mode_info = FAILURE_MODES[failure_mode]

        # Framework-specific prompting
        fw_context = {
            "langchain": "LangChain/LangGraph workflow",
            "autogen": "Microsoft AutoGen multi-agent system",
            "crewai": "CrewAI crew with role-based agents",
            "n8n": "n8n workflow automation",
        }

        prompt = f"""You are a {role.upper()} agent in a {fw_context[framework]}.
Generate realistic output for this scenario.

Task: {task}
Failure mode to exhibit: {mode_info['name']}
Scenario: {scenario}
Description: {mode_info['description']}

{f"Prior context: {context[:400]}" if context else ""}

Generate output that subtly exhibits this failure mode. Be realistic, natural, and specific to {framework}."""

        try:
            response = await self.model.ainvoke([
                SystemMessage(content=f"You are a {role} agent in {fw_context[framework]}."),
                HumanMessage(content=prompt),
            ])
            return prompt, response.content
        except Exception as e:
            return prompt, f"Agent {role} encountered: {str(e)}"

    def _create_tool_span(
        self,
        trace_id: str,
        parent_id: str,
        tool: str,
        framework: str,
        start_time: datetime,
        inject_failure: bool = False,
    ) -> tuple[dict, datetime]:
        """Create a tool call span."""

        success = not inject_failure and random.random() > 0.15
        duration = random.randint(100, 2000)
        end_time = start_time + timedelta(milliseconds=duration)

        return {
            "trace_id": trace_id,
            "span_id": self._generate_id(framework, "span"),
            "parent_id": parent_id,
            "name": f"tool.{tool}",
            "agent_id": f"tool_{tool}",
            "span_type": "tool_call",
            "status": "ok" if success else "error",
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration,
            "input_data": {"tool": tool, "params": {}},
            "output_data": {"success": success, "result": "OK" if success else "Error"},
            "metadata": {"framework": framework, "tool": tool},
        }, end_time

    def _create_validation_span(
        self,
        trace_id: str,
        parent_id: str,
        val_type: str,
        framework: str,
        start_time: datetime,
        passed: bool = True,
        bypassed: bool = False,
    ) -> tuple[dict, datetime]:
        """Create a validation span."""

        duration = random.randint(50, 200)
        end_time = start_time + timedelta(milliseconds=duration)
        status = "ok" if passed else ("bypassed" if bypassed else "failed")

        return {
            "trace_id": trace_id,
            "span_id": self._generate_id(framework, "span"),
            "parent_id": parent_id,
            "name": f"validation.{val_type}",
            "agent_id": "validator",
            "span_type": "validation",
            "status": status,
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration,
            "input_data": {"validation_type": val_type},
            "output_data": {"passed": passed, "bypassed": bypassed},
            "metadata": {"framework": framework, "validation_type": val_type},
        }, end_time

    async def generate_simple_trace(
        self,
        framework: str,
        failure_mode: str,
        scenario: str,
        trace_num: int,
    ) -> dict:
        """Generate a simple 2-3 agent trace."""

        trace_id = self._generate_id(framework, "trace")
        fw = self.FRAMEWORKS[framework]
        start_time = datetime.now(UTC)
        spans = []
        mode_info = FAILURE_MODES[failure_mode]

        root_span_id = self._generate_id(framework, "span")

        # Agent 1: Research/Analysis
        prompt1, response1 = await self._generate_content(
            "researcher", scenario, failure_mode, scenario, framework
        )
        agent1_start = start_time + timedelta(milliseconds=100)
        agent1_end = datetime.now(UTC)

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_id(framework, "span"),
            "parent_id": root_span_id,
            "name": fw["agent_format"].format(role="researcher"),
            "agent_id": "researcher",
            "span_type": "agent",
            "status": "ok",
            "start_time": agent1_start.isoformat() + "Z",
            "end_time": agent1_end.isoformat() + "Z",
            "duration_ms": int((agent1_end - agent1_start).total_seconds() * 1000),
            "input_data": {"task": scenario},
            "output_data": {"result": response1[:500]},
            "metadata": {"framework": framework, "role": "research", "failure_mode": failure_mode},
        })

        # Agent 2: Writer/Executor
        prompt2, response2 = await self._generate_content(
            "writer", scenario, failure_mode, scenario, framework, context=response1
        )
        agent2_start = agent1_end + timedelta(milliseconds=50)
        agent2_end = datetime.now(UTC)

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_id(framework, "span"),
            "parent_id": root_span_id,
            "name": fw["agent_format"].format(role="writer"),
            "agent_id": "writer",
            "span_type": "agent",
            "status": "ok",
            "start_time": agent2_start.isoformat() + "Z",
            "end_time": agent2_end.isoformat() + "Z",
            "duration_ms": int((agent2_end - agent2_start).total_seconds() * 1000),
            "input_data": {"context": response1[:200]},
            "output_data": {"result": response2[:500]},
            "metadata": {"framework": framework, "role": "writing", "failure_mode": failure_mode},
        })

        # Root span
        root_end = agent2_end + timedelta(milliseconds=50)
        spans.insert(0, {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": fw["root_name"],
            "agent_id": "orchestrator",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": root_end.isoformat() + "Z",
            "duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "input_data": {"task": scenario},
            "metadata": {
                "framework": framework,
                "failure_mode": failure_mode,
                "complexity": "simple",
                "trace_num": trace_num,
            },
        })

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "failure_name": mode_info["name"],
            "scenario": scenario,
            "complexity": "simple",
            "framework": framework,
            "spans": spans,
            "research_prompt": prompt1,
            "research_response": response1,
            "writer_response": response2,
        }

    async def generate_medium_trace(
        self,
        framework: str,
        failure_mode: str,
        scenario: str,
        trace_num: int,
    ) -> dict:
        """Generate a medium complexity trace with 4-5 agents and tools."""

        trace_id = self._generate_id(framework, "trace")
        fw = self.FRAMEWORKS[framework]
        start_time = datetime.now(UTC)
        spans = []
        mode_info = FAILURE_MODES[failure_mode]
        current_time = start_time

        root_span_id = self._generate_id(framework, "span")
        context = ""

        # Multiple agents with tool calls
        agents = ["researcher", "analyst", "writer", "reviewer"]
        for i, role in enumerate(agents):
            prompt, response = await self._generate_content(
                role, scenario, failure_mode, scenario, framework, context=context
            )
            agent_start = current_time + timedelta(milliseconds=50)
            agent_end = datetime.now(UTC)

            agent_span_id = self._generate_id(framework, "span")
            spans.append({
                "trace_id": trace_id,
                "span_id": agent_span_id,
                "parent_id": root_span_id,
                "name": fw["agent_format"].format(role=role),
                "agent_id": role,
                "span_type": "agent",
                "status": "ok",
                "start_time": agent_start.isoformat() + "Z",
                "end_time": agent_end.isoformat() + "Z",
                "duration_ms": int((agent_end - agent_start).total_seconds() * 1000),
                "input_data": {"task": scenario, "context": context[:200]},
                "output_data": {"result": response[:500]},
                "metadata": {"framework": framework, "role": role, "failure_mode": failure_mode},
            })

            context = response
            current_time = agent_end

            # Add tool calls for some agents
            if role in ["researcher", "analyst"]:
                tool = random.choice(self.TOOLS[:4])
                tool_span, current_time = self._create_tool_span(
                    trace_id, agent_span_id, tool, framework, current_time,
                    inject_failure=(failure_mode == "F4" and i == 1)
                )
                spans.append(tool_span)

        # Add validation
        if failure_mode in ["F12", "F13"]:
            bypassed = failure_mode == "F13" and random.random() < 0.5
            val_span, current_time = self._create_validation_span(
                trace_id, root_span_id, "quality_check", framework, current_time,
                passed=not bypassed, bypassed=bypassed
            )
            spans.append(val_span)

        # Root span
        root_end = current_time + timedelta(milliseconds=50)
        spans.insert(0, {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": fw["root_name"],
            "agent_id": "orchestrator",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": root_end.isoformat() + "Z",
            "duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "input_data": {"task": scenario},
            "metadata": {
                "framework": framework,
                "failure_mode": failure_mode,
                "complexity": "medium",
                "trace_num": trace_num,
            },
        })

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "failure_name": mode_info["name"],
            "scenario": scenario,
            "complexity": "medium",
            "framework": framework,
            "spans": spans,
        }

    async def generate_complex_trace(
        self,
        framework: str,
        failure_mode: str,
        scenario: str,
        trace_num: int,
    ) -> dict:
        """Generate a complex trace with 6+ agents, parallel execution, errors, and retries."""

        trace_id = self._generate_id(framework, "trace")
        fw = self.FRAMEWORKS[framework]
        start_time = datetime.now(UTC)
        spans = []
        mode_info = FAILURE_MODES[failure_mode]
        current_time = start_time

        root_span_id = self._generate_id(framework, "span")

        # Supervisor/Planner
        prompt, response = await self._generate_content(
            "supervisor", f"Plan and supervise: {scenario}", failure_mode, scenario, framework
        )
        sup_start = current_time + timedelta(milliseconds=50)
        sup_end = datetime.now(UTC)

        sup_span_id = self._generate_id(framework, "span")
        spans.append({
            "trace_id": trace_id,
            "span_id": sup_span_id,
            "parent_id": root_span_id,
            "name": fw["agent_format"].format(role="supervisor"),
            "agent_id": "supervisor",
            "span_type": "agent",
            "status": "ok",
            "start_time": sup_start.isoformat() + "Z",
            "end_time": sup_end.isoformat() + "Z",
            "duration_ms": int((sup_end - sup_start).total_seconds() * 1000),
            "input_data": {"task": scenario},
            "output_data": {"plan": response[:500]},
            "metadata": {"framework": framework, "role": "supervisor", "failure_mode": failure_mode},
        })

        current_time = sup_end
        plan_context = response

        # Parallel executor agents (simulated)
        executor_results = []
        for i, (role, tool) in enumerate([
            ("researcher", "web_search"),
            ("analyst", "database_query"),
            ("executor", "code_execute"),
        ]):
            prompt, response = await self._generate_content(
                role, f"Execute phase {i+1}", failure_mode, scenario, framework, context=plan_context
            )
            exec_start = current_time + timedelta(milliseconds=50)
            exec_end = datetime.now(UTC)

            exec_span_id = self._generate_id(framework, "span")
            spans.append({
                "trace_id": trace_id,
                "span_id": exec_span_id,
                "parent_id": sup_span_id,
                "name": fw["agent_format"].format(role=role),
                "agent_id": f"{role}_{i+1}",
                "span_type": "agent",
                "status": "ok",
                "start_time": exec_start.isoformat() + "Z",
                "end_time": exec_end.isoformat() + "Z",
                "duration_ms": int((exec_end - exec_start).total_seconds() * 1000),
                "input_data": {"phase": i+1, "task": plan_context[:200]},
                "output_data": {"result": response[:500]},
                "metadata": {"framework": framework, "role": role, "phase": i+1, "failure_mode": failure_mode},
            })

            executor_results.append(response)

            # Tool call
            inject_failure = failure_mode == "F4" and i == 1
            tool_span, tool_end = self._create_tool_span(
                trace_id, exec_span_id, tool, framework, exec_end, inject_failure
            )
            spans.append(tool_span)

            # Retry on failure
            if not tool_span["output_data"]["success"]:
                for attempt in range(1, 3):
                    retry_span = {
                        "trace_id": trace_id,
                        "span_id": self._generate_id(framework, "span"),
                        "parent_id": exec_span_id,
                        "name": f"retry.attempt_{attempt}",
                        "agent_id": "retry_handler",
                        "span_type": "retry",
                        "status": "ok" if attempt == 2 else "retry",
                        "start_time": tool_end.isoformat() + "Z",
                        "end_time": (tool_end + timedelta(milliseconds=200)).isoformat() + "Z",
                        "duration_ms": 200,
                        "metadata": {"attempt": attempt, "max_attempts": 3, "framework": framework},
                    }
                    spans.append(retry_span)
                    tool_end = tool_end + timedelta(milliseconds=200)

            current_time = tool_end

        # Aggregator
        prompt, response = await self._generate_content(
            "aggregator", "Combine results", failure_mode, scenario, framework,
            context="\n".join(executor_results)
        )
        agg_start = current_time + timedelta(milliseconds=50)
        agg_end = datetime.now(UTC)

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_id(framework, "span"),
            "parent_id": root_span_id,
            "name": fw["agent_format"].format(role="aggregator"),
            "agent_id": "aggregator",
            "span_type": "agent",
            "status": "ok",
            "start_time": agg_start.isoformat() + "Z",
            "end_time": agg_end.isoformat() + "Z",
            "duration_ms": int((agg_end - agg_start).total_seconds() * 1000),
            "input_data": {"inputs": len(executor_results)},
            "output_data": {"result": response[:500]},
            "metadata": {"framework": framework, "role": "aggregator", "failure_mode": failure_mode},
        })

        current_time = agg_end

        # Multiple validations
        for val_type in ["schema", "content", "approval"]:
            bypassed = failure_mode == "F13" and val_type == "approval" and random.random() < 0.5
            passed = failure_mode != "F12" or val_type != "content"
            val_span, current_time = self._create_validation_span(
                trace_id, root_span_id, val_type, framework, current_time,
                passed=passed, bypassed=bypassed
            )
            spans.append(val_span)

        # Error span for certain modes
        if failure_mode in ["F5", "F11"] and random.random() < 0.3:
            error_span = {
                "trace_id": trace_id,
                "span_id": self._generate_id(framework, "span"),
                "parent_id": root_span_id,
                "name": "error.workflow",
                "agent_id": "error_handler",
                "span_type": "error",
                "status": "error",
                "start_time": current_time.isoformat() + "Z",
                "end_time": (current_time + timedelta(milliseconds=50)).isoformat() + "Z",
                "duration_ms": 50,
                "output_data": {"error": "Coordination error in workflow"},
                "metadata": {"framework": framework, "error_type": "coordination"},
            }
            spans.append(error_span)
            current_time = current_time + timedelta(milliseconds=50)

        # Final validator
        prompt, response = await self._generate_content(
            "validator", "Final validation", failure_mode, scenario, framework
        )
        val_start = current_time + timedelta(milliseconds=50)
        val_end = datetime.now(UTC)

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_id(framework, "span"),
            "parent_id": root_span_id,
            "name": fw["agent_format"].format(role="validator"),
            "agent_id": "validator",
            "span_type": "agent",
            "status": "ok",
            "start_time": val_start.isoformat() + "Z",
            "end_time": val_end.isoformat() + "Z",
            "duration_ms": int((val_end - val_start).total_seconds() * 1000),
            "input_data": {},
            "output_data": {"result": response[:500]},
            "metadata": {"framework": framework, "role": "validator", "failure_mode": failure_mode},
        })

        # Root span
        root_end = val_end + timedelta(milliseconds=50)
        spans.insert(0, {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": fw["root_name"],
            "agent_id": "orchestrator",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": root_end.isoformat() + "Z",
            "duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "input_data": {"task": scenario},
            "metadata": {
                "framework": framework,
                "failure_mode": failure_mode,
                "complexity": "complex",
                "trace_num": trace_num,
                "agent_count": len([s for s in spans if s.get("span_type") == "agent"]),
            },
        })

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "failure_name": mode_info["name"],
            "scenario": scenario,
            "complexity": "complex",
            "framework": framework,
            "spans": spans,
        }

    async def generate_framework_traces(
        self,
        framework: str,
        traces_per_framework: int = 2000,
        concurrency: int = 10,
    ) -> list[dict]:
        """Generate all traces for a single framework."""

        traces_per_mode = traces_per_framework // len(FAILURE_MODES)
        # Split: 40% simple, 35% medium, 25% complex
        simple_count = int(traces_per_mode * 0.40)
        medium_count = int(traces_per_mode * 0.35)
        complex_count = traces_per_mode - simple_count - medium_count

        all_traces = []
        semaphore = asyncio.Semaphore(concurrency)
        total = traces_per_framework
        completed = [0]

        async def generate_with_semaphore(
            complexity: str,
            failure_mode: str,
            scenario_idx: int,
            trace_num: int,
        ):
            async with semaphore:
                try:
                    mode_info = FAILURE_MODES[failure_mode]
                    scenario = mode_info["scenarios"][scenario_idx % len(mode_info["scenarios"])]

                    if complexity == "simple":
                        trace = await self.generate_simple_trace(framework, failure_mode, scenario, trace_num)
                    elif complexity == "medium":
                        trace = await self.generate_medium_trace(framework, failure_mode, scenario, trace_num)
                    else:
                        trace = await self.generate_complex_trace(framework, failure_mode, scenario, trace_num)

                    completed[0] += 1
                    if completed[0] % 50 == 0:
                        print(f"    [{completed[0]}/{total}] {framework}/{failure_mode}/{complexity} ({len(trace['spans'])} spans)")
                    return trace
                except Exception as e:
                    completed[0] += 1
                    print(f"    [{completed[0]}/{total}] ERROR: {framework}/{failure_mode}/{complexity}: {e}")
                    return None

        print(f"\n{'='*70}")
        print(f"Generating {traces_per_framework} traces for {framework.upper()}")
        print(f"  Simple: {simple_count * len(FAILURE_MODES)}, Medium: {medium_count * len(FAILURE_MODES)}, Complex: {complex_count * len(FAILURE_MODES)}")
        print(f"{'='*70}")

        for failure_mode in FAILURE_MODES:
            print(f"\n  {failure_mode}: {FAILURE_MODES[failure_mode]['name']}")

            # Generate simple traces
            tasks = [
                generate_with_semaphore("simple", failure_mode, i, i+1)
                for i in range(simple_count)
            ]
            results = await asyncio.gather(*tasks)
            mode_traces = [t for t in results if t is not None]

            # Generate medium traces
            tasks = [
                generate_with_semaphore("medium", failure_mode, i, i+1+simple_count)
                for i in range(medium_count)
            ]
            results = await asyncio.gather(*tasks)
            mode_traces.extend([t for t in results if t is not None])

            # Generate complex traces
            tasks = [
                generate_with_semaphore("complex", failure_mode, i, i+1+simple_count+medium_count)
                for i in range(complex_count)
            ]
            results = await asyncio.gather(*tasks)
            mode_traces.extend([t for t in results if t is not None])

            all_traces.extend(mode_traces)

            # Save mode-specific file
            fw_suffix = f"_{framework}" if framework != "langchain" else ""
            mode_file = self.output_dir / f"{failure_mode}{fw_suffix}_scaled_traces.jsonl"
            with open(mode_file, "w") as f:
                for trace in mode_traces:
                    f.write(json.dumps(trace) + "\n")

        print(f"\n  Generated {len(all_traces)} traces for {framework}")
        return all_traces

    async def generate_all_frameworks(
        self,
        traces_per_framework: int = 2000,
        concurrency: int = 10,
    ) -> dict[str, list[dict]]:
        """Generate traces for all frameworks."""

        all_results = {}

        for framework in self.FRAMEWORKS:
            traces = await self.generate_framework_traces(
                framework, traces_per_framework, concurrency
            )
            all_results[framework] = traces

            # Save combined file for framework
            combined_file = self.output_dir / f"all_{framework}_scaled_traces.jsonl"
            with open(combined_file, "w") as f:
                for trace in traces:
                    f.write(json.dumps(trace) + "\n")

        # Summary
        print(f"\n{'='*70}")
        print("GENERATION COMPLETE")
        print(f"{'='*70}")
        for fw, traces in all_results.items():
            print(f"  {fw}: {len(traces)} traces")
        print(f"  TOTAL: {sum(len(t) for t in all_results.values())} traces")

        return all_results


async def main():
    """Main entry point."""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    generator = ScaledTraceGenerator(
        api_key=api_key,
        output_dir="traces"
    )

    # Generate 2000 traces per framework
    await generator.generate_all_frameworks(
        traces_per_framework=2000,
        concurrency=10,
    )


if __name__ == "__main__":
    asyncio.run(main())
