"""Quality assessment and healing CLI commands."""

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

quality_app = typer.Typer(
    name="quality",
    help="Quality assessment and healing commands for n8n workflows",
)
console = Console()


@quality_app.command()
def assess(
    workflow_file: Path = typer.Argument(..., help="Path to n8n workflow JSON file"),
    threshold: float = typer.Option(0.7, "--threshold", "-t", help="Score threshold for improvement suggestions"),
    max_suggestions: int = typer.Option(10, "--max-suggestions", "-m", help="Maximum improvement suggestions"),
):
    """Assess quality of an n8n workflow."""
    if not workflow_file.exists():
        console.print(f"[red]File not found: {workflow_file}[/red]")
        raise typer.Exit(1)

    try:
        workflow = json.loads(workflow_file.read_text())
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON: {e}[/red]")
        raise typer.Exit(1)

    # Add backend to path for imports
    backend_path = Path(__file__).parent.parent.parent / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

    from app.enterprise.quality import QualityAssessor

    assessor = QualityAssessor(use_llm_judge=False)
    report = assessor.assess_workflow(workflow, max_suggestions=max_suggestions)

    # Display results
    console.print(Panel.fit(
        f"[bold]Overall Score:[/bold] {report.overall_score:.0%} ({report.overall_grade})\n"
        f"[bold]Agents:[/bold] {len(report.agent_scores)}\n"
        f"[bold]Orchestration:[/bold] {report.orchestration_score.overall_score:.0%} ({report.orchestration_score.grade})\n"
        f"[bold]Improvements:[/bold] {len(report.improvements)}",
        title=f"Quality Assessment: {report.workflow_name}",
    ))

    if report.improvements:
        table = Table(title="Top Improvements")
        table.add_column("Priority", style="cyan", width=4)
        table.add_column("Title", style="white")
        table.add_column("Severity", style="yellow")
        table.add_column("Dimension", style="blue")

        for i, imp in enumerate(report.improvements[:max_suggestions], 1):
            table.add_row(str(i), imp.title, imp.severity.value, imp.dimension)

        console.print(table)


@quality_app.command()
def heal(
    workflow_file: Path = typer.Argument(..., help="Path to n8n workflow JSON file"),
    threshold: float = typer.Option(0.7, "--threshold", "-t", help="Score threshold for healing"),
    auto_apply: bool = typer.Option(False, "--auto-apply", "-a", help="Automatically apply fixes"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save healed workflow to file"),
):
    """Trigger quality healing on a workflow."""
    if not workflow_file.exists():
        console.print(f"[red]File not found: {workflow_file}[/red]")
        raise typer.Exit(1)

    try:
        workflow = json.loads(workflow_file.read_text())
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON: {e}[/red]")
        raise typer.Exit(1)

    backend_path = Path(__file__).parent.parent.parent / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

    from app.enterprise.quality import QualityAssessor
    from app.enterprise.quality.healing.engine import QualityHealingEngine

    # Step 1: Assess
    assessor = QualityAssessor(use_llm_judge=False)
    report = assessor.assess_workflow(workflow)

    console.print(f"[bold]Before:[/bold] {report.overall_score:.0%} ({report.overall_grade})")

    # Step 2: Heal
    engine = QualityHealingEngine(auto_apply=auto_apply, score_threshold=threshold)
    result = engine.heal(report, workflow)

    # Step 3: Display results
    status_colors = {
        "success": "green",
        "partial_success": "yellow",
        "pending": "cyan",
        "failed": "red",
    }
    color = status_colors.get(result.status.value, "white")
    console.print(f"[bold]Status:[/bold] [{color}]{result.status.value}[/{color}]")
    console.print(f"[bold]Dimensions targeted:[/bold] {len(result.dimensions_targeted)}")

    if result.dimensions_targeted:
        for dim in result.dimensions_targeted:
            console.print(f"  - {dim}")

    if result.applied_fixes:
        console.print(f"\n[bold]Applied fixes:[/bold] {len(result.applied_fixes)}")
        for fix in result.applied_fixes:
            console.print(f"  - [{fix.dimension}] {fix.fix_id}")

    if result.after_score is not None:
        improvement = result.score_improvement or 0
        console.print(f"\n[bold]After:[/bold] {result.after_score:.0%} ({'+' if improvement > 0 else ''}{improvement:.1%})")

    if result.status.value == "pending":
        suggestions = result.metadata.get("fix_suggestions", [])
        console.print(f"\n[bold]Pending fixes:[/bold] {len(suggestions)}")
        for s in suggestions:
            console.print(f"  - [{s.get('dimension', '?')}] {s.get('title', s.get('id', '?'))}")

    # Save healed workflow if requested and fixes were applied
    if output and result.applied_fixes:
        modified = result.applied_fixes[-1].modified_state
        output.write_text(json.dumps(modified, indent=2))
        console.print(f"\n[green]Healed workflow saved to {output}[/green]")
