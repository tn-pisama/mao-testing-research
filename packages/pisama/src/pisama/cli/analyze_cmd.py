"""pisama analyze <path> command."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from pisama._analyze import analyze
from pisama.output.terminal import display_analysis_result

console = Console(stderr=True)


@click.command("analyze")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--min-severity",
    type=int,
    default=0,
    help="Only show issues at or above this severity (0-100).",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output raw JSON instead of formatted table.",
)
def analyze_cmd(path: str, min_severity: int, output_json: bool) -> None:
    """Analyze a trace file for multi-agent failures.

    PATH is a .json or .jsonl trace file.
    """
    file_path = Path(path)
    if file_path.suffix not in (".json", ".jsonl"):
        console.print(
            f"[red]Error:[/red] Expected a .json or .jsonl file, got {file_path.suffix!r}"
        )
        sys.exit(1)

    try:
        result = analyze(str(file_path))
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)

    # Filter by severity
    if min_severity > 0:
        result.issues = [i for i in result.issues if i.severity >= min_severity]

    if output_json:
        _print_json(result)
    else:
        display_analysis_result(result)

    # Exit code: 1 if critical issues found, 0 otherwise
    if result.critical_issues:
        sys.exit(1)


def _print_json(result: object) -> None:
    """Print result as JSON to stdout."""
    import json
    from dataclasses import asdict

    click.echo(json.dumps(asdict(result), indent=2, default=str))  # type: ignore[call-overload]
