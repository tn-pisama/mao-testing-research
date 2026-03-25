"""Causal Intervention for Root Cause Analysis.

Instead of correlating failure patterns, systematically perturb trace
components to find what CAUSED the failure:
- Remove an agent → does failure disappear?
- Swap tool order → does failure disappear?
- Truncate context → does failure appear?

This is principled root cause analysis, not pattern matching.
TRAIL benchmark shows even frontier LLMs only achieve 18.3% on RCA.
Causal intervention would be industry-first.

Reference: Pearl's do-calculus applied to agent traces.
"""

import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CausalFactor:
    """A component identified as causal for the failure."""
    component: str  # What was perturbed (e.g., "agent_2", "tool_order", "context")
    perturbation: str  # What was done (e.g., "removed", "swapped", "truncated")
    failure_before: float  # Detection confidence before perturbation
    failure_after: float  # Detection confidence after perturbation
    is_causal: bool  # Did the perturbation resolve the failure?
    effect_size: float  # How much confidence changed (0-1)


@dataclass
class CausalGraph:
    """Root cause analysis result."""
    detection_type: str
    root_causes: List[CausalFactor]  # Sorted by effect size
    necessary_conditions: List[str]  # Components that must be present for failure
    sufficient_conditions: List[str]  # Components that alone cause failure
    explanation: str


class CausalAnalyzer:
    """Identifies root causes by systematic perturbation.

    Algorithm:
    1. Run detector on original trace → get baseline confidence
    2. For each perturbation (remove agent, swap tools, etc.):
       a. Apply perturbation to trace copy
       b. Re-run detector
       c. If confidence drops significantly → this is a causal factor
    3. Rank causes by effect size
    4. Classify as necessary (must be present) or sufficient (alone causes failure)
    """

    # Perturbation functions: each takes input_data and returns modified copy
    PERTURBATIONS = {
        "remove_last_step": ("Remove last step from trajectory", lambda d: _remove_last_step(d)),
        "remove_first_step": ("Remove first step", lambda d: _remove_first_step(d)),
        "truncate_half": ("Keep only first half of steps", lambda d: _truncate_half(d)),
        "clear_output": ("Clear all output fields", lambda d: _clear_outputs(d)),
        "swap_agent_order": ("Reverse agent/step order", lambda d: _swap_order(d)),
        "remove_errors": ("Remove all error statuses", lambda d: _remove_errors(d)),
        "add_context": ("Add task context to output", lambda d: _add_context(d)),
        "deduplicate_states": ("Remove duplicate states", lambda d: _deduplicate(d)),
    }

    def __init__(self, confidence_threshold: float = 0.3):
        self.confidence_threshold = confidence_threshold

    def analyze(
        self,
        detection_type: str,
        input_data: Dict[str, Any],
        detector_fn: Callable[[Dict], Tuple[bool, float]],
    ) -> CausalGraph:
        """Run causal analysis on a detected failure.

        Args:
            detection_type: The failure type detected
            input_data: The trace/entry data
            detector_fn: Function that returns (detected, confidence)
        """
        # Baseline: run detector on original
        try:
            baseline_det, baseline_conf = detector_fn(input_data)
        except Exception:
            baseline_det, baseline_conf = False, 0.0

        if not baseline_det or baseline_conf < self.confidence_threshold:
            return CausalGraph(
                detection_type=detection_type,
                root_causes=[],
                necessary_conditions=[],
                sufficient_conditions=[],
                explanation="No failure detected in original trace — nothing to analyze.",
            )

        # Apply each perturbation and measure effect
        factors = []
        for pert_name, (description, pert_fn) in self.PERTURBATIONS.items():
            try:
                perturbed = pert_fn(copy.deepcopy(input_data))
                pert_det, pert_conf = detector_fn(perturbed)
            except Exception:
                continue

            effect = baseline_conf - pert_conf
            is_causal = effect > baseline_conf * 0.3  # >30% confidence drop

            factors.append(CausalFactor(
                component=pert_name,
                perturbation=description,
                failure_before=round(baseline_conf, 4),
                failure_after=round(pert_conf, 4),
                is_causal=is_causal,
                effect_size=round(abs(effect), 4),
            ))

        # Sort by effect size
        factors.sort(key=lambda f: -f.effect_size)

        # Classify conditions
        necessary = [f.component for f in factors if f.is_causal and f.failure_after < self.confidence_threshold]
        sufficient = [f.component for f in factors if f.effect_size > baseline_conf * 0.8]

        # Generate explanation
        if necessary:
            explanation = f"Root cause: {', '.join(necessary)}. Removing these resolves the {detection_type} failure."
        elif factors and factors[0].is_causal:
            explanation = f"Primary factor: {factors[0].component} ({factors[0].perturbation}). Effect: {factors[0].effect_size:.0%} confidence reduction."
        else:
            explanation = f"No single perturbation resolves the failure. The {detection_type} may be caused by the interaction of multiple components."

        return CausalGraph(
            detection_type=detection_type,
            root_causes=factors,
            necessary_conditions=necessary,
            sufficient_conditions=sufficient,
            explanation=explanation,
        )


# ── Perturbation functions ──

def _remove_last_step(d):
    for key in ("states", "steps", "events", "turns"):
        if key in d and isinstance(d[key], list) and len(d[key]) > 1:
            d[key] = d[key][:-1]
    return d

def _remove_first_step(d):
    for key in ("states", "steps", "events", "turns"):
        if key in d and isinstance(d[key], list) and len(d[key]) > 1:
            d[key] = d[key][1:]
    return d

def _truncate_half(d):
    for key in ("states", "steps", "events", "turns"):
        if key in d and isinstance(d[key], list):
            d[key] = d[key][:len(d[key]) // 2]
    return d

def _clear_outputs(d):
    if "output" in d:
        d["output"] = ""
    if "agent_output" in d:
        d["agent_output"] = ""
    for key in ("states", "steps"):
        if key in d and isinstance(d[key], list):
            for item in d[key]:
                if isinstance(item, dict):
                    item.pop("output", None)
                    if "state_delta" in item:
                        item["state_delta"].pop("output", None)
    return d

def _swap_order(d):
    for key in ("states", "steps", "events"):
        if key in d and isinstance(d[key], list):
            d[key] = list(reversed(d[key]))
    return d

def _remove_errors(d):
    for key in ("states", "steps", "events"):
        if key in d and isinstance(d[key], list):
            d[key] = [s for s in d[key] if not (isinstance(s, dict) and s.get("status") in ("error", "failed"))]
    if "current_state" in d and isinstance(d["current_state"], dict):
        if d["current_state"].get("status") in ("error", "failed"):
            d["current_state"]["status"] = "completed"
    return d

def _add_context(d):
    task = d.get("task", d.get("task_description", ""))
    if "output" in d and task:
        d["output"] = f"Regarding the task '{task[:100]}': {d['output']}"
    return d

def _deduplicate(d):
    for key in ("states", "steps"):
        if key in d and isinstance(d[key], list):
            seen = set()
            unique = []
            for item in d[key]:
                item_key = str(item.get("content", item.get("output", str(item))))[:100]
                if item_key not in seen:
                    seen.add(item_key)
                    unique.append(item)
            d[key] = unique
    return d


# Singleton
causal_analyzer = CausalAnalyzer()
