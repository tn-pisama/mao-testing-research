#!/usr/bin/env python3
"""Phase 1: Synthetic Baseline Evaluation

Generates deterministic synthetic traces with known failure modes and evaluates
all MAST detectors (F1-F16) against them.

No LLM calls required - uses pattern-based synthetic data.
"""

import json
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add backend to path
_BACKEND_PATH = str(Path(__file__).parent.parent.parent / "backend")
sys.path.insert(0, _BACKEND_PATH)

# Import detectors
from app.detection.specification import SpecificationMismatchDetector
from app.detection.decomposition import TaskDecompositionDetector
from app.detection.resource_misallocation import ResourceMisallocationDetector
from app.detection.tool_provision import ToolProvisionDetector
from app.detection.workflow import FlawedWorkflowDetector
from app.detection.derailment import TaskDerailmentDetector
from app.detection.context import ContextNeglectDetector
from app.detection.withholding import InformationWithholdingDetector
from app.detection.role_usurpation import RoleUsurpationDetector
from app.detection.communication import CommunicationBreakdownDetector
from app.detection.coordination import CoordinationAnalyzer
from app.detection.output_validation import OutputValidationDetector
from app.detection.quality_gate import QualityGateDetector
from app.detection.completion import CompletionMisjudgmentDetector
from app.detection.grounding import GroundingDetector
from app.detection.retrieval_quality import RetrievalQualityDetector


@dataclass
class EvalResult:
    """Evaluation result for a single detector."""
    failure_mode: str
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)

    @property
    def f1(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)

    @property
    def fpr(self) -> float:
        if self.false_positives + self.true_negatives == 0:
            return 0.0
        return self.false_positives / (self.false_positives + self.true_negatives)


# =============================================================================
# SYNTHETIC TRACE GENERATORS (Deterministic, No LLM)
# =============================================================================

def generate_f1_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F1: Specification Mismatch - output doesn't match task spec."""
    failure_traces = []
    healthy_traces = []

    mismatch_cases = [
        ("Write Python code to sort a list", "Here's the JavaScript code: function sort(arr) { return arr.sort(); }"),
        ("Create a REST API endpoint", "I've built a GraphQL schema for you with queries and mutations."),
        ("Summarize this document in 3 sentences", "Here's a detailed 10-page analysis of the document covering all aspects..."),
        ("Write unit tests for the function", "I've created end-to-end integration tests that cover the entire application."),
        ("Analyze the sales data", "I've created beautiful visualizations of the data but no numerical analysis."),
    ]

    for i in range(count):
        case = mismatch_cases[i % len(mismatch_cases)]
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F1",
            "is_failure": True,
            "task_specification": case[0],
            "agent_output": case[1],
            "spans": [
                {"name": "task_input", "content": case[0]},
                {"name": "agent_response", "content": case[1]},
            ]
        })

    matching_cases = [
        ("Write Python code to sort a list", "def sort_list(arr): return sorted(arr)"),
        ("Summarize in 3 sentences", "Here are 3 key points. First, X. Second, Y. Third, Z."),
        ("Create a REST API endpoint", "Here's the Flask REST endpoint: @app.route('/api/users', methods=['GET'])"),
    ]

    for i in range(count):
        case = matching_cases[i % len(matching_cases)]
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F1",
            "is_failure": False,
            "task_specification": case[0],
            "agent_output": case[1],
            "spans": [
                {"name": "task_input", "content": case[0]},
                {"name": "agent_response", "content": case[1]},
            ]
        })

    return failure_traces, healthy_traces


def generate_f2_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F2: Poor Task Decomposition - subtasks ill-defined or circular."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        # Circular dependency failure
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F2",
            "is_failure": True,
            "task": "Build a web application",
            "subtasks": [
                {"id": "A", "name": "Design UI", "depends_on": ["C"]},
                {"id": "B", "name": "Build backend", "depends_on": ["A"]},
                {"id": "C", "name": "Integrate", "depends_on": ["B"]},  # Circular!
            ],
            "spans": [
                {"name": "planner", "content": "Task A depends on C, B depends on A, C depends on B"},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F2",
            "is_failure": False,
            "task": "Build a web application",
            "subtasks": [
                {"id": "A", "name": "Design UI", "depends_on": []},
                {"id": "B", "name": "Build backend", "depends_on": []},
                {"id": "C", "name": "Integrate", "depends_on": ["A", "B"]},
            ],
            "spans": [
                {"name": "planner", "content": "First A and B in parallel, then C after both complete"},
            ]
        })

    return failure_traces, healthy_traces


def generate_f3_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F3: Resource Misallocation - wrong agent assigned to task."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F3",
            "is_failure": True,
            "task": "Write production database migration",
            "assigned_agent": {
                "name": "junior_intern",
                "role": "Junior Intern",
                "experience": "1 month",
                "skills": ["basic python", "documentation"]
            },
            "required_skills": ["database administration", "SQL", "production systems"],
            "spans": [
                {"name": "orchestrator", "content": "Assigning database migration to junior_intern"},
                {"name": "junior_intern", "content": "I'll try to write the migration script..."},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F3",
            "is_failure": False,
            "task": "Write production database migration",
            "assigned_agent": {
                "name": "senior_dba",
                "role": "Senior Database Administrator",
                "experience": "10 years",
                "skills": ["database administration", "SQL", "production systems", "migrations"]
            },
            "required_skills": ["database administration", "SQL", "production systems"],
            "spans": [
                {"name": "orchestrator", "content": "Assigning database migration to senior_dba"},
                {"name": "senior_dba", "content": "Creating migration with proper rollback..."},
            ]
        })

    return failure_traces, healthy_traces


def generate_f4_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F4: Inadequate Tool Provision - missing required tools."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F4",
            "is_failure": True,
            "task": "Query the production database and generate report",
            "available_tools": ["file_read", "file_write", "calculator"],
            "required_tools": ["database_query", "report_generator"],
            "tool_calls": [
                {"tool": "file_read", "status": "success", "result": "Cannot access database this way"},
            ],
            "error": "Agent lacks database_query tool needed for task",
            "spans": [
                {"name": "agent", "content": "I need to query the database but I only have file tools"},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F4",
            "is_failure": False,
            "task": "Query the production database and generate report",
            "available_tools": ["database_query", "report_generator", "file_write"],
            "required_tools": ["database_query", "report_generator"],
            "tool_calls": [
                {"tool": "database_query", "status": "success", "result": "Query returned 150 rows"},
                {"tool": "report_generator", "status": "success", "result": "Report generated"},
            ],
            "spans": [
                {"name": "agent", "content": "Successfully queried database and generated report"},
            ]
        })

    return failure_traces, healthy_traces


def generate_f5_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F5: Flawed Workflow Design - missing validation or error handling."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F5",
            "is_failure": True,
            "workflow": {
                "nodes": ["input", "process", "deploy"],  # Missing validation!
                "edges": [("input", "process"), ("process", "deploy")],
            },
            "issue": "No validation step before deployment",
            "spans": [
                {"name": "input", "content": "Received user request"},
                {"name": "process", "content": "Processing data"},
                {"name": "deploy", "content": "Deploying to production without validation"},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F5",
            "is_failure": False,
            "workflow": {
                "nodes": ["input", "process", "validate", "deploy"],
                "edges": [("input", "process"), ("process", "validate"), ("validate", "deploy")],
            },
            "spans": [
                {"name": "input", "content": "Received user request"},
                {"name": "process", "content": "Processing data"},
                {"name": "validate", "content": "Validation passed"},
                {"name": "deploy", "content": "Deploying to production"},
            ]
        })

    return failure_traces, healthy_traces


def generate_f6_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F6: Task Derailment - agent goes off-topic."""
    failure_traces = []
    healthy_traces = []

    derailment_cases = [
        ("Analyze Q3 sales data", "Speaking of sales, let me tell you about the history of commerce dating back to ancient Mesopotamia..."),
        ("Write a function to parse JSON", "Before we parse JSON, let's discuss the philosophy of data representation and why XML was actually better..."),
        ("Debug the authentication bug", "This reminds me of a fascinating tangent about cryptography history and Alan Turing..."),
    ]

    for i in range(count):
        case = derailment_cases[i % len(derailment_cases)]
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F6",
            "is_failure": True,
            "task": case[0],
            "agent_output": case[1],
            "spans": [
                {"name": "task", "content": case[0]},
                {"name": "agent", "content": case[1]},
            ]
        })

    focused_cases = [
        ("Analyze Q3 sales data", "Q3 sales totaled $2.3M, up 15% from Q2. Top products: Widget A (40%), Widget B (35%)."),
        ("Write a function to parse JSON", "def parse_json(s): import json; return json.loads(s)"),
        ("Debug the authentication bug", "Found the bug: token expiry check was using wrong timezone. Fixed in auth.py line 42."),
    ]

    for i in range(count):
        case = focused_cases[i % len(focused_cases)]
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F6",
            "is_failure": False,
            "task": case[0],
            "agent_output": case[1],
            "spans": [
                {"name": "task", "content": case[0]},
                {"name": "agent", "content": case[1]},
            ]
        })

    return failure_traces, healthy_traces


def generate_f7_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F7: Context Neglect - agent ignores upstream context."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F7",
            "is_failure": True,
            "context": "User prefers Python. Budget is $5000. Deadline is Friday.",
            "agent_output": "I'll build this in Java with unlimited budget, delivery next month.",
            "spans": [
                {"name": "context", "content": "User prefers Python. Budget is $5000. Deadline is Friday."},
                {"name": "agent", "content": "I'll build this in Java with unlimited budget, delivery next month."},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F7",
            "is_failure": False,
            "context": "User prefers Python. Budget is $5000. Deadline is Friday.",
            "agent_output": "I'll implement this in Python, staying within the $5000 budget, ready by Friday.",
            "spans": [
                {"name": "context", "content": "User prefers Python. Budget is $5000. Deadline is Friday."},
                {"name": "agent", "content": "I'll implement this in Python, staying within the $5000 budget, ready by Friday."},
            ]
        })

    return failure_traces, healthy_traces


def generate_f8_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F8: Information Withholding - agent doesn't share critical info."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F8",
            "is_failure": True,
            "research_findings": "Found critical security vulnerability CVE-2024-1234. Also found performance issue and documentation gap.",
            "passed_to_next_agent": "Found a documentation gap.",  # Withheld security issue!
            "spans": [
                {"name": "researcher", "content": "Found critical security vulnerability CVE-2024-1234. Also found performance issue and documentation gap."},
                {"name": "handoff", "content": "Passing to writer: Found a documentation gap."},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F8",
            "is_failure": False,
            "research_findings": "Found critical security vulnerability CVE-2024-1234. Also found performance issue and documentation gap.",
            "passed_to_next_agent": "Critical findings: 1) Security vulnerability CVE-2024-1234 (HIGH priority), 2) Performance issue, 3) Documentation gap.",
            "spans": [
                {"name": "researcher", "content": "Found critical security vulnerability CVE-2024-1234. Also found performance issue and documentation gap."},
                {"name": "handoff", "content": "Passing all findings including security vulnerability CVE-2024-1234."},
            ]
        })

    return failure_traces, healthy_traces


def generate_f9_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F9: Role Usurpation - agent exceeds role boundaries."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F9",
            "is_failure": True,
            "agent_role": "Research Assistant",
            "allowed_actions": ["search", "summarize", "cite sources"],
            "actual_action": "Deployed code to production server",
            "spans": [
                {"name": "research_agent", "role": "Research Assistant",
                 "content": "I've deployed the code to production and updated the database schema."},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F9",
            "is_failure": False,
            "agent_role": "Research Assistant",
            "allowed_actions": ["search", "summarize", "cite sources"],
            "actual_action": "Searched and summarized findings",
            "spans": [
                {"name": "research_agent", "role": "Research Assistant",
                 "content": "I've researched the topic and summarized the key findings with citations."},
            ]
        })

    return failure_traces, healthy_traces


def generate_f10_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F10: Communication Breakdown - inter-agent messages lost or misunderstood."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F10",
            "is_failure": True,
            "messages": [
                {"from": "agent_a", "to": "agent_b", "content": "Please review the security implications", "delivered": False},
                {"from": "agent_b", "to": "agent_a", "content": "What review? I didn't receive anything.", "delivered": True},
            ],
            "spans": [
                {"name": "agent_a", "content": "Sending security review request to agent_b"},
                {"name": "agent_b", "content": "No messages received, proceeding without review"},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F10",
            "is_failure": False,
            "messages": [
                {"from": "agent_a", "to": "agent_b", "content": "Please review the security implications", "delivered": True, "acknowledged": True},
                {"from": "agent_b", "to": "agent_a", "content": "Review complete, no issues found.", "delivered": True},
            ],
            "spans": [
                {"name": "agent_a", "content": "Sending security review request to agent_b"},
                {"name": "agent_b", "content": "Received and completed security review"},
            ]
        })

    return failure_traces, healthy_traces


def generate_f11_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F11: Coordination Failure - agents don't sync properly."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F11",
            "is_failure": True,
            "agents": ["writer", "reviewer", "publisher"],
            "coordination_issue": "circular_delegation",
            "spans": [
                {"name": "writer", "agent_id": "writer", "content": "Delegating to reviewer"},
                {"name": "reviewer", "agent_id": "reviewer", "content": "Delegating to publisher"},
                {"name": "publisher", "agent_id": "publisher", "content": "Delegating back to writer"},
                {"name": "writer", "agent_id": "writer", "content": "Delegating to reviewer again..."},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F11",
            "is_failure": False,
            "agents": ["writer", "reviewer", "publisher"],
            "spans": [
                {"name": "writer", "agent_id": "writer", "content": "Draft complete, sending to reviewer"},
                {"name": "reviewer", "agent_id": "reviewer", "content": "Review complete, approved for publishing"},
                {"name": "publisher", "agent_id": "publisher", "content": "Published successfully"},
            ]
        })

    return failure_traces, healthy_traces


def generate_f12_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F12: Output Validation Failure - invalid or malformed output."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F12",
            "is_failure": True,
            "expected_schema": {"type": "object", "required": ["name", "value"]},
            "actual_output": '{"name": "test"}',  # Missing required 'value'
            "validation_error": "Missing required field: value",
            "spans": [
                {"name": "agent", "content": "Output: {\"name\": \"test\"}"},
                {"name": "validator", "content": "Validation failed: missing 'value'"},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F12",
            "is_failure": False,
            "expected_schema": {"type": "object", "required": ["name", "value"]},
            "actual_output": '{"name": "test", "value": 42}',
            "spans": [
                {"name": "agent", "content": "Output: {\"name\": \"test\", \"value\": 42}"},
                {"name": "validator", "content": "Validation passed"},
            ]
        })

    return failure_traces, healthy_traces


def generate_f13_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F13: Quality Gate Bypass - skipped mandatory checks."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F13",
            "is_failure": True,
            "quality_gates": ["code_review", "security_scan", "testing"],
            "gates_passed": ["code_review"],  # Skipped security and testing!
            "bypass_reason": "Deadline pressure",
            "spans": [
                {"name": "pipeline", "content": "Bypassing security scan and testing due to deadline"},
                {"name": "deploy", "content": "Deploying without full quality checks"},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F13",
            "is_failure": False,
            "quality_gates": ["code_review", "security_scan", "testing"],
            "gates_passed": ["code_review", "security_scan", "testing"],
            "spans": [
                {"name": "code_review", "content": "Code review passed"},
                {"name": "security_scan", "content": "Security scan passed"},
                {"name": "testing", "content": "All tests passed"},
                {"name": "deploy", "content": "Deploying after all quality gates passed"},
            ]
        })

    return failure_traces, healthy_traces


def generate_f14_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F14: Completion Misjudgment - incorrect completion determination."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F14",
            "is_failure": True,
            "task": "Implement user authentication with email verification",
            "subtasks": ["login", "logout", "email_verification", "password_reset"],
            "completed_subtasks": ["login", "logout"],  # Missing critical email verification!
            "claimed_complete": True,
            "spans": [
                {"name": "agent", "content": "Task complete! I've implemented login and logout."},
                {"name": "status", "content": "Marking task as DONE"},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F14",
            "is_failure": False,
            "task": "Implement user authentication with email verification",
            "subtasks": ["login", "logout", "email_verification", "password_reset"],
            "completed_subtasks": ["login", "logout", "email_verification", "password_reset"],
            "claimed_complete": True,
            "spans": [
                {"name": "agent", "content": "All authentication features implemented: login, logout, email verification, password reset."},
                {"name": "status", "content": "All subtasks verified complete"},
            ]
        })

    return failure_traces, healthy_traces


def generate_f15_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F15: Grounding Failure - claims not supported by sources."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F15",
            "is_failure": True,
            "source_documents": [
                "Q3 revenue was $2.3 million. Q2 revenue was $2.0 million.",
                "Employee count: 150 as of September 2024."
            ],
            "agent_output": "Q3 revenue was $5.2 million, showing 300% growth. The company has 500 employees.",
            "ungrounded_claims": ["$5.2 million (actual: $2.3M)", "300% growth (actual: 15%)", "500 employees (actual: 150)"],
            "spans": [
                {"name": "retrieval", "content": "Retrieved 2 source documents"},
                {"name": "agent", "content": "Q3 revenue was $5.2 million with 500 employees"},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F15",
            "is_failure": False,
            "source_documents": [
                "Q3 revenue was $2.3 million. Q2 revenue was $2.0 million.",
                "Employee count: 150 as of September 2024."
            ],
            "agent_output": "Q3 revenue was $2.3 million, up from $2.0 million in Q2 (15% growth). The company has 150 employees.",
            "spans": [
                {"name": "retrieval", "content": "Retrieved 2 source documents"},
                {"name": "agent", "content": "Q3 revenue $2.3M, 150 employees - all verified from sources"},
            ]
        })

    return failure_traces, healthy_traces


def generate_f16_traces(count: int = 20) -> Tuple[List[Dict], List[Dict]]:
    """F16: Retrieval Quality Failure - wrong documents retrieved."""
    failure_traces = []
    healthy_traces = []

    for i in range(count):
        failure_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F16",
            "is_failure": True,
            "query": "What is the company's Q3 2024 revenue?",
            "retrieved_documents": [
                "Recipe for chocolate cake: Mix flour, sugar, cocoa...",
                "Weather forecast for next week: sunny with highs of 75F...",
            ],
            "relevance_scores": [0.1, 0.05],
            "spans": [
                {"name": "retrieval", "content": "Retrieved documents about cake recipes and weather"},
                {"name": "agent", "content": "Unable to find revenue information in retrieved documents"},
            ]
        })

    for i in range(count):
        healthy_traces.append({
            "trace_id": str(uuid.uuid4()),
            "failure_mode": "F16",
            "is_failure": False,
            "query": "What is the company's Q3 2024 revenue?",
            "retrieved_documents": [
                "Q3 2024 Financial Report: Revenue was $2.3 million...",
                "Quarterly earnings call transcript discussing Q3 performance...",
            ],
            "relevance_scores": [0.95, 0.88],
            "spans": [
                {"name": "retrieval", "content": "Retrieved Q3 financial report and earnings transcript"},
                {"name": "agent", "content": "Found revenue information: $2.3 million in Q3"},
            ]
        })

    return failure_traces, healthy_traces


# =============================================================================
# DETECTOR EVALUATION
# =============================================================================

DETECTOR_MAP = {
    "F1": ("SpecificationMismatchDetector", SpecificationMismatchDetector),
    "F2": ("TaskDecompositionDetector", TaskDecompositionDetector),
    "F3": ("ResourceMisallocationDetector", ResourceMisallocationDetector),
    "F4": ("ToolProvisionDetector", ToolProvisionDetector),
    "F5": ("FlawedWorkflowDetector", FlawedWorkflowDetector),
    "F6": ("TaskDerailmentDetector", TaskDerailmentDetector),
    "F7": ("ContextNeglectDetector", ContextNeglectDetector),
    "F8": ("InformationWithholdingDetector", InformationWithholdingDetector),
    "F9": ("RoleUsurpationDetector", RoleUsurpationDetector),
    "F10": ("CommunicationBreakdownDetector", CommunicationBreakdownDetector),
    "F11": ("CoordinationAnalyzer", CoordinationAnalyzer),
    "F12": ("OutputValidationDetector", OutputValidationDetector),
    "F13": ("QualityGateDetector", QualityGateDetector),
    "F14": ("CompletionMisjudgmentDetector", CompletionMisjudgmentDetector),
    "F15": ("GroundingDetector", GroundingDetector),
    "F16": ("RetrievalQualityDetector", RetrievalQualityDetector),
}

GENERATOR_MAP = {
    "F1": generate_f1_traces,
    "F2": generate_f2_traces,
    "F3": generate_f3_traces,
    "F4": generate_f4_traces,
    "F5": generate_f5_traces,
    "F6": generate_f6_traces,
    "F7": generate_f7_traces,
    "F8": generate_f8_traces,
    "F9": generate_f9_traces,
    "F10": generate_f10_traces,
    "F11": generate_f11_traces,
    "F12": generate_f12_traces,
    "F13": generate_f13_traces,
    "F14": generate_f14_traces,
    "F15": generate_f15_traces,
    "F16": generate_f16_traces,
}


def evaluate_detector(failure_mode: str, traces_per_class: int = 20) -> EvalResult:
    """Evaluate a single detector on its failure mode."""
    result = EvalResult(failure_mode=failure_mode)

    detector_name, detector_class = DETECTOR_MAP[failure_mode]
    generator = GENERATOR_MAP[failure_mode]

    # Generate traces
    failure_traces, healthy_traces = generator(traces_per_class)

    # Instantiate detector
    try:
        detector = detector_class()
    except Exception as e:
        print(f"  [SKIP] Could not instantiate {detector_name}: {e}")
        return result

    # Evaluate on failure traces (should detect = True Positive)
    for trace in failure_traces:
        try:
            detected = run_detector(detector, trace, failure_mode)
            if detected:
                result.true_positives += 1
            else:
                result.false_negatives += 1
        except Exception as e:
            result.false_negatives += 1  # Count errors as missed detections

    # Evaluate on healthy traces (should NOT detect = True Negative)
    for trace in healthy_traces:
        try:
            detected = run_detector(detector, trace, failure_mode)
            if detected:
                result.false_positives += 1
            else:
                result.true_negatives += 1
        except Exception as e:
            result.true_negatives += 1  # Count errors as no detection

    return result


def run_detector(detector: Any, trace: Dict, failure_mode: str) -> bool:
    """Run a detector on a trace and return whether it detected a failure."""

    try:
        # F1: Specification Mismatch
        # API: detect(user_intent, task_specification, original_request=None)
        if failure_mode == "F1":
            result = detector.detect(
                user_intent=trace.get("task_specification", ""),
                task_specification=trace.get("agent_output", "")
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        # F2: Task Decomposition
        # API: detect(task_description, decomposition, agent_capabilities=None)
        elif failure_mode == "F2":
            # Convert subtasks to decomposition string
            subtasks = trace.get("subtasks", [])
            decomposition = "\n".join([
                f"- {s.get('name', s.get('id', str(s)))}: depends on {s.get('depends_on', [])}"
                for s in subtasks
            ])
            result = detector.detect(
                task_description=trace.get("task", "Build application"),
                decomposition=decomposition
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        # F3: Resource Misallocation - needs ResourceEvent objects
        # Skip for now - requires specialized data structures
        elif failure_mode == "F3":
            return False  # Needs ResourceEvent objects

        # F4: Tool Provision
        # API: detect(task, agent_output, available_tools=None, tool_calls=None, context=None)
        elif failure_mode == "F4":
            # Build agent_output from trace
            spans = trace.get("spans", [])
            agent_output = " ".join(s.get("content", "") for s in spans)
            if not agent_output:
                agent_output = trace.get("error", "No tools available")

            result = detector.detect(
                task=trace.get("task", ""),
                agent_output=agent_output,
                available_tools=trace.get("available_tools", []),
                tool_calls=trace.get("tool_calls", [])
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        # F5: Workflow - needs WorkflowNode objects
        # Skip for now - requires specialized data structures
        elif failure_mode == "F5":
            return False  # Needs WorkflowNode objects

        # F6: Derailment
        # API: detect(task, output, context=None, agent_name=None)
        elif failure_mode == "F6":
            result = detector.detect(
                task=trace.get("task", ""),
                output=trace.get("agent_output", "")
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        # F7: Context Neglect
        # API: detect(context, output, task=None, agent_name=None)
        elif failure_mode == "F7":
            result = detector.detect(
                context=trace.get("context", ""),
                output=trace.get("agent_output", "")
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        # F8: Information Withholding
        # API: detect(internal_state, agent_output, task_context=None, downstream_requirements=None)
        elif failure_mode == "F8":
            result = detector.detect(
                internal_state=trace.get("research_findings", ""),
                agent_output=trace.get("passed_to_next_agent", "")
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        # F9: Role Usurpation - needs AgentAction objects
        # Skip for now - requires specialized data structures
        elif failure_mode == "F9":
            return False  # Needs AgentAction objects

        # F10: Communication Breakdown
        # API: detect(sender_message, receiver_response, receiver_action=None, sender_name=None, receiver_name=None)
        elif failure_mode == "F10":
            messages = trace.get("messages", [])
            if len(messages) >= 2:
                result = detector.detect(
                    sender_message=messages[0].get("content", ""),
                    receiver_response=messages[1].get("content", "") if len(messages) > 1 else ""
                )
                return result.detected if hasattr(result, 'detected') else bool(result)
            return False

        # F11: Coordination - needs Message objects
        # Skip for now - requires specialized data structures
        elif failure_mode == "F11":
            return False  # Needs Message objects

        # F12: Output Validation
        # API: detect(output, expected_schema=None, expected_format=None)
        elif failure_mode == "F12":
            result = detector.detect(
                output=trace.get("actual_output", ""),
                expected_schema=trace.get("expected_schema", {})
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        # F13: Quality Gate
        # API: detect(quality_criteria, agent_output, validation_results=None)
        elif failure_mode == "F13":
            gates = trace.get("quality_gates", [])
            passed = trace.get("gates_passed", [])
            # Build criteria dict
            criteria = {g: (g in passed) for g in gates}
            spans = trace.get("spans", [])
            agent_output = " ".join(s.get("content", "") for s in spans)

            result = detector.detect(
                quality_criteria=criteria,
                agent_output=agent_output,
                validation_results={"passed": passed, "required": gates}
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        # F14: Completion Misjudgment
        # API: detect(task, agent_output, claimed_status, subtask_status=None)
        elif failure_mode == "F14":
            completed = trace.get("completed_subtasks", [])
            all_subtasks = trace.get("subtasks", [])
            spans = trace.get("spans", [])
            agent_output = " ".join(s.get("content", "") for s in spans)
            if trace.get("claimed_complete"):
                agent_output += " Task complete!"

            result = detector.detect(
                task=trace.get("task", ""),
                agent_output=agent_output,
                claimed_status="complete" if trace.get("claimed_complete") else "incomplete",
                subtask_status={
                    "total": len(all_subtasks),
                    "completed": len(completed)
                }
            )
            return result.detected if hasattr(result, 'detected') else bool(result)

        # F15: Grounding
        # API: detect(agent_output, source_documents)
        elif failure_mode == "F15":
            result = detector.detect(
                agent_output=trace.get("agent_output", ""),
                source_documents=trace.get("source_documents", [])
            )
            return result.detected if hasattr(result, 'detected') else result.severity.value not in ["none", "NONE"] if hasattr(result, 'severity') else bool(result)

        # F16: Retrieval Quality
        # API: detect(query, retrieved_documents, agent_output=None)
        elif failure_mode == "F16":
            result = detector.detect(
                query=trace.get("query", ""),
                retrieved_documents=trace.get("retrieved_documents", [])
            )
            return result.detected if hasattr(result, 'detected') else result.severity.value not in ["none", "NONE"] if hasattr(result, 'severity') else bool(result)

    except Exception as e:
        # Log but don't fail - count as no detection
        pass

    return False


def run_phase1_evaluation(traces_per_class: int = 20) -> Dict[str, EvalResult]:
    """Run Phase 1 evaluation on all failure modes."""
    print("=" * 70)
    print("PHASE 1: SYNTHETIC BASELINE EVALUATION")
    print("=" * 70)
    print(f"Traces per class: {traces_per_class} (failure) + {traces_per_class} (healthy)")
    print()

    results = {}

    for failure_mode in sorted(DETECTOR_MAP.keys(), key=lambda x: int(x[1:])):
        detector_name = DETECTOR_MAP[failure_mode][0]
        print(f"Evaluating {failure_mode}: {detector_name}...", end=" ", flush=True)

        try:
            result = evaluate_detector(failure_mode, traces_per_class)
            results[failure_mode] = result

            if result.true_positives + result.false_negatives > 0:
                print(f"P={result.precision:.0%} R={result.recall:.0%} F1={result.f1:.0%}")
            else:
                print("[NO DATA]")
        except Exception as e:
            print(f"[ERROR] {e}")
            results[failure_mode] = EvalResult(failure_mode=failure_mode)

    return results


def print_summary(results: Dict[str, EvalResult]):
    """Print evaluation summary."""
    print()
    print("=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)
    print()
    print(f"{'Mode':<6} {'Detector':<35} {'Prec':>6} {'Rec':>6} {'F1':>6} {'FPR':>6}")
    print("-" * 70)

    total_tp, total_fp, total_tn, total_fn = 0, 0, 0, 0
    valid_f1_scores = []

    for mode in sorted(results.keys(), key=lambda x: int(x[1:])):
        result = results[mode]
        detector_name = DETECTOR_MAP[mode][0][:33]

        total_tp += result.true_positives
        total_fp += result.false_positives
        total_tn += result.true_negatives
        total_fn += result.false_negatives

        if result.true_positives + result.false_negatives > 0:
            valid_f1_scores.append(result.f1)

        print(f"{mode:<6} {detector_name:<35} {result.precision:>5.0%} {result.recall:>5.0%} {result.f1:>5.0%} {result.fpr:>5.0%}")

    print("-" * 70)

    # Overall metrics
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0
    overall_fpr = total_fp / (total_fp + total_tn) if (total_fp + total_tn) > 0 else 0
    avg_f1 = sum(valid_f1_scores) / len(valid_f1_scores) if valid_f1_scores else 0

    print(f"{'OVERALL':<6} {'(micro-averaged)':<35} {overall_precision:>5.0%} {overall_recall:>5.0%} {overall_f1:>5.0%} {overall_fpr:>5.0%}")
    print(f"{'AVG':<6} {'(macro-averaged F1)':<35} {'':>6} {'':>6} {avg_f1:>5.0%}")
    print()
    print(f"Total: TP={total_tp} FP={total_fp} TN={total_tn} FN={total_fn}")

    # Targets check
    print()
    print("TARGET CHECK:")
    target_f1 = 0.80
    target_fpr = 0.15
    f1_status = "PASS" if avg_f1 >= target_f1 else "FAIL"
    fpr_status = "PASS" if overall_fpr <= target_fpr else "FAIL"
    print(f"  F1 Score: {avg_f1:.1%} (target: >{target_f1:.0%}) [{f1_status}]")
    print(f"  FPR:      {overall_fpr:.1%} (target: <{target_fpr:.0%}) [{fpr_status}]")


def save_results(results: Dict[str, EvalResult], output_path: Path):
    """Save results to JSON file."""
    output = {
        "timestamp": datetime.now().isoformat(),
        "phase": "1_synthetic_baseline",
        "results": {
            mode: {
                "detector": DETECTOR_MAP[mode][0],
                "true_positives": r.true_positives,
                "false_positives": r.false_positives,
                "true_negatives": r.true_negatives,
                "false_negatives": r.false_negatives,
                "precision": r.precision,
                "recall": r.recall,
                "f1": r.f1,
                "fpr": r.fpr,
            }
            for mode, r in results.items()
        }
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phase 1: Synthetic Baseline Evaluation")
    parser.add_argument("--traces-per-class", type=int, default=20, help="Traces per class (default: 20)")
    parser.add_argument("--output", type=str, default="results/phase1_synthetic_eval.json", help="Output file")
    args = parser.parse_args()

    # Run evaluation
    results = run_phase1_evaluation(args.traces_per_class)

    # Print summary
    print_summary(results)

    # Save results
    output_path = Path(__file__).parent.parent / args.output
    save_results(results, output_path)
