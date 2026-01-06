"""n8n workflow-style trace generator.

Generates traces simulating n8n workflow automation patterns:
- Workflow nodes (triggers, actions, AI agents)
- Sequential and parallel execution paths
- AI agent nodes with tool use
- Error handling and retry patterns
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


class N8NTraceGenerator:
    """Generate traces simulating n8n workflow automation patterns."""

    NODE_TYPES = {
        "webhook_trigger": {
            "type": "n8n-nodes-base.webhook",
            "description": "Receives HTTP webhook requests",
            "category": "trigger",
        },
        "schedule_trigger": {
            "type": "n8n-nodes-base.scheduleTrigger",
            "description": "Triggers on schedule",
            "category": "trigger",
        },
        "ai_agent": {
            "type": "@n8n/n8n-nodes-langchain.agent",
            "description": "AI agent that can reason and use tools",
            "category": "ai",
        },
        "ai_chain": {
            "type": "@n8n/n8n-nodes-langchain.chainLlm",
            "description": "LLM chain for text generation",
            "category": "ai",
        },
        "http_request": {
            "type": "n8n-nodes-base.httpRequest",
            "description": "Makes HTTP requests",
            "category": "action",
        },
        "code": {
            "type": "n8n-nodes-base.code",
            "description": "Executes JavaScript/Python code",
            "category": "action",
        },
        "if": {
            "type": "n8n-nodes-base.if",
            "description": "Conditional branching",
            "category": "logic",
        },
        "merge": {
            "type": "n8n-nodes-base.merge",
            "description": "Merges multiple inputs",
            "category": "logic",
        },
        "set": {
            "type": "n8n-nodes-base.set",
            "description": "Sets workflow variables",
            "category": "action",
        },
        "split_in_batches": {
            "type": "n8n-nodes-base.splitInBatches",
            "description": "Splits items into batches",
            "category": "logic",
        },
    }

    AI_TOOLS = {
        "web_search": {"description": "Search the web for information"},
        "code_executor": {"description": "Execute code snippets"},
        "wikipedia": {"description": "Search Wikipedia"},
        "calculator": {"description": "Perform calculations"},
        "memory": {"description": "Store and retrieve information"},
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
        return f"n8n_exec_{uuid.uuid4().hex[:16]}"

    def _generate_span_id(self) -> str:
        return f"n8n_node_{uuid.uuid4().hex[:12]}"

    def _generate_execution_id(self) -> str:
        return str(random.randint(1000, 99999))

    async def _generate_ai_output(
        self,
        node_name: str,
        task: str,
        failure_mode: str,
        scenario: str,
        context: str = "",
    ) -> tuple[str, str]:
        """Generate realistic n8n AI node output using LLM."""

        mode_info = FAILURE_MODES[failure_mode]

        prompt = f"""You are simulating an AI Agent node in an n8n workflow.
Generate realistic output for this automation step.

Node Name: {node_name}
Task: {task}
Failure mode to exhibit: {mode_info['name']}
Scenario: {scenario}
Description: {mode_info['description']}

{f"Input from previous nodes: {context[:500]}" if context else ""}

Generate output that subtly exhibits this failure mode.
Format as structured JSON-like data that would flow through n8n."""

        try:
            response = await self.model.ainvoke([
                SystemMessage(content="You are an AI agent node in an n8n workflow."),
                HumanMessage(content=prompt),
            ])
            return prompt, response.content
        except Exception as e:
            return prompt, f"Node execution error: {str(e)}"

    def _create_node_span(
        self,
        trace_id: str,
        parent_id: str,
        node_name: str,
        node_type: str,
        start_time: datetime,
        input_data: dict,
        output_data: dict,
        status: str = "ok",
        prompt: str = "",
        response: str = "",
    ) -> tuple[dict, datetime]:
        """Create a node execution span."""

        node_info = self.NODE_TYPES.get(node_type, {"type": node_type, "category": "unknown"})
        duration_ms = random.randint(50, 2000)
        end_time = start_time + timedelta(milliseconds=duration_ms)

        span = {
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": parent_id,
            "name": f"n8n.node.{node_name}",
            "agent_id": node_name,
            "span_type": "agent" if node_info.get("category") == "ai" else "chain",
            "status": status,
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration_ms,
            "input_data": input_data,
            "output_data": output_data,
            "metadata": {
                "framework": "n8n",
                "node_type": node_info.get("type", node_type),
                "node_category": node_info.get("category", "unknown"),
            }
        }

        if prompt:
            span["prompt"] = prompt
        if response:
            span["response"] = response

        return span, end_time

    def _create_tool_span(
        self,
        trace_id: str,
        parent_id: str,
        tool_name: str,
        start_time: datetime,
        success: bool = True,
    ) -> tuple[dict, datetime]:
        """Create a tool execution span within AI agent."""

        tool_info = self.AI_TOOLS.get(tool_name, {"description": "Unknown tool"})
        duration_ms = random.randint(100, 1500)
        end_time = start_time + timedelta(milliseconds=duration_ms)

        span = {
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": parent_id,
            "name": f"n8n.tool.{tool_name}",
            "agent_id": f"tool_{tool_name}",
            "span_type": "tool_call",
            "status": "ok" if success else "error",
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration_ms,
            "input_data": {"tool": tool_name},
            "output_data": {
                "result": f"Tool {tool_name} executed" if success else f"Tool {tool_name} failed",
                "success": success,
            },
            "metadata": {
                "framework": "n8n",
                "tool_type": "langchain",
            }
        }

        return span, end_time

    async def generate_simple_workflow_trace(
        self,
        failure_mode: str,
        scenario: str,
        task: str,
    ) -> list[dict]:
        """Generate a simple linear workflow trace."""

        trace_id = self._generate_trace_id()
        execution_id = self._generate_execution_id()
        spans = []
        start_time = datetime.utcnow()

        # Root span - Workflow execution
        root_span_id = self._generate_span_id()
        spans.append({
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "n8n.workflow.execute",
            "agent_id": "workflow_executor",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "input_data": {
                "workflow_name": f"Workflow_{failure_mode}",
                "execution_id": execution_id,
                "task": task,
            },
            "metadata": {
                "framework": "n8n",
                "workflow_type": "simple",
                "failure_mode": failure_mode,
                "execution_id": execution_id,
            }
        })

        current_time = start_time + timedelta(milliseconds=50)
        context = ""

        # Webhook trigger
        trigger_span, current_time = self._create_node_span(
            trace_id, root_span_id, "Webhook", "webhook_trigger",
            current_time, {"method": "POST", "path": "/webhook"},
            {"received": True, "body": {"task": task}}
        )
        spans.append(trigger_span)
        current_time = current_time + timedelta(milliseconds=30)

        # AI Agent node
        ai_prompt, ai_output = await self._generate_ai_output(
            "AI Agent", task, failure_mode, scenario, context
        )
        context = ai_output

        ai_span_id = self._generate_span_id()
        duration = random.randint(1000, 5000)
        end_time = current_time + timedelta(milliseconds=duration)

        spans.append({
            "trace_id": trace_id,
            "span_id": ai_span_id,
            "parent_id": root_span_id,
            "name": "n8n.node.AI Agent",
            "agent_id": "ai_agent",
            "span_type": "agent",
            "status": "ok",
            "start_time": current_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration,
            "prompt": ai_prompt,
            "response": ai_output,
            "input_data": {"task": task},
            "output_data": {"response": ai_output[:300]},
            "metadata": {
                "framework": "n8n",
                "node_type": "@n8n/n8n-nodes-langchain.agent",
                "node_category": "ai",
            }
        })

        current_time = end_time + timedelta(milliseconds=30)

        # Tool calls within AI agent
        for _ in range(random.randint(1, 3)):
            tool = random.choice(list(self.AI_TOOLS.keys()))
            tool_span, current_time = self._create_tool_span(
                trace_id, ai_span_id, tool, current_time
            )
            spans.append(tool_span)

        # Code node for post-processing
        code_span, current_time = self._create_node_span(
            trace_id, root_span_id, "Format Output", "code",
            current_time, {"code": "return items.map(...)"},
            {"formatted": True, "items_count": 1}
        )
        spans.append(code_span)

        # Update root span
        spans[0]["end_time"] = current_time.isoformat() + "Z"
        spans[0]["duration_ms"] = int((current_time - start_time).total_seconds() * 1000)
        spans[0]["output_data"] = {"result": context[:500], "status": "success"}

        return spans

    async def generate_complex_workflow_trace(
        self,
        failure_mode: str,
        scenario: str,
        task: str,
    ) -> list[dict]:
        """Generate a complex workflow with branching and multiple AI agents."""

        trace_id = self._generate_trace_id()
        execution_id = self._generate_execution_id()
        spans = []
        start_time = datetime.utcnow()

        # Root span
        root_span_id = self._generate_span_id()
        spans.append({
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "n8n.workflow.execute",
            "agent_id": "workflow_executor",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "input_data": {
                "workflow_name": f"Complex_Workflow_{failure_mode}",
                "execution_id": execution_id,
                "task": task,
            },
            "metadata": {
                "framework": "n8n",
                "workflow_type": "complex",
                "failure_mode": failure_mode,
                "execution_id": execution_id,
            }
        })

        current_time = start_time + timedelta(milliseconds=50)
        context = ""

        # Trigger
        trigger_span, current_time = self._create_node_span(
            trace_id, root_span_id, "Schedule Trigger", "schedule_trigger",
            current_time, {"cron": "0 9 * * *"},
            {"triggered": True, "timestamp": datetime.utcnow().isoformat()}
        )
        spans.append(trigger_span)
        current_time = current_time + timedelta(milliseconds=30)

        # HTTP Request to fetch data
        http_span, current_time = self._create_node_span(
            trace_id, root_span_id, "Fetch Data", "http_request",
            current_time, {"url": "https://api.example.com/data", "method": "GET"},
            {"status_code": 200, "data": {"items": []}}
        )
        spans.append(http_span)
        current_time = current_time + timedelta(milliseconds=30)

        # Split into batches
        split_span, current_time = self._create_node_span(
            trace_id, root_span_id, "Split In Batches", "split_in_batches",
            current_time, {"batch_size": 10},
            {"batches": 3}
        )
        spans.append(split_span)
        split_span_id = split_span["span_id"]
        current_time = current_time + timedelta(milliseconds=30)

        # Multiple AI agents processing batches
        ai_agents = ["Research Agent", "Analysis Agent", "Summary Agent"]
        for i, agent_name in enumerate(ai_agents):
            ai_prompt, ai_output = await self._generate_ai_output(
                agent_name, f"Process batch {i+1}: {task}", failure_mode, scenario, context
            )
            context += f"\n{agent_name}: {ai_output[:200]}"

            ai_span_id = self._generate_span_id()
            duration = random.randint(1000, 4000)
            end_time = current_time + timedelta(milliseconds=duration)

            spans.append({
                "trace_id": trace_id,
                "span_id": ai_span_id,
                "parent_id": split_span_id,
                "name": f"n8n.node.{agent_name}",
                "agent_id": agent_name.lower().replace(" ", "_"),
                "span_type": "agent",
                "status": "ok",
                "start_time": current_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z",
                "duration_ms": duration,
                "prompt": ai_prompt,
                "response": ai_output,
                "input_data": {"batch": i, "task": task},
                "output_data": {"response": ai_output[:200]},
                "metadata": {
                    "framework": "n8n",
                    "node_type": "@n8n/n8n-nodes-langchain.agent",
                    "batch_index": i,
                }
            })

            current_time = end_time + timedelta(milliseconds=30)

            # Tool calls
            if random.random() > 0.3:
                tool = random.choice(list(self.AI_TOOLS.keys()))
                tool_span, current_time = self._create_tool_span(
                    trace_id, ai_span_id, tool, current_time
                )
                spans.append(tool_span)

        # Merge results
        merge_span, current_time = self._create_node_span(
            trace_id, root_span_id, "Merge Results", "merge",
            current_time, {"mode": "append"},
            {"merged_items": len(ai_agents)}
        )
        spans.append(merge_span)

        # Conditional check
        if_span, current_time = self._create_node_span(
            trace_id, root_span_id, "Check Results", "if",
            current_time, {"condition": "{{ $json.success }}"},
            {"branch": "true"}
        )
        spans.append(if_span)

        # Final processing
        final_span, current_time = self._create_node_span(
            trace_id, root_span_id, "Final Output", "set",
            current_time, {"values": {"status": "complete"}},
            {"result": context[:300]}
        )
        spans.append(final_span)

        # Update root span
        spans[0]["end_time"] = current_time.isoformat() + "Z"
        spans[0]["duration_ms"] = int((current_time - start_time).total_seconds() * 1000)
        spans[0]["output_data"] = {"result": context[:500], "status": "success"}

        return spans

    async def generate_trace(
        self,
        failure_mode: str,
        complexity: Literal["simple", "medium", "complex"] = "medium",
    ) -> list[dict]:
        """Generate a trace for the given failure mode and complexity."""

        mode_info = FAILURE_MODES[failure_mode]
        scenario = random.choice(mode_info["scenarios"])
        task = f"n8n workflow for {mode_info['name']}: {scenario}"

        if complexity == "simple":
            return await self.generate_simple_workflow_trace(failure_mode, scenario, task)
        else:
            return await self.generate_complex_workflow_trace(failure_mode, scenario, task)

    async def generate_all_traces(
        self,
        traces_per_mode: int = 10,
        complexity: Literal["simple", "medium", "complex"] = "simple",
    ) -> dict[str, list[list[dict]]]:
        """Generate traces for all failure modes."""

        all_traces = {}

        for mode in FAILURE_MODES:
            print(f"  Generating n8n traces for {mode}...")
            mode_traces = []

            for i in range(traces_per_mode):
                try:
                    trace = await self.generate_trace(mode, complexity)
                    mode_traces.append(trace)
                except Exception as e:
                    print(f"    Error generating trace {i}: {e}")

            all_traces[mode] = mode_traces

            # Save to file
            output_file = self.output_dir / f"{mode}_n8n_{complexity}_traces.jsonl"
            with open(output_file, "w") as f:
                for trace in mode_traces:
                    for span in trace:
                        f.write(json.dumps(span) + "\n")

            print(f"    Saved {len(mode_traces)} traces to {output_file}")

        return all_traces


async def main():
    """Generate n8n traces for all failure modes."""
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    generator = N8NTraceGenerator(api_key, output_dir="traces")

    print("Generating n8n traces...")
    for complexity in ["simple", "medium"]:
        print(f"\nComplexity: {complexity}")
        await generator.generate_all_traces(traces_per_mode=10, complexity=complexity)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
