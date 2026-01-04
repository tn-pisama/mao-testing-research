"""Enhanced trace generator with multi-tier complexity and advanced patterns.

Generates traces at 3 complexity levels:
- Simple: 2 agents, 3 spans, linear flow
- Medium: 3-4 agents, 6-10 spans, review loop, basic tools
- Complex: 5-6+ agents, 12-20+ spans, parallel, nested, errors, retries
"""

import asyncio
import json
import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

# Import failure mode definitions from original generator
from src.trace_generator import FAILURE_MODES


class ComplexTraceGenerator:
    """Enhanced trace generator with multi-tier complexity."""

    SPAN_TYPES = ["agent", "chain", "tool_call", "validation", "retry", "error", "human_input"]

    TOOLS = {
        "web_search": {"success_rate": 0.9, "avg_duration_ms": 1500},
        "code_execute": {"success_rate": 0.75, "avg_duration_ms": 2000},
        "database_query": {"success_rate": 0.85, "avg_duration_ms": 500},
        "file_read": {"success_rate": 0.95, "avg_duration_ms": 100},
        "file_write": {"success_rate": 0.9, "avg_duration_ms": 200},
        "api_call": {"success_rate": 0.8, "avg_duration_ms": 800},
    }

    AGENT_ROLES = {
        "researcher": {"description": "Gathers and analyzes information"},
        "writer": {"description": "Creates and refines content"},
        "planner": {"description": "Decomposes tasks and creates plans"},
        "reviewer": {"description": "Reviews and provides feedback"},
        "validator": {"description": "Validates against specifications"},
        "executor": {"description": "Executes tasks using tools"},
        "aggregator": {"description": "Combines results from multiple sources"},
        "supervisor": {"description": "Orchestrates workflow and delegation"},
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
        return f"trace_{uuid.uuid4().hex[:16]}"

    def _generate_span_id(self) -> str:
        return f"span_{uuid.uuid4().hex[:12]}"

    async def _generate_agent_content(
        self,
        role: str,
        task: str,
        failure_mode: str,
        scenario: str,
        context: str = "",
    ) -> tuple[str, str, dict]:
        """Generate realistic agent prompt/response content using LLM."""

        mode_info = FAILURE_MODES[failure_mode]

        prompt = f"""You are simulating a {role.upper()} AGENT in a multi-agent system.
Generate realistic {role} output for this scenario.

Task: {task}
Failure mode to exhibit: {mode_info['name']}
Scenario: {scenario}
Description: {mode_info['description']}

{f"Context from previous steps: {context[:500]}" if context else ""}

Generate output that subtly exhibits this failure mode. Be realistic and natural."""

        try:
            response = await self.model.ainvoke([
                SystemMessage(content=f"You are a {role} agent in a multi-agent system."),
                HumanMessage(content=prompt),
            ])
            response_text = response.content
            tokens = getattr(response, 'usage_metadata', {})
        except Exception as e:
            response_text = f"{role.title()} error: {str(e)}"
            tokens = {}

        return prompt, response_text, tokens

    def _create_tool_call_span(
        self,
        trace_id: str,
        parent_id: str,
        tool_name: str,
        start_time: datetime,
        inject_failure: bool = False,
    ) -> tuple[dict, datetime]:
        """Create a tool call span with success/failure simulation."""

        tool_config = self.TOOLS.get(tool_name, {"success_rate": 0.8, "avg_duration_ms": 500})

        # Determine success/failure
        if inject_failure:
            success = False
            status = random.choice(["error", "timeout"])
        else:
            success = random.random() < tool_config["success_rate"]
            status = "ok" if success else random.choice(["error", "timeout"])

        duration_ms = int(tool_config["avg_duration_ms"] * (0.5 + random.random()))
        end_time = start_time + timedelta(milliseconds=duration_ms)

        span = {
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": parent_id,
            "name": f"tool.{tool_name}",
            "agent_id": f"tool_{tool_name}",
            "span_type": "tool_call",
            "status": status,
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration_ms,
            "input_data": {"tool": tool_name, "params": {"query": "example"}},
            "output_data": {
                "result": "Success" if success else f"Error: {status}",
                "success": success,
            },
            "metadata": {
                "tool_name": tool_name,
                "tool_status": status,
                "success": success,
            }
        }

        return span, end_time

    def _create_validation_span(
        self,
        trace_id: str,
        parent_id: str,
        validation_type: str,
        start_time: datetime,
        passed: bool = True,
        bypassed: bool = False,
    ) -> tuple[dict, datetime]:
        """Create a validation checkpoint span."""

        duration_ms = random.randint(50, 200)
        end_time = start_time + timedelta(milliseconds=duration_ms)

        status = "ok" if passed else "failed"
        if bypassed:
            status = "bypassed"

        span = {
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": parent_id,
            "name": f"validation.{validation_type}",
            "agent_id": "validator",
            "span_type": "validation",
            "status": status,
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration_ms,
            "input_data": {"validation_type": validation_type},
            "output_data": {
                "result": "PASSED" if passed else ("BYPASSED" if bypassed else "FAILED"),
                "passed": passed,
                "bypassed": bypassed,
            },
            "metadata": {
                "validation_type": validation_type,
                "validation_passed": passed,
                "validation_bypassed": bypassed,
                "role": "validation",
            }
        }

        return span, end_time

    def _create_retry_span(
        self,
        trace_id: str,
        parent_id: str,
        attempt: int,
        max_attempts: int,
        start_time: datetime,
        success: bool = False,
    ) -> tuple[dict, datetime]:
        """Create a retry attempt span."""

        duration_ms = random.randint(100, 500)
        end_time = start_time + timedelta(milliseconds=duration_ms)

        span = {
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": parent_id,
            "name": f"retry.attempt_{attempt}",
            "agent_id": "retry_handler",
            "span_type": "retry",
            "status": "ok" if success else "retry",
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration_ms,
            "input_data": {"attempt": attempt, "max_attempts": max_attempts},
            "output_data": {"success": success, "should_retry": not success and attempt < max_attempts},
            "metadata": {
                "retry_attempt": attempt,
                "max_attempts": max_attempts,
                "retry_success": success,
            }
        }

        return span, end_time

    def _create_error_span(
        self,
        trace_id: str,
        parent_id: str,
        error_type: str,
        error_message: str,
        start_time: datetime,
    ) -> tuple[dict, datetime]:
        """Create an error span."""

        duration_ms = random.randint(10, 50)
        end_time = start_time + timedelta(milliseconds=duration_ms)

        span = {
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": parent_id,
            "name": f"error.{error_type}",
            "agent_id": "error_handler",
            "span_type": "error",
            "status": "error",
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_ms": duration_ms,
            "input_data": {},
            "output_data": {"error_type": error_type, "error_message": error_message},
            "metadata": {
                "error_type": error_type,
                "error_message": error_message,
            }
        }

        return span, end_time

    async def generate_simple_trace(
        self,
        failure_mode: str,
        scenario: str,
        trace_num: int,
    ) -> dict:
        """Generate a simple 2-agent trace (research → write)."""

        trace_id = self._generate_trace_id()
        start_time = datetime.utcnow()
        spans = []

        mode_info = FAILURE_MODES[failure_mode]

        # Root span
        root_span_id = self._generate_span_id()

        # Research agent
        research_prompt, research_response, research_tokens = await self._generate_agent_content(
            role="researcher",
            task=scenario,
            failure_mode=failure_mode,
            scenario=scenario,
        )

        research_start = start_time + timedelta(milliseconds=100)
        research_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": root_span_id,
            "name": "research_agent",
            "agent_id": "researcher",
            "span_type": "agent",
            "status": "ok",
            "start_time": research_start.isoformat() + "Z",
            "end_time": research_end.isoformat() + "Z",
            "duration_ms": int((research_end - research_start).total_seconds() * 1000),
            "input_data": {"task": scenario},
            "output_data": {"research": research_response[:500]},
            "prompt": research_prompt,
            "response": research_response,
            "model": "claude-3-5-haiku-20241022",
            "tokens_input": research_tokens.get('input_tokens', 0),
            "tokens_output": research_tokens.get('output_tokens', 0),
            "metadata": {
                "failure_mode": failure_mode,
                "failure_name": mode_info["name"],
                "scenario": scenario,
                "role": "research",
            }
        })

        # Writer agent
        writer_prompt, writer_response, writer_tokens = await self._generate_agent_content(
            role="writer",
            task=scenario,
            failure_mode=failure_mode,
            scenario=scenario,
            context=research_response,
        )

        writer_start = research_end + timedelta(milliseconds=50)
        writer_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": root_span_id,
            "name": "writer_agent",
            "agent_id": "writer",
            "span_type": "agent",
            "status": "ok",
            "start_time": writer_start.isoformat() + "Z",
            "end_time": writer_end.isoformat() + "Z",
            "duration_ms": int((writer_end - writer_start).total_seconds() * 1000),
            "input_data": {"research": research_response[:200]},
            "output_data": {"content": writer_response[:500]},
            "prompt": writer_prompt,
            "response": writer_response,
            "model": "claude-3-5-haiku-20241022",
            "tokens_input": writer_tokens.get('input_tokens', 0),
            "tokens_output": writer_tokens.get('output_tokens', 0),
            "metadata": {
                "failure_mode": failure_mode,
                "failure_name": mode_info["name"],
                "scenario": scenario,
                "role": "writing",
            }
        })

        # Root span
        root_end = writer_end + timedelta(milliseconds=50)
        spans.insert(0, {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "workflow.simple",
            "agent_id": "orchestrator",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": root_end.isoformat() + "Z",
            "duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "input_data": {"task": scenario},
            "output_data": {"result": "completed"},
            "metadata": {
                "failure_mode": failure_mode,
                "failure_name": mode_info["name"],
                "scenario": scenario,
                "complexity": "simple",
                "trace_num": trace_num,
            }
        })

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "failure_name": mode_info["name"],
            "scenario": scenario,
            "complexity": "simple",
            "spans": spans,
            "source_format": "langgraph",
            "total_duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "total_tokens": sum(s.get("tokens_input", 0) + s.get("tokens_output", 0) for s in spans),
        }

    async def generate_medium_trace(
        self,
        failure_mode: str,
        scenario: str,
        trace_num: int,
    ) -> dict:
        """Generate a medium complexity trace (research → write → review → revise)."""

        trace_id = self._generate_trace_id()
        start_time = datetime.utcnow()
        spans = []

        mode_info = FAILURE_MODES[failure_mode]

        # Root span
        root_span_id = self._generate_span_id()

        # Research agent
        research_prompt, research_response, research_tokens = await self._generate_agent_content(
            role="researcher",
            task=scenario,
            failure_mode=failure_mode,
            scenario=scenario,
        )

        research_start = start_time + timedelta(milliseconds=100)
        research_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": root_span_id,
            "name": "research_agent",
            "agent_id": "researcher",
            "span_type": "agent",
            "status": "ok",
            "start_time": research_start.isoformat() + "Z",
            "end_time": research_end.isoformat() + "Z",
            "duration_ms": int((research_end - research_start).total_seconds() * 1000),
            "prompt": research_prompt,
            "response": research_response,
            "model": "claude-3-5-haiku-20241022",
            "tokens_input": research_tokens.get('input_tokens', 0),
            "tokens_output": research_tokens.get('output_tokens', 0),
            "metadata": {"role": "research", "failure_mode": failure_mode}
        })

        # Add a tool call for research
        tool_span, current_time = self._create_tool_call_span(
            trace_id, root_span_id, "web_search", research_end
        )
        spans.append(tool_span)

        # Writer agent
        writer_prompt, writer_response, writer_tokens = await self._generate_agent_content(
            role="writer",
            task=scenario,
            failure_mode=failure_mode,
            scenario=scenario,
            context=research_response,
        )

        writer_start = current_time + timedelta(milliseconds=50)
        writer_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": root_span_id,
            "name": "writer_agent",
            "agent_id": "writer",
            "span_type": "agent",
            "status": "ok",
            "start_time": writer_start.isoformat() + "Z",
            "end_time": writer_end.isoformat() + "Z",
            "duration_ms": int((writer_end - writer_start).total_seconds() * 1000),
            "prompt": writer_prompt,
            "response": writer_response,
            "model": "claude-3-5-haiku-20241022",
            "tokens_input": writer_tokens.get('input_tokens', 0),
            "tokens_output": writer_tokens.get('output_tokens', 0),
            "metadata": {"role": "writing", "failure_mode": failure_mode}
        })

        # Reviewer agent
        reviewer_prompt, reviewer_response, reviewer_tokens = await self._generate_agent_content(
            role="reviewer",
            task=f"Review this content: {writer_response[:300]}",
            failure_mode=failure_mode,
            scenario=scenario,
            context=writer_response,
        )

        reviewer_start = writer_end + timedelta(milliseconds=50)
        reviewer_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": root_span_id,
            "name": "reviewer_agent",
            "agent_id": "reviewer",
            "span_type": "agent",
            "status": "ok",
            "start_time": reviewer_start.isoformat() + "Z",
            "end_time": reviewer_end.isoformat() + "Z",
            "duration_ms": int((reviewer_end - reviewer_start).total_seconds() * 1000),
            "prompt": reviewer_prompt,
            "response": reviewer_response,
            "model": "claude-3-5-haiku-20241022",
            "tokens_input": reviewer_tokens.get('input_tokens', 0),
            "tokens_output": reviewer_tokens.get('output_tokens', 0),
            "metadata": {"role": "review", "failure_mode": failure_mode}
        })

        # Add validation span (may be bypassed for F13)
        bypass_validation = failure_mode == "F13" and random.random() < 0.5
        validation_span, current_time = self._create_validation_span(
            trace_id, root_span_id, "content_quality", reviewer_end,
            passed=not bypass_validation, bypassed=bypass_validation
        )
        spans.append(validation_span)

        # Revision (writer revises based on feedback)
        revision_prompt, revision_response, revision_tokens = await self._generate_agent_content(
            role="writer",
            task=f"Revise based on feedback: {reviewer_response[:300]}",
            failure_mode=failure_mode,
            scenario=scenario,
            context=f"{writer_response[:200]}\n\nFeedback: {reviewer_response[:200]}",
        )

        revision_start = current_time + timedelta(milliseconds=50)
        revision_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": root_span_id,
            "name": "writer_agent_revision",
            "agent_id": "writer",
            "span_type": "agent",
            "status": "ok",
            "start_time": revision_start.isoformat() + "Z",
            "end_time": revision_end.isoformat() + "Z",
            "duration_ms": int((revision_end - revision_start).total_seconds() * 1000),
            "prompt": revision_prompt,
            "response": revision_response,
            "model": "claude-3-5-haiku-20241022",
            "tokens_input": revision_tokens.get('input_tokens', 0),
            "tokens_output": revision_tokens.get('output_tokens', 0),
            "metadata": {"role": "revision", "failure_mode": failure_mode, "is_revision": True}
        })

        # Root span
        root_end = revision_end + timedelta(milliseconds=50)
        spans.insert(0, {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "workflow.review_loop",
            "agent_id": "orchestrator",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": root_end.isoformat() + "Z",
            "duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "metadata": {
                "failure_mode": failure_mode,
                "failure_name": mode_info["name"],
                "scenario": scenario,
                "complexity": "medium",
                "trace_num": trace_num,
            }
        })

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "failure_name": mode_info["name"],
            "scenario": scenario,
            "complexity": "medium",
            "spans": spans,
            "source_format": "langgraph",
            "total_duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "total_tokens": sum(s.get("tokens_input", 0) + s.get("tokens_output", 0) for s in spans),
        }

    async def generate_complex_trace(
        self,
        failure_mode: str,
        scenario: str,
        trace_num: int,
    ) -> dict:
        """Generate a complex trace with hierarchical delegation, tools, retries, and errors."""

        trace_id = self._generate_trace_id()
        start_time = datetime.utcnow()
        spans = []

        mode_info = FAILURE_MODES[failure_mode]

        # Root span (supervisor)
        root_span_id = self._generate_span_id()

        # Supervisor initiates
        supervisor_start = start_time
        supervisor_end = start_time + timedelta(milliseconds=100)

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": root_span_id,
            "name": "supervisor_agent",
            "agent_id": "supervisor",
            "span_type": "agent",
            "status": "ok",
            "start_time": supervisor_start.isoformat() + "Z",
            "end_time": supervisor_end.isoformat() + "Z",
            "duration_ms": 100,
            "prompt": f"Supervise task: {scenario}",
            "response": "Initiating hierarchical workflow",
            "metadata": {"role": "supervision", "failure_mode": failure_mode}
        })

        # Planner decomposes task
        planner_prompt, planner_response, planner_tokens = await self._generate_agent_content(
            role="planner",
            task=scenario,
            failure_mode=failure_mode,
            scenario=scenario,
        )

        planner_start = supervisor_end + timedelta(milliseconds=50)
        planner_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": root_span_id,
            "name": "planner_agent",
            "agent_id": "planner",
            "span_type": "agent",
            "status": "ok",
            "start_time": planner_start.isoformat() + "Z",
            "end_time": planner_end.isoformat() + "Z",
            "duration_ms": int((planner_end - planner_start).total_seconds() * 1000),
            "prompt": planner_prompt,
            "response": planner_response,
            "model": "claude-3-5-haiku-20241022",
            "tokens_input": planner_tokens.get('input_tokens', 0),
            "tokens_output": planner_tokens.get('output_tokens', 0),
            "metadata": {"role": "planning", "failure_mode": failure_mode}
        })

        current_time = planner_end

        # Multiple executor agents with tool calls
        executor_contexts = []
        for i, (tool_name, role_desc) in enumerate([
            ("web_search", "research"),
            ("database_query", "data_retrieval"),
            ("code_execute", "processing"),
        ]):
            executor_prompt, executor_response, executor_tokens = await self._generate_agent_content(
                role="executor",
                task=f"Execute phase {i+1}: {role_desc}",
                failure_mode=failure_mode,
                scenario=scenario,
                context=planner_response[:300],
            )

            executor_start = current_time + timedelta(milliseconds=50)
            executor_end = datetime.utcnow()

            executor_span_id = self._generate_span_id()
            spans.append({
                "trace_id": trace_id,
                "span_id": executor_span_id,
                "parent_id": root_span_id,
                "name": f"executor_agent_{i+1}",
                "agent_id": f"executor_{i+1}",
                "span_type": "agent",
                "status": "ok",
                "start_time": executor_start.isoformat() + "Z",
                "end_time": executor_end.isoformat() + "Z",
                "duration_ms": int((executor_end - executor_start).total_seconds() * 1000),
                "prompt": executor_prompt,
                "response": executor_response,
                "model": "claude-3-5-haiku-20241022",
                "tokens_input": executor_tokens.get('input_tokens', 0),
                "tokens_output": executor_tokens.get('output_tokens', 0),
                "metadata": {"role": role_desc, "executor_index": i+1, "failure_mode": failure_mode}
            })

            executor_contexts.append(executor_response)

            # Tool call for this executor
            inject_failure = (failure_mode == "F4" and i == 1)  # Tool failure for F4
            tool_span, current_time = self._create_tool_call_span(
                trace_id, executor_span_id, tool_name, executor_end,
                inject_failure=inject_failure
            )
            spans.append(tool_span)

            # Add retry spans if tool failed
            if not tool_span["output_data"]["success"]:
                for attempt in range(1, 3):
                    retry_success = attempt == 2 and random.random() > 0.3
                    retry_span, current_time = self._create_retry_span(
                        trace_id, executor_span_id, attempt, 3, current_time, retry_success
                    )
                    spans.append(retry_span)
                    if retry_success:
                        break

        # Aggregator combines results
        aggregator_prompt, aggregator_response, aggregator_tokens = await self._generate_agent_content(
            role="aggregator",
            task="Combine executor results",
            failure_mode=failure_mode,
            scenario=scenario,
            context="\n".join(executor_contexts),
        )

        aggregator_start = current_time + timedelta(milliseconds=50)
        aggregator_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": root_span_id,
            "name": "aggregator_agent",
            "agent_id": "aggregator",
            "span_type": "agent",
            "status": "ok",
            "start_time": aggregator_start.isoformat() + "Z",
            "end_time": aggregator_end.isoformat() + "Z",
            "duration_ms": int((aggregator_end - aggregator_start).total_seconds() * 1000),
            "prompt": aggregator_prompt,
            "response": aggregator_response,
            "model": "claude-3-5-haiku-20241022",
            "tokens_input": aggregator_tokens.get('input_tokens', 0),
            "tokens_output": aggregator_tokens.get('output_tokens', 0),
            "metadata": {"role": "aggregation", "failure_mode": failure_mode}
        })

        # Validation checkpoints
        validations = [
            ("schema", True),
            ("content", failure_mode not in ["F12"]),
            ("approval", failure_mode not in ["F13"]),
        ]

        current_time = aggregator_end
        for val_type, passed in validations:
            bypassed = failure_mode == "F13" and val_type == "approval" and random.random() < 0.5
            val_span, current_time = self._create_validation_span(
                trace_id, root_span_id, val_type, current_time,
                passed=passed, bypassed=bypassed
            )
            spans.append(val_span)

        # Add error span for certain failure modes
        if failure_mode in ["F5", "F11"] and random.random() < 0.3:
            error_span, current_time = self._create_error_span(
                trace_id, root_span_id,
                "coordination_error" if failure_mode == "F11" else "workflow_error",
                "Unexpected state during workflow execution",
                current_time
            )
            spans.append(error_span)

        # Final validator
        validator_prompt, validator_response, validator_tokens = await self._generate_agent_content(
            role="validator",
            task="Validate final output",
            failure_mode=failure_mode,
            scenario=scenario,
            context=aggregator_response,
        )

        validator_start = current_time + timedelta(milliseconds=50)
        validator_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": self._generate_span_id(),
            "parent_id": root_span_id,
            "name": "validator_agent",
            "agent_id": "validator",
            "span_type": "agent",
            "status": "ok",
            "start_time": validator_start.isoformat() + "Z",
            "end_time": validator_end.isoformat() + "Z",
            "duration_ms": int((validator_end - validator_start).total_seconds() * 1000),
            "prompt": validator_prompt,
            "response": validator_response,
            "model": "claude-3-5-haiku-20241022",
            "tokens_input": validator_tokens.get('input_tokens', 0),
            "tokens_output": validator_tokens.get('output_tokens', 0),
            "metadata": {"role": "validation", "failure_mode": failure_mode}
        })

        # Root span
        root_end = validator_end + timedelta(milliseconds=50)
        spans.insert(0, {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "workflow.hierarchical",
            "agent_id": "orchestrator",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": root_end.isoformat() + "Z",
            "duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "metadata": {
                "failure_mode": failure_mode,
                "failure_name": mode_info["name"],
                "scenario": scenario,
                "complexity": "complex",
                "trace_num": trace_num,
                "agent_count": 7,
            }
        })

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "failure_name": mode_info["name"],
            "scenario": scenario,
            "complexity": "complex",
            "spans": spans,
            "source_format": "langgraph",
            "total_duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "total_tokens": sum(s.get("tokens_input", 0) + s.get("tokens_output", 0) for s in spans),
        }

    async def generate_tiered_traces(
        self,
        traces_per_tier: int = 50,
        concurrency: int = 5,
    ) -> dict[str, list[dict]]:
        """Generate traces for all failure modes at all complexity tiers."""

        all_traces = {"simple": [], "medium": [], "complex": []}
        total = len(FAILURE_MODES) * 3 * traces_per_tier
        completed = [0]
        semaphore = asyncio.Semaphore(concurrency)

        async def generate_with_semaphore(
            tier: str,
            failure_mode: str,
            scenario_idx: int,
            trace_num: int,
        ):
            async with semaphore:
                try:
                    mode_info = FAILURE_MODES[failure_mode]
                    scenario = mode_info["scenarios"][scenario_idx % len(mode_info["scenarios"])]

                    if tier == "simple":
                        trace = await self.generate_simple_trace(failure_mode, scenario, trace_num)
                    elif tier == "medium":
                        trace = await self.generate_medium_trace(failure_mode, scenario, trace_num)
                    else:
                        trace = await self.generate_complex_trace(failure_mode, scenario, trace_num)

                    completed[0] += 1
                    print(f"  [{completed[0]}/{total}] {tier}/{failure_mode} #{trace_num} ✓ ({len(trace['spans'])} spans)", flush=True)
                    return trace
                except Exception as e:
                    completed[0] += 1
                    print(f"  [{completed[0]}/{total}] {tier}/{failure_mode} #{trace_num} ✗ {e}")
                    return None

        for tier in ["simple", "medium", "complex"]:
            print(f"\n{'='*60}")
            print(f"Generating {tier.upper()} traces")
            print(f"{'='*60}")

            for failure_mode in FAILURE_MODES:
                print(f"\n{failure_mode}: {FAILURE_MODES[failure_mode]['name']}")

                tasks = [
                    generate_with_semaphore(tier, failure_mode, i, i+1)
                    for i in range(traces_per_tier)
                ]
                results = await asyncio.gather(*tasks)
                mode_traces = [t for t in results if t is not None]
                all_traces[tier].extend(mode_traces)

                # Save traces for this mode/tier
                mode_file = self.output_dir / f"{failure_mode}_{tier}_traces.jsonl"
                with open(mode_file, "w") as f:
                    for trace in mode_traces:
                        for span in trace["spans"]:
                            span["_trace_metadata"] = {
                                "failure_mode": trace["failure_mode"],
                                "failure_name": trace["failure_name"],
                                "scenario": trace["scenario"],
                                "complexity": tier,
                            }
                            f.write(json.dumps(span) + "\n")

        # Save combined traces
        for tier in ["simple", "medium", "complex"]:
            combined_file = self.output_dir / f"all_{tier}_traces.jsonl"
            with open(combined_file, "w") as f:
                for trace in all_traces[tier]:
                    for span in trace["spans"]:
                        f.write(json.dumps(span) + "\n")

        # Summary
        print(f"\n{'='*60}")
        print("GENERATION COMPLETE")
        print(f"{'='*60}")
        for tier in all_traces:
            print(f"  {tier}: {len(all_traces[tier])} traces")
        print(f"  TOTAL: {sum(len(t) for t in all_traces.values())} traces")

        return all_traces


async def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    generator = ComplexTraceGenerator(
        api_key=api_key,
        output_dir="traces"
    )

    # Generate tiered traces (50 per tier per mode = 2100 total)
    traces = await generator.generate_tiered_traces(traces_per_tier=50, concurrency=5)


if __name__ == "__main__":
    asyncio.run(main())
