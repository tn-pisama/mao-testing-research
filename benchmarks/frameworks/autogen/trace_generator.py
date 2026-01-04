"""AutoGen-style multi-agent trace generator.

Generates traces simulating Microsoft AutoGen conversation patterns:
- AssistantAgent, UserProxyAgent, GroupChat
- Two-agent, group chat, and nested conversation patterns
- Code execution and tool use patterns
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


class AutoGenTraceGenerator:
    """Generate traces simulating AutoGen multi-agent patterns."""

    AGENT_TYPES = {
        "assistant": {
            "class": "AssistantAgent",
            "description": "AI assistant that can write code and reason",
            "can_execute_code": False,
        },
        "user_proxy": {
            "class": "UserProxyAgent",
            "description": "Proxy for user that can execute code",
            "can_execute_code": True,
        },
        "coder": {
            "class": "AssistantAgent",
            "description": "Specialized coding assistant",
            "can_execute_code": False,
        },
        "critic": {
            "class": "AssistantAgent",
            "description": "Reviews and critiques solutions",
            "can_execute_code": False,
        },
        "planner": {
            "class": "AssistantAgent",
            "description": "Creates execution plans",
            "can_execute_code": False,
        },
        "executor": {
            "class": "UserProxyAgent",
            "description": "Executes code and returns results",
            "can_execute_code": True,
        },
    }

    CONVERSATION_PATTERNS = ["two_agent", "group_chat", "nested"]

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
        return f"autogen_trace_{uuid.uuid4().hex[:16]}"

    def _generate_span_id(self) -> str:
        return f"ag_span_{uuid.uuid4().hex[:12]}"

    async def _generate_agent_message(
        self,
        agent_type: str,
        task: str,
        failure_mode: str,
        scenario: str,
        conversation_history: str = "",
    ) -> tuple[str, str]:
        """Generate realistic AutoGen agent message using LLM."""

        agent_info = self.AGENT_TYPES.get(agent_type, self.AGENT_TYPES["assistant"])
        mode_info = FAILURE_MODES[failure_mode]

        prompt = f"""You are simulating a {agent_info['class']} ({agent_type}) in Microsoft AutoGen.
Generate a realistic agent message for this conversation.

Task: {task}
Agent Type: {agent_info['class']} - {agent_info['description']}
Failure mode to exhibit: {mode_info['name']}
Scenario: {scenario}
Description: {mode_info['description']}

{f"Conversation history: {conversation_history[:500]}" if conversation_history else ""}

Generate output that subtly exhibits this failure mode. Include code blocks if appropriate for a coder/assistant.
Format as a natural AutoGen agent response."""

        try:
            response = await self.model.ainvoke([
                SystemMessage(content=f"You are a {agent_info['class']} in AutoGen."),
                HumanMessage(content=prompt),
            ])
            return prompt, response.content
        except Exception as e:
            return prompt, f"Agent error: {str(e)}"

    def _create_code_execution_span(
        self,
        trace_id: str,
        parent_id: str,
        code: str,
        start_time: datetime,
        success: bool = True,
    ) -> tuple[dict, datetime]:
        """Create a code execution span (AutoGen pattern)."""

        duration_ms = random.randint(100, 3000)
        end_time = start_time + timedelta(milliseconds=duration_ms)

        span = {
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": parent_id,
            "name": "code_execution",
            "agent_id": "executor",
            "span_type": "tool_call",
            "status": "ok" if success else "error",
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration_ms,
            "input_data": {"code": code[:200], "language": "python"},
            "output_data": {
                "result": "Execution successful" if success else "ExecutionError: Code failed",
                "exit_code": 0 if success else 1,
            },
            "metadata": {
                "framework": "autogen",
                "execution_type": "code",
            }
        }

        return span, end_time

    async def generate_two_agent_trace(
        self,
        failure_mode: str,
        scenario: str,
        task: str,
    ) -> list[dict]:
        """Generate a two-agent conversation trace (assistant + user_proxy)."""

        trace_id = self._generate_trace_id()
        spans = []
        start_time = datetime.utcnow()

        # Root span
        root_span_id = self._generate_span_id()
        spans.append({
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "autogen.two_agent_chat",
            "agent_id": "orchestrator",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "input_data": {"task": task, "pattern": "two_agent"},
            "metadata": {
                "framework": "autogen",
                "pattern": "two_agent",
                "failure_mode": failure_mode,
            }
        })

        current_time = start_time + timedelta(milliseconds=50)
        conversation = ""

        # User proxy initiates
        user_prompt, user_msg = await self._generate_agent_message(
            "user_proxy", task, failure_mode, scenario
        )
        conversation += f"User: {user_msg}\n"

        user_span_id = self._generate_span_id()
        duration = random.randint(100, 500)
        end_time = current_time + timedelta(milliseconds=duration)

        spans.append({
            "trace_id": trace_id,
            "span_id": user_span_id,
            "parent_id": root_span_id,
            "name": "UserProxyAgent.send",
            "agent_id": "user_proxy",
            "span_type": "agent",
            "status": "ok",
            "start_time": current_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration,
            "prompt": user_prompt,
            "response": user_msg,
            "input_data": {"message": task},
            "output_data": {"response": user_msg[:200]},
            "metadata": {"framework": "autogen", "agent_class": "UserProxyAgent"}
        })

        current_time = end_time + timedelta(milliseconds=50)

        # Assistant responds (2-3 turns)
        for turn in range(random.randint(2, 3)):
            assistant_prompt, assistant_msg = await self._generate_agent_message(
                "assistant", task, failure_mode, scenario, conversation
            )
            conversation += f"Assistant: {assistant_msg}\n"

            assistant_span_id = self._generate_span_id()
            duration = random.randint(500, 2000)
            end_time = current_time + timedelta(milliseconds=duration)

            spans.append({
                "trace_id": trace_id,
                "span_id": assistant_span_id,
                "parent_id": root_span_id,
                "name": "AssistantAgent.generate_reply",
                "agent_id": "assistant",
                "span_type": "agent",
                "status": "ok",
                "start_time": current_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z",
                "duration_ms": duration,
                "prompt": assistant_prompt,
                "response": assistant_msg,
                "input_data": {"messages": conversation[:500]},
                "output_data": {"response": assistant_msg[:200]},
                "metadata": {"framework": "autogen", "agent_class": "AssistantAgent", "turn": turn}
            })

            current_time = end_time + timedelta(milliseconds=50)

            # Code execution if code block present
            if "```" in assistant_msg:
                code_span, current_time = self._create_code_execution_span(
                    trace_id, assistant_span_id, assistant_msg,
                    current_time, success=random.random() > 0.2
                )
                spans.append(code_span)
                current_time = current_time + timedelta(milliseconds=50)

        # Update root span end time
        spans[0]["end_time"] = current_time.isoformat() + "Z"
        spans[0]["duration_ms"] = int((current_time - start_time).total_seconds() * 1000)
        spans[0]["output_data"] = {"result": conversation[:500]}

        return spans

    async def generate_group_chat_trace(
        self,
        failure_mode: str,
        scenario: str,
        task: str,
    ) -> list[dict]:
        """Generate a group chat trace (multiple agents)."""

        trace_id = self._generate_trace_id()
        spans = []
        start_time = datetime.utcnow()

        agents = ["planner", "coder", "critic", "executor"]

        # Root span
        root_span_id = self._generate_span_id()
        spans.append({
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "autogen.group_chat",
            "agent_id": "group_chat_manager",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "input_data": {"task": task, "pattern": "group_chat", "agents": agents},
            "metadata": {
                "framework": "autogen",
                "pattern": "group_chat",
                "failure_mode": failure_mode,
                "num_agents": len(agents),
            }
        })

        current_time = start_time + timedelta(milliseconds=50)
        conversation = ""

        # Multiple agent turns
        for turn in range(random.randint(4, 6)):
            agent = agents[turn % len(agents)]
            agent_info = self.AGENT_TYPES[agent]

            prompt, response = await self._generate_agent_message(
                agent, task, failure_mode, scenario, conversation
            )
            conversation += f"{agent}: {response}\n"

            span_id = self._generate_span_id()
            duration = random.randint(500, 2000)
            end_time = current_time + timedelta(milliseconds=duration)

            spans.append({
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_id": root_span_id,
                "name": f"{agent_info['class']}.generate_reply",
                "agent_id": agent,
                "span_type": "agent",
                "status": "ok",
                "start_time": current_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z",
                "duration_ms": duration,
                "prompt": prompt,
                "response": response,
                "input_data": {"messages": conversation[:300]},
                "output_data": {"response": response[:200]},
                "metadata": {
                    "framework": "autogen",
                    "agent_class": agent_info["class"],
                    "turn": turn,
                    "speaker": agent,
                }
            })

            current_time = end_time + timedelta(milliseconds=50)

            # Code execution for executor
            if agent == "executor" and "```" in response:
                code_span, current_time = self._create_code_execution_span(
                    trace_id, span_id, response, current_time
                )
                spans.append(code_span)

        # Update root span
        spans[0]["end_time"] = current_time.isoformat() + "Z"
        spans[0]["duration_ms"] = int((current_time - start_time).total_seconds() * 1000)
        spans[0]["output_data"] = {"result": conversation[:500]}

        return spans

    async def generate_trace(
        self,
        failure_mode: str,
        complexity: Literal["simple", "medium", "complex"] = "medium",
    ) -> list[dict]:
        """Generate a trace for the given failure mode and complexity."""

        mode_info = FAILURE_MODES[failure_mode]
        scenario = random.choice(mode_info["scenarios"])
        task = f"Task for {mode_info['name']}: {scenario}"

        if complexity == "simple":
            return await self.generate_two_agent_trace(failure_mode, scenario, task)
        else:
            return await self.generate_group_chat_trace(failure_mode, scenario, task)

    async def generate_all_traces(
        self,
        traces_per_mode: int = 10,
        complexity: Literal["simple", "medium", "complex"] = "simple",
    ) -> dict[str, list[list[dict]]]:
        """Generate traces for all failure modes."""

        all_traces = {}

        for mode in FAILURE_MODES:
            print(f"  Generating AutoGen traces for {mode}...")
            mode_traces = []

            for i in range(traces_per_mode):
                try:
                    trace = await self.generate_trace(mode, complexity)
                    mode_traces.append(trace)
                except Exception as e:
                    print(f"    Error generating trace {i}: {e}")

            all_traces[mode] = mode_traces

            # Save to file
            output_file = self.output_dir / f"{mode}_autogen_{complexity}_traces.jsonl"
            with open(output_file, "w") as f:
                for trace in mode_traces:
                    for span in trace:
                        f.write(json.dumps(span) + "\n")

            print(f"    Saved {len(mode_traces)} traces to {output_file}")

        return all_traces


async def main():
    """Generate AutoGen traces for all failure modes."""
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    generator = AutoGenTraceGenerator(api_key, output_dir="traces")

    print("Generating AutoGen traces...")
    for complexity in ["simple", "medium"]:
        print(f"\nComplexity: {complexity}")
        await generator.generate_all_traces(traces_per_mode=10, complexity=complexity)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
