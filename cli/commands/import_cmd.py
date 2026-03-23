"""CLI command for importing traces from external platforms.

Usage:
    pisama import trace_export.json --from langfuse
    pisama import traces/ --from phoenix
"""

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

import_app = typer.Typer(
    name="import",
    help="Import traces from external platforms (Langfuse, Phoenix, LangSmith)",
    invoke_without_command=True,
)
console = Console()


@import_app.callback(invoke_without_command=True)
def import_traces(
    file: Path = typer.Argument(..., help="Path to trace file or directory"),
    source: str = typer.Option("auto", "--from", "-f", help="Source platform (langfuse, phoenix, langsmith, otel, auto)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file for converted traces (default: stdout)"),
):
    """Import and convert traces from external platforms to Pisama format."""
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

    files_to_process = []
    if file.is_dir():
        files_to_process = sorted(file.glob("*.json"))
        if not files_to_process:
            console.print(f"[red]No JSON files found in {file}[/red]")
            raise typer.Exit(1)
        console.print(f"Found {len(files_to_process)} JSON files in {file}")
    else:
        files_to_process = [file]

    total_spans = 0
    total_traces = 0

    for trace_file in files_to_process:
        content = trace_file.read_text()

        # Detect format if auto
        fmt = source
        if fmt == "auto":
            from app.ingestion.importers.base import BaseImporter
            fmt = BaseImporter.detect_format(content)
            console.print(f"[dim]{trace_file.name}: detected as {fmt}[/dim]")

        try:
            from app.ingestion.importers import get_importer
            importer = get_importer(fmt)
            trace = importer.import_trace(content)
            total_traces += 1
            total_spans += len(trace.spans)

            console.print(
                f"[green]{trace_file.name}[/green]: "
                f"{len(trace.spans)} spans, "
                f"trace_id={trace.trace_id[:16]}..."
            )

            if output:
                # Append to output file as JSONL
                with open(output, "a") as f:
                    for span in trace.spans:
                        span_dict = {
                            "trace_id": span.trace_id,
                            "span_id": span.id,
                            "name": span.name,
                            "type": span.span_type.value,
                            "status": span.status.value,
                            "start_time": span.start_time.isoformat() if span.start_time else None,
                            "end_time": span.end_time.isoformat() if span.end_time else None,
                            "agent_id": span.agent_id,
                            "model": span.model,
                            "tokens_input": span.tokens_input,
                            "tokens_output": span.tokens_output,
                            "error": span.error,
                            "source_format": span.source_format,
                        }
                        f.write(json.dumps(span_dict) + "\n")

        except Exception as e:
            console.print(f"[red]{trace_file.name}: {e}[/red]")

    console.print(f"\n[bold]Imported {total_traces} traces with {total_spans} total spans[/bold]")

    if output:
        console.print(f"[green]Output written to {output}[/green]")
