"""CLI runner for synthetic customer agents."""

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

from .account import AccountManager
from .base import AgentReport
from .agents import ALL_AGENTS

console = Console()


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False, show_time=False)],
    )


def print_report(reports: list[AgentReport]) -> None:
    """Print a summary table of all agent results."""
    table = Table(title="Synthetic Agent Results", show_lines=True)
    table.add_column("Agent", style="bold")
    table.add_column("Steps", justify="right")
    table.add_column("Passed", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Errors", justify="right", style="red")
    table.add_column("Duration", justify="right")
    table.add_column("Status", justify="center")

    total_passed = 0
    total_failed = 0
    total_errors = 0

    for r in reports:
        status = "[green]PASS[/green]" if r.ok else "[red]FAIL[/red]"
        table.add_row(
            r.agent_name,
            str(r.steps_run),
            str(r.passed),
            str(r.failed),
            str(len(r.errors)),
            f"{r.duration_s:.1f}s",
            status,
        )
        total_passed += r.passed
        total_failed += r.failed
        total_errors += len(r.errors)

    console.print()
    console.print(table)
    console.print()

    # Print failures detail
    for r in reports:
        failed_assertions = [a for a in r.assertions if not a.passed]
        if failed_assertions:
            console.print(f"[red bold]{r.agent_name} failures:[/red bold]")
            for a in failed_assertions:
                console.print(f"  [red]x[/red] {a.name}: {a.detail}")
        if r.errors:
            console.print(f"[red bold]{r.agent_name} errors:[/red bold]")
            for e in r.errors:
                console.print(f"  [red]![/red] {e}")

    # Summary line
    all_ok = total_failed == 0 and total_errors == 0
    if all_ok:
        console.print(f"[green bold]All {total_passed} assertions passed across {len(reports)} agents[/green bold]")
    else:
        console.print(
            f"[red bold]{total_failed} failures, {total_errors} errors "
            f"out of {total_passed + total_failed} assertions across {len(reports)} agents[/red bold]"
        )


async def run_agents(
    target: str,
    agent_names: list[str],
    reuse_tenants: bool,
    parallel: bool,
) -> list[AgentReport]:
    """Run specified agents and return their reports."""
    account_mgr = AccountManager(base_url=target)

    # Create accounts
    console.print(f"[bold]Setting up accounts for {len(agent_names)} agents...[/bold]")
    accounts = await account_mgr.ensure_accounts(agent_names, reuse=reuse_tenants)

    # Instantiate agents
    agents = []
    for name in agent_names:
        agent_cls = ALL_AGENTS[name]
        creds = accounts[name]
        agent = agent_cls(
            base_url=target,
            api_key=creds.api_key,
            tenant_id=creds.tenant_id,
        )
        agents.append(agent)

    # Run
    if parallel:
        console.print("[bold]Running agents in parallel...[/bold]")
        reports = await asyncio.gather(*[a.run() for a in agents])
    else:
        reports = []
        for agent in agents:
            console.print(f"[bold]Running {agent.name}...[/bold]")
            report = await agent.run()
            reports.append(report)

    return list(reports)


@click.group()
def cli() -> None:
    """Pisama Synthetic Customer Agents."""
    pass


@cli.command()
@click.option("--target", "-t", required=True, help="Pisama backend URL (e.g., http://localhost:8000)")
@click.option("--agents", "-a", default="all", help="Comma-separated agent names or 'all'")
@click.option("--reuse-tenants", is_flag=True, help="Reuse existing tenant accounts if available")
@click.option("--parallel", is_flag=True, help="Run agents in parallel (use for local dev only)")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def run(target: str, agents: str, reuse_tenants: bool, parallel: bool, verbose: bool) -> None:
    """Run synthetic customer agents against a Pisama instance."""
    setup_logging(verbose)

    if agents == "all":
        agent_names = list(ALL_AGENTS.keys())
    else:
        agent_names = [a.strip() for a in agents.split(",")]
        invalid = [a for a in agent_names if a not in ALL_AGENTS]
        if invalid:
            console.print(f"[red]Unknown agents: {', '.join(invalid)}[/red]")
            console.print(f"Available: {', '.join(ALL_AGENTS.keys())}")
            sys.exit(1)

    console.print(f"[bold]Target:[/bold] {target}")
    console.print(f"[bold]Agents:[/bold] {', '.join(agent_names)}")
    console.print()

    reports = asyncio.run(run_agents(target, agent_names, reuse_tenants, parallel))
    print_report(reports)

    # Exit code
    all_ok = all(r.ok for r in reports)
    sys.exit(0 if all_ok else 1)


@cli.command()
@click.option("--target", "-t", required=True, help="Pisama backend URL")
@click.option("--max-age", default=24.0, help="Max age in hours before cleanup (default: 24)")
def cleanup(target: str, max_age: float) -> None:
    """Clean up old synthetic tenant accounts."""
    setup_logging()

    async def _cleanup() -> int:
        mgr = AccountManager(base_url=target)
        return await mgr.cleanup(max_age_hours=max_age)

    removed = asyncio.run(_cleanup())
    console.print(f"Cleaned up {removed} accounts")


@cli.command(name="list")
def list_agents() -> None:
    """List available synthetic agents."""
    table = Table(title="Available Agents")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    for name, cls in ALL_AGENTS.items():
        table.add_row(name, cls.description)
    console.print(table)


@cli.command()
@click.option("--target", "-t", required=True, help="Pisama backend URL")
def status(target: str) -> None:
    """Show what each synth agent created in the platform."""
    setup_logging(verbose=False)

    import httpx

    base = target.rstrip("/")
    synth_resp = httpx.get(f"{base}/api/v1/auth/synth-tenants", timeout=10)
    synth_data = synth_resp.json()
    tenants = synth_data.get("tenants", [])

    if not tenants:
        console.print("[yellow]No synth tenants found[/yellow]")
        return

    # Overview table
    table = Table(title="Synth Agent Platform Data", show_lines=True)
    table.add_column("Agent", style="bold")
    table.add_column("Tenant", style="dim")
    table.add_column("Traces", justify="right")
    table.add_column("Detections", justify="right")
    table.add_column("Healings", justify="right")

    for t in tenants:
        table.add_row(
            t["agent_name"],
            t["id"][:8] + "...",
            str(t["traces"]),
            str(t["detections"]),
            str(t["healings"]),
        )

    console.print()
    console.print(table)

    # Detail per agent with data
    for t in tenants:
        if t["traces"] == 0 and t["detections"] == 0:
            continue

        # Get a token for this tenant
        imp_resp = httpx.post(f"{base}/api/v1/auth/synth-tenants/{t['id']}/impersonate", timeout=10)
        token = imp_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        tid = t["id"]

        console.print(f"\n[bold cyan]--- {t['agent_name'].upper()} ---[/bold cyan]")

        # Traces
        if t["traces"] > 0:
            traces_resp = httpx.get(f"{base}/api/v1/tenants/{tid}/traces", headers=headers, timeout=10)
            traces = traces_resp.json().get("traces", [])
            trace_table = Table(title=f"Traces ({len(traces)})", show_lines=False)
            trace_table.add_column("ID", style="dim")
            trace_table.add_column("Framework")
            trace_table.add_column("States", justify="right")
            trace_table.add_column("Detections", justify="right")
            trace_table.add_column("Tokens", justify="right")
            for tr in traces:
                trace_table.add_row(
                    str(tr["id"])[:8] + "...",
                    tr.get("framework", "?"),
                    str(tr.get("state_count", 0)),
                    str(tr.get("detection_count", 0)),
                    str(tr.get("total_tokens", 0)),
                )
            console.print(trace_table)

        # Detections
        if t["detections"] > 0:
            det_resp = httpx.get(f"{base}/api/v1/tenants/{tid}/detections", headers=headers, timeout=10)
            dets = det_resp.json().get("items", [])
            det_table = Table(title=f"Detections ({len(dets)})", show_lines=False)
            det_table.add_column("Type")
            det_table.add_column("Confidence", justify="right")
            det_table.add_column("Method")
            det_table.add_column("Tier")
            for d in dets:
                det_table.add_row(
                    d.get("detection_type", "?"),
                    str(d.get("confidence", 0)),
                    d.get("method", "?"),
                    d.get("confidence_tier", "?"),
                )
            console.print(det_table)

        # Healing
        if t["healings"] > 0:
            heal_resp = httpx.get(f"{base}/api/v1/tenants/{tid}/healing", headers=headers, timeout=10)
            heals = heal_resp.json().get("items", [])
            heal_table = Table(title=f"Healing Records ({len(heals)})", show_lines=False)
            heal_table.add_column("Status")
            heal_table.add_column("Fix Type")
            heal_table.add_column("Approved By")
            for h in heals:
                heal_table.add_row(
                    h.get("status", "?"),
                    h.get("fix_type", "?"),
                    h.get("approved_by") or "-",
                )
            console.print(heal_table)


if __name__ == "__main__":
    cli()
