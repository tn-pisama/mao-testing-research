"""CrewAI-style multi-agent trace generator.

Generates traces simulating CrewAI patterns:
- Agents with roles, goals, and backstories
- Tasks with descriptions and expected outputs
- Sequential and hierarchical crew processes
- Tool usage and delegation patterns
"""

import asyncio
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.trace_generator import FAILURE_MODES


class CrewAITraceGenerator:
    """Generate traces simulating CrewAI multi-agent patterns."""

    AGENTS = {
        "researcher": {
            "role": "Senior Research Analyst",
            "goal": "Uncover cutting-edge developments and provide comprehensive analysis",
            "backstory": "You're a seasoned researcher with decades of experience analyzing complex topics.",
        },
        "writer": {
            "role": "Content Strategist",
            "goal": "Create compelling and accurate content based on research",
            "backstory": "You're a skilled writer who transforms complex information into clear narratives.",
        },
        "reviewer": {
            "role": "Quality Assurance Specialist",
            "goal": "Ensure all outputs meet quality standards and specifications",
            "backstory": "You're meticulous about quality and catch issues others miss.",
        },
        "planner": {
            "role": "Project Manager",
            "goal": "Break down complex projects into actionable tasks",
            "backstory": "You excel at organizing work and managing dependencies.",
        },
        "developer": {
            "role": "Senior Software Engineer",
            "goal": "Write clean, efficient, and maintainable code",
            "backstory": "You're an expert programmer with deep knowledge of best practices.",
        },
        "analyst": {
            "role": "Data Analyst",
            "goal": "Extract insights from data and present findings clearly",
            "backstory": "You turn raw data into actionable insights.",
        },
    }

    TOOLS = {
        "search_tool": {"description": "Search the internet for information"},
        "scrape_tool": {"description": "Scrape content from websites"},
        "file_tool": {"description": "Read and write files"},
        "code_interpreter": {"description": "Execute Python code"},
        "calculator": {"description": "Perform calculations"},
    }

    def __init__(self, api_key: str, output_dir: str = "traces"):
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.model = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            api_key=api_key,
        )

    def _generate_trace_id(self) -> str:
        return f"crewai_trace_{uuid.uuid4().hex[:16]}"

    def _generate_span_id(self) -> str:
        return f"crew_span_{uuid.uuid4().hex[:12]}"

    async def _generate_task_output(
        self,
        agent_name: str,
        task_description: str,
        failure_mode: str,
        scenario: str,
        context: str = "",
    ) -> tuple[str, str]:
        """Generate realistic CrewAI task output using LLM."""

        agent_info = self.AGENTS.get(agent_name, self.AGENTS["researcher"])
        mode_info = FAILURE_MODES[failure_mode]

        prompt = f"""You are simulating a CrewAI agent executing a task.

Agent Role: {agent_info['role']}
Agent Goal: {agent_info['goal']}
Agent Backstory: {agent_info['backstory']}

Task: {task_description}
Failure mode to exhibit: {mode_info['name']}
Scenario: {scenario}
Description: {mode_info['description']}

{f"Context from previous tasks: {context[:500]}" if context else ""}

Generate output that subtly exhibits this failure mode while staying in character.
Format as a natural CrewAI task output with clear sections."""

        try:
            response = await self.model.ainvoke([
                SystemMessage(content=f"You are {agent_info['role']} executing a CrewAI task."),
                HumanMessage(content=prompt),
            ])
            return prompt, response.content
        except Exception as e:
            return prompt, f"Task execution error: {str(e)}"

    def _create_tool_use_span(
        self,
        trace_id: str,
        parent_id: str,
        tool_name: str,
        start_time: datetime,
        success: bool = True,
    ) -> tuple[dict, datetime]:
        """Create a tool use span (CrewAI pattern)."""

        tool_info = self.TOOLS.get(tool_name, {"description": "Unknown tool"})
        duration_ms = random.randint(200, 2000)
        end_time = start_time + timedelta(milliseconds=duration_ms)

        span = {
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": parent_id,
            "name": f"tool.{tool_name}",
            "agent_id": f"tool_{tool_name}",
            "span_type": "tool_call",
            "status": "ok" if success else "error",
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration_ms,
            "input_data": {"tool": tool_name, "description": tool_info["description"]},
            "output_data": {
                "result": "Tool execution successful" if success else "Tool execution failed",
                "success": success,
            },
            "metadata": {
                "framework": "crewai",
                "tool_type": "crewai_tool",
            }
        }

        return span, end_time

    async def generate_sequential_crew_trace(
        self,
        failure_mode: str,
        scenario: str,
        task: str,
    ) -> list[dict]:
        """Generate a sequential crew execution trace."""

        trace_id = self._generate_trace_id()
        spans = []
        start_time = datetime.utcnow()

        agents = ["researcher", "writer", "reviewer"]

        # Root span - Crew execution
        root_span_id = self._generate_span_id()
        spans.append({
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "crewai.crew.kickoff",
            "agent_id": "crew_manager",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "input_data": {"task": task, "process": "sequential", "agents": agents},
            "metadata": {
                "framework": "crewai",
                "process_type": "sequential",
                "failure_mode": failure_mode,
                "num_agents": len(agents),
            }
        })

        current_time = start_time + timedelta(milliseconds=100)
        context = ""

        # Execute tasks sequentially
        for i, agent_name in enumerate(agents):
            agent_info = self.AGENTS[agent_name]
            task_desc = f"Task {i+1} for {agent_info['role']}: {scenario}"

            prompt, output = await self._generate_task_output(
                agent_name, task_desc, failure_mode, scenario, context
            )
            context += f"\n{agent_name}: {output[:300]}"

            task_span_id = self._generate_span_id()
            duration = random.randint(1000, 5000)
            end_time = current_time + timedelta(milliseconds=duration)

            spans.append({
                "trace_id": trace_id,
                "span_id": task_span_id,
                "parent_id": root_span_id,
                "name": f"crewai.task.execute",
                "agent_id": agent_name,
                "span_type": "agent",
                "status": "ok",
                "start_time": current_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z",
                "duration_ms": duration,
                "prompt": prompt,
                "response": output,
                "input_data": {
                    "task_description": task_desc,
                    "agent_role": agent_info["role"],
                },
                "output_data": {"result": output[:300]},
                "metadata": {
                    "framework": "crewai",
                    "agent_role": agent_info["role"],
                    "task_index": i,
                }
            })

            current_time = end_time + timedelta(milliseconds=50)

            # Random tool usage
            if random.random() > 0.5:
                tool = random.choice(list(self.TOOLS.keys()))
                tool_span, current_time = self._create_tool_use_span(
                    trace_id, task_span_id, tool, current_time
                )
                spans.append(tool_span)

        # Update root span
        spans[0]["end_time"] = current_time.isoformat() + "Z"
        spans[0]["duration_ms"] = int((current_time - start_time).total_seconds() * 1000)
        spans[0]["output_data"] = {"result": context[:500]}

        return spans

    async def generate_hierarchical_crew_trace(
        self,
        failure_mode: str,
        scenario: str,
        task: str,
    ) -> list[dict]:
        """Generate a hierarchical crew execution trace (manager + workers)."""

        trace_id = self._generate_trace_id()
        spans = []
        start_time = datetime.utcnow()

        manager = "planner"
        workers = ["researcher", "developer", "analyst"]

        # Root span
        root_span_id = self._generate_span_id()
        spans.append({
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "crewai.crew.kickoff",
            "agent_id": "crew_manager",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "input_data": {"task": task, "process": "hierarchical"},
            "metadata": {
                "framework": "crewai",
                "process_type": "hierarchical",
                "failure_mode": failure_mode,
                "manager": manager,
                "workers": workers,
            }
        })

        current_time = start_time + timedelta(milliseconds=100)

        # Manager creates plan
        manager_info = self.AGENTS[manager]
        manager_prompt, manager_output = await self._generate_task_output(
            manager, f"Create plan for: {task}", failure_mode, scenario
        )

        manager_span_id = self._generate_span_id()
        duration = random.randint(1000, 3000)
        end_time = current_time + timedelta(milliseconds=duration)

        spans.append({
            "trace_id": trace_id,
            "span_id": manager_span_id,
            "parent_id": root_span_id,
            "name": "crewai.manager.delegate",
            "agent_id": manager,
            "span_type": "agent",
            "status": "ok",
            "start_time": current_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration,
            "prompt": manager_prompt,
            "response": manager_output,
            "input_data": {"task": task, "role": "manager"},
            "output_data": {"plan": manager_output[:300]},
            "metadata": {
                "framework": "crewai",
                "is_manager": True,
                "delegating_to": workers,
            }
        })

        current_time = end_time + timedelta(milliseconds=50)
        context = f"Plan: {manager_output[:300]}"

        # Workers execute delegated tasks
        for i, worker in enumerate(workers):
            worker_info = self.AGENTS[worker]

            worker_prompt, worker_output = await self._generate_task_output(
                worker, f"Execute subtask {i+1}: {scenario}", failure_mode, scenario, context
            )
            context += f"\n{worker}: {worker_output[:200]}"

            worker_span_id = self._generate_span_id()
            duration = random.randint(1000, 4000)
            end_time = current_time + timedelta(milliseconds=duration)

            spans.append({
                "trace_id": trace_id,
                "span_id": worker_span_id,
                "parent_id": manager_span_id,
                "name": "crewai.task.execute",
                "agent_id": worker,
                "span_type": "agent",
                "status": "ok",
                "start_time": current_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z",
                "duration_ms": duration,
                "prompt": worker_prompt,
                "response": worker_output,
                "input_data": {
                    "delegated_task": f"Subtask {i+1}",
                    "agent_role": worker_info["role"],
                },
                "output_data": {"result": worker_output[:200]},
                "metadata": {
                    "framework": "crewai",
                    "agent_role": worker_info["role"],
                    "delegated_by": manager,
                    "subtask_index": i,
                }
            })

            current_time = end_time + timedelta(milliseconds=50)

            # Tool usage for some workers
            if worker in ["developer", "analyst"] and random.random() > 0.4:
                tool = "code_interpreter" if worker == "developer" else "calculator"
                tool_span, current_time = self._create_tool_use_span(
                    trace_id, worker_span_id, tool, current_time
                )
                spans.append(tool_span)

        # Update root span
        spans[0]["end_time"] = current_time.isoformat() + "Z"
        spans[0]["duration_ms"] = int((current_time - start_time).total_seconds() * 1000)
        spans[0]["output_data"] = {"result": context[:500]}

        return spans

    async def generate_trace(
        self,
        failure_mode: str,
        complexity: Literal["simple", "medium", "complex"] = "medium",
    ) -> list[dict]:
        """Generate a trace for the given failure mode and complexity."""

        mode_info = FAILURE_MODES[failure_mode]
        scenario = random.choice(mode_info["scenarios"])
        task = f"CrewAI task for {mode_info['name']}: {scenario}"

        if complexity == "simple":
            return await self.generate_sequential_crew_trace(failure_mode, scenario, task)
        else:
            return await self.generate_hierarchical_crew_trace(failure_mode, scenario, task)

    async def generate_all_traces(
        self,
        traces_per_mode: int = 10,
        complexity: Literal["simple", "medium", "complex"] = "simple",
    ) -> dict[str, list[list[dict]]]:
        """Generate traces for all failure modes."""

        all_traces = {}

        for mode in FAILURE_MODES:
            print(f"  Generating CrewAI traces for {mode}...")
            mode_traces = []

            for i in range(traces_per_mode):
                try:
                    trace = await self.generate_trace(mode, complexity)
                    mode_traces.append(trace)
                except Exception as e:
                    print(f"    Error generating trace {i}: {e}")

            all_traces[mode] = mode_traces

            # Save to file
            output_file = self.output_dir / f"{mode}_crewai_{complexity}_traces.jsonl"
            with open(output_file, "w") as f:
                for trace in mode_traces:
                    for span in trace:
                        f.write(json.dumps(span) + "\n")

            print(f"    Saved {len(mode_traces)} traces to {output_file}")

        return all_traces


async def main():
    """Generate CrewAI traces for all failure modes."""
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    generator = CrewAITraceGenerator(api_key, output_dir="traces")

    print("Generating CrewAI traces...")
    for complexity in ["simple", "medium"]:
        print(f"\nComplexity: {complexity}")
        await generator.generate_all_traces(traces_per_mode=10, complexity=complexity)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
