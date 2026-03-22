"""CLI entry point for detection threshold calibration.

Extracted from calibrate.py for testability.

Usage:
    python -m app.detection_enterprise.calibrate_cli [OPTIONS]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from app.detection_enterprise.calibrate import (
    calibrate_all,
    calibrate_multi_trial,
    generate_capability_registry,
    save_calibration_report,
    generate_error_report,
    _compute_readiness,
    _apply_tiered_runners,
    CalibrationContext,
)
from app.detection_enterprise.detector_adapters import DETECTOR_RUNNERS

logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point for calibration."""

    parser = argparse.ArgumentParser(description="Detection threshold calibration")
    parser.add_argument("--compare", type=int, metavar="N", help="Compare last N experiments")
    parser.add_argument("--no-history", action="store_true", help="Skip saving to history")
    parser.add_argument(
        "--generate-data", action="store_true",
        help="Generate LLM golden data for types below 30 samples, then re-calibrate",
    )
    parser.add_argument(
        "--generate-target", type=int, default=50, metavar="N",
        help="Target entries per type for --generate-data (default: 50)",
    )
    parser.add_argument(
        "--difficulty", type=str, choices=["easy", "medium", "hard", "mixed"],
        default="mixed",
        help="Difficulty level for --generate-data (default: mixed = easy/medium/hard passes)",
    )
    parser.add_argument(
        "--phoenix", action="store_true",
        help="Export calibration spans to Phoenix via OTEL",
    )
    parser.add_argument(
        "--phoenix-endpoint", type=str, default="http://localhost:6006/v1/traces",
        help="Phoenix OTLP endpoint (default: http://localhost:6006/v1/traces)",
    )
    parser.add_argument(
        "--apply-thresholds", action="store_true",
        help="Auto-apply calibrated thresholds to threshold config",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print report only — skip threshold application and history save",
    )
    parser.add_argument(
        "--registry", action="store_true",
        help="Generate/update capability_registry.json from calibration results",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print progress log summary and exit",
    )
    parser.add_argument(
        "--tiered", action="store_true",
        help="Use tiered detectors (with LLM escalation) instead of raw heuristic detectors",
    )
    parser.add_argument(
        "--from-db", action="store_true",
        help="Load golden dataset from PostgreSQL instead of in-memory samples",
    )
    parser.add_argument(
        "--error-analysis", action="store_true",
        help="Generate per-sample error analysis report (FPs/FNs per detector)",
    )
    parser.add_argument(
        "--trials", type=int, default=1, metavar="N",
        help="Run N calibration trials to measure F1 variance (requires --tiered)",
    )
    parser.add_argument(
        "--generate-hard", action="store_true",
        help="Generate hard samples for saturated detectors (F1>=0.95 with <5 hard samples)",
    )
    parser.add_argument(
        "--hard-count", type=int, default=10, metavar="N",
        help="Number of hard samples to generate per saturated detector (default: 10)",
    )
    parser.add_argument(
        "--correlations", action="store_true",
        help="Compute and display cross-detector correlation matrix (Phi coefficient)",
    )
    parser.add_argument(
        "--generate-contrastive", action="store_true",
        help="Generate contrastive samples from FP/FN error analysis (requires --error-analysis)",
    )
    parser.add_argument(
        "--alert-webhook", type=str, metavar="URL", default=None,
        help="Slack webhook URL for regression alerts (fires when a detector crosses a gate threshold)",
    )
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    if args.status:
        from app.detection_enterprise.progress_log import ProgressLog
        print(ProgressLog().format_status())
        sys.exit(0)
    
    if args.compare:
        from app.detection_enterprise.calibration_history import CalibrationHistory
        history = CalibrationHistory()
        print(history.format_comparison(args.compare))
        sys.exit(0)
    
    if args.registry and not args.generate_data:
        # Standalone registry generation from existing report (no re-calibration)
        report_path = Path(__file__).parent.parent.parent / "data" / "calibration_report.json"
        if not report_path.exists():
            print("  ERROR: No calibration report found. Run calibration first.")
            sys.exit(1)
        with open(report_path) as f:
            existing_report = json.load(f)
        registry = generate_capability_registry(existing_report)
        s = registry["summary"]
        print(f"  Registry: {s['production']} production, {s['beta']} beta, "
              f"{s['experimental']} experimental, {s['failing']} failing, {s['untested']} untested")
        try:
            from app.detection_enterprise.progress_log import ProgressLog
            ProgressLog().log("registry_updated", "calibrate.py",
                f"Registry: {s['production']} production, {s['beta']} beta, "
                f"{s['experimental']} experimental, {s['failing']} failing, {s['untested']} untested")
        except Exception:
            pass
        sys.exit(0)
    
    # --- LLM golden data expansion ---
    if args.generate_data:
        from app.detection_enterprise.golden_data_generator import GoldenDataGenerator
        from app.detection_enterprise.golden_dataset import create_default_golden_dataset
    
        generator = GoldenDataGenerator()
        if not generator.is_available:
            print("  ERROR: No ANTHROPIC_API_KEY set — cannot generate data")
            sys.exit(1)
    
        dataset = create_default_golden_dataset()
        print(f"\n  Current dataset: {len(dataset.entries)} entries")
        use_difficulty_passes = (args.difficulty == "mixed")
        new_entries = generator.generate_all(
            dataset,
            target_per_type=args.generate_target,
            use_difficulty_passes=use_difficulty_passes,
        )
        if new_entries:
            for entry in new_entries:
                dataset.add_entry(entry)
            save_path = Path(__file__).parent.parent.parent / "data" / "golden_dataset_expanded.json"
            dataset.save(save_path)
            print(f"  Generated {len(new_entries)} new entries")
            print(f"  Expanded dataset saved to: {save_path}")
        else:
            print("  All types already at target — no generation needed")
        print()
    
    # --- Hard sample generation for saturated detectors ---
    if args.generate_hard:
        from app.detection_enterprise.golden_data_generator import GoldenDataGenerator
        from app.detection_enterprise.golden_dataset import create_default_golden_dataset
    
        generator = GoldenDataGenerator()
        if not generator.is_available:
            print("  ERROR: No ANTHROPIC_API_KEY set — cannot generate data")
            sys.exit(1)
    
        dataset = create_default_golden_dataset()
    
        # First run calibration to identify saturated detectors
        print("\n  Running calibration to identify saturated detectors...")
        pre_report = calibrate_all()
        registry = generate_capability_registry(pre_report)
    
        saturated = [
            name for name, entry in registry["capabilities"].items()
            if entry.get("eval_category") == "saturated"
        ]
    
        if not saturated:
            print("  No saturated detectors found — no hard samples needed")
        else:
            print(f"  Saturated detectors: {', '.join(saturated)}")
            all_new = []
            for det_name in saturated:
                try:
                    dt = DetectionType(det_name)
                except ValueError:
                    print(f"    Skipping unknown type: {det_name}")
                    continue
                existing = dataset.get_entries_by_type(dt)
                dist = dataset.get_difficulty_distribution(dt)
                print(f"\n    [{det_name.upper()}] current distribution: {dist}")
                new_entries = generator.generate_for_type(
                    detection_type=dt,
                    difficulty="hard",
                    count=args.hard_count,
                    existing_entries=existing,
                )
                all_new.extend(new_entries)
                print(f"    Generated {len(new_entries)} hard samples")
    
            if all_new:
                for entry in all_new:
                    dataset.add_entry(entry)
                save_path = Path(__file__).parent.parent.parent / "data" / "golden_dataset_expanded.json"
                dataset.save(save_path)
                print(f"\n  Total: {len(all_new)} hard samples generated")
                print(f"  Expanded dataset saved to: {save_path}")
                print("  Re-run calibration to measure impact.")
            else:
                print("  No entries generated")
        print()
    
    # --- Phoenix OTEL setup ---
    phoenix_tracer = None
    if args.phoenix:
        try:
            from app.detection_enterprise.phoenix_exporter import setup_phoenix_exporter
            phoenix_tracer = setup_phoenix_exporter(endpoint=args.phoenix_endpoint)
            print(f"  Phoenix tracing enabled → {args.phoenix_endpoint}")
        except Exception as exc:
            print(f"  WARNING: Could not enable Phoenix tracing: {exc}")
    
    # If --tiered, rebuild detector runners to use tiered detectors
    if args.tiered:
        _apply_tiered_runners()
    
    db_session = None
    if args.from_db:
        import asyncio as _aio
        from app.storage.database import async_session_maker
        db_session = _aio.run(async_session_maker().__aenter__())
        print("  Loading golden dataset from PostgreSQL...")
    
    multi_trial_report = None
    if args.trials > 1:
        if not args.tiered:
            print("  WARNING: --trials requires --tiered (rule-based detectors are deterministic)")
            print("  Running single trial instead.")
        else:
            print(f"\n  Running {args.trials} calibration trials for variance measurement...")
            multi_trial_report = calibrate_multi_trial(
                n_trials=args.trials,
                phoenix_tracer=phoenix_tracer,
                db_session=db_session,
            )
            # Use the last trial's report for display/history
            report = multi_trial_report["raw_trials"][-1]
    
    if multi_trial_report is None:
        report = calibrate_all(phoenix_tracer=phoenix_tracer, db_session=db_session)
    
    if db_session:
        import asyncio as _aio
    
        async def _close():
            await db_session.close()
            await db_session.get_bind().dispose()
    
        try:
            _aio.run(_close())
        except Exception:
            pass  # Best-effort cleanup
    
    # v1.3: Error analysis report
    if args.error_analysis:
        generate_error_report(report)
    
    # --- Contrastive sample generation (requires error analysis data) ---
    if args.generate_contrastive:
        sample_preds = report.get("sample_predictions", [])
        if not sample_preds:
            print("  WARNING: No sample predictions — run without --no-history first")
        else:
            from app.detection_enterprise.golden_data_generator import GoldenDataGenerator
            from app.detection.validation import DetectionType
            gen = GoldenDataGenerator()
            if gen.is_available:
                # Group FP/FN by detector type
                from collections import defaultdict
                fps_by_type = defaultdict(list)
                fns_by_type = defaultdict(list)
                for sp in sample_preds:
                    cls = sp.get("classification", "")
                    dt = sp.get("detection_type", "")
                    if cls == "FP":
                        fps_by_type[dt].append(sp)
                    elif cls == "FN":
                        fns_by_type[dt].append(sp)
                # Generate for types with errors
                all_contrastive = []
                for dt_name in sorted(set(fps_by_type) | set(fns_by_type)):
                    try:
                        dt = DetectionType(dt_name)
                    except ValueError:
                        continue
                    fps = fps_by_type.get(dt_name, [])
                    fns = fns_by_type.get(dt_name, [])
                    if not fps and not fns:
                        continue
                    print(f"  Generating contrastive samples for {dt_name} ({len(fps)} FP, {len(fns)} FN)...")
                    entries = gen.generate_contrastive(dt, fps, fns, count=5)
                    all_contrastive.extend(entries)
                    print(f"    Generated {len(entries)} contrastive samples")
                if all_contrastive:
                    from app.detection_enterprise.golden_dataset import create_default_golden_dataset
                    dataset = create_default_golden_dataset()
                    for e in all_contrastive:
                        dataset.add_entry(e)
                    save_path = Path(__file__).parent.parent.parent / "data" / "golden_dataset_expanded.json"
                    dataset.save(save_path)
                    print(f"  Total contrastive samples: {len(all_contrastive)}")
                    print(f"  Dataset saved to: {save_path}")
            else:
                print("  WARNING: Anthropic SDK not available — skipping contrastive generation")
    
    # Pretty-print summary to stdout.
    print("\n" + "=" * 72)
    print("  DETECTION THRESHOLD CALIBRATION REPORT")
    print("=" * 72)
    print(f"  Timestamp : {report['calibrated_at']}")
    print(f"  Detectors : {report['detector_count']} calibrated")
    if report["skipped"]:
        print(f"  Skipped   : {', '.join(report['skipped'])}")
    print("-" * 72)
    
    for dtype, metrics in report["results"].items():
        f1 = metrics['f1']
        ci_lo = metrics.get('f1_ci_lower', 0.0)
        ci_hi = metrics.get('f1_ci_upper', 0.0)
        readiness = _compute_readiness(
            f1, metrics.get('precision', 0.0), metrics.get('sample_count', 0),
        )
        print(f"\n  [{dtype.upper()}]")
        print(f"    Optimal threshold : {metrics['optimal_threshold']:.2f}")
        print(f"    Precision         : {metrics['precision']:.4f}")
        print(f"    Recall            : {metrics['recall']:.4f}")
        print(f"    F1                : {f1:.4f} (95% CI: {ci_lo:.2f}\u2013{ci_hi:.2f})")
        print(f"    Readiness         : {readiness}")
        print(f"    Samples           : {metrics['sample_count']}")
        print(
            f"    Confusion         : TP={metrics['true_positives']}  "
            f"TN={metrics['true_negatives']}  "
            f"FP={metrics['false_positives']}  "
            f"FN={metrics['false_negatives']}"
        )
        if "ece" in metrics:
            print(f"    ECE               : {metrics['ece']:.4f}")
        # v1.5: Latency stats
        lat = metrics.get("latency_stats", {})
        if lat and lat.get("mean_ms", 0) > 0:
            print(f"    Latency           : mean={lat['mean_ms']:.1f}ms  p95={lat['p95_ms']:.1f}ms  total={lat['total_ms']:.0f}ms")
        # v1.5: LLM cost stats
        llm = metrics.get("llm_cost", {})
        if llm and llm.get("escalations", 0) > 0:
            print(f"    LLM cost          : ${llm['cost_usd']:.4f} ({llm['escalations']} escalations, {llm['tokens']} tokens)")
        # v1.5: Per-difficulty breakdown
        diff_breakdown = metrics.get("difficulty_breakdown", {})
        if diff_breakdown:
            parts = []
            for diff in ("easy", "medium", "hard"):
                dm = diff_breakdown.get(diff)
                if dm:
                    parts.append(f"{diff}={dm['f1']:.3f} (n={dm['n']})")
            if parts:
                print(f"    Difficulty        : {', '.join(parts)}")
            # Saturation warning
            easy_m = diff_breakdown.get("easy", {})
            hard_m = diff_breakdown.get("hard", {})
            if (easy_m.get("f1", 0) >= 0.95
                    and hard_m.get("n", 0) < 5
                    and metrics.get("f1", 0) >= 0.95):
                print(f"    Saturation        : WARNING — easy F1={easy_m['f1']:.2f} with <5 hard samples")
    
    # LLM cost summary (if tiered mode was used)
    llm_summary = report.get("llm_cost_summary", {})
    if llm_summary.get("total_escalations", 0) > 0:
        print(f"\n  LLM JUDGE COST SUMMARY")
        print(f"    Total escalations : {llm_summary['total_escalations']}")
        print(f"    Total tokens      : {llm_summary['total_tokens']:,}")
        print(f"    Total cost        : ${llm_summary['total_cost_usd']:.4f}")
    
    # Multi-trial variance summary
    if multi_trial_report is not None:
        print(f"\n  MULTI-TRIAL VARIANCE ({multi_trial_report['trials']} trials)")
        print(f"  {'Detector':<20s} {'Mean F1':>8s} {'Std':>7s} {'Min':>7s} {'Max':>7s} {'Pass@k':>7s}")
        print(f"  {'-'*20} {'-'*8} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")
        unstable = []
        for det_type, v in sorted(multi_trial_report["variance"].items()):
            flag = " *" if v["std_f1"] > 0.10 else ""
            print(f"  {det_type:<20s} {v['mean_f1']:>8.4f} {v['std_f1']:>7.4f} "
                  f"{v['min_f1']:>7.4f} {v['max_f1']:>7.4f} {v['pass_at_k']:>7.2f}{flag}")
            if v["std_f1"] > 0.10:
                unstable.append(det_type)
        if unstable:
            print(f"\n  * Unstable detectors (std>0.10): {', '.join(unstable)}")
    
    print("\n" + "=" * 72)
    
    # Apply thresholds (unless --dry-run)
    if args.apply_thresholds and not args.dry_run:
        from app.detection_enterprise.threshold_config import ThresholdConfig
        config = ThresholdConfig()
        changes = config.update_from_calibration(report)
        config.save()
        if changes:
            print(f"\n  Thresholds updated ({len(changes)} changed):")
            for dtype, delta in sorted(changes.items()):
                print(f"    {dtype}: {delta['old']:.2f} \u2192 {delta['new']:.2f} (F1={delta['f1']:.4f})")
        else:
            print(f"\n  Thresholds unchanged (no significant changes)")
    
    if args.dry_run:
        print("\n  Dry run \u2014 no thresholds or history saved")
    
    # Save to history (unless --no-history or --dry-run)
    if not args.no_history and not args.dry_run:
        from app.detection_enterprise.calibration_history import (
            CalibrationHistory, create_experiment_from_report,
        )
        history = CalibrationHistory()
        experiment = create_experiment_from_report(report)
        history.append(experiment)
        print(f"  Experiment {experiment.id} saved to history")
    
    # Write the report to a JSON file.
    default_report_path = Path(__file__).parent.parent.parent / "data" / "calibration_report.json"
    save_calibration_report(report, default_report_path)
    print(f"\n  Report written to: {default_report_path}")
    
    # Generate capability registry (if --registry or always after calibration)
    if args.registry:
        registry = generate_capability_registry(report)
        s = registry["summary"]
        print(f"  Registry: {s['production']} production, {s['beta']} beta, "
              f"{s['experimental']} experimental, {s['failing']} failing, {s['untested']} untested")
    
    # Log to progress log (unless dry-run)
    if not args.dry_run:
        try:
            from app.detection_enterprise.progress_log import ProgressLog
            progress = ProgressLog()
            avg_f1 = sum(m["f1"] for m in report["results"].values()) / len(report["results"])
            progress.log("calibration_run", "calibrate.py",
                f"Calibrated {report['detector_count']} detectors, avg F1={avg_f1:.4f}",
                detector_count=report["detector_count"],
                average_f1=round(avg_f1, 4),
                skipped=report["skipped"])
            if args.apply_thresholds:
                progress.log("threshold_update", "calibrate.py",
                    f"Updated thresholds from calibration")
            if args.registry:
                s = registry["summary"]
                progress.log("registry_updated", "calibrate.py",
                    f"Registry: {s['production']} production, {s['beta']} beta, "
                    f"{s['experimental']} experimental, {s['failing']} failing, {s['untested']} untested")
        except Exception:
            pass  # Progress logging is non-critical
    
    # --- Cross-detector correlation analysis ---
    if args.correlations:
        from app.detection_enterprise.calibrate import compute_correlation_matrix
        corr = compute_correlation_matrix(report)
        pairs = corr.get("pairs", [])
        if pairs:
            print(f"\n{'='*70}")
            print("CROSS-DETECTOR CORRELATIONS (|phi| > 0.3)")
            print(f"{'='*70}")
            for p in pairs[:20]:
                print(f"  {p['a']:30s} ↔ {p['b']:30s}  phi={p['phi']:+.4f}")
        else:
            print("\n  No strong cross-detector correlations found (all |phi| <= 0.3)")
    
    # --- Regression alerting ---
    if args.alert_webhook:
        from app.detection_enterprise.calibration_history import CalibrationHistory
        history = CalibrationHistory()
        recent = history.load_recent(n=2)
        if len(recent) >= 2:
            current, previous = recent[0], recent[1]
            comparison = current.compare(previous)
            regressions = []
            for dt, delta in comparison.get("detector_deltas", {}).items():
                if delta["delta"] < -0.05:
                    regressions.append(delta | {"detector": dt})
            if regressions:
                import urllib.request
                payload = json.dumps({
                    "text": f"⚠️ PISAMA Calibration Regression Alert\n"
                            + "\n".join(
                                f"  • {r['detector']}: {r['previous_f1']:.3f} → {r['current_f1']:.3f} (Δ{r['delta']:+.4f})"
                                for r in regressions
                            ),
                }).encode()
                try:
                    req = urllib.request.Request(
                        args.alert_webhook,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    urllib.request.urlopen(req, timeout=10)
                    print(f"\n  Regression alert sent to webhook ({len(regressions)} detectors)")
                except Exception as e:
                    print(f"\n  WARNING: Failed to send alert: {e}")
            else:
                print("\n  No regressions detected — no alert sent")
        else:
            print("\n  Not enough history for regression comparison — skipping alert")
    
    print()


if __name__ == "__main__":
    main()
