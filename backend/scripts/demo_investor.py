#!/usr/bin/env python3
"""
PISAMA Investor Demo — Quality Assessment & Self-Healing

Demonstrates the full assess -> heal -> re-assess pipeline on real n8n workflows.
Workflows are sourced from the production golden dataset (7,606 real workflows).

Usage:
    python scripts/demo_investor.py                    # Default: 3 workflows (1 single + 2 multi-agent)
    python scripts/demo_investor.py --workflow "SQL agent with memory"
    python scripts/demo_investor.py --all              # Run all demo workflows
    python scripts/demo_investor.py --find-worst 10    # Find & heal 10 worst workflows
    python scripts/demo_investor.py --multi-agent 5    # Find & heal 5 multi-agent workflows
    python scripts/demo_investor.py --failure-modes     # Demo all 17 MAST failure modes
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Setup
os.environ.setdefault("JWT_SECRET", "xK8mN3pQ7vR2sT5wY9zA4cF6hJ0lM3nP")
os.environ.setdefault("POSTGRES_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.enterprise.quality import QualityAssessor
from app.enterprise.quality.healing import QualityHealingEngine
from app.core.n8n_utils import count_ai_agents


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}


def c(text: str, color: str) -> str:
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def bar(score: float, width: int = 20) -> str:
    filled = int(score * width)
    if score >= 0.7:
        color = "green"
    elif score >= 0.5:
        color = "yellow"
    else:
        color = "red"
    return c("█" * filled, color) + c("░" * (width - filled), "dim")


def grade_color(grade: str) -> str:
    if grade in ("Healthy", "Good"):
        return "green"
    elif grade == "Needs Attention":
        return "yellow"
    else:
        return "red"


def print_header(text: str) -> None:
    print(f"\n{c('═' * 70, 'blue')}")
    print(f"  {c(text, 'bold')}")
    print(f"{c('═' * 70, 'blue')}")


def print_score_card(report, label: str = "Assessment") -> Dict[str, float]:
    """Print a score card and return dimension scores."""
    grade = report.overall_grade
    gc = grade_color(grade)
    print(f"\n  {c(label, 'bold')}: {c(f'{report.overall_score:.0%}', gc)} ({c(grade, gc)})")

    dims = {}

    if report.agent_scores:
        print(f"\n  {c('Agent Quality', 'cyan')} ({len(report.agent_scores)} agent{'s' if len(report.agent_scores) != 1 else ''})")
        for agent in report.agent_scores:
            print(f"    {agent.agent_name}")
            for d in agent.dimensions:
                dims.setdefault(d.dimension, []).append(d.score)
                print(f"      {d.dimension:25s} {bar(d.score, 15)} {d.score:.0%}")

    print(f"\n  {c('Orchestration Quality', 'cyan')}")
    for d in report.orchestration_score.dimensions:
        dims[d.dimension] = [d.score]
        print(f"    {d.dimension:25s} {bar(d.score, 15)} {d.score:.0%}")

    return {k: sum(v) / len(v) for k, v in dims.items()}


# ---------------------------------------------------------------------------
# MAST failure mode definitions (17 modes)
# ---------------------------------------------------------------------------

MAST_MODES = {
    # FC1: Planning Failures
    "F1": {"label": "Specification Mismatch", "category": "FC1", "golden_prefix": None,
            "primary_dims": ["output_consistency", "role_clarity", "ai_architecture"],
            "agent_roles": [("Content Generator", "Generate content"), ("Format Checker", "Check format"), ("Quality Reviewer", "Review quality")],
            "weaknesses": {"vague_prompt", "no_output_format", "no_validation"}},
    "F2": {"label": "Poor Task Decomposition", "category": "FC1", "golden_prefix": None,
            "primary_dims": ["role_clarity", "complexity_management"],
            "agent_roles": [("General Assistant", "Help the user"), ("Helper", "Assist with tasks"), ("Processor", "Process data")],
            "weaknesses": {"overlapping_roles", "no_output_format"}},
    "F3": {"label": "Resource Misallocation", "category": "FC1", "golden_prefix": "RESOURCE",
            "primary_dims": ["config_appropriateness", "error_handling", "best_practices"],
            "agent_roles": [], "weaknesses": set()},
    "F4": {"label": "Inadequate Tool Provision", "category": "FC1", "golden_prefix": None,
            "primary_dims": ["tool_usage", "ai_architecture"],
            "agent_roles": [("Data Fetcher", "Fetch data from APIs"), ("Analyzer", "Analyze the data"), ("Reporter", "Generate reports")],
            "weaknesses": {"no_tools", "vague_prompt"}},
    "F5": {"label": "Flawed Workflow Design", "category": "FC1", "golden_prefix": "LOOP",
            "primary_dims": ["agent_coupling", "role_clarity", "complexity_management"],
            "agent_roles": [], "weaknesses": set()},
    # FC2: Execution Failures
    "F6": {"label": "Task Derailment", "category": "FC2", "golden_prefix": None,
            "primary_dims": ["role_clarity", "config_appropriateness"],
            "agent_roles": [("Task Planner", "Plan tasks"), ("Task Executor", "Execute the plan"), ("Progress Tracker", "Track progress")],
            "weaknesses": {"weak_boundaries", "high_temperature"}},
    "F7": {"label": "Context Neglect", "category": "FC2", "golden_prefix": "STATE",
            "primary_dims": ["data_flow_clarity", "best_practices", "observability"],
            "agent_roles": [], "weaknesses": set()},
    "F8": {"label": "Information Withholding", "category": "FC2", "golden_prefix": None,
            "primary_dims": ["output_consistency", "data_flow_clarity", "agent_coupling"],
            "agent_roles": [("Data Collector", "Collect information"), ("Summarizer", "Summarize findings"), ("Decision Maker", "Make decisions")],
            "weaknesses": {"no_output_format", "no_handoff"}},
    "F9": {"label": "Role Usurpation", "category": "FC2", "golden_prefix": "PERSONA",
            "primary_dims": ["role_clarity", "output_consistency", "config_appropriateness"],
            "agent_roles": [], "weaknesses": set()},
    "F10": {"label": "Communication Breakdown", "category": "FC2", "golden_prefix": "COORD",
            "primary_dims": ["agent_coupling", "data_flow_clarity", "observability"],
            "agent_roles": [], "weaknesses": set()},
    "F11": {"label": "Coordination Failure", "category": "FC2", "golden_prefix": "COORD",
            "primary_dims": ["agent_coupling", "data_flow_clarity", "best_practices"],
            "agent_roles": [], "weaknesses": set()},
    # FC3: Verification Failures
    "F12": {"label": "Output Validation Failure", "category": "FC3", "golden_prefix": None,
            "primary_dims": ["ai_architecture", "error_handling", "best_practices"],
            "agent_roles": [("Generator", "Generate output"), ("Validator", "Validate results"), ("Publisher", "Publish approved content")],
            "weaknesses": {"no_validation", "no_error_handling"}},
    "F13": {"label": "Quality Gate Bypass", "category": "FC3", "golden_prefix": None,
            "primary_dims": ["observability", "best_practices", "test_coverage"],
            "agent_roles": [("Processor", "Process input"), ("Checker", "Check quality"), ("Dispatcher", "Send results")],
            "weaknesses": {"no_checkpoints", "no_error_trigger", "no_pin_data"}},
    "F14": {"label": "Completion Misjudgment", "category": "FC3", "golden_prefix": None,
            "primary_dims": ["role_clarity", "error_handling", "observability"],
            "agent_roles": [("Worker", "Do the work"), ("Evaluator", "Evaluate completion"), ("Finalizer", "Finalize output")],
            "weaknesses": {"no_completion_criteria", "no_validation"}},
    # Extended
    "F15": {"label": "Termination Awareness", "category": "EXT", "golden_prefix": "LOOP",
            "primary_dims": ["agent_coupling", "role_clarity", "error_handling"],
            "agent_roles": [], "weaknesses": set()},
    "F16": {"label": "Reasoning/Action Mismatch", "category": "EXT", "golden_prefix": None,
            "primary_dims": ["output_consistency", "config_appropriateness", "role_clarity"],
            "agent_roles": [("Reasoner", "Analyze and reason"), ("Actor", "Take action"), ("Verifier", "Verify alignment")],
            "weaknesses": {"no_output_format", "high_temperature", "weak_boundaries"}},
    "F17": {"label": "Clarification Request", "category": "EXT", "golden_prefix": None,
            "primary_dims": ["role_clarity", "error_handling"],
            "agent_roles": [("Interpreter", "Interpret requests"), ("Clarifier", "Ask for clarification"), ("Executor", "Execute clear requests")],
            "weaknesses": {"no_clarification", "no_error_handling"}},
}

MAST_CATEGORIES = {
    "FC1": "Planning Failures",
    "FC2": "Execution Failures",
    "FC3": "Verification Failures",
    "EXT": "Extended Failure Modes",
}



# count_ai_agents imported from app.core.n8n_utils


# ---------------------------------------------------------------------------
# Synthetic MAST workflow generator
# ---------------------------------------------------------------------------

# Weakness -> system prompt fragments
_PROMPT_FRAGMENTS = {
    "vague_prompt": "Help the user with their request.",
    "weak_boundaries": "You are an assistant. Try your best.",
    "overlapping_roles": "You are a general-purpose AI assistant. Handle any task.",
    "no_clarification": "Process the input and produce output.",
    "no_completion_criteria": "Work on the task until done.",
}


def _make_agent_node(
    index: int,
    role_name: str,
    role_prompt: str,
    weaknesses: set,
    position_x: int,
) -> Dict[str, Any]:
    """Create a single agent node with specific weaknesses injected."""
    agent_id = f"agent-{index}"

    # Build system message based on weaknesses
    if weaknesses & {"vague_prompt", "weak_boundaries", "overlapping_roles",
                      "no_clarification", "no_completion_criteria"}:
        # Use the first matching weakness prompt
        for w in ["overlapping_roles", "vague_prompt", "weak_boundaries",
                   "no_clarification", "no_completion_criteria"]:
            if w in weaknesses:
                system_msg = _PROMPT_FRAGMENTS[w]
                break
    else:
        system_msg = ""  # No prompt at all

    params: Dict[str, Any] = {}
    if system_msg:
        params["systemMessage"] = system_msg

    # Inject high temperature if specified
    if "high_temperature" in weaknesses:
        params.setdefault("options", {})["temperature"] = 1.0

    return {
        "id": agent_id,
        "name": role_name,
        "type": "@n8n/n8n-nodes-langchain.agent",
        "parameters": params,
        "position": [position_x, 0],
    }


def generate_mast_workflow(mode_id: str, agent_count: int) -> Dict[str, Any]:
    """Generate a synthetic n8n workflow exhibiting a specific MAST failure mode."""
    mode = MAST_MODES[mode_id]
    weaknesses = mode["weaknesses"]
    roles = mode["agent_roles"]
    label = "Simple" if agent_count == 1 else "Multi"

    # Build nodes
    nodes: List[Dict[str, Any]] = [
        {"id": "t1", "name": "Webhook Trigger", "type": "n8n-nodes-base.webhook",
         "parameters": {"path": f"/{mode_id.lower()}"}, "position": [0, 0]},
    ]

    for i in range(agent_count):
        role_name = roles[i % len(roles)][0] if roles else f"Agent {i + 1}"
        role_prompt = roles[i % len(roles)][1] if roles else "Process input"
        nodes.append(_make_agent_node(i, role_name, role_prompt, weaknesses, (i + 1) * 200))

    nodes.append(
        {"id": "out", "name": "Output", "type": "n8n-nodes-base.respondToWebhook",
         "parameters": {}, "position": [(agent_count + 1) * 200, 0]},
    )

    # Chain connections: trigger -> agent0 -> agent1 -> ... -> output
    connections: Dict[str, Any] = {}
    for i in range(len(nodes) - 1):
        src = nodes[i]["name"]
        dst = nodes[i + 1]["name"]
        connections[src] = {"main": [[{"node": dst, "type": "main", "index": 0}]]}

    return {
        "name": f"{mode_id} {label}: {mode['label']}",
        "nodes": nodes,
        "connections": connections,
        "settings": {},
    }


def find_golden_dataset_for_mode(
    entries: List[Dict[str, Any]], prefix: str
) -> Dict[str, Dict[str, Any]]:
    """Find smallest-team and largest-team workflows for a golden dataset prefix."""
    seen: set = set()
    candidates: List[Dict[str, Any]] = []
    for e in entries:
        name = e.get("input_data", {}).get("workflow_name", "")
        if not name.startswith(prefix) or name in seen:
            continue
        seen.add(name)
        wf = build_workflow(e)
        agents = count_ai_agents(wf)
        candidates.append({"workflow": wf, "agents": agents, "name": name})

    if not candidates:
        return {}

    candidates.sort(key=lambda x: x["agents"])
    return {"small": candidates[0], "large": candidates[-1]}


# ---------------------------------------------------------------------------
# Workflow loading
# ---------------------------------------------------------------------------

def load_golden_dataset() -> List[Dict[str, Any]]:
    """Load workflows from the production golden dataset."""
    paths = [
        Path(__file__).resolve().parent.parent / "data" / "golden_dataset_n8n_full.json",
        Path(__file__).resolve().parent.parent / "data" / "golden_dataset_n8n.json",
    ]
    for path in paths:
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            return data.get("entries", [])
    return []


def build_workflow(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Build a proper workflow dict from a golden dataset entry."""
    inp = entry.get("input_data", {})
    return {
        "name": inp.get("workflow_name", "Unknown Workflow"),
        "nodes": inp.get("nodes", []),
        "connections": inp.get("connections", {}),
        "settings": inp.get("settings", {}),
    }


def find_workflow_by_name(entries: List[Dict], name: str) -> Optional[Dict]:
    """Find a workflow by exact or partial name match."""
    # Exact match first
    for e in entries:
        if e.get("input_data", {}).get("workflow_name", "") == name:
            return e
    # Partial match
    name_lower = name.lower()
    for e in entries:
        wf_name = e.get("input_data", {}).get("workflow_name", "").lower()
        if name_lower in wf_name:
            return e
    return None


def find_demo_workflows(entries: List[Dict]) -> List[Dict[str, Any]]:
    """Find the best demo workflows automatically."""
    assessor = QualityAssessor(use_llm_judge=False)

    # Filter to external AI workflows with good names
    candidates = []
    seen_names = set()
    for e in entries:
        name = e.get("input_data", {}).get("workflow_name", "")
        if name.startswith("ext_") or name.startswith("neg_") or not name:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)

        nodes = e.get("input_data", {}).get("nodes", [])
        node_types = [n.get("type", "") for n in nodes]
        has_ai = any("langchain" in t or "openAi" in t for t in node_types)
        if has_ai and 4 <= len(nodes) <= 25:
            candidates.append(e)

    # Assess and sort
    scored = []
    for e in candidates[:200]:  # Cap for speed
        workflow = build_workflow(e)
        try:
            report = assessor.assess_workflow(workflow)
            scored.append((report.overall_score, workflow["name"], e))
        except Exception:
            pass

    scored.sort(key=lambda x: x[0])

    # Pick worst, medium, and best
    result = []
    if scored:
        result.append(scored[0][2])  # Worst
    if len(scored) > 10:
        mid = len(scored) // 2
        result.append(scored[mid][2])  # Medium
    if len(scored) > 20:
        result.append(scored[-1][2])  # Best (highest scoring)

    return result


# ---------------------------------------------------------------------------
# Main demo flow
# ---------------------------------------------------------------------------

def run_demo_on_workflow(
    workflow: Dict[str, Any],
    assessor: QualityAssessor,
    engine: QualityHealingEngine,
) -> Dict[str, Any]:
    """Run full assess -> heal -> re-assess on a single workflow."""
    name = workflow["name"]
    n_nodes = len(workflow.get("nodes", []))
    n_ai = sum(
        1 for n in workflow.get("nodes", [])
        if "langchain" in n.get("type", "") or "openAi" in n.get("type", "")
    )

    print_header(f"{name} ({n_nodes} nodes, {n_ai} AI agent{'s' if n_ai != 1 else ''})")

    # Step 1: Initial assessment
    print(f"\n  {c('Step 1:', 'bold')} Assessing workflow quality...")
    t0 = time.time()
    report = assessor.assess_workflow(workflow)
    assess_time = time.time() - t0

    before_dims = print_score_card(report, "BEFORE")
    print(f"\n  {c('dim', 'dim')} assessed in {assess_time:.1f}s")

    # Step 2: Check if healing is needed
    if report.overall_score >= 0.75:
        print(f"\n  {c('Score above 75% — no healing needed.', 'green')}")
        return {
            "name": name,
            "before": report.overall_score,
            "after": report.overall_score,
            "improvement": 0,
            "fixes": 0,
            "status": "healthy",
            "before_dims": before_dims,
            "after_dims": before_dims,
        }

    # Step 3: Heal
    print(f"\n  {c('Step 2:', 'bold')} Generating and applying fixes...")
    t0 = time.time()
    result = engine.heal(report, workflow)
    heal_time = time.time() - t0

    n_fixes = len(result.applied_fixes)
    print(f"  {n_fixes} fixes applied ({result.status.value}) in {heal_time:.1f}s")

    if result.applied_fixes:
        # Group fixes by dimension
        fix_by_dim: Dict[str, List] = {}
        for fix in result.applied_fixes:
            fix_by_dim.setdefault(fix.dimension, []).append(fix)

        print(f"\n  {c('Applied Fixes:', 'cyan')}")
        for dim, fixes in sorted(fix_by_dim.items()):
            print(f"    {dim}: {len(fixes)} fix{'es' if len(fixes) != 1 else ''}")
            for fix in fixes[:2]:  # Show first 2 per dim
                comp = fix.target_component
                if comp and comp != "unknown":
                    print(f"      -> {comp}")

    # Step 4: Re-assess
    healed_workflow = result.metadata.get("healed_workflow", workflow)
    print(f"\n  {c('Step 3:', 'bold')} Re-assessing healed workflow...")
    after_report = assessor.assess_workflow(healed_workflow)
    after_dims = print_score_card(after_report, "AFTER")

    # Step 5: Show improvement delta
    improvement = after_report.overall_score - report.overall_score
    print(f"\n  {c('Improvement:', 'bold')} {c(f'{improvement:+.0%}', 'green' if improvement > 0 else 'red')}")

    # Dimension-level deltas
    print(f"\n  {c('Per-Dimension Changes:', 'cyan')}")
    all_dims = sorted(set(list(before_dims.keys()) + list(after_dims.keys())))
    for dim in all_dims:
        b = before_dims.get(dim, 0)
        a = after_dims.get(dim, 0)
        delta = a - b
        if abs(delta) > 0.01:
            dc = "green" if delta > 0 else "red"
            print(f"    {dim:25s} {b:.0%} -> {a:.0%}  {c(f'({delta:+.0%})', dc)}")

    return {
        "name": name,
        "before": report.overall_score,
        "after": after_report.overall_score,
        "improvement": improvement,
        "fixes": n_fixes,
        "status": result.status.value,
        "before_dims": before_dims,
        "after_dims": after_dims,
    }


def print_summary(results: List[Dict[str, Any]]) -> None:
    """Print final summary table."""
    print_header("Demo Summary")

    healed = [r for r in results if r["improvement"] > 0]

    print(f"\n  {'Workflow':<45s} {'Before':>8s} {'After':>8s} {'Delta':>8s} {'Fixes':>6s}")
    print(f"  {'─' * 45} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 6}")
    for r in results:
        imp = r["improvement"]
        dc = "green" if imp > 0.15 else "yellow" if imp > 0.05 else "dim"
        print(
            f"  {r['name'][:45]:<45s} "
            f"{r['before']:>7.0%} "
            f"{r['after']:>7.0%} "
            f"{c(f'{imp:+7.0%}', dc)} "
            f"{r['fixes']:>5d}"
        )

    if healed:
        avg_before = sum(r["before"] for r in healed) / len(healed)
        avg_after = sum(r["after"] for r in healed) / len(healed)
        avg_imp = sum(r["improvement"] for r in healed) / len(healed)
        print(f"\n  {c('Average (healed):', 'bold')} {avg_before:.0%} -> {avg_after:.0%} ({c(f'{avg_imp:+.0%}', 'green')})")
        best_imp = max(r["improvement"] for r in healed)
        print(f"  {c('Best improvement:', 'bold')} {c(f'{best_imp:+.0%}', 'green')}")


def print_failure_mode_summary(mode_results: Dict[str, List[Dict[str, Any]]]) -> None:
    """Print failure-mode-organized summary with per-dimension improvements."""
    print_header("MAST Failure Mode Healing Summary")

    all_results: List[Dict[str, Any]] = []

    # Group by MAST category
    for cat_id, cat_label in MAST_CATEGORIES.items():
        cat_modes = [m for m, cfg in MAST_MODES.items() if cfg["category"] == cat_id]
        cat_has_results = any(m in mode_results for m in cat_modes)
        if not cat_has_results:
            continue

        print(f"\n  {c(f'{cat_id}: {cat_label}', 'bold')}")
        print(f"  {'Mode':<6s} {'Failure':<28s} {'Small':>14s} {'Large':>14s} {'Avg Delta':>10s}")
        print(f"  {'─' * 6} {'─' * 28} {'─' * 14} {'─' * 14} {'─' * 10}")

        for mode_id in cat_modes:
            results = mode_results.get(mode_id, [])
            if not results:
                continue
            all_results.extend(results)
            label = MAST_MODES[mode_id]["label"][:28]

            small_r = next((r for r in results if r.get("team_size") == "small"), None)
            large_r = next((r for r in results if r.get("team_size") == "large"), None)

            small_str = f"{small_r['before']:.0%}->{small_r['after']:.0%}" if small_r else "—"
            large_str = f"{large_r['before']:.0%}->{large_r['after']:.0%}" if large_r else "—"

            imps = [r["improvement"] for r in results if r["improvement"] > 0]
            avg_imp = sum(imps) / len(imps) if imps else 0
            dc = "green" if avg_imp > 0.15 else "yellow" if avg_imp > 0.05 else "dim"

            print(f"  {c(mode_id, 'cyan'):<15s} {label:<28s} {small_str:>14s} {large_str:>14s} {c(f'{avg_imp:+.0%}', dc):>19s}")

    # Per-mode primary dimension improvements
    print(f"\n  {c('Key Dimension Improvements by Mode:', 'bold')}")
    for mode_id in sorted(mode_results.keys(), key=lambda x: int(x[1:])):
        results = mode_results[mode_id]
        mode = MAST_MODES[mode_id]
        dim_deltas = []
        for dim in mode["primary_dims"]:
            befores = [r["before_dims"].get(dim, 0) for r in results if "before_dims" in r]
            afters = [r["after_dims"].get(dim, 0) for r in results if "after_dims" in r]
            if befores and afters:
                delta = (sum(afters) / len(afters)) - (sum(befores) / len(befores))
                if abs(delta) > 0.01:
                    dc = "green" if delta > 0 else "red"
                    dim_deltas.append(f"{dim} {c(f'{delta:+.0%}', dc)}")
        if dim_deltas:
            print(f"    {c(mode_id, 'cyan')} {mode['label'][:25]:<25s}  {', '.join(dim_deltas)}")

    # Overall stats
    if all_results:
        healed = [r for r in all_results if r["improvement"] > 0]
        modes_covered = len(mode_results)
        print(f"\n  {c(f'{modes_covered}/17 MAST failure modes covered', 'bold')}")
        print(f"  {len(all_results)} workflows tested, {len(healed)} improved")
        if healed:
            avg_b = sum(r["before"] for r in healed) / len(healed)
            avg_a = sum(r["after"] for r in healed) / len(healed)
            avg_imp = sum(r["improvement"] for r in healed) / len(healed)
            best_imp = max(r["improvement"] for r in healed)
            print(f"  Average: {avg_b:.0%} -> {avg_a:.0%} ({c(f'{avg_imp:+.0%}', 'green')})")
            print(f"  Best single improvement: {c(f'{best_imp:+.0%}', 'green')}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="PISAMA Investor Demo")
    parser.add_argument("--workflow", type=str, help="Run on a specific workflow by name")
    parser.add_argument("--all", action="store_true", help="Run all 3 demo workflows")
    parser.add_argument("--find-worst", type=int, metavar="N", help="Find and heal N worst-scoring workflows")
    parser.add_argument("--multi-agent", type=int, metavar="N", help="Find and heal N multi-agent workflows (3+ agents)")
    parser.add_argument("--failure-modes", action="store_true", help="Demo all 17 MAST failure modes with small/large teams")
    parser.add_argument("--max-fixes", type=int, default=50, help="Max fixes per workflow (default: 50)")
    args = parser.parse_args()

    print(c("\n  ╔══════════════════════════════════════════════════════════╗", "blue"))
    print(c("  ║", "blue") + c("   PISAMA — n8n Workflow Quality & Self-Healing Demo   ", "bold") + c("║", "blue"))
    print(c("  ╚══════════════════════════════════════════════════════════╝", "blue"))

    entries = load_golden_dataset()
    if not entries:
        print(c("\n  ERROR: No golden dataset found.", "red"))
        sys.exit(1)
    print(f"\n  Loaded {c(str(len(entries)), 'cyan')} production workflows from golden dataset")

    assessor = QualityAssessor(use_llm_judge=False)
    engine = QualityHealingEngine(
        auto_apply=True,
        score_threshold=0.7,
        max_fix_attempts=args.max_fixes,
    )

    workflows_to_test = []

    if args.workflow:
        entry = find_workflow_by_name(entries, args.workflow)
        if not entry:
            print(c(f"\n  Workflow '{args.workflow}' not found in dataset.", "red"))
            sys.exit(1)
        workflows_to_test.append(build_workflow(entry))

    elif args.find_worst:
        print(f"\n  Finding {args.find_worst} worst-scoring AI workflows...")
        # Quick assessment of many workflows
        scored = []
        seen = set()
        for e in entries:
            name = e.get("input_data", {}).get("workflow_name", "")
            if name in seen or name.startswith("ext_") or name.startswith("neg_"):
                continue
            seen.add(name)
            nodes = e.get("input_data", {}).get("nodes", [])
            has_ai = any("langchain" in n.get("type", "") or "openAi" in n.get("type", "") for n in nodes)
            if not has_ai or len(nodes) < 4:
                continue
            wf = build_workflow(e)
            try:
                report = assessor.assess_workflow(wf)
                if report.overall_score < 0.55:
                    scored.append((report.overall_score, wf))
            except Exception:
                pass
            if len(scored) >= args.find_worst * 3:
                break

        scored.sort(key=lambda x: x[0])
        workflows_to_test = [wf for _, wf in scored[: args.find_worst]]
        print(f"  Found {len(workflows_to_test)} workflows below 55%")

    elif args.multi_agent:
        print(f"\n  Finding {args.multi_agent} worst multi-agent workflows (3+ agents)...")
        scored = []
        seen = set()
        for e in entries:
            name = e.get("input_data", {}).get("workflow_name", "")
            if name in seen or name.startswith("ext_") or name.startswith("neg_"):
                continue
            seen.add(name)
            nodes = e.get("input_data", {}).get("nodes", [])
            ai_count = sum(
                1 for n in nodes
                if "langchain" in n.get("type", "") or "openAi" in n.get("type", "")
            )
            if ai_count < 3 or len(nodes) < 6:
                continue
            wf = build_workflow(e)
            try:
                report = assessor.assess_workflow(wf)
                if report.overall_score < 0.60:
                    scored.append((report.overall_score, ai_count, wf))
            except Exception:
                pass
            if len(scored) >= args.multi_agent * 3:
                break

        scored.sort(key=lambda x: x[0])
        workflows_to_test = [wf for _, _, wf in scored[: args.multi_agent]]
        print(f"  Found {len(workflows_to_test)} multi-agent workflows below 60%")

    elif args.failure_modes:
        print(f"\n  {c('All 17 MAST Failure Modes', 'bold')} — single-agent & multi-agent healing")
        print(f"  17 modes x 2 team sizes = 34 workflows\n")

        mode_results: Dict[str, List[Dict[str, Any]]] = {}
        seen_prefixes: set = set()

        for mode_id in sorted(MAST_MODES.keys(), key=lambda x: int(x[1:])):
            mode = MAST_MODES[mode_id]
            cat = MAST_CATEGORIES[mode["category"]]
            prefix = mode["golden_prefix"]

            mode_label = mode["label"]
            print(f"\n  {c(f'{mode_id}: {mode_label}', 'bold')} ({cat})")

            mode_results[mode_id] = []

            if prefix and prefix not in seen_prefixes:
                # Use golden dataset workflows
                seen_prefixes.add(prefix)
                gd = find_golden_dataset_for_mode(entries, prefix)
                if gd:
                    # Small team
                    small = gd["small"]
                    n_small = small["agents"]
                    print(f"  {c(f'Small team ({n_small} agents) — golden dataset', 'dim')}")
                    result = run_demo_on_workflow(small["workflow"], assessor, engine)
                    result["team_size"] = "small"
                    result["agents"] = n_small
                    mode_results[mode_id].append(result)

                    # Large team
                    large = gd["large"]
                    n_large = large["agents"]
                    print(f"  {c(f'Large team ({n_large} agents) — golden dataset', 'dim')}")
                    result = run_demo_on_workflow(large["workflow"], assessor, engine)
                    result["team_size"] = "large"
                    result["agents"] = large["agents"]
                    mode_results[mode_id].append(result)
                else:
                    print(c(f"  No golden dataset workflows for {prefix}", "yellow"))

            elif prefix and prefix in seen_prefixes:
                # This prefix was already used by another mode (e.g., COORD for F10 and F11)
                # Generate synthetic instead to avoid duplicates
                for agent_count, team_label in [(1, "small"), (3, "large")]:
                    wf = generate_mast_workflow(mode_id, agent_count)
                    suffix = "s" if agent_count > 1 else ""
                    print(f"  {c(f'{team_label.title()} team ({agent_count} agent{suffix}) — synthetic', 'dim')}")
                    result = run_demo_on_workflow(wf, assessor, engine)
                    result["team_size"] = team_label
                    result["agents"] = agent_count
                    mode_results[mode_id].append(result)

            else:
                # Generate synthetic workflows
                for agent_count, team_label in [(1, "small"), (3, "large")]:
                    wf = generate_mast_workflow(mode_id, agent_count)
                    suffix = "s" if agent_count > 1 else ""
                    print(f"  {c(f'{team_label.title()} team ({agent_count} agent{suffix}) — synthetic', 'dim')}")
                    result = run_demo_on_workflow(wf, assessor, engine)
                    result["team_size"] = team_label
                    result["agents"] = agent_count
                    mode_results[mode_id].append(result)

        print_failure_mode_summary(mode_results)
        print()
        return

    else:
        # Default: 1 single-agent + auto-selected multi-agent workflows
        # Start with a known single-agent workflow
        demo_names = ["SQL agent with memory"]
        for name in demo_names:
            entry = find_workflow_by_name(entries, name)
            if entry:
                workflows_to_test.append(build_workflow(entry))
            else:
                print(c(f"  Warning: '{name}' not found, skipping", "yellow"))

        # Auto-find 2 multi-agent workflows from the dataset
        print(f"  Auto-selecting multi-agent workflows...")
        ma_scored = []
        seen = {wf["name"] for wf in workflows_to_test}
        for e in entries:
            name = e.get("input_data", {}).get("workflow_name", "")
            if name in seen or name.startswith("ext_") or name.startswith("neg_") or not name:
                continue
            seen.add(name)
            nodes = e.get("input_data", {}).get("nodes", [])
            ai_count = sum(
                1 for n in nodes
                if "langchain" in n.get("type", "") or "openAi" in n.get("type", "")
            )
            if ai_count < 2 or len(nodes) < 5:
                continue
            wf = build_workflow(e)
            try:
                report = assessor.assess_workflow(wf)
                if report.overall_score < 0.60:
                    ma_scored.append((report.overall_score, ai_count, wf))
            except Exception:
                pass
            if len(ma_scored) >= 20:
                break

        ma_scored.sort(key=lambda x: x[0])
        # Pick one with 2-3 agents and one with 4+ if available
        small_ma = [s for s in ma_scored if s[1] <= 3]
        large_ma = [s for s in ma_scored if s[1] >= 4]
        if small_ma:
            workflows_to_test.append(small_ma[0][2])
        if large_ma:
            workflows_to_test.append(large_ma[0][2])
        elif len(small_ma) > 1:
            workflows_to_test.append(small_ma[1][2])

    if not workflows_to_test:
        print(c("\n  No workflows to demo.", "red"))
        sys.exit(1)

    results = []
    for wf in workflows_to_test:
        result = run_demo_on_workflow(wf, assessor, engine)
        results.append(result)

    print_summary(results)
    print()


if __name__ == "__main__":
    main()
