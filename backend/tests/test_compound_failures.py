"""Tests for compound failure analysis module.

Validates co-occurrence detection, causal chain building, clustering,
root cause selection, and confidence adjustment for multi-failure traces.
"""

import os
import sys
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.detection.compound_failures import (
    analyze_compound,
    _find_co_occurrences,
    _build_causal_chains,
    _cluster_failures,
    _pick_root_cause,
    CO_OCCURRENCE_MAP,
    CAUSAL_DEPTH,
    FAILURE_MODE_LABELS,
    CompoundAnalysis,
)


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

def _make_detection(category: str, confidence: float = 0.7, severity: str = "moderate",
                    title: str = "", description: str = "test", affected_spans=None):
    """Create a detection dict matching the diagnose endpoint format."""
    return {
        "category": category,
        "detected": True,
        "confidence": confidence,
        "severity": severity,
        "title": title or FAILURE_MODE_LABELS.get(category, category),
        "description": description,
        "evidence": [],
        "affected_spans": affected_spans or [],
        "suggested_fix": None,
    }


# --------------------------------------------------------------------------- #
#  Single Failure — no compound analysis
# --------------------------------------------------------------------------- #

class TestSingleFailure:
    def test_single_detection_returns_none(self):
        """Compound analysis should not trigger for a single failure."""
        detections = [_make_detection("F1")]
        result = analyze_compound(detections)
        assert result is None

    def test_empty_detections_returns_none(self):
        detections = []
        result = analyze_compound(detections)
        assert result is None


# --------------------------------------------------------------------------- #
#  Co-Occurrence Detection
# --------------------------------------------------------------------------- #

class TestCoOccurrence:
    def test_known_f9_co_occurrence(self):
        """F9 + F11 is a known co-occurrence pair from MAST research."""
        matches = _find_co_occurrences(["F9", "F11"])
        assert len(matches) == 1
        assert "co-occurrence" in matches[0][2].lower() or "pattern" in matches[0][2].lower()

    def test_f5_f7_co_occurrence(self):
        """F5 (Flawed Workflow) → F7 (Context Neglect) is a known cascade."""
        matches = _find_co_occurrences(["F5", "F7"])
        assert len(matches) == 1

    def test_no_co_occurrence_for_unrelated(self):
        """F4 and F16 are not known co-occurrence partners."""
        matches = _find_co_occurrences(["F4", "F16"])
        assert len(matches) == 0

    def test_multiple_co_occurrences(self):
        """Multiple known pairs should all be detected."""
        matches = _find_co_occurrences(["F9", "F1", "F11"])
        # F9+F1 and F9+F11 are both known pairs
        assert len(matches) >= 2

    def test_co_occurrence_map_is_symmetric(self):
        """Both directions should work — order shouldn't matter."""
        m1 = _find_co_occurrences(["F5", "F6"])
        m2 = _find_co_occurrences(["F6", "F5"])
        assert len(m1) == len(m2)


# --------------------------------------------------------------------------- #
#  Causal Chain Building
# --------------------------------------------------------------------------- #

class TestCausalChains:
    def test_two_mode_chain(self):
        """F5 → F7 should produce a chain with F5 as root (depth 1 < depth 3)."""
        chains = _build_causal_chains(["F5", "F7"])
        assert len(chains) == 1
        assert chains[0].chain[0] == "F5"  # Root cause
        assert chains[0].chain[-1] == "F7"  # Symptom

    def test_three_mode_cascade(self):
        """F5 → F6 → F14 should order by causal depth."""
        chains = _build_causal_chains(["F5", "F6", "F14"])
        assert len(chains) == 1
        chain = chains[0].chain
        assert chain[0] == "F5"   # depth 1
        assert chain[1] == "F6"   # depth 3
        assert chain[2] == "F14"  # depth 4

    def test_no_chain_for_unrelated_modes(self):
        """F4 and F16 have no co-occurrence link, so no causal chain."""
        chains = _build_causal_chains(["F4", "F16"])
        assert len(chains) == 0

    def test_single_mode_no_chain(self):
        chains = _build_causal_chains(["F1"])
        assert len(chains) == 0

    def test_chain_explanation_contains_labels(self):
        """Chain explanation should reference human-readable names."""
        chains = _build_causal_chains(["F5", "F7"])
        assert "Flawed Workflow" in chains[0].explanation
        assert "Context Neglect" in chains[0].explanation

    def test_disconnected_components(self):
        """Two separate pairs should produce two separate chains."""
        # F5→F6 and F10→F11 are independent pairs
        chains = _build_causal_chains(["F5", "F6", "F10", "F11"])
        assert len(chains) == 2


# --------------------------------------------------------------------------- #
#  Clustering
# --------------------------------------------------------------------------- #

class TestClustering:
    def test_causal_chain_cluster(self):
        detections = [_make_detection("F5"), _make_detection("F7")]
        modes = ["F5", "F7"]
        co_occs = _find_co_occurrences(modes)
        chains = _build_causal_chains(modes)
        clusters = _cluster_failures(detections, modes, co_occs, chains)
        # Should have one cluster from the causal chain
        chain_clusters = [c for c in clusters if c.relationship == "causal_chain"]
        assert len(chain_clusters) == 1
        assert chain_clusters[0].root_cause_mode == "F5"

    def test_standalone_mode_gets_own_cluster(self):
        """A mode with no co-occurrence partners gets a standalone cluster."""
        detections = [_make_detection("F5"), _make_detection("F16")]
        modes = ["F5", "F16"]
        co_occs = _find_co_occurrences(modes)
        chains = _build_causal_chains(modes)
        clusters = _cluster_failures(detections, modes, co_occs, chains)
        standalone = [c for c in clusters if c.relationship == "standalone"]
        assert len(standalone) >= 1

    def test_confidence_boost_for_causal_chain(self):
        detections = [_make_detection("F5"), _make_detection("F6")]
        modes = ["F5", "F6"]
        co_occs = _find_co_occurrences(modes)
        chains = _build_causal_chains(modes)
        clusters = _cluster_failures(detections, modes, co_occs, chains)
        chain_clusters = [c for c in clusters if c.relationship == "causal_chain"]
        assert chain_clusters[0].confidence_boost > 0


# --------------------------------------------------------------------------- #
#  Root Cause Selection
# --------------------------------------------------------------------------- #

class TestRootCauseSelection:
    def test_picks_causal_root_over_severity(self):
        """Should prefer causal chain root even if a symptom has higher severity."""
        detections = [
            _make_detection("F5", confidence=0.6, severity="moderate"),  # root cause, depth 1
            _make_detection("F14", confidence=0.9, severity="severe"),   # symptom, depth 4
        ]
        chains = _build_causal_chains(["F5", "F14"])
        root_mode, explanation = _pick_root_cause(detections, chains)
        assert root_mode == "F5"
        assert "Root cause" in explanation
        assert "Flawed Workflow" in explanation

    def test_falls_back_to_depth_without_chain(self):
        """Without causal chains, should still pick by causal depth."""
        detections = [
            _make_detection("F1", confidence=0.5, severity="minor"),    # depth 1
            _make_detection("F14", confidence=0.9, severity="severe"),  # depth 4
        ]
        root_mode, explanation = _pick_root_cause(detections, [])
        assert root_mode == "F1"

    def test_explanation_mentions_cascade(self):
        detections = [_make_detection("F5"), _make_detection("F7")]
        chains = _build_causal_chains(["F5", "F7"])
        _, explanation = _pick_root_cause(detections, chains)
        assert "cascade" in explanation.lower() or "caused" in explanation.lower() or "triggered" in explanation.lower()


# --------------------------------------------------------------------------- #
#  Full analyze_compound Integration
# --------------------------------------------------------------------------- #

class TestAnalyzeCompound:
    def test_two_known_co_occurring_failures(self):
        """F9 + F11 should produce compound analysis with known pattern note."""
        detections = [_make_detection("F9"), _make_detection("F11")]
        result = analyze_compound(detections)
        assert result is not None
        assert len(result.co_occurrence_notes) > 0
        assert result.root_cause_mode is not None

    def test_cascade_f5_f6_f14(self):
        """F5 → F6 → F14 should produce a causal chain."""
        detections = [
            _make_detection("F5", severity="moderate"),
            _make_detection("F6", severity="moderate"),
            _make_detection("F14", severity="severe"),
        ]
        result = analyze_compound(detections)
        assert result is not None
        assert len(result.causal_chains) >= 1
        # Root should be F5, not F14 despite higher severity
        assert result.root_cause_mode == "F5"

    def test_mixed_related_and_unrelated(self):
        """Mix of related and unrelated failures: 5 detections → 2+ clusters."""
        detections = [
            _make_detection("F5"),   # related to F6
            _make_detection("F6"),
            _make_detection("F16"),  # standalone
            _make_detection("F10"),  # related to F11
            _make_detection("F11"),
        ]
        result = analyze_compound(detections)
        assert result is not None
        assert len(result.clusters) >= 3  # F5+F6 chain, F10+F11 chain, F16 standalone

    def test_to_dict_serializable(self):
        """CompoundAnalysis.to_dict() should produce JSON-serializable output."""
        import json
        detections = [_make_detection("F5"), _make_detection("F7")]
        result = analyze_compound(detections)
        assert result is not None
        d = result.to_dict()
        # Should not raise
        json.dumps(d)
        assert "clusters" in d
        assert "causal_chains" in d
        assert "co_occurrence_notes" in d

    def test_error_plus_f_mode(self):
        """An 'error' detection + failure mode should still cluster (error is standalone)."""
        detections = [
            _make_detection("error", severity="severe"),
            _make_detection("F7"),
        ]
        result = analyze_compound(detections)
        assert result is not None
        # Both should appear in clusters
        all_modes = []
        for c in result.clusters:
            all_modes.extend(c.member_modes)
        assert "error" in all_modes
        assert "F7" in all_modes

    def test_all_modes_accounted_for(self):
        """Every detection's failure mode should appear in exactly one cluster."""
        detections = [
            _make_detection("F1"),
            _make_detection("F5"),
            _make_detection("F9"),
            _make_detection("F14"),
        ]
        result = analyze_compound(detections)
        assert result is not None
        clustered_modes = []
        for c in result.clusters:
            clustered_modes.extend(c.member_modes)
        for d in detections:
            assert d["category"] in clustered_modes


# --------------------------------------------------------------------------- #
#  Static Data Validation
# --------------------------------------------------------------------------- #

class TestStaticData:
    def test_all_f_modes_have_causal_depth(self):
        """All F1-F17 should have a defined causal depth."""
        for i in range(1, 18):
            mode = f"F{i}"
            assert mode in CAUSAL_DEPTH, f"{mode} missing from CAUSAL_DEPTH"

    def test_all_f_modes_have_labels(self):
        """All F1-F17 should have human-readable labels."""
        for i in range(1, 18):
            mode = f"F{i}"
            assert mode in FAILURE_MODE_LABELS, f"{mode} missing from FAILURE_MODE_LABELS"

    def test_co_occurrence_map_references_valid_modes(self):
        """All modes in CO_OCCURRENCE_MAP should be F1-F17."""
        valid = {f"F{i}" for i in range(1, 18)}
        for src, targets in CO_OCCURRENCE_MAP.items():
            assert src in valid, f"Unknown source mode: {src}"
            for tgt in targets:
                assert tgt in valid, f"Unknown target mode: {tgt}"
