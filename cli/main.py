"""MAO Healer CLI - Self-healing agent for n8n workflows.

Usage:
    mao-healer init              # Create config file
    mao-healer start             # Start webhook server
    mao-healer status            # Show recent healing activity
    mao-healer test              # Send test notification
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from . import __version__
from .config import (
    HealerConfig,
    CONFIG_FILE,
    CONFIG_DIR,
    get_default_config_template,
    ensure_config_dir,
)

app = typer.Typer(
    name="mao-healer",
    help="Self-healing agent for n8n workflows",
    add_completion=False,
)
console = Console()

from .commands.quality import quality_app
from .commands.detect import detect_app
from .commands.import_cmd import import_app
app.add_typer(quality_app)
app.add_typer(detect_app, name="detect")
app.add_typer(import_app, name="import")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
):
    """Initialize MAO Healer configuration."""
    ensure_config_dir()

    if CONFIG_FILE.exists() and not force:
        console.print(f"[yellow]Config already exists at {CONFIG_FILE}[/yellow]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)

    # Write default config
    template = get_default_config_template()
    CONFIG_FILE.write_text(template)

    console.print(Panel.fit(
        f"[green]Created config file at:[/green]\n{CONFIG_FILE}\n\n"
        "[yellow]Next steps:[/yellow]\n"
        "1. Edit the config file with your n8n settings\n"
        "2. Run [cyan]mao-healer start[/cyan] to start the server",
        title="MAO Healer Initialized",
    ))


@app.command()
def start(
    port: int = typer.Option(None, "--port", "-p", help="Server port"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Start the MAO Healer webhook server."""
    # Load config
    config_file = config_path or CONFIG_FILE

    if not config_file.exists():
        console.print(f"[red]Config not found at {config_file}[/red]")
        console.print("Run [cyan]mao-healer init[/cyan] first")
        raise typer.Exit(1)

    config = HealerConfig.load(config_file)

    # Validate config
    if not config.n8n.webhook_secret:
        console.print("[yellow]Warning: webhook_secret not set. Webhooks will not be verified.[/yellow]")

    if not config.n8n.api_key:
        console.print("[yellow]Warning: api_key not set. Cannot apply fixes automatically.[/yellow]")

    server_port = port or config.server_port

    console.print(Panel.fit(
        f"[green]Starting MAO Healer[/green]\n\n"
        f"Port: {server_port}\n"
        f"Auto-apply: {'enabled' if config.auto_apply.enabled else 'disabled'}\n"
        f"Git backup: {'enabled' if config.auto_apply.git_backup else 'disabled'}\n"
        f"Discord: {'configured' if config.notifications.discord_webhook else 'not configured'}\n"
        f"Slack: {'configured' if config.notifications.slack_webhook else 'not configured'}\n"
        f"Email: {'configured' if config.notifications.email_to else 'not configured'}\n\n"
        f"[dim]Webhook URL: http://localhost:{server_port}/webhook/n8n[/dim]",
        title="Pisama Healer",
    ))

    # Start server
    from .server import run_server
    run_server(config, port=server_port)


@app.command()
def status(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Show MAO Healer status and recent activity."""
    config_file = config_path or CONFIG_FILE

    if not config_file.exists():
        console.print(f"[red]Config not found at {config_file}[/red]")
        console.print("Run [cyan]mao-healer init[/cyan] first")
        raise typer.Exit(1)

    config = HealerConfig.load(config_file)

    # Show config status
    console.print(Panel.fit(
        f"[bold]Configuration[/bold]\n"
        f"Config file: {config_file}\n"
        f"n8n URL: {config.n8n.api_url}\n"
        f"Webhook secret: {'set' if config.n8n.webhook_secret else '[red]not set[/red]'}\n"
        f"API key: {'set' if config.n8n.api_key else '[red]not set[/red]'}\n\n"
        f"[bold]Detection[/bold]\n"
        f"Enabled modes: {', '.join(config.detection.enabled_modes)}\n"
        f"LLM verification: {'enabled' if config.detection.llm_verification else 'disabled'}\n\n"
        f"[bold]Auto-apply[/bold]\n"
        f"Enabled: {'yes' if config.auto_apply.enabled else 'no'}\n"
        f"Max fixes/hour: {config.auto_apply.max_fixes_per_hour}\n"
        f"Git backup: {'enabled' if config.auto_apply.git_backup else 'disabled'}\n"
        f"Git repo: {config.auto_apply.git_repo}\n\n"
        f"[bold]Notifications[/bold]\n"
        f"Discord: {'configured' if config.notifications.discord_webhook else 'not configured'}\n"
        f"Slack: {'configured' if config.notifications.slack_webhook else 'not configured'}\n"
        f"Email: {'configured' if config.notifications.email_to else 'not configured'}",
        title="Pisama Healer Status",
    ))

    # Try to get server status
    import httpx

    try:
        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"http://localhost:{config.server_port}/stats")
            if response.status_code == 200:
                data = response.json()

                console.print("\n[bold green]Server is running![/bold green]\n")

                # Server stats table
                stats = data.get("server_stats", {})
                table = Table(title="Server Statistics")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")

                table.add_row("Webhooks received", str(stats.get("webhooks_received", 0)))
                table.add_row("Detections", str(stats.get("detections", 0)))
                table.add_row("Fixes applied", str(stats.get("fixes_applied", 0)))
                table.add_row("Fixes failed", str(stats.get("fixes_failed", 0)))

                console.print(table)

                # Recent applies
                recent = data.get("recent_applies", [])
                if recent:
                    console.print("\n[bold]Recent Activity[/bold]")
                    apply_table = Table()
                    apply_table.add_column("Time")
                    apply_table.add_column("Workflow")
                    apply_table.add_column("Status")
                    apply_table.add_column("Backup")

                    for r in recent[:5]:
                        status_style = "green" if r.get("success") else "red"
                        apply_table.add_row(
                            r.get("applied_at", "N/A")[:19],
                            r.get("workflow_id", "N/A")[:20],
                            f"[{status_style}]{'Success' if r.get('success') else 'Failed'}[/{status_style}]",
                            r.get("backup_commit_sha", "N/A")[:8] if r.get("backup_commit_sha") else "-",
                        )

                    console.print(apply_table)
            else:
                console.print(f"\n[yellow]Server returned status {response.status_code}[/yellow]")
    except httpx.ConnectError:
        console.print(f"\n[dim]Server not running on port {config.server_port}[/dim]")
        console.print(f"Run [cyan]mao-healer start[/cyan] to start the server")


@app.command()
def test(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Send test notification to configured channels."""
    config_file = config_path or CONFIG_FILE

    if not config_file.exists():
        console.print(f"[red]Config not found at {config_file}[/red]")
        raise typer.Exit(1)

    config = HealerConfig.load(config_file)

    async def send_test():
        from backend.app.notifications import NotificationRouter, NotifyConfig

        notify_config = NotifyConfig(
            discord_webhook=config.notifications.discord_webhook or None,
            slack_webhook=config.notifications.slack_webhook or None,
            email_enabled=bool(config.notifications.email_to),
            email_smtp_host=config.notifications.email_smtp_host,
            email_smtp_port=config.notifications.email_smtp_port,
            email_smtp_user=config.notifications.email_smtp_user or None,
            email_smtp_password=config.notifications.email_smtp_password or None,
            email_from=config.notifications.email_from,
            email_to=[config.notifications.email_to] if config.notifications.email_to else [],
        )

        router = NotificationRouter(notify_config)
        results = await router.test_notifications()
        await router.close()
        return results

    console.print("Sending test notifications...")

    results = asyncio.run(send_test())

    if results.get("discord"):
        console.print("[green]Discord: sent successfully[/green]")
    elif "discord" in results:
        console.print("[red]Discord: failed to send[/red]")
    else:
        console.print("[dim]Discord: not configured[/dim]")

    if results.get("email"):
        console.print("[green]Email: sent successfully[/green]")
    elif "email" in results:
        console.print("[red]Email: failed to send[/red]")
    else:
        console.print("[dim]Email: not configured[/dim]")


@app.command()
def version():
    """Show version information."""
    console.print(f"MAO Healer v{__version__}")


@app.command()
def detections(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of detections to show"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """List recent detections for feedback.

    Shows recent detection results that can be used with the feedback command.
    """
    config_file = config_path or CONFIG_FILE

    if not config_file.exists():
        console.print(f"[red]Config not found at {config_file}[/red]")
        console.print("Run [cyan]mao-healer init[/cyan] first")
        raise typer.Exit(1)

    config = HealerConfig.load(config_file)

    # Try to get recent detections from the server
    import httpx

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"http://localhost:{config.server_port}/api/v1/detections",
                params={"limit": limit},
            )
            if response.status_code == 200:
                data = response.json()
                detections_list = data.get("detections", [])

                if not detections_list:
                    console.print("[yellow]No recent detections found[/yellow]")
                    return

                table = Table(title=f"Recent Detections (last {limit})")
                table.add_column("ID", style="cyan", no_wrap=True)
                table.add_column("Mode", style="green")
                table.add_column("Confidence", justify="right")
                table.add_column("Workflow")
                table.add_column("Time")

                for d in detections_list:
                    det_id = d.get("id", "N/A")[:8]
                    mode = d.get("failure_mode", "N/A")
                    confidence = f"{d.get('confidence', 0):.0f}%"
                    workflow = d.get("workflow_name", "N/A")[:20]
                    timestamp = d.get("created_at", "N/A")[:19]

                    table.add_row(det_id, mode, confidence, workflow, timestamp)

                console.print(table)
                console.print("\n[dim]Use [cyan]mao-healer feedback <id> --correct/--incorrect[/cyan] to provide feedback[/dim]")
            else:
                console.print(f"[yellow]Server returned status {response.status_code}[/yellow]")
    except httpx.ConnectError:
        console.print(f"[red]Cannot connect to server on port {config.server_port}[/red]")
        console.print("Run [cyan]mao-healer start[/cyan] first")


@app.command()
def feedback(
    detection_id: str = typer.Argument(..., help="Detection ID to provide feedback on"),
    correct: bool = typer.Option(..., "--correct/--incorrect", help="Was detection correct?"),
    reason: Optional[str] = typer.Option(None, "--reason", "-r", help="Feedback reason"),
    severity: Optional[int] = typer.Option(None, "--severity", "-s", help="Severity rating 1-5"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Submit feedback on a detection result.

    This feedback is used to improve detection accuracy over time.
    Human graders provide the gold standard for detection evaluation.

    Examples:
        mao-healer feedback abc123 --correct --reason "Valid loop detected"
        mao-healer feedback def456 --incorrect --reason "False positive - legitimate retry"
    """
    config_file = config_path or CONFIG_FILE

    if not config_file.exists():
        console.print(f"[red]Config not found at {config_file}[/red]")
        raise typer.Exit(1)

    config = HealerConfig.load(config_file)

    # Validate severity if provided
    if severity is not None and not (1 <= severity <= 5):
        console.print("[red]Severity must be between 1 and 5[/red]")
        raise typer.Exit(1)

    # Submit feedback to the server
    import httpx

    feedback_data = {
        "detection_id": detection_id,
        "is_correct": correct,
        "reason": reason,
        "severity_rating": severity,
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                f"http://localhost:{config.server_port}/api/v1/feedback",
                json=feedback_data,
            )
            if response.status_code in (200, 201):
                data = response.json()
                feedback_type = "true_positive" if correct else "false_positive"
                console.print(Panel.fit(
                    f"[green]Feedback submitted successfully![/green]\n\n"
                    f"Detection: {detection_id[:8]}...\n"
                    f"Type: {feedback_type}\n"
                    f"Reason: {reason or 'N/A'}\n"
                    f"Severity: {severity or 'N/A'}",
                    title="Feedback Recorded",
                ))
            elif response.status_code == 404:
                console.print(f"[red]Detection '{detection_id}' not found[/red]")
            else:
                error = response.json().get("detail", "Unknown error")
                console.print(f"[red]Failed to submit feedback: {error}[/red]")
    except httpx.ConnectError:
        console.print(f"[red]Cannot connect to server on port {config.server_port}[/red]")
        console.print("Run [cyan]mao-healer start[/cyan] first")


@app.callback()
def callback():
    """MAO Healer - Self-healing agent for n8n workflows."""
    pass


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
