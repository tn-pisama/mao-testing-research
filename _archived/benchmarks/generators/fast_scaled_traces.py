"""Fast scaled trace generation using templates with variation.

Generates 2000 traces per framework without LLM calls for speed.
Uses varied templates, randomized content, and realistic patterns.
"""

import functools
import json
import random
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

# Force unbuffered output
print = functools.partial(print, flush=True)

from src.trace_generator import FAILURE_MODES

# Content templates with variations for realistic traces
RESEARCH_OUTPUTS = [
    "Analyzed market trends showing {metric}% growth in {sector}",
    "Investigated {topic} revealing significant insights about {aspect}",
    "Gathered data from {count} sources on {subject}",
    "Research indicates {finding} with {confidence}% confidence",
    "Identified key patterns in {domain} suggesting {implication}",
    "Compiled comprehensive analysis of {target} performance metrics",
    "Examined {factor} impact on {outcome} across {scope}",
    "Discovered correlation between {var1} and {var2} in dataset",
    "Synthesized findings from {sources} on {topic}",
    "Quantified {measure} showing {trend} over {period}",
]

WRITER_OUTPUTS = [
    "Drafted comprehensive report on {topic} with {sections} sections",
    "Created executive summary highlighting {count} key findings",
    "Produced detailed documentation covering {aspect}",
    "Composed analysis memo addressing {points} main points",
    "Generated content outline for {target} deliverable",
    "Wrote technical specification for {component}",
    "Prepared briefing document on {subject}",
    "Developed narrative covering {scope} implications",
    "Authored assessment of {topic} recommendations",
    "Formatted final report with {elements} key elements",
]

REVIEWER_OUTPUTS = [
    "Reviewed submission: found {issues} issues requiring revision",
    "Quality check passed with {score}% compliance score",
    "Identified {gaps} gaps in coverage requiring attention",
    "Verified accuracy of {claims} factual claims",
    "Assessment: {verdict} - {reason}",
    "Flagged {count} items for clarification",
    "Review complete: recommends {action}",
    "Validation passed {checks} of {total} quality checks",
    "Critique: {strength} strengths, {weakness} areas for improvement",
    "Final review status: {status}",
]

VALIDATOR_OUTPUTS = [
    "Schema validation: {passed}/{total} fields valid",
    "Data integrity check: {status}",
    "Format compliance: {percent}% adherent",
    "Required fields present: {fields}",
    "Type validation: all types conform to spec",
    "Constraint check: {violations} violations detected",
    "Output validation completed with {result}",
    "Verified against specification v{version}",
    "Structural validation: {status}",
    "Semantic check: {result}",
]

EXECUTOR_OUTPUTS = [
    "Executed {tool} with result: {result}",
    "Tool invocation returned: {response}",
    "API call to {service} completed in {ms}ms",
    "Command execution: exit code {code}",
    "Retrieved {count} results from {source}",
    "Operation {op} completed successfully",
    "Fetched data from {endpoint}",
    "Processed {items} items in {time}s",
    "External call to {target} returned {status}",
    "Action completed: {action}",
]

ROLE_OUTPUTS = {
    "researcher": RESEARCH_OUTPUTS,
    "writer": WRITER_OUTPUTS,
    "reviewer": REVIEWER_OUTPUTS,
    "validator": VALIDATOR_OUTPUTS,
    "executor": EXECUTOR_OUTPUTS,
    "planner": [
        "Decomposed task into {steps} steps",
        "Created execution plan with {phases} phases",
        "Identified {deps} dependencies",
        "Priority queue established: {priorities}",
        "Resource allocation: {allocation}",
    ],
    "aggregator": [
        "Aggregated {count} responses into unified output",
        "Merged results from {sources} sources",
        "Combined findings with {conflicts} conflicts resolved",
        "Synthesis complete: {summary}",
        "Consolidated {items} items",
    ],
    "supervisor": [
        "Delegated tasks to {agents} agents",
        "Coordinated workflow: {status}",
        "Monitored execution: {progress}% complete",
        "Task assignment: {assignment}",
        "Orchestration complete",
    ],
}

FILLER_WORDS = [
    "comprehensive", "detailed", "thorough", "strategic", "actionable",
    "critical", "essential", "primary", "secondary", "preliminary",
    "significant", "notable", "key", "major", "minor",
]

# Healthy trace markers - demonstrate proper behavior
HEALTHY_MARKERS = {
    "F1": [  # Spec followed
        " [Specification fully addressed: all requirements met]",
        " [Output aligned with requested format and content]",
        " [Deliverable matches original request precisely]",
    ],
    "F2": [  # Good decomposition
        " [Task properly decomposed into manageable subtasks]",
        " [Dependencies identified and sequenced correctly]",
        " [Granularity appropriate for task complexity]",
    ],
    "F3": [  # Good resource allocation
        " [Resources allocated efficiently, no contention]",
        " [Capacity within limits, optimal utilization]",
        " [Resource requirements met without bottlenecks]",
    ],
    "F4": [  # Tools working
        " [All required tools available and functioning]",
        " [Tool outputs validated and integrated correctly]",
        " [Appropriate tools selected for each subtask]",
    ],
    "F5": [  # Good workflow
        " [Error handling in place for all paths]",
        " [Validation gates functioning correctly]",
        " [Workflow covers all expected scenarios]",
    ],
    "F6": [  # On task
        " [Focus maintained on original objective]",
        " [No deviation from assigned task scope]",
        " [Output directly addresses the request]",
    ],
    "F7": [  # Context used
        " [Previous context fully utilized in response]",
        " [All relevant prior information incorporated]",
        " [Context continuity maintained throughout]",
    ],
    "F8": [  # Info preserved
        " [All research findings included in output]",
        " [No information lost during synthesis]",
        " [Complete details preserved from source]",
    ],
    "F9": [  # Role respected
        " [Operating within defined role boundaries]",
        " [Responsibilities respected, no scope creep]",
        " [Proper delegation to appropriate agents]",
    ],
    "F10": [  # Clear communication
        " [Terminology consistent across all agents]",
        " [Definitions clearly aligned and understood]",
        " [No semantic ambiguity in communication]",
    ],
    "F11": [  # Good coordination
        " [Handoff completed successfully with full context]",
        " [Coordination clear, no duplicate work]",
        " [Responsibilities clearly delineated]",
    ],
    "F12": [  # Valid output
        " [Output passes all validation checks]",
        " [Schema compliance verified]",
        " [Format matches expected specification]",
    ],
    "F13": [  # Quality gates passed
        " [All quality checks performed and passed]",
        " [No validation steps bypassed]",
        " [Review process completed thoroughly]",
    ],
    "F14": [  # Proper completion
        " [Task fully completed, all objectives met]",
        " [No pending items or incomplete sections]",
        " [Deliverables match completion criteria]",
    ],
    "F15": [  # Properly grounded
        " [All claims verified against source documents]",
        " [Numerical values match source exactly]",
        " [Citations accurately represent source content]",
        " [Output fully grounded in provided sources]",
    ],
    "F16": [  # Good retrieval
        " [Retrieved documents highly relevant to query]",
        " [Comprehensive document coverage for task]",
        " [Retrieval precision: all docs on-topic]",
        " [No evidence of missed relevant documents]",
    ],
}

TOPICS = [
    "market analysis", "user behavior", "system performance", "revenue trends",
    "customer feedback", "operational metrics", "risk assessment", "compliance review",
    "product roadmap", "technical architecture", "security audit", "cost optimization",
]

SECTORS = [
    "technology", "finance", "healthcare", "retail", "manufacturing",
    "energy", "logistics", "education", "entertainment", "agriculture",
]


class FastScaledTraceGenerator:
    """Generate large-scale traces using templates with variation."""

    FRAMEWORKS = {
        "langchain": {
            "prefix": "trace",
            "span_prefix": "span",
            "root_name": "langchain.run",
            "agent_format": "{role}_agent",
        },
        "autogen": {
            "prefix": "autogen_trace",
            "span_prefix": "ag_span",
            "root_name": "autogen.groupchat.run",
            "agent_format": "{role}_assistant",
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

    TOOLS = [
        "web_search", "code_execute", "database_query", "file_read",
        "file_write", "api_call", "http_request", "email_send",
    ]

    def __init__(self, output_dir: str = "traces"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.stats = {"generated": 0, "failed": 0}

    def _generate_id(self, framework: str, id_type: str = "trace") -> str:
        fw = self.FRAMEWORKS[framework]
        prefix = fw["prefix"] if id_type == "trace" else fw["span_prefix"]
        return f"{prefix}_{uuid.uuid4().hex[:16 if id_type == 'trace' else 12]}"

    def _varied_output(self, role: str, variation_seed: int) -> str:
        """Generate varied output based on role and seed."""
        templates = ROLE_OUTPUTS.get(role, RESEARCH_OUTPUTS)
        template = templates[variation_seed % len(templates)]

        # Random substitutions
        return template.format(
            metric=random.randint(5, 95),
            sector=random.choice(SECTORS),
            topic=random.choice(TOPICS),
            aspect=random.choice(FILLER_WORDS),
            count=random.randint(3, 20),
            subject=random.choice(TOPICS),
            finding=random.choice(["positive trend", "negative correlation", "neutral impact"]),
            confidence=random.randint(70, 99),
            domain=random.choice(SECTORS),
            implication=random.choice(["growth opportunity", "risk factor", "optimization potential"]),
            target=random.choice(TOPICS),
            factor=random.choice(FILLER_WORDS),
            outcome=random.choice(["efficiency", "accuracy", "performance"]),
            scope=random.choice(["global", "regional", "local"]),
            var1=random.choice(["cost", "time", "quality"]),
            var2=random.choice(["output", "satisfaction", "retention"]),
            sources=random.choice(["internal reports", "external data", "surveys"]),
            measure=random.choice(["efficiency", "throughput", "accuracy"]),
            trend=random.choice(["increase", "decrease", "stability"]),
            period=random.choice(["Q1", "last month", "past year"]),
            sections=random.randint(3, 10),
            points=random.randint(3, 8),
            component=random.choice(["API", "module", "service"]),
            elements=random.randint(4, 12),
            issues=random.randint(0, 5),
            score=random.randint(75, 100),
            gaps=random.randint(0, 3),
            claims=random.randint(5, 20),
            verdict=random.choice(["approved", "needs revision", "conditional"]),
            reason=random.choice(["meets criteria", "minor issues", "requires updates"]),
            action=random.choice(["proceed", "revise", "escalate"]),
            checks=random.randint(8, 15),
            total=random.randint(10, 15),
            strength=random.randint(3, 7),
            weakness=random.randint(1, 3),
            status=random.choice(["passed", "warning", "failed"]),
            passed=random.randint(8, 10),
            percent=random.randint(85, 100),
            fields=random.randint(5, 15),
            violations=random.randint(0, 2),
            result=random.choice(["valid", "invalid", "partial"]),
            version=f"{random.randint(1, 3)}.{random.randint(0, 9)}",
            tool=random.choice(FastScaledTraceGenerator.TOOLS),
            response=random.choice(["200 OK", "data retrieved", "success"]),
            service=random.choice(["search API", "database", "external service"]),
            ms=random.randint(50, 500),
            code=random.choice([0, 0, 0, 1]),
            source=random.choice(["cache", "database", "API"]),
            op=random.choice(["fetch", "store", "update", "delete"]),
            endpoint=random.choice(["/api/v1/data", "/search", "/query"]),
            items=random.randint(10, 1000),
            time=round(random.uniform(0.1, 2.0), 2),
            steps=random.randint(3, 8),
            phases=random.randint(2, 5),
            deps=random.randint(1, 5),
            priorities=random.choice(["P0, P1, P2", "high, medium, low"]),
            allocation=random.choice(["balanced", "optimized", "priority-based"]),
            agents=random.randint(2, 6),
            progress=random.randint(70, 100),
            assignment=random.choice(["complete", "in progress", "queued"]),
            conflicts=random.randint(0, 3),
            summary=random.choice(["unified view", "consolidated report", "merged analysis"]),
        )

    def _inject_healthy(self, failure_mode: str, content: str) -> str:
        """Inject healthy behavior markers into content."""
        if failure_mode in HEALTHY_MARKERS:
            marker = random.choice(HEALTHY_MARKERS[failure_mode])
            content = content + marker
        return content

    def _inject_failure(self, failure_mode: str, content: str, span_data: dict) -> str:
        """Inject failure mode signals into content."""
        mode_info = FAILURE_MODES[failure_mode]

        # Add failure-specific markers based on mode
        injections = {
            "F1": [
                f" [Note: Deviating from original spec: {random.choice(TOPICS)}]",
                f" [Adjusted requirements to match {random.choice(['capability', 'timeline', 'resource'])} constraints]",
                f" [Interpreted specification as {random.choice(['flexible', 'approximate', 'guideline'])}]",
            ],
            "F2": [
                f" [Sub-task complexity: {random.choice(['underestimated', 'oversimplified', 'incomplete'])}]",
                f" [Missing breakdown for {random.choice(['edge cases', 'dependencies', 'prerequisites'])}]",
                f" [Decomposition depth: insufficient for {random.choice(['scale', 'complexity', 'requirements'])}]",
            ],
            "F3": [
                f" [Resource contention detected: {random.choice(['memory', 'API quota', 'connection pool'])}]",
                f" [Waiting for resource: {random.choice(['database lock', 'rate limit reset', 'cache'])}]",
                f" [Resource utilization: {random.randint(85, 99)}%]",
            ],
            "F4": [
                f" [Tool {random.choice(FastScaledTraceGenerator.TOOLS)} unavailable, proceeding without]",
                f" [Expected tool output missing, using fallback]",
                f" [Tool returned unexpected format, adapting]",
            ],
            "F5": [
                f" [Unhandled case: {random.choice(['null response', 'timeout', 'partial data'])}]",
                f" [Path not covered: {random.choice(['error recovery', 'edge case', 'validation'])}]",
                f" [Missing handler for {random.choice(['exception', 'state', 'condition'])}]",
            ],
            "F6": [
                f" [Task scope expanded to include {random.choice(['additional analysis', 'extra validation', 'more research'])}]",
                f" [Investigating tangential topic: {random.choice(TOPICS)}]",
                f" [Deviation from main objective: exploring {random.choice(['alternative', 'related', 'adjacent'])} area]",
            ],
            "F7": [
                f" [Context note: previous findings may be {random.choice(['incomplete', 'outdated', 'misremembered'])}]",
                f" [Recall limitation: earlier {random.choice(['constraints', 'requirements', 'decisions'])} unclear]",
                f" [Memory gap: reconstructing context from {random.choice(['partial data', 'assumptions', 'inference'])}]",
            ],
            "F8": [
                f" [Simplified from original: {random.choice(['details omitted', 'nuances reduced', 'complexity hidden'])}]",
                f" [Key detail potentially lost: {random.choice(['caveat', 'exception', 'condition'])}]",
                f" [Summarized aggressively, some {random.choice(['precision', 'context', 'detail'])} lost]",
            ],
            "F9": [
                f" [Expanding scope: taking on {random.choice(['review', 'validation', 'planning'])} responsibilities]",
                f" [Role extension: performing {random.choice(['writer', 'reviewer', 'executor'])} tasks]",
                f" [Boundary note: this may exceed {random.choice(['mandate', 'authorization', 'scope'])}]",
            ],
            "F10": [
                f" [Term interpretation: '{random.choice(['deliverable', 'requirement', 'metric'])}' defined as {random.choice(['output', 'spec', 'measure'])}]",
                f" [Semantic note: agent terms may differ from {random.choice(['standard', 'expected', 'common'])} usage]",
                f" [Definition variance detected in '{random.choice(['priority', 'status', 'type'])}'']",
            ],
            "F11": [
                f" [Handoff pending: awaiting {random.choice(['acknowledgment', 'confirmation', 'response'])}]",
                f" [Coordination gap: {random.choice(['unclear responsibility', 'missing transition', 'dropped context'])}]",
                f" [Inter-agent sync: {random.choice(['delayed', 'incomplete', 'misaligned'])}]",
            ],
            "F12": [
                f" [Format note: output structure {random.choice(['differs from', 'incompatible with', 'varies from'])} expectation]",
                f" [Schema adaptation: converting from {random.choice(['legacy', 'alternate', 'custom'])} format]",
                f" [Data format: {random.choice(['JSON', 'text', 'structured'])} instead of expected {random.choice(['table', 'list', 'object'])}]",
            ],
            "F13": [
                f" [Validation bypassed: {random.choice(['time constraint', 'low risk', 'similar to verified case'])}]",
                f" [Check skipped: {random.choice(['optional validation', 'redundant step', 'pre-validated input'])}]",
                f" [Proceeding without: {random.choice(['full verification', 'complete check', 'thorough review'])}]",
            ],
            "F14": [
                f" [Progress marker: task {random.choice(['mostly', 'essentially', 'substantially'])} complete]",
                f" [Completion estimate: {random.randint(85, 99)}% done, remaining items {random.choice(['minor', 'trivial', 'non-blocking'])}]",
                f" [Status: {random.choice(['near complete', 'almost done', 'finishing up'])} - final steps pending]",
            ],
            "F15": [
                f" [Note: This figure differs from source - source shows ${random.randint(30,50)}M but reporting ${random.randint(40,60)}M]",
                f" [Grounding issue: Claim not found in any source document]",
                f" [Citation inaccuracy: Source actually states the opposite of what's claimed]",
                f" [Numerical extraction error: Pulled value from wrong column in table]",
                f" [Ungrounded claim: No supporting evidence in provided sources]",
                f" [Data mismatch: Source says Q{random.randint(1,2)} but output claims Q{random.randint(3,4)}]",
            ],
            "F16": [
                f" [Retrieval issue: Documents retrieved are not relevant to query]",
                f" [Coverage gap: Missing critical documents for this topic]",
                f" [Low precision: Most retrieved docs off-topic or outdated]",
                f" [Retrieval miss: Key document not in retrieved set]",
                f" [Query-doc mismatch: Retrieved {random.choice(['2019', '2020', '2021'])} reports instead of {random.choice(['2023', '2024'])}]",
                f" [Wrong source: Retrieved competitor data instead of company data]",
            ],
        }

        if failure_mode in injections:
            injection = random.choice(injections[failure_mode])
            # Add to output at a natural point
            content = content + injection

        return content

    def generate_simple_trace(
        self,
        framework: str,
        failure_mode: str,
        scenario: str,
        trace_num: int,
        is_healthy: bool = False,
    ) -> dict:
        """Generate a simple 2-agent trace."""
        fw = self.FRAMEWORKS[framework]
        trace_id = self._generate_id(framework, "trace")
        root_span_id = self._generate_id(framework, "span")

        start_time = datetime.now(UTC)
        spans = []

        # Agent 1: Researcher
        agent1_id = self._generate_id(framework, "span")
        agent1_end = start_time + timedelta(milliseconds=random.randint(800, 2000))
        agent1_output = self._varied_output("researcher", trace_num)
        if is_healthy:
            agent1_output = self._inject_healthy(failure_mode, agent1_output)
        else:
            agent1_output = self._inject_failure(failure_mode, agent1_output, {})

        spans.append({
            "trace_id": trace_id,
            "span_id": agent1_id,
            "parent_id": root_span_id,
            "name": fw["agent_format"].format(role="researcher"),
            "agent_id": "researcher",
            "span_type": "agent",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": agent1_end.isoformat() + "Z",
            "duration_ms": int((agent1_end - start_time).total_seconds() * 1000),
            "input_data": {"task": scenario},
            "output_data": {"result": agent1_output},
        })

        # Agent 2: Writer
        agent2_id = self._generate_id(framework, "span")
        agent2_end = agent1_end + timedelta(milliseconds=random.randint(600, 1500))
        agent2_output = self._varied_output("writer", trace_num + 1)
        if is_healthy:
            agent2_output = self._inject_healthy(failure_mode, agent2_output)
        else:
            agent2_output = self._inject_failure(failure_mode, agent2_output, {})

        spans.append({
            "trace_id": trace_id,
            "span_id": agent2_id,
            "parent_id": root_span_id,
            "name": fw["agent_format"].format(role="writer"),
            "agent_id": "writer",
            "span_type": "agent",
            "status": "ok",
            "start_time": agent1_end.isoformat() + "Z",
            "end_time": agent2_end.isoformat() + "Z",
            "duration_ms": int((agent2_end - agent1_end).total_seconds() * 1000),
            "input_data": {"research": agent1_output[:100]},
            "output_data": {"document": agent2_output},
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
                "is_healthy": is_healthy,
            },
        })

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "failure_name": FAILURE_MODES[failure_mode]["name"],
            "scenario": scenario,
            "complexity": "simple",
            "framework": framework,
            "is_healthy": is_healthy,
            "spans": spans,
        }

    def generate_medium_trace(
        self,
        framework: str,
        failure_mode: str,
        scenario: str,
        trace_num: int,
        is_healthy: bool = False,
    ) -> dict:
        """Generate medium complexity trace with 4-5 agents and tools."""
        fw = self.FRAMEWORKS[framework]
        trace_id = self._generate_id(framework, "trace")
        root_span_id = self._generate_id(framework, "span")

        start_time = datetime.now(UTC)
        spans = []
        current_time = start_time

        # 4-5 agents in sequence with some tools
        roles = random.sample(["researcher", "planner", "executor", "reviewer", "writer"], k=random.randint(4, 5))

        for i, role in enumerate(roles):
            agent_id = self._generate_id(framework, "span")
            duration = random.randint(500, 1800)
            agent_end = current_time + timedelta(milliseconds=duration)

            output = self._varied_output(role, trace_num + i)
            if is_healthy:
                output = self._inject_healthy(failure_mode, output)
            else:
                output = self._inject_failure(failure_mode, output, {})

            span = {
                "trace_id": trace_id,
                "span_id": agent_id,
                "parent_id": root_span_id,
                "name": fw["agent_format"].format(role=role),
                "agent_id": role,
                "span_type": "agent",
                "status": "ok",
                "start_time": current_time.isoformat() + "Z",
                "end_time": agent_end.isoformat() + "Z",
                "duration_ms": duration,
                "input_data": {"task": scenario if i == 0 else f"Continue from {roles[i-1]}"},
                "output_data": {"result": output},
            }

            spans.append(span)

            # Add tool_call span for executors
            if role == "executor" and random.random() > 0.3:
                tool = random.choice(self.TOOLS)
                tool_id = self._generate_id(framework, "span")
                tool_duration = random.randint(100, 400)
                tool_start = current_time + timedelta(milliseconds=random.randint(20, 100))
                tool_end = tool_start + timedelta(milliseconds=tool_duration)
                tool_status = random.choice(["success", "success", "error"])

                spans.append({
                    "trace_id": trace_id,
                    "span_id": tool_id,
                    "parent_id": agent_id,
                    "name": f"tool.{tool}",
                    "agent_id": role,
                    "span_type": "tool_call",
                    "status": tool_status,
                    "start_time": tool_start.isoformat() + "Z",
                    "end_time": tool_end.isoformat() + "Z",
                    "duration_ms": tool_duration,
                    "input_data": {"query": random.choice(TOPICS)},
                    "output_data": {"result": self._varied_output("executor", trace_num)} if tool_status == "success" else {"error": "Tool failed"},
                })
            current_time = agent_end

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
                "agent_count": len(roles),
                "is_healthy": is_healthy,
            },
        })

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "failure_name": FAILURE_MODES[failure_mode]["name"],
            "scenario": scenario,
            "complexity": "medium",
            "framework": framework,
            "is_healthy": is_healthy,
            "spans": spans,
        }

    def generate_complex_trace(
        self,
        framework: str,
        failure_mode: str,
        scenario: str,
        trace_num: int,
        is_healthy: bool = False,
    ) -> dict:
        """Generate complex trace with 6+ agents, parallel execution, retries."""
        fw = self.FRAMEWORKS[framework]
        trace_id = self._generate_id(framework, "trace")
        root_span_id = self._generate_id(framework, "span")

        start_time = datetime.now(UTC)
        spans = []

        # Helper to inject appropriate markers
        def inject_marker(content: str) -> str:
            if is_healthy:
                return self._inject_healthy(failure_mode, content)
            return self._inject_failure(failure_mode, content, {})

        # Supervisor span
        sup_id = self._generate_id(framework, "span")
        sup_end = start_time + timedelta(milliseconds=random.randint(200, 500))

        spans.append({
            "trace_id": trace_id,
            "span_id": sup_id,
            "parent_id": root_span_id,
            "name": fw["agent_format"].format(role="supervisor"),
            "agent_id": "supervisor",
            "span_type": "agent",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": sup_end.isoformat() + "Z",
            "duration_ms": int((sup_end - start_time).total_seconds() * 1000),
            "input_data": {"task": scenario},
            "output_data": {"result": inject_marker(self._varied_output("supervisor", trace_num))},
        })

        # Parallel executor agents (3-4)
        executor_count = random.randint(3, 4)
        parallel_start = sup_end
        parallel_ends = []

        for i in range(executor_count):
            exec_id = self._generate_id(framework, "span")
            duration = random.randint(800, 2500)
            exec_end = parallel_start + timedelta(milliseconds=duration)
            parallel_ends.append(exec_end)

            # Some executors have retries
            has_retry = random.random() > 0.7
            status = "ok" if not has_retry else random.choice(["ok", "retry"])

            output = self._varied_output("executor", trace_num + i)
            output = inject_marker(output)

            span = {
                "trace_id": trace_id,
                "span_id": exec_id,
                "parent_id": sup_id,
                "name": fw["agent_format"].format(role=f"executor_{i+1}"),
                "agent_id": f"executor_{i+1}",
                "span_type": "agent",
                "status": status,
                "start_time": parallel_start.isoformat() + "Z",
                "end_time": exec_end.isoformat() + "Z",
                "duration_ms": duration,
                "input_data": {"subtask": f"Subtask {i+1} of {scenario}"},
                "output_data": {"result": output},
            }
            spans.append(span)

            # Add tool_call span as child of executor
            tool_name = random.choice(self.TOOLS)
            tool_id = self._generate_id(framework, "span")
            tool_duration = random.randint(100, 500)
            tool_start = parallel_start + timedelta(milliseconds=random.randint(50, 200))
            tool_end = tool_start + timedelta(milliseconds=tool_duration)
            tool_status = random.choice(["success", "success", "success", "error"])

            spans.append({
                "trace_id": trace_id,
                "span_id": tool_id,
                "parent_id": exec_id,
                "name": f"tool.{tool_name}",
                "agent_id": f"executor_{i+1}",
                "span_type": "tool_call",
                "status": tool_status,
                "start_time": tool_start.isoformat() + "Z",
                "end_time": tool_end.isoformat() + "Z",
                "duration_ms": tool_duration,
                "input_data": {"query": random.choice(TOPICS)},
                "output_data": {"data": f"Retrieved {random.randint(10, 100)} items"} if tool_status == "success" else {"error": "Tool execution failed"},
            })

            # Add retry span if needed
            if has_retry:
                retry_id = self._generate_id(framework, "span")
                retry_count = random.randint(1, 3)
                retry_start = tool_end + timedelta(milliseconds=50)
                retry_end = retry_start + timedelta(milliseconds=random.randint(200, 600))

                spans.append({
                    "trace_id": trace_id,
                    "span_id": retry_id,
                    "parent_id": exec_id,
                    "name": f"retry.{tool_name}",
                    "agent_id": f"executor_{i+1}",
                    "span_type": "retry",
                    "status": "ok",
                    "start_time": retry_start.isoformat() + "Z",
                    "end_time": retry_end.isoformat() + "Z",
                    "duration_ms": int((retry_end - retry_start).total_seconds() * 1000),
                    "input_data": {"retry_attempt": retry_count, "original_tool": tool_name},
                    "output_data": {"result": "Retry successful"},
                    "retry_count": retry_count,
                })

        # Aggregator after parallel execution
        agg_start = max(parallel_ends)
        agg_id = self._generate_id(framework, "span")
        agg_end = agg_start + timedelta(milliseconds=random.randint(400, 800))

        spans.append({
            "trace_id": trace_id,
            "span_id": agg_id,
            "parent_id": root_span_id,
            "name": fw["agent_format"].format(role="aggregator"),
            "agent_id": "aggregator",
            "span_type": "agent",
            "status": "ok",
            "start_time": agg_start.isoformat() + "Z",
            "end_time": agg_end.isoformat() + "Z",
            "duration_ms": int((agg_end - agg_start).total_seconds() * 1000),
            "input_data": {"executor_results": f"Results from {executor_count} executors"},
            "output_data": {"result": inject_marker(self._varied_output("aggregator", trace_num))},
        })

        # Reviewer
        rev_id = self._generate_id(framework, "span")
        rev_end = agg_end + timedelta(milliseconds=random.randint(500, 1200))

        spans.append({
            "trace_id": trace_id,
            "span_id": rev_id,
            "parent_id": root_span_id,
            "name": fw["agent_format"].format(role="reviewer"),
            "agent_id": "reviewer",
            "span_type": "agent",
            "status": "ok",
            "start_time": agg_end.isoformat() + "Z",
            "end_time": rev_end.isoformat() + "Z",
            "duration_ms": int((rev_end - agg_end).total_seconds() * 1000),
            "input_data": {"aggregated_result": "Merged output"},
            "output_data": {"result": inject_marker(self._varied_output("reviewer", trace_num))},
        })

        # Validator
        val_id = self._generate_id(framework, "span")
        val_end = rev_end + timedelta(milliseconds=random.randint(300, 700))

        spans.append({
            "trace_id": trace_id,
            "span_id": val_id,
            "parent_id": root_span_id,
            "name": fw["agent_format"].format(role="validator"),
            "agent_id": "validator",
            "span_type": "validation",
            "status": "ok",
            "start_time": rev_end.isoformat() + "Z",
            "end_time": val_end.isoformat() + "Z",
            "duration_ms": int((val_end - rev_end).total_seconds() * 1000),
            "input_data": {"to_validate": "Final output"},
            "output_data": {"result": inject_marker(self._varied_output("validator", trace_num))},
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
                "agent_count": 2 + executor_count + 3,  # supervisor + executors + agg + rev + val
                "parallel_execution": True,
                "is_healthy": is_healthy,
            },
        })

        return {
            "trace_id": trace_id,
            "failure_mode": failure_mode,
            "failure_name": FAILURE_MODES[failure_mode]["name"],
            "scenario": scenario,
            "complexity": "complex",
            "framework": framework,
            "is_healthy": is_healthy,
            "spans": spans,
        }

    def generate_framework_traces(
        self,
        framework: str,
        traces_per_framework: int = 2000,
        include_healthy: bool = True,
    ) -> list[dict]:
        """Generate all traces for a single framework.

        Args:
            framework: Framework name (langchain, autogen, crewai, n8n)
            traces_per_framework: Total failure traces per framework
            include_healthy: If True, also generate healthy traces (1:1 ratio)
        """
        traces_per_mode = traces_per_framework // len(FAILURE_MODES)
        # 40% simple, 35% medium, 25% complex
        simple_count = int(traces_per_mode * 0.40)
        medium_count = int(traces_per_mode * 0.35)
        complex_count = traces_per_mode - simple_count - medium_count

        failure_traces = []
        healthy_traces = []

        total_traces = traces_per_framework * 2 if include_healthy else traces_per_framework
        print(f"\n{'='*70}")
        print(f"Generating {total_traces} traces for {framework.upper()}")
        print(f"  Failure traces: {traces_per_framework}")
        if include_healthy:
            print(f"  Healthy traces: {traces_per_framework}")
        print(f"  Per complexity - Simple: {simple_count}, Medium: {medium_count}, Complex: {complex_count}")
        print(f"{'='*70}")

        total_generated = 0
        for mode_idx, failure_mode in enumerate(FAILURE_MODES):
            mode_info = FAILURE_MODES[failure_mode]
            print(f"\n  [{mode_idx+1}/{len(FAILURE_MODES)}] {failure_mode}: {mode_info['name']}")

            mode_failure_traces = []
            mode_healthy_traces = []

            # Generate failure traces (simple, medium, complex)
            for i in range(simple_count):
                scenario = mode_info["scenarios"][i % len(mode_info["scenarios"])]
                trace = self.generate_simple_trace(framework, failure_mode, scenario, i+1, is_healthy=False)
                mode_failure_traces.append(trace)

            for i in range(medium_count):
                scenario = mode_info["scenarios"][i % len(mode_info["scenarios"])]
                trace = self.generate_medium_trace(framework, failure_mode, scenario, i+1, is_healthy=False)
                mode_failure_traces.append(trace)

            for i in range(complex_count):
                scenario = mode_info["scenarios"][i % len(mode_info["scenarios"])]
                trace = self.generate_complex_trace(framework, failure_mode, scenario, i+1, is_healthy=False)
                mode_failure_traces.append(trace)

            # Generate healthy traces (same distribution)
            if include_healthy:
                for i in range(simple_count):
                    scenario = mode_info["scenarios"][i % len(mode_info["scenarios"])]
                    trace = self.generate_simple_trace(framework, failure_mode, scenario, i+1000, is_healthy=True)
                    mode_healthy_traces.append(trace)

                for i in range(medium_count):
                    scenario = mode_info["scenarios"][i % len(mode_info["scenarios"])]
                    trace = self.generate_medium_trace(framework, failure_mode, scenario, i+1000, is_healthy=True)
                    mode_healthy_traces.append(trace)

                for i in range(complex_count):
                    scenario = mode_info["scenarios"][i % len(mode_info["scenarios"])]
                    trace = self.generate_complex_trace(framework, failure_mode, scenario, i+1000, is_healthy=True)
                    mode_healthy_traces.append(trace)

            total_generated += len(mode_failure_traces) + len(mode_healthy_traces)
            print(f"      Generated {len(mode_failure_traces)} failure + {len(mode_healthy_traces)} healthy traces")

            failure_traces.extend(mode_failure_traces)
            healthy_traces.extend(mode_healthy_traces)

        # Save failure traces
        output_file = self.output_dir / f"{framework}_scaled_traces.jsonl"
        with open(output_file, "w") as f:
            for trace in failure_traces:
                f.write(json.dumps(trace) + "\n")
        print(f"\n  Saved {len(failure_traces)} failure traces to {output_file}")

        # Save healthy traces separately
        if include_healthy:
            healthy_file = self.output_dir / f"{framework}_healthy_traces.jsonl"
            with open(healthy_file, "w") as f:
                for trace in healthy_traces:
                    f.write(json.dumps(trace) + "\n")
            print(f"  Saved {len(healthy_traces)} healthy traces to {healthy_file}")

        # Return combined traces
        return failure_traces + healthy_traces

    def generate_all_frameworks(
        self,
        traces_per_framework: int = 2000,
        include_healthy: bool = True,
    ) -> dict:
        """Generate traces for all frameworks.

        Args:
            traces_per_framework: Failure traces per framework
            include_healthy: If True, also generate healthy traces (1:1 ratio)
        """
        all_traces = {}

        total_per_fw = traces_per_framework * 2 if include_healthy else traces_per_framework
        print("\n" + "="*70)
        print("FAST SCALED TRACE GENERATION")
        print(f"Target: {total_per_fw} traces per framework ({traces_per_framework} failure + {traces_per_framework if include_healthy else 0} healthy)")
        print(f"Total: {total_per_fw * len(self.FRAMEWORKS)} traces")
        print("="*70)

        for framework in self.FRAMEWORKS:
            traces = self.generate_framework_traces(framework, traces_per_framework, include_healthy)
            all_traces[framework] = traces

        # Summary
        print("\n" + "="*70)
        print("GENERATION COMPLETE")
        print("="*70)

        for framework, traces in all_traces.items():
            print(f"  {framework}: {len(traces)} traces")
            failure_count = sum(1 for t in traces if not t.get("is_healthy", False))
            healthy_count = sum(1 for t in traces if t.get("is_healthy", False))
            simple = sum(1 for t in traces if t["complexity"] == "simple")
            medium = sum(1 for t in traces if t["complexity"] == "medium")
            complex_ = sum(1 for t in traces if t["complexity"] == "complex")
            print(f"    Failure: {failure_count}, Healthy: {healthy_count}")
            print(f"    Simple: {simple}, Medium: {medium}, Complex: {complex_}")

        total = sum(len(t) for t in all_traces.values())
        total_failure = sum(sum(1 for t in traces if not t.get("is_healthy", False)) for traces in all_traces.values())
        total_healthy = sum(sum(1 for t in traces if t.get("is_healthy", False)) for traces in all_traces.values())
        print(f"\n  TOTAL: {total} traces generated")
        print(f"    Failure: {total_failure}, Healthy: {total_healthy}")

        return all_traces


def main():
    import os

    generator = FastScaledTraceGenerator(output_dir="traces")
    generator.generate_all_frameworks(traces_per_framework=2000)


if __name__ == "__main__":
    main()
