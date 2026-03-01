"""Compound Failure Analyzer — post-detection analysis for multi-failure traces.

When a trace triggers multiple detectors simultaneously, this module enriches
the flat detection list with:
- Failure clusters (related failures grouped together)
- Causal chains (root cause → symptom ordering)
- Co-occurrence pattern matching (from MAST research)
- Confidence adjustments (boost known pairs, flag unusual combinations)

ICP-tier: No ML, no LLM, no database. Pure pattern matching on detection results.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# --------------------------------------------------------------------------- #
#  MAST Co-Occurrence Map
#  Empirical data: which failure modes frequently appear together.
#  Source: MAST taxonomy research — F9 co-occurs with F1/F3/F5/F7/F8/F11/F12/F14.
# --------------------------------------------------------------------------- #

CO_OCCURRENCE_MAP: Dict[str, List[str]] = {
    # F9 (Role Usurpation) always co-occurs with others in MAST
    "F9":  ["F1", "F3", "F5", "F7", "F8", "F11", "F12", "F14"],
    # Workflow failures cascade downstream
    "F5":  ["F6", "F7", "F14"],
    # Communication breakdown → coordination failure
    "F10": ["F11", "F3"],
    # Poor decomposition → resource issues → derailment
    "F2":  ["F3", "F6"],
    # Specification mismatch → completion misjudgment
    "F1":  ["F14", "F12"],
    # Context neglect → withholding → communication issues
    "F7":  ["F8", "F10"],
    # Information withholding → coordination problems
    "F8":  ["F11", "F10"],
}

# Bidirectional lookup: build reverse map
_CO_OCCURRENCE_PAIRS: Set[Tuple[str, str]] = set()
for src, targets in CO_OCCURRENCE_MAP.items():
    for tgt in targets:
        pair = tuple(sorted([src, tgt]))
        _CO_OCCURRENCE_PAIRS.add(pair)


# --------------------------------------------------------------------------- #
#  Causal Precedence — which failures tend to be causes vs symptoms.
#  Lower number = more likely to be root cause.
# --------------------------------------------------------------------------- #

CAUSAL_DEPTH: Dict[str, int] = {
    # Root causes (design-level issues)
    "F1": 1,   # Specification Mismatch — flawed from the start
    "F2": 1,   # Poor Task Decomposition — structural issue
    "F5": 1,   # Flawed Workflow — design flaw

    # Mid-level causes (execution-level)
    "F3": 2,   # Resource Misallocation
    "F4": 2,   # Tool Provision Failure
    "F9": 2,   # Role Usurpation — agent overreach
    "F10": 2,  # Communication Breakdown

    # Symptoms (downstream effects)
    "F6": 3,   # Task Derailment
    "F7": 3,   # Context Neglect
    "F8": 3,   # Information Withholding
    "F11": 3,  # Coordination Failure
    "F12": 3,  # Output Validation Failure
    "F13": 3,  # Quality Gate Bypass

    # Terminal symptoms (end-state indicators)
    "F14": 4,  # Completion Misjudgment
    "F15": 4,  # Termination Awareness
    "F16": 4,  # Reasoning-Action Mismatch
    "F17": 4,  # Clarification Request Failure
}

DEFAULT_DEPTH = 3  # For unknown failure modes like "error", "loop"


# --------------------------------------------------------------------------- #
#  Human-readable names for failure modes
# --------------------------------------------------------------------------- #

FAILURE_MODE_LABELS: Dict[str, str] = {
    "F1": "Specification Mismatch",
    "F2": "Poor Task Decomposition",
    "F3": "Resource Misallocation",
    "F4": "Tool Provision Failure",
    "F5": "Flawed Workflow",
    "F6": "Task Derailment",
    "F7": "Context Neglect",
    "F8": "Information Withholding",
    "F9": "Role Usurpation",
    "F10": "Communication Breakdown",
    "F11": "Coordination Failure",
    "F12": "Output Validation Failure",
    "F13": "Quality Gate Bypass",
    "F14": "Completion Misjudgment",
    "F15": "Termination Awareness",
    "F16": "Reasoning-Action Mismatch",
    "F17": "Clarification Request Failure",
    "error": "Explicit Error",
    "loop": "Infinite Loop",
}


# --------------------------------------------------------------------------- #
#  Result Dataclasses
# --------------------------------------------------------------------------- #

@dataclass
class FailureCluster:
    """A group of related failures that stem from a common cause or pattern."""
    cluster_id: int
    label: str
    root_cause_mode: Optional[str]  # The failure mode that is the root
    member_modes: List[str]
    relationship: str  # "causal_chain", "co_occurrence", "shared_spans"
    confidence_boost: float = 0.0  # How much to boost confidence for known patterns

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "label": self.label,
            "root_cause_mode": self.root_cause_mode,
            "member_modes": self.member_modes,
            "relationship": self.relationship,
            "confidence_boost": round(self.confidence_boost, 2),
        }


@dataclass
class CausalChain:
    """An ordered sequence of failures from root cause to terminal symptom."""
    chain: List[str]  # Ordered: root → ... → symptom
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        labels = [FAILURE_MODE_LABELS.get(fm, fm) for fm in self.chain]
        return {
            "chain": self.chain,
            "chain_labels": labels,
            "explanation": self.explanation,
        }


@dataclass
class CompoundAnalysis:
    """Complete analysis of compound failure interactions."""
    clusters: List[FailureCluster] = field(default_factory=list)
    causal_chains: List[CausalChain] = field(default_factory=list)
    co_occurrence_notes: List[str] = field(default_factory=list)
    root_cause_mode: Optional[str] = None
    root_cause_explanation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clusters": [c.to_dict() for c in self.clusters],
            "causal_chains": [c.to_dict() for c in self.causal_chains],
            "co_occurrence_notes": self.co_occurrence_notes,
            "root_cause_mode": self.root_cause_mode,
            "root_cause_explanation": self.root_cause_explanation,
        }


# --------------------------------------------------------------------------- #
#  Core Analysis Functions
# --------------------------------------------------------------------------- #

def _find_co_occurrences(modes: List[str]) -> List[Tuple[str, str, str]]:
    """Find known co-occurrence pairs among detected failure modes.

    Returns list of (mode_a, mode_b, note) tuples.
    """
    matches = []
    mode_set = set(modes)

    for i, m1 in enumerate(modes):
        for m2 in modes[i + 1:]:
            pair = tuple(sorted([m1, m2]))
            if pair in _CO_OCCURRENCE_PAIRS:
                src = pair[0] if pair[0] in CO_OCCURRENCE_MAP else pair[1]
                note = (
                    f"{FAILURE_MODE_LABELS.get(m1, m1)} + "
                    f"{FAILURE_MODE_LABELS.get(m2, m2)}: "
                    f"known co-occurrence pattern from MAST research"
                )
                matches.append((m1, m2, note))

    return matches


def _build_causal_chains(modes: List[str]) -> List[CausalChain]:
    """Build causal chains by ordering failure modes by depth.

    Groups connected modes (via co-occurrence) and orders them
    from root cause (lowest depth) to symptom (highest depth).
    """
    if len(modes) < 2:
        return []

    # Build adjacency from co-occurrence
    adj: Dict[str, Set[str]] = {m: set() for m in modes}
    mode_set = set(modes)
    for m1 in modes:
        for m2 in modes:
            if m1 != m2:
                pair = tuple(sorted([m1, m2]))
                if pair in _CO_OCCURRENCE_PAIRS:
                    adj[m1].add(m2)
                    adj[m2].add(m1)

    # Find connected components via BFS
    visited: Set[str] = set()
    components: List[List[str]] = []

    for mode in modes:
        if mode in visited:
            continue
        component = []
        queue = [mode]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in adj[current]:
                if neighbor not in visited:
                    queue.append(neighbor)
        if len(component) >= 2:
            components.append(component)

    # For each component, sort by causal depth and build chain
    chains = []
    for component in components:
        ordered = sorted(component, key=lambda m: CAUSAL_DEPTH.get(m, DEFAULT_DEPTH))
        root = ordered[0]
        symptom = ordered[-1]

        root_label = FAILURE_MODE_LABELS.get(root, root)
        symptom_label = FAILURE_MODE_LABELS.get(symptom, symptom)

        if len(ordered) == 2:
            explanation = f"{root_label} likely caused {symptom_label}"
        else:
            mid_labels = [FAILURE_MODE_LABELS.get(m, m) for m in ordered[1:-1]]
            explanation = (
                f"{root_label} cascaded through "
                f"{', '.join(mid_labels)} to produce {symptom_label}"
            )

        chains.append(CausalChain(chain=ordered, explanation=explanation))

    return chains


def _cluster_failures(
    detections: List[Dict[str, Any]],
    modes: List[str],
    co_occurrences: List[Tuple[str, str, str]],
    causal_chains: List[CausalChain],
) -> List[FailureCluster]:
    """Group detections into clusters based on causal chains and co-occurrence."""
    clusters: List[FailureCluster] = []
    clustered: Set[str] = set()
    cluster_id = 0

    # First: cluster modes that are part of causal chains
    for chain in causal_chains:
        root = chain.chain[0]
        root_label = FAILURE_MODE_LABELS.get(root, root)
        clusters.append(FailureCluster(
            cluster_id=cluster_id,
            label=f"Cascade from {root_label}",
            root_cause_mode=root,
            member_modes=chain.chain,
            relationship="causal_chain",
            confidence_boost=0.10,  # Known chain boosts confidence
        ))
        clustered.update(chain.chain)
        cluster_id += 1

    # Second: cluster remaining co-occurring pairs not already in a chain
    for m1, m2, note in co_occurrences:
        if m1 in clustered and m2 in clustered:
            continue
        remaining = [m for m in [m1, m2] if m not in clustered]
        if not remaining:
            continue
        # Find the root of the pair
        root = min([m1, m2], key=lambda m: CAUSAL_DEPTH.get(m, DEFAULT_DEPTH))
        root_label = FAILURE_MODE_LABELS.get(root, root)
        members = [m for m in [m1, m2]]
        clusters.append(FailureCluster(
            cluster_id=cluster_id,
            label=f"Co-occurring: {root_label}",
            root_cause_mode=root,
            member_modes=members,
            relationship="co_occurrence",
            confidence_boost=0.05,
        ))
        clustered.update(members)
        cluster_id += 1

    # Third: any remaining unclustered failures are standalone
    for mode in modes:
        if mode not in clustered:
            label = FAILURE_MODE_LABELS.get(mode, mode)
            clusters.append(FailureCluster(
                cluster_id=cluster_id,
                label=label,
                root_cause_mode=mode,
                member_modes=[mode],
                relationship="standalone",
                confidence_boost=0.0,
            ))
            cluster_id += 1

    return clusters


def _pick_root_cause(
    detections: List[Dict[str, Any]],
    causal_chains: List[CausalChain],
) -> Tuple[Optional[str], Optional[str]]:
    """Pick the deepest root cause, preferring causal chain roots over severity.

    Returns (failure_mode, explanation).
    """
    if not detections:
        return None, None

    # If we have causal chains, the root of the longest chain is the root cause
    if causal_chains:
        longest = max(causal_chains, key=lambda c: len(c.chain))
        root_mode = longest.chain[0]
        root_label = FAILURE_MODE_LABELS.get(root_mode, root_mode)
        # Find the detection for this mode
        root_det = next((d for d in detections if d["category"] == root_mode), None)
        if root_det:
            return root_mode, (
                f"Root cause: {root_label}. {root_det['description']} "
                f"This triggered a failure cascade: {longest.explanation}."
            )

    # Fall back to deepest causal depth among detections
    modes_present = [d["category"] for d in detections]
    deepest_root = min(
        modes_present,
        key=lambda m: (CAUSAL_DEPTH.get(m, DEFAULT_DEPTH), -_det_score(detections, m)),
    )
    root_label = FAILURE_MODE_LABELS.get(deepest_root, deepest_root)
    root_det = next((d for d in detections if d["category"] == deepest_root), None)

    if root_det:
        desc = root_det["description"]
        n_others = len(detections) - 1
        if n_others > 0:
            return deepest_root, (
                f"Root cause: {root_label}. {desc} "
                f"This contributed to {n_others} additional failure(s)."
            )
        return deepest_root, f"Root cause: {root_label}. {desc}"

    return None, None


def _det_score(detections: List[Dict[str, Any]], mode: str) -> float:
    """Get combined severity+confidence score for a mode."""
    severity_order = {"severe": 4, "moderate": 3, "minor": 2, "none": 1}
    for d in detections:
        if d["category"] == mode:
            return severity_order.get(d["severity"], 0) + d["confidence"]
    return 0.0


# --------------------------------------------------------------------------- #
#  Public API
# --------------------------------------------------------------------------- #

def analyze_compound(detections: List[Dict[str, Any]]) -> Optional[CompoundAnalysis]:
    """Analyze compound failure patterns across multiple detections.

    Only runs when 2+ detections are present. Returns None for single failures.

    Args:
        detections: Flat list of detection dicts with "category", "confidence",
                   "severity", "title", "description", "affected_spans" keys.

    Returns:
        CompoundAnalysis with clusters, causal chains, and root cause, or None.
    """
    if len(detections) < 2:
        return None

    # Extract failure modes
    modes = [d["category"] for d in detections]

    # 1. Find known co-occurrence patterns
    co_occurrences = _find_co_occurrences(modes)
    notes = [note for _, _, note in co_occurrences]

    # 2. Build causal chains
    causal_chains = _build_causal_chains(modes)

    # 3. Cluster related failures
    clusters = _cluster_failures(detections, modes, co_occurrences, causal_chains)

    # 4. Pick true root cause (causal depth > severity)
    root_mode, root_explanation = _pick_root_cause(detections, causal_chains)

    return CompoundAnalysis(
        clusters=clusters,
        causal_chains=causal_chains,
        co_occurrence_notes=notes,
        root_cause_mode=root_mode,
        root_cause_explanation=root_explanation,
    )
