"""CLI command for running detectors on trace files.

Usage:
    pisama detect trace.json
    pisama detect trace.json --detector loop,injection
    pisama detect trace.json --format langfuse
"""

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

detect_app = typer.Typer(
    name="detect",
    help="Run failure detectors on trace files",
    invoke_without_command=True,
)
console = Console()


@detect_app.callback(invoke_without_command=True)
def detect(
    file: Path = typer.Argument(..., help="Path to trace file (JSON)"),
    detectors: Optional[str] = typer.Option(None, "--detector", "-d", help="Comma-separated detector names (default: all)"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Trace format (auto, langfuse, phoenix, langsmith, otel, generic)"),
    output_format: str = typer.Option("table", "--output", "-o", help="Output format (table, json)"),
):
    """Run Pisama detectors on a trace file."""
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    content = file.read_text()

    # Parse the trace
    try:
        trace_data = json.loads(content)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON: {e}[/red]")
        raise typer.Exit(1)

    # Detect format if not specified
    if not format:
        format = _detect_format(content)
        console.print(f"[dim]Detected format: {format}[/dim]")

    # Import and run detectors
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
        from app.ingestion.importers import get_importer, IMPORTERS

        if format in IMPORTERS:
            importer = get_importer(format)
            trace = importer.import_trace(content)
            console.print(f"[green]Imported {len(trace.spans)} spans from {format} format[/green]")
        else:
            console.print(f"[yellow]Unknown format '{format}', treating as raw JSON[/yellow]")

    except Exception as e:
        console.print(f"[yellow]Could not import as trace: {e}. Running detectors on raw data.[/yellow]")

    # Determine which detectors to run
    try:
        from pisama_detectors import DETECTOR_REGISTRY, run_all_detectors
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages" / "pisama-detectors" / "src"))
        from pisama_detectors import DETECTOR_REGISTRY, run_all_detectors

    selected = None
    if detectors:
        selected = [d.strip() for d in detectors.split(",")]
        unknown = [d for d in selected if d not in DETECTOR_REGISTRY]
        if unknown:
            console.print(f"[yellow]Unknown detectors: {', '.join(unknown)}[/yellow]")
            console.print(f"[dim]Available: {', '.join(DETECTOR_REGISTRY.keys())}[/dim]")

    # Run detectors
    console.print("\n[bold]Running detectors...[/bold]\n")

    results = run_all_detectors(trace_data)

    if selected:
        results = {k: v for k, v in results.items() if k in selected}

    # Output results
    if output_format == "json":
        output = {}
        for name, result in results.items():
            if isinstance(result, dict):
                output[name] = result
            else:
                output[name] = {
                    "detected": getattr(result, "detected", None),
                    "confidence": getattr(result, "confidence", None),
                }
        console.print(json.dumps(output, indent=2, default=str))
    else:
        _print_table(results)


def _print_table(results):
    """Print detection results as a rich table."""
    table = Table(title="Detection Results")
    table.add_column("Detector", style="cyan")
    table.add_column("Detected", style="bold")
    table.add_column("Confidence")
    table.add_column("Details")

    for name, result in sorted(results.items()):
        if isinstance(result, dict) and "error" in result:
            table.add_row(name, "[yellow]error[/yellow]", "-", str(result["error"])[:60])
            continue

        detected = getattr(result, "detected", None)
        confidence = getattr(result, "confidence", None)

        if detected is True:
            det_str = "[red]YES[/red]"
        elif detected is False:
            det_str = "[green]no[/green]"
        else:
            det_str = "[dim]n/a[/dim]"

        conf_str = f"{confidence:.1%}" if confidence is not None else "-"

        # Get first relevant detail
        detail = ""
        for attr in ["severity", "failure_type", "attack_type", "loop_type", "breakdown_type"]:
            val = getattr(result, attr, None)
            if val:
                detail = str(val.value if hasattr(val, "value") else val)
                break

        table.add_row(name, det_str, conf_str, detail[:60])

    console.print(table)

    detected_count = sum(1 for r in results.values() if getattr(r, "detected", False))
    total = len(results)
    console.print(f"\n[bold]{detected_count}/{total} failures detected[/bold]")


def _detect_format(content: str) -> str:
    """Auto-detect trace format."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
        from app.ingestion.importers.base import BaseImporter
        return BaseImporter.detect_format(content)
    except Exception:
        return "generic"
