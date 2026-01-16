"""CLI interface for MAST benchmarks.

Usage:
    python -m app.benchmark.cli run data.jsonl -o report.md
    python -m app.benchmark.cli stats data.jsonl
    python -m app.benchmark.cli train-model data.jsonl -o model.pkl
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
    verbose: bool,
):
    """Run MAST benchmark.

    DATA_PATH: Path to MAST data file (JSONL or JSON format)

    Examples:
        python -m app.benchmark.cli run fixtures/mast/data.jsonl -o report.md
        python -m app.benchmark.cli run data.jsonl --framework ChatDev
        python -m app.benchmark.cli run data.jsonl --modes F1,F7,F12 --train
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

    result = runner.run(
        progress_callback=progress_callback,
        use_ml_detector=use_ml,
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
