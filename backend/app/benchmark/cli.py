"""CLI interface for MAST benchmarks.

Usage:
    python -m app.benchmark.cli run data.jsonl -o report.md
    python -m app.benchmark.cli stats data.jsonl
    python -m app.benchmark.cli train-model data.jsonl -o model.pkl
    python -m app.benchmark.cli train-multirun data.jsonl --num-runs 5
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import click

from app.benchmark.mast_loader import MASTDataLoader, ALL_FAILURE_MODES
from app.benchmark.runner import BenchmarkRunner
from app.benchmark.metrics import MetricsComputer
from app.benchmark.report import ReportFormat, ReportConfig, ReportGenerator

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


@click.group()
def cli():
    """MAST Benchmark CLI - Evaluate detection accuracy against MAST dataset."""
    pass


@cli.command()
@click.argument("data_path", type=click.Path(exists=True))
@click.option(
    "--output", "-o",
    default="benchmark_report.md",
    help="Output file path",
)
@click.option(
    "--format", "-f",
    type=click.Choice(["json", "markdown", "console"]),
    default="markdown",
    help="Output format",
)
@click.option(
    "--framework",
    help="Filter to specific framework (e.g., ChatDev, MetaGPT)",
)
@click.option(
    "--modes",
    help="Comma-separated failure modes (e.g., F1,F7,F12)",
)
@click.option(
    "--use-ml/--no-ml",
    default=True,
    help="Use ML detector (requires training or pre-trained model)",
)
@click.option(
    "--train/--no-train",
    default=False,
    help="Train ML detector before running benchmark",
)
@click.option(
    "--epochs",
    default=50,
    help="Training epochs (if --train)",
)
@click.option(
    "--batch-size",
    default=32,
    help="Batch size for ML detector",
)
@click.option(
    "--llm/--no-llm",
    default=False,
    help="Use LLM (Claude) for semantic failure mode detection (F6,F8,F9,F13)",
)
@click.option(
    "--llm-model",
    type=click.Choice(["haiku", "sonnet", "opus"]),
    default="haiku",
    help="LLM model to use (haiku=fast/cheap, sonnet=balanced, opus=best)",
)
@click.option(
    "--llm-modes",
    default=None,
    help="Comma-separated modes for LLM detection (default: F6,F8,F9,F13)",
)
@click.option(
    "--max-llm-records",
    default=None,
    type=int,
    help="Maximum records for LLM detection (cost control)",
)
@click.option(
    "--hybrid/--no-hybrid",
    default=False,
    help="Use hybrid turn-aware + LLM detection for semantic modes (F6,F8,F9,F13)",
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    help="Anthropic API key for LLM/hybrid detection",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Verbose output",
)
def run(
    data_path: str,
    output: str,
    format: str,
    framework: Optional[str],
    modes: Optional[str],
    use_ml: bool,
    train: bool,
    epochs: int,
    batch_size: int,
    llm: bool,
    llm_model: str,
    llm_modes: Optional[str],
    max_llm_records: Optional[int],
    hybrid: bool,
    api_key: Optional[str],
    verbose: bool,
):
    """Run MAST benchmark.

    DATA_PATH: Path to MAST data file (JSONL or JSON format)

    Examples:
        # Basic rule-based benchmark
        python -m app.benchmark.cli run data.jsonl --no-ml -o report.md

        # With LLM detection for semantic modes
        python -m app.benchmark.cli run data.jsonl --no-ml --llm -o llm_report.md

        # LLM with specific modes and model
        python -m app.benchmark.cli run data.jsonl --no-ml --llm --llm-model sonnet --llm-modes F6,F9

        # Cost-controlled LLM run
        python -m app.benchmark.cli run data.jsonl --no-ml --llm --max-llm-records 50
    """
    setup_logging(verbose)

    click.echo(f"Loading data from {data_path}...")

    # Load data
    loader = MASTDataLoader(Path(data_path))
    count = loader.load()
    click.echo(f"Loaded {count:,} records")

    # Filter by framework if specified
    if framework:
        records = loader.filter_by_framework(framework)
        click.echo(f"Filtered to {len(records):,} records for framework: {framework}")
        # Update loader with filtered records
        loader._records = records

    # Parse failure modes
    failure_modes = None
    if modes:
        failure_modes = [m.strip().upper() for m in modes.split(",")]
        # Validate modes
        invalid_modes = set(failure_modes) - set(ALL_FAILURE_MODES)
        if invalid_modes:
            click.echo(f"Warning: Invalid modes ignored: {invalid_modes}", err=True)
        failure_modes = [m for m in failure_modes if m in ALL_FAILURE_MODES]
        click.echo(f"Evaluating modes: {', '.join(failure_modes)}")

    # Create runner
    runner = BenchmarkRunner(
        loader=loader,
        failure_modes=failure_modes,
        batch_size=batch_size,
        api_key=api_key,
    )

    # Train if requested
    if train and use_ml:
        click.echo(f"Training ML detector ({epochs} epochs)...")
        try:
            train_result = runner.train_ml_detector(epochs=epochs)
            click.echo(f"Training complete: {train_result}")
        except Exception as e:
            click.echo(f"Training failed: {e}", err=True)
            use_ml = False

    # Run benchmark with progress bar
    click.echo("Running benchmark...")

    def progress_callback(processed: int, total: int):
        if total > 0:
            pct = processed / total * 100
            click.echo(f"\rProgress: {processed:,}/{total:,} ({pct:.1f}%)", nl=False)

    # Parse LLM modes if specified
    llm_modes_list = None
    if llm_modes:
        llm_modes_list = [m.strip().upper() for m in llm_modes.split(",")]

    # Show LLM detection info
    if llm:
        click.echo(f"LLM detection enabled: model={llm_model}, modes={llm_modes_list or 'F6,F8,F9,F13'}")
        if max_llm_records:
            click.echo(f"  Max records for LLM: {max_llm_records}")

    # Show hybrid detection info
    if hybrid:
        click.echo(f"Hybrid detection enabled (turn-aware + LLM escalation)")
        click.echo(f"  Modes: {llm_modes_list or ['F6', 'F8', 'F9', 'F13']}")
        click.echo(f"  API key: {'set' if api_key else 'NOT SET (turn-aware only)'}")

    result = runner.run(
        progress_callback=progress_callback,
        use_ml_detector=use_ml,
        use_llm_detector=llm,
        use_hybrid_detector=hybrid,
        llm_model=llm_model,
        llm_modes=llm_modes_list,
        max_llm_records=max_llm_records,
    )
    click.echo()  # Newline after progress
    click.echo(f"Processed {result.processed_records:,} records, "
               f"{result.total_detections:,} detections")

    # Compute metrics
    click.echo("Computing metrics...")
    computer = MetricsComputer()
    metrics = computer.compute(
        predictions=result.get_predictions(),
        ground_truths=result.ground_truths,
        latencies=result.get_latencies(),
    )

    # Generate report
    click.echo("Generating report...")
    report_format = ReportFormat(format)
    config = ReportConfig(format=report_format)
    generator = ReportGenerator(config)
    report = generator.generate(metrics, result)

    # Output
    if output == "-":
        click.echo(report)
    else:
        with open(output, "w") as f:
            f.write(report)
        click.echo(f"Report saved to {output}")

    # Summary
    click.echo("")
    click.echo("=" * 50)
    click.echo(f"Macro F1:    {metrics.macro_f1:.3f}")
    click.echo(f"Micro F1:    {metrics.micro_f1:.3f}")
    click.echo(f"Accuracy:    {metrics.overall_accuracy:.1%}")
    click.echo("=" * 50)


@cli.command()
@click.argument("data_path", type=click.Path(exists=True))
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def stats(data_path: str, verbose: bool):
    """Show MAST dataset statistics.

    DATA_PATH: Path to MAST data file

    Example:
        python -m app.benchmark.cli stats fixtures/mast/data.jsonl
    """
    setup_logging(verbose)

    click.echo(f"Loading data from {data_path}...")

    loader = MASTDataLoader(Path(data_path))
    count = loader.load()

    stats = loader.get_statistics()

    click.echo("")
    click.echo("=" * 50)
    click.echo("MAST DATASET STATISTICS")
    click.echo("=" * 50)
    click.echo("")
    click.echo(f"Total Records:    {stats['total']:,}")
    click.echo(f"With Failures:    {stats['with_failures']:,}")
    click.echo(f"Healthy:          {stats['healthy']:,}")
    click.echo("")

    if stats.get("by_framework"):
        click.echo("BY FRAMEWORK:")
        click.echo("-" * 30)
        for fw, count in stats["by_framework"].items():
            click.echo(f"  {fw:<20} {count:>6,}")
        click.echo("")

    if stats.get("by_failure_mode"):
        click.echo("BY FAILURE MODE:")
        click.echo("-" * 30)
        for mode, count in stats["by_failure_mode"].items():
            from app.benchmark.mast_loader import FAILURE_MODE_NAMES
            name = FAILURE_MODE_NAMES.get(mode, "")
            click.echo(f"  {mode:<5} {name:<20} {count:>6,}")
        click.echo("")

    if stats.get("by_llm"):
        click.echo("BY LLM:")
        click.echo("-" * 30)
        for llm, count in list(stats["by_llm"].items())[:10]:
            click.echo(f"  {llm:<25} {count:>6,}")
        if len(stats["by_llm"]) > 10:
            click.echo(f"  ... and {len(stats['by_llm']) - 10} more")
        click.echo("")


@cli.command("train-model")
@click.argument("data_path", type=click.Path(exists=True))
@click.option(
    "--output", "-o",
    default="ml_model.pkl",
    help="Output model path",
)
@click.option(
    "--epochs",
    default=50,
    help="Training epochs",
)
@click.option(
    "--test-split",
    default=0.2,
    help="Test split ratio",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def train_model(
    data_path: str,
    output: str,
    epochs: int,
    test_split: float,
    verbose: bool,
):
    """Train ML detector on MAST data.

    DATA_PATH: Path to MAST training data

    Example:
        python -m app.benchmark.cli train-model data.jsonl -o model.pkl
    """
    setup_logging(verbose)

    click.echo(f"Loading training data from {data_path}...")

    loader = MASTDataLoader(Path(data_path))
    count = loader.load()
    click.echo(f"Loaded {count:,} records")

    # Create runner and train
    runner = BenchmarkRunner(loader=loader)

    click.echo(f"Training ML detector ({epochs} epochs)...")
    try:
        result = runner.train_ml_detector(epochs=epochs)
        click.echo(f"Training complete!")
        click.echo(f"Result: {result}")

        # Save model
        if runner._ml_detector:
            import pickle
            with open(output, "wb") as f:
                pickle.dump(runner._ml_detector, f)
            click.echo(f"Model saved to {output}")

    except Exception as e:
        click.echo(f"Training failed: {e}", err=True)
        sys.exit(1)


@cli.command("train-multirun")
@click.argument("data_path", type=click.Path(exists=True))
@click.option(
    "--output", "-o",
    default="ml_model_multirun.pkl",
    help="Output model path (saves best model)",
)
@click.option(
    "--num-runs", "-n",
    default=5,
    help="Number of training runs with different seeds",
)
@click.option(
    "--base-seed",
    default=42,
    help="Starting random seed (runs use base_seed, base_seed+1, ...)",
)
@click.option(
    "--epochs",
    default=50,
    help="Training epochs per run",
)
@click.option(
    "--test-split",
    default=0.2,
    help="Test split ratio",
)
@click.option(
    "--batch-size",
    default=32,
    help="Batch size for training",
)
@click.option(
    "--use-attention/--no-attention",
    default=False,
    help="Use self-attention on embeddings",
)
@click.option(
    "--cv-folds",
    default=1,
    help="Cross-validation folds for threshold optimization",
)
@click.option(
    "--label-smoothing",
    default=0.0,
    help="Label smoothing for confidence regularization",
)
@click.option(
    "--report", "-r",
    default=None,
    help="Optional JSON report output path",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def train_multirun(
    data_path: str,
    output: str,
    num_runs: int,
    base_seed: int,
    epochs: int,
    test_split: float,
    batch_size: int,
    use_attention: bool,
    cv_folds: int,
    label_smoothing: float,
    report: Optional[str],
    verbose: bool,
):
    """Train ML detector multiple times with different seeds for robust evaluation.

    This provides more reliable metrics by averaging across multiple runs,
    accounting for variance from random initialization and data splits.

    DATA_PATH: Path to MAST training data

    Examples:
        # Basic 5-run training
        python -m app.benchmark.cli train-multirun data.jsonl --num-runs 5

        # With all options
        python -m app.benchmark.cli train-multirun data.jsonl \\
            --num-runs 10 --base-seed 0 --epochs 100 --use-attention \\
            -o best_model.pkl -r multirun_report.json
    """
    import json
    setup_logging(verbose)

    click.echo(f"Loading training data from {data_path}...")

    loader = MASTDataLoader(Path(data_path))
    count = loader.load()
    click.echo(f"Loaded {count:,} records")

    # Convert records to dict format expected by ML detector
    records = []
    for record in loader:
        records.append({
            "trace": {"trajectory": record.trajectory},
            "mast_annotation": record.raw_annotations,
        })

    click.echo("")
    click.echo("=" * 60)
    click.echo(f"MULTI-RUN TRAINING: {num_runs} runs")
    click.echo(f"Seeds: {base_seed} to {base_seed + num_runs - 1}")
    click.echo(f"Epochs: {epochs}, Batch size: {batch_size}")
    click.echo(f"Attention: {use_attention}, CV folds: {cv_folds}")
    click.echo("=" * 60)
    click.echo("")

    try:
        from app.detection_enterprise.ml_detector_v3 import MultiTaskDetector

        result = MultiTaskDetector.train_multirun(
            records=records,
            num_runs=num_runs,
            base_seed=base_seed,
            test_split=test_split,
            epochs=epochs,
            batch_size=batch_size,
            use_attention=use_attention,
            cv_folds=cv_folds,
            label_smoothing=label_smoothing,
        )

        # Print summary
        aggregated = result["aggregated"]
        click.echo("")
        click.echo("=" * 60)
        click.echo("FINAL RESULTS")
        click.echo("=" * 60)
        click.echo("")
        click.echo(f"Macro F1: {aggregated['overall']['macro_f1_mean']:.4f} "
                   f"± {aggregated['overall']['macro_f1_std']:.4f}")
        click.echo(f"95% CI:   [{aggregated['overall']['macro_f1_ci_lower']:.4f}, "
                   f"{aggregated['overall']['macro_f1_ci_upper']:.4f}]")
        click.echo(f"Range:    [{aggregated['overall']['macro_f1_min']:.4f}, "
                   f"{aggregated['overall']['macro_f1_max']:.4f}]")
        click.echo("")
        click.echo(f"Best run: {result['best_run'] + 1} (seed={result['seeds_used'][result['best_run']]})")
        click.echo("")

        # Per-mode results
        click.echo("PER-MODE RESULTS (mean ± std):")
        click.echo("-" * 50)
        for mode, metrics in sorted(aggregated["modes"].items()):
            f1_mean = metrics.get("f1_mean", 0)
            f1_std = metrics.get("f1_std", 0)
            click.echo(f"  {mode}: F1 = {f1_mean:.3f} ± {f1_std:.3f}")
        click.echo("")

        # Save best model
        best_detector = result["best_detector"]
        if best_detector:
            import pickle
            with open(output, "wb") as f:
                pickle.dump(best_detector, f)
            click.echo(f"Best model saved to {output}")

        # Save report if requested
        if report:
            # Prepare serializable report
            report_data = {
                "num_runs": num_runs,
                "base_seed": base_seed,
                "seeds_used": result["seeds_used"],
                "best_run": result["best_run"],
                "aggregated": aggregated,
                "run_results": result["run_results"],
                "config": {
                    "epochs": epochs,
                    "batch_size": batch_size,
                    "test_split": test_split,
                    "use_attention": use_attention,
                    "cv_folds": cv_folds,
                    "label_smoothing": label_smoothing,
                },
            }
            with open(report, "w") as f:
                json.dump(report_data, f, indent=2)
            click.echo(f"Report saved to {report}")

    except Exception as e:
        import traceback
        click.echo(f"Training failed: {e}", err=True)
        if verbose:
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("report_path", type=click.Path(exists=True))
@click.option("--mode", help="Show details for specific failure mode")
def analyze(report_path: str, mode: Optional[str]):
    """Analyze benchmark report.

    REPORT_PATH: Path to JSON benchmark report

    Example:
        python -m app.benchmark.cli analyze report.json --mode F7
    """
    import json

    with open(report_path) as f:
        report = json.load(f)

    click.echo("=" * 50)
    click.echo("BENCHMARK ANALYSIS")
    click.echo("=" * 50)
    click.echo("")

    # Summary
    if "metrics" in report and "summary" in report["metrics"]:
        summary = report["metrics"]["summary"]
        click.echo("SUMMARY:")
        click.echo(f"  Macro F1:    {summary.get('macro_f1', 'N/A')}")
        click.echo(f"  Micro F1:    {summary.get('micro_f1', 'N/A')}")
        click.echo(f"  Accuracy:    {summary.get('overall_accuracy', 'N/A')}")
        click.echo("")

    # Mode details
    if mode and "metrics" in report and "by_mode" in report["metrics"]:
        mode_data = report["metrics"]["by_mode"].get(mode.upper())
        if mode_data:
            click.echo(f"DETAILS FOR {mode.upper()}:")
            click.echo(f"  Name:      {mode_data.get('name', 'N/A')}")
            click.echo(f"  Precision: {mode_data.get('precision', 'N/A')}")
            click.echo(f"  Recall:    {mode_data.get('recall', 'N/A')}")
            click.echo(f"  F1:        {mode_data.get('f1', 'N/A')}")
            click.echo(f"  Samples:   {mode_data.get('sample_count', 'N/A')}")

            if "confusion_matrix" in mode_data:
                cm = mode_data["confusion_matrix"]
                click.echo("")
                click.echo("  Confusion Matrix:")
                click.echo(f"    TP: {cm.get('tp', 0):5}  FN: {cm.get('fn', 0):5}")
                click.echo(f"    FP: {cm.get('fp', 0):5}  TN: {cm.get('tn', 0):5}")
        else:
            click.echo(f"Mode {mode.upper()} not found in report")


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
