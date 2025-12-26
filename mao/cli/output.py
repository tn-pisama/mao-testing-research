"""CLI output formatting with Rich."""

from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich import box

console = Console()


def print_trace_analysis(result: Dict[str, Any]) -> None:
    """Print trace analysis result."""
    trace_id = result.get("trace_id", "unknown")
    framework = result.get("framework", "unknown")
    duration = result.get("duration_ms", 0)
    healthy = result.get("healthy", True)
    status = result.get("status", "UNKNOWN")
    
    status_color = "green" if healthy else "red"
    
    console.print(f"\n[bold]🔍 Trace: {trace_id}[/bold]")
    console.print(f"├─ Framework: {framework}")
    console.print(f"├─ Duration: {duration}ms")
    console.print(f"└─ Status: [{status_color}]{status}[/{status_color}]")
    
    detections = result.get("detections", [])
    if detections:
        console.print("\n[bold]Issues Found:[/bold]")
        for d in detections:
            severity = d.get("severity", "medium")
            icon = "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"
            det_type = d.get("type", "unknown")
            det_id = d.get("id", "")
            summary = d.get("summary", "")
            
            console.print(f"  {icon} {det_type} ({severity.upper()})  [dim]{det_id}[/dim]")
            if summary:
                console.print(f"     {summary}")
        
        console.print(f"\n💡 Run [cyan]mao fix {trace_id}[/cyan] to see suggested fixes")
    else:
        console.print("\n[green]✅ No issues detected[/green]")


def print_detections_table(detections: List[Dict[str, Any]]) -> None:
    """Print detections as a table."""
    if not detections:
        console.print("[dim]No detections found[/dim]")
        return
    
    table = Table(box=box.ROUNDED)
    table.add_column("ID", style="dim")
    table.add_column("Type")
    table.add_column("Severity")
    table.add_column("Trace")
    table.add_column("Summary", max_width=40)
    
    for d in detections:
        severity = d.get("severity", "medium")
        severity_style = "red" if severity == "high" else "yellow" if severity == "medium" else "green"
        
        table.add_row(
            d.get("id", "")[:12],
            d.get("type", ""),
            f"[{severity_style}]{severity.upper()}[/{severity_style}]",
            d.get("trace_id", "")[:12],
            d.get("summary", "")[:40],
        )
    
    console.print(table)


def print_fix_suggestions(fixes: List[Dict[str, Any]], detection_id: str) -> None:
    """Print fix suggestions."""
    if not fixes:
        console.print("[dim]No fix suggestions available[/dim]")
        return
    
    console.print(f"\n[bold]Fix Suggestions for {detection_id}[/bold]\n")
    
    for i, fix in enumerate(fixes, 1):
        confidence = fix.get("confidence", "medium")
        conf_style = "green" if confidence == "high" else "yellow" if confidence == "medium" else "dim"
        
        title = fix.get("title", "Unknown fix")
        description = fix.get("description", "")
        
        console.print(f"[bold]{i}. {title}[/bold] [{conf_style}]({confidence} confidence)[/{conf_style}]")
        console.print(f"   {description}")
        
        code_changes = fix.get("code_changes", [])
        if code_changes:
            console.print("\n   [dim]Code changes:[/dim]")
            for change in code_changes[:2]:
                file_path = change.get("file_path", "")
                console.print(f"   📄 {file_path}")
                
                code = change.get("suggested_code", "")
                if code:
                    syntax = Syntax(code[:500], "python", theme="monokai", line_numbers=False)
                    console.print(Panel(syntax, title=file_path, border_style="dim"))
        
        console.print()
    
    console.print(f"💡 Run [cyan]mao fix {detection_id} --apply[/cyan] to apply a fix")


def print_error(message: str, hint: Optional[str] = None) -> None:
    """Print an error message."""
    console.print(f"[red]❌ Error:[/red] {message}")
    if hint:
        console.print(f"[dim]💡 {hint}[/dim]")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✅ {message}[/green]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠️  {message}[/yellow]")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ️  {message}[/blue]")


async def run_with_spinner(coro, message: str = "Loading..."):
    """Run a coroutine with a spinner."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task(description=message, total=None)
        return await coro
