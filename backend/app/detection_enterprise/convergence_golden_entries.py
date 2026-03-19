"""Golden dataset entries for convergence detection.

100 entries: 50 positive (plateau, regression, thrashing, divergence),
50 negative (healthy variations). Balanced across easy/medium/hard difficulty.
"""

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDatasetEntry


def _metrics(values, direction="minimize", name="val_bpb"):
    """Helper to build metrics input_data."""
    return {
        "metrics": [{"step": i, "value": v} for i, v in enumerate(values)],
        "direction": direction,
        "metric_name": name,
    }


def create_convergence_golden_entries():
    """Create 100 convergence golden dataset entries."""
    entries = []

    # ===================================================================
    # POSITIVE: PLATEAU (12 entries)
    # ===================================================================

    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_01",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.65] * 10),
        expected_detected=True,
        description="Perfectly flat loss for 10 steps",
        tags=["plateau", "clear_positive"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_02",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.48, 0.47, 0.47, 0.47, 0.47, 0.47, 0.47]),
        expected_detected=True,
        description="Loss plateaus after initial improvement",
        tags=["plateau", "clear_positive"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_03",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.0, 0.8, 0.7, 0.65, 0.64, 0.64, 0.64, 0.64, 0.64, 0.64]),
        expected_detected=True,
        description="Fast initial progress then complete stall",
        tags=["plateau", "clear_positive"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_04",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.9, 0.85, 0.82, 0.81, 0.808, 0.806, 0.805, 0.805]),
        expected_detected=True,
        description="Very slight improvements below threshold",
        tags=["plateau", "subtle"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_05",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.6, 0.65, 0.66, 0.665, 0.667, 0.668, 0.668], direction="maximize", name="accuracy"),
        expected_detected=True,
        description="Accuracy plateaus near 0.668 (maximize)",
        tags=["plateau", "maximize"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_06",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([2.1, 1.5, 1.2, 1.15, 1.14, 1.145, 1.14, 1.142, 1.141, 1.141]),
        expected_detected=True,
        description="Loss converges to 1.14 with negligible movement",
        tags=["plateau", "subtle"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_07",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.7, 0.69, 0.691, 0.689, 0.6905, 0.6898, 0.6901, 0.6899]),
        expected_detected=True,
        description="Noisy plateau with sub-threshold oscillation",
        tags=["plateau", "noisy"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_08",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.4, 0.38, 0.375, 0.374, 0.3739, 0.3738, 0.3738, 0.3738, 0.3738, 0.3738]),
        expected_detected=True,
        description="Near-perfect convergence — improvement is essentially zero",
        tags=["plateau", "subtle"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_09",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([3.0, 2.0, 1.5, 1.3, 1.2, 1.19, 1.19, 1.19, 1.19]),
        expected_detected=True,
        description="Rapid early improvement then complete plateau",
        tags=["plateau"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_10",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.82, 0.83, 0.835, 0.836, 0.836, 0.836, 0.836], direction="maximize", name="f1_score"),
        expected_detected=True,
        description="F1 score saturates at 0.836",
        tags=["plateau", "maximize"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_11",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.55, 0.55, 0.55, 0.55, 0.55, 0.55]),
        expected_detected=True,
        description="No improvement from the start",
        tags=["plateau", "clear_positive"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_plateau_12",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.8, 0.75, 0.72, 0.715, 0.714, 0.7139, 0.7138, 0.7138]),
        expected_detected=True,
        description="Plateau with sub-0.001 improvements",
        tags=["plateau", "subtle"],
        difficulty="hard",
    ))

    # ===================================================================
    # POSITIVE: REGRESSION (13 entries)
    # ===================================================================

    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_01",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.0, 0.7, 0.5, 0.6, 0.7, 0.8]),
        expected_detected=True,
        description="Clear regression from best (0.5) back to 0.8",
        tags=["regression", "clear_positive"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_02",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.9, 0.85, 0.8, 0.95]),
        expected_detected=True,
        description="Single large regression past starting value",
        tags=["regression", "clear_positive"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_03",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.7, 0.9, 0.85, 0.7, 0.6], direction="maximize"),
        expected_detected=True,
        description="Accuracy regresses from 0.9 peak (maximize)",
        tags=["regression", "maximize"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_04",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.0, 0.8, 0.6, 0.5, 0.52, 0.55, 0.58]),
        expected_detected=True,
        description="Gradual regression after reaching best",
        tags=["regression"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_05",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([2.0, 1.5, 1.2, 1.0, 1.1, 1.05, 1.15, 1.2]),
        expected_detected=True,
        description="Noisy regression with brief recovery attempts",
        tags=["regression", "noisy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_06",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.6, 0.55, 0.5, 0.48, 0.55, 0.52, 0.54]),
        expected_detected=True,
        description="Regression from 0.48 best to 0.54 current",
        tags=["regression"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_07",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.3, 0.28, 0.25, 0.27, 0.26, 0.28, 0.30]),
        expected_detected=True,
        description="Regression from 0.25 back to starting point",
        tags=["regression"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_08",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.7, 0.65, 0.6, 0.58, 0.62, 0.60, 0.61, 0.63]),
        expected_detected=True,
        description="Subtle regression — current 0.63 vs best 0.58",
        tags=["regression", "subtle"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_09",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.8, 0.85, 0.9, 0.92, 0.88, 0.85, 0.82], direction="maximize"),
        expected_detected=True,
        description="Maximize regression from 0.92 to 0.82",
        tags=["regression", "maximize"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_10",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.5, 1.2, 1.0, 0.9, 0.85, 0.9, 0.88, 0.92, 0.95]),
        expected_detected=True,
        description="Initial improvement then gradual regression",
        tags=["regression"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_11",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.4, 0.38, 0.35, 0.34, 0.36, 0.355, 0.37, 0.38]),
        expected_detected=True,
        description="Regression of ~10% from best",
        tags=["regression"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_12",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.45, 0.4, 0.35, 0.5, 0.48]),
        expected_detected=True,
        description="Sharp regression then partial recovery",
        tags=["regression"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_regr_13",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.6, 0.55, 0.5, 0.48, 0.5, 0.52, 0.53, 0.55, 0.58]),
        expected_detected=True,
        description="Sustained regression over many steps",
        tags=["regression"],
        difficulty="hard",
    ))

    # ===================================================================
    # POSITIVE: THRASHING (12 entries)
    # ===================================================================

    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_01",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.64, 0.68, 0.64, 0.68, 0.64, 0.68, 0.64, 0.68]),
        expected_detected=True,
        description="Perfect alternation between two values",
        tags=["thrashing", "clear_positive"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_02",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.55, 0.48, 0.56, 0.49, 0.54, 0.50, 0.55]),
        expected_detected=True,
        description="Oscillating around 0.52 with no trend",
        tags=["thrashing", "clear_positive"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_03",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.7, 0.8, 0.65, 0.85, 0.6, 0.9, 0.55], direction="maximize"),
        expected_detected=True,
        description="Wide oscillation in accuracy (maximize)",
        tags=["thrashing", "maximize"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_04",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.0, 0.95, 1.02, 0.93, 1.05, 0.91, 1.08, 0.90]),
        expected_detected=True,
        description="Loss oscillating around 1.0",
        tags=["thrashing"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_05",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.3, 0.32, 0.29, 0.33, 0.28, 0.34, 0.27, 0.35]),
        expected_detected=True,
        description="Increasing amplitude oscillation",
        tags=["thrashing"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_06",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.52, 0.49, 0.53, 0.48, 0.51, 0.50, 0.52]),
        expected_detected=True,
        description="Small-amplitude thrashing around 0.505",
        tags=["thrashing", "subtle"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_07",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.6, 0.65, 0.58, 0.66, 0.57, 0.67, 0.56, 0.68]),
        expected_detected=True,
        description="Diverging oscillation — amplitude increasing",
        tags=["thrashing"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_08",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.4, 0.42, 0.39, 0.41, 0.395, 0.41, 0.40, 0.415]),
        expected_detected=True,
        description="Tight thrashing with very small amplitude",
        tags=["thrashing", "subtle"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_09",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.75, 0.72, 0.78, 0.71, 0.79, 0.70, 0.80, 0.69]),
        expected_detected=True,
        description="Thrashing with diverging envelope",
        tags=["thrashing"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_10",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.85, 0.88, 0.83, 0.89, 0.82, 0.90, 0.81], direction="maximize"),
        expected_detected=True,
        description="Accuracy thrashing (maximize)",
        tags=["thrashing", "maximize"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_11",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.55, 0.58, 0.53, 0.59, 0.52, 0.60, 0.51]),
        expected_detected=True,
        description="7 steps all reversing direction",
        tags=["thrashing", "clear_positive"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_thrash_12",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.45, 0.46, 0.44, 0.47, 0.43, 0.46, 0.445, 0.46]),
        expected_detected=True,
        description="Subtle thrashing with slight upward bias",
        tags=["thrashing", "subtle"],
        difficulty="hard",
    ))

    # ===================================================================
    # POSITIVE: DIVERGENCE (13 entries)
    # ===================================================================

    entries.append(GoldenDatasetEntry(
        id="conv_p_div_01",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85]),
        expected_detected=True,
        description="Loss monotonically increasing — pure divergence",
        tags=["divergence", "clear_positive"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_02",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.3, 0.35, 0.4, 0.5, 0.6, 0.8]),
        expected_detected=True,
        description="Accelerating divergence",
        tags=["divergence", "clear_positive"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_03",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6], direction="maximize"),
        expected_detected=True,
        description="Accuracy steadily declining (maximize)",
        tags=["divergence", "maximize"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_04",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.0, 1.1, 1.05, 1.15, 1.2, 1.3, 1.25, 1.4]),
        expected_detected=True,
        description="Noisy divergence with overall upward trend",
        tags=["divergence", "noisy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_05",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.2, 0.22, 0.25, 0.28, 0.32, 0.37]),
        expected_detected=True,
        description="Gradual divergence with increasing step size",
        tags=["divergence"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_06",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.45, 0.55, 0.6, 0.65, 0.7, 0.75]),
        expected_detected=True,
        description="Brief improvement then sustained divergence",
        tags=["divergence"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_07",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.6, 0.62, 0.61, 0.64, 0.63, 0.66, 0.65, 0.68]),
        expected_detected=True,
        description="Slow noisy divergence",
        tags=["divergence", "subtle"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_08",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.4, 0.42, 0.44, 0.47, 0.50, 0.54]),
        expected_detected=True,
        description="Steady divergence at ~0.03/step",
        tags=["divergence"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_09",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.7, 0.68, 0.65, 0.61, 0.56, 0.50], direction="maximize"),
        expected_detected=True,
        description="F1 diverging downward (maximize)",
        tags=["divergence", "maximize"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_10",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.48, 0.52, 0.54, 0.56, 0.59, 0.62]),
        expected_detected=True,
        description="Divergence after brief dip",
        tags=["divergence"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_11",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.2, 1.25, 1.22, 1.28, 1.3, 1.35, 1.32, 1.40]),
        expected_detected=True,
        description="Noisy divergence in high-loss regime",
        tags=["divergence", "noisy"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_12",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.35, 0.36, 0.38, 0.37, 0.40, 0.39, 0.42, 0.44]),
        expected_detected=True,
        description="Very gradual divergence with noise",
        tags=["divergence", "subtle"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_p_div_13",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.8, 0.82, 0.85, 0.88, 0.92, 0.97, 1.05]),
        expected_detected=True,
        description="Divergence accelerating toward instability",
        tags=["divergence"],
        difficulty="medium",
    ))

    # ===================================================================
    # NEGATIVE: HEALTHY (50 entries)
    # ===================================================================

    # --- Easy negatives: clear improvement ---

    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_01",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.0, 0.8, 0.6, 0.4, 0.3, 0.2]),
        expected_detected=False,
        description="Strong monotonic improvement",
        tags=["healthy", "clear_negative"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_02",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.6, 0.7, 0.8, 0.85, 0.9], direction="maximize"),
        expected_detected=False,
        description="Steady accuracy improvement (maximize)",
        tags=["healthy", "maximize"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_03",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([2.0, 1.5, 1.2, 1.0, 0.9, 0.85, 0.82]),
        expected_detected=False,
        description="Rapid then gradual improvement",
        tags=["healthy"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_04",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.8, 0.7, 0.6, 0.5, 0.4]),
        expected_detected=False,
        description="Consistent 0.1 improvement per step",
        tags=["healthy", "clear_negative"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_05",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([3.0, 2.0, 1.5, 1.0, 0.8, 0.65, 0.55, 0.5]),
        expected_detected=False,
        description="Diminishing but still meaningful returns",
        tags=["healthy"],
        difficulty="easy",
    ))

    # --- Easy negatives: slow but steady ---

    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_06",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.49, 0.48, 0.47, 0.46, 0.45]),
        expected_detected=False,
        description="Slow but consistent improvement",
        tags=["healthy", "slow"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_07",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.7, 0.68, 0.66, 0.64, 0.62, 0.60, 0.58]),
        expected_detected=False,
        description="Steady 0.02/step improvement",
        tags=["healthy", "slow"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_08",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.6, 0.62, 0.64, 0.66, 0.68, 0.70], direction="maximize"),
        expected_detected=False,
        description="Slow accuracy growth (maximize)",
        tags=["healthy", "maximize"],
        difficulty="easy",
    ))

    # --- Medium negatives: noisy improvement ---

    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_09",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.0, 0.95, 0.98, 0.9, 0.88, 0.85, 0.82]),
        expected_detected=False,
        description="Noisy but clearly improving",
        tags=["healthy", "noisy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_10",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.8, 0.75, 0.78, 0.72, 0.70, 0.68, 0.65]),
        expected_detected=False,
        description="Two-steps-forward-one-step-back improvement",
        tags=["healthy", "noisy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_11",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.6, 0.55, 0.58, 0.52, 0.50, 0.48, 0.45]),
        expected_detected=False,
        description="Noisy descent with clear trend",
        tags=["healthy", "noisy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_12",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.52, 0.48, 0.55, 0.58, 0.62, 0.65], direction="maximize"),
        expected_detected=False,
        description="Noisy accuracy growth with dips (maximize)",
        tags=["healthy", "noisy", "maximize"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_13",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.5, 1.45, 1.48, 1.40, 1.38, 1.42, 1.35, 1.30]),
        expected_detected=False,
        description="Noisy but net improvement of 0.2",
        tags=["healthy", "noisy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_14",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.9, 0.92, 0.88, 0.85, 0.87, 0.82, 0.80]),
        expected_detected=False,
        description="Recovery after brief worsening",
        tags=["healthy", "recovery"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_15",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.7, 0.68, 0.72, 0.65, 0.63, 0.60]),
        expected_detected=False,
        description="One outlier step but overall improving",
        tags=["healthy", "outlier"],
        difficulty="medium",
    ))

    # --- Medium negatives: brief plateau then breakthrough ---

    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_16",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.0, 0.8, 0.7, 0.7, 0.7, 0.5, 0.3]),
        expected_detected=False,
        description="Brief 3-step plateau then breakthrough",
        tags=["healthy", "breakthrough"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_17",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.6, 0.55, 0.55, 0.55, 0.4, 0.35]),
        expected_detected=False,
        description="Short plateau followed by improvement",
        tags=["healthy", "breakthrough"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_18",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.48, 0.48, 0.49, 0.48, 0.40, 0.35, 0.30]),
        expected_detected=False,
        description="Plateau at 0.48 then dramatic improvement",
        tags=["healthy", "breakthrough"],
        difficulty="medium",
    ))

    # --- Hard negatives: look like issues but aren't ---

    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_19",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.48, 0.50, 0.46, 0.44, 0.45, 0.42, 0.40]),
        expected_detected=False,
        description="Noisy with occasional worsening but net improvement",
        tags=["healthy", "noisy"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_20",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.7, 0.65, 0.68, 0.62, 0.60, 0.63, 0.58, 0.55]),
        expected_detected=False,
        description="Looks oscillatory but has clear downward trend",
        tags=["healthy", "looks_like_thrashing"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_21",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.8, 0.78, 0.78, 0.77, 0.76, 0.75, 0.73]),
        expected_detected=False,
        description="Very slow but above-threshold improvement",
        tags=["healthy", "looks_like_plateau"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_22",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.6, 0.58, 0.59, 0.57, 0.58, 0.56, 0.55, 0.53]),
        expected_detected=False,
        description="Tiny oscillations around a downward trend",
        tags=["healthy", "looks_like_thrashing"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_23",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.45, 0.48, 0.42, 0.40, 0.38]),
        expected_detected=False,
        description="One reversal but strong overall improvement",
        tags=["healthy", "reversal"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_24",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.4, 0.42, 0.39, 0.38, 0.36, 0.35]),
        expected_detected=False,
        description="One step up then steady improvement",
        tags=["healthy"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_25",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.3, 0.28, 0.29, 0.27, 0.26, 0.24, 0.23]),
        expected_detected=False,
        description="Minor noise but clear downward trend",
        tags=["healthy", "noisy"],
        difficulty="hard",
    ))

    # --- More easy/medium negatives for balance ---

    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_26",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([5.0, 4.0, 3.0, 2.5, 2.0, 1.8, 1.6]),
        expected_detected=False,
        description="Large-scale steady improvement",
        tags=["healthy"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_27",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], direction="maximize"),
        expected_detected=False,
        description="Linear accuracy growth (maximize)",
        tags=["healthy", "maximize"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_28",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.9, 0.85, 0.80, 0.76, 0.73, 0.71]),
        expected_detected=False,
        description="Gradual convergence with meaningful steps",
        tags=["healthy"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_29",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.2, 1.0, 0.9, 0.85, 0.82, 0.80]),
        expected_detected=False,
        description="Decelerating improvement still above threshold",
        tags=["healthy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_30",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.7, 0.75, 0.78, 0.82, 0.85, 0.88, 0.90], direction="maximize"),
        expected_detected=False,
        description="Steady accuracy gains (maximize)",
        tags=["healthy", "maximize"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_31",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.65, 0.60, 0.58, 0.55, 0.52, 0.50]),
        expected_detected=False,
        description="Consistent ~0.03/step improvement",
        tags=["healthy"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_32",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.4, 0.38, 0.35, 0.33, 0.30, 0.28, 0.25]),
        expected_detected=False,
        description="Well-behaved convergence",
        tags=["healthy"],
        difficulty="easy",
    ))

    # --- Hard negatives: exploration phases ---

    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_33",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.55, 0.48, 0.45, 0.42, 0.40]),
        expected_detected=False,
        description="Initial exploration spike then convergence",
        tags=["healthy", "exploration"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_34",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.8, 0.85, 0.78, 0.75, 0.70, 0.65, 0.60]),
        expected_detected=False,
        description="Worse first step then strong improvement",
        tags=["healthy", "exploration"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_35",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.6, 0.58, 0.62, 0.55, 0.52, 0.48, 0.45]),
        expected_detected=False,
        description="One outlier amid strong improvement",
        tags=["healthy", "outlier"],
        difficulty="hard",
    ))

    # --- More medium negatives ---

    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_36",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.55, 0.53, 0.54, 0.51, 0.49, 0.47, 0.45]),
        expected_detected=False,
        description="Slightly noisy but improving",
        tags=["healthy", "noisy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_37",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.0, 0.9, 0.92, 0.85, 0.80, 0.78]),
        expected_detected=False,
        description="One reversal early on then steady descent",
        tags=["healthy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_38",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.7, 0.65, 0.60, 0.55, 0.52, 0.50, 0.48]),
        expected_detected=False,
        description="Textbook convergence with decreasing deltas",
        tags=["healthy"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_39",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.45, 0.43, 0.44, 0.41, 0.40, 0.38]),
        expected_detected=False,
        description="Minor fluctuation in healthy descent",
        tags=["healthy", "noisy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_40",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6], direction="maximize"),
        expected_detected=False,
        description="Linear accuracy improvement (maximize)",
        tags=["healthy", "maximize"],
        difficulty="easy",
    ))

    # --- Remaining negatives ---

    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_41",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.9, 0.88, 0.85, 0.82, 0.80, 0.78]),
        expected_detected=False,
        description="Above-threshold improvement each step",
        tags=["healthy"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_42",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.6, 0.57, 0.55, 0.52, 0.50, 0.47]),
        expected_detected=False,
        description="Consistent loss reduction",
        tags=["healthy"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_43",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.75, 0.72, 0.73, 0.70, 0.68, 0.65, 0.62]),
        expected_detected=False,
        description="One bump but clear improvement",
        tags=["healthy", "noisy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_44",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.5, 0.55, 0.6, 0.65, 0.7, 0.72], direction="maximize"),
        expected_detected=False,
        description="Steady accuracy growth (maximize)",
        tags=["healthy", "maximize"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_45",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.8, 0.75, 0.78, 0.70, 0.65, 0.60]),
        expected_detected=False,
        description="One bump but large net improvement",
        tags=["healthy", "noisy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_46",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.4, 0.38, 0.36, 0.34, 0.32, 0.30]),
        expected_detected=False,
        description="Perfect monotonic improvement at 0.02/step",
        tags=["healthy", "clear_negative"],
        difficulty="easy",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_47",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([1.5, 1.3, 1.35, 1.2, 1.1, 1.0, 0.9]),
        expected_detected=False,
        description="Noisy descent with strong trend",
        tags=["healthy", "noisy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_48",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.65, 0.63, 0.64, 0.61, 0.59, 0.57, 0.55]),
        expected_detected=False,
        description="Tiny oscillation around downward trend",
        tags=["healthy", "looks_like_thrashing"],
        difficulty="hard",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_49",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.55, 0.50, 0.52, 0.48, 0.45, 0.42]),
        expected_detected=False,
        description="One reversal then steady improvement",
        tags=["healthy"],
        difficulty="medium",
    ))
    entries.append(GoldenDatasetEntry(
        id="conv_n_healthy_50",
        detection_type=DetectionType.CONVERGENCE,
        input_data=_metrics([0.35, 0.33, 0.30, 0.28, 0.25, 0.22, 0.20]),
        expected_detected=False,
        description="Strong consistent improvement",
        tags=["healthy", "clear_negative"],
        difficulty="easy",
    ))

    return entries
