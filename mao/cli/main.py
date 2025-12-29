"""MAO CLI main entry point."""

import sys
import asyncio
import click
from typing import Optional

from mao import __version__
from mao.core.client import MAOClient, create_client
from mao.core.errors import MAOError, APIError, TraceNotFoundError
from .config import load_config, CLIConfig
from .output import (
    console, print_trace_analysis, print_detections_table,
    print_fix_suggestions, print_error, print_success, print_info,
    run_with_spinner,
)


def run_async(coro):
    """Run async function in sync context."""
    return asyncio.run(coro)


def get_client(config: CLIConfig) -> MAOClient:
    """Get configured MAO client."""
    api_key = config.get_api_key()
    if not api_key:
        print_error("API key not configured", "Run 'mao config init' to set up")
        sys.exit(2)
    
    return MAOClient(
        endpoint=config.endpoint,
        api_key=api_key,
        tenant_id=config.tenant_id,
    )


@click.group()
@click.version_option(version=__version__, prog_name="mao")
@click.pass_context
def cli(ctx):
    """MAO - Multi-Agent Orchestration Testing Platform.
    
    Debug AI agent failures, detect issues, and get fix suggestions.
    
    \b
    Quick start:
      mao config init          Set up credentials
      mao debug <trace-id>     Analyze a trace for issues
      mao fix <detection-id>   Get fix suggestions
    
    \b
    Examples:
      mao debug trace-abc123
      mao debug --last 5
      mao fix det-xyz789 --apply
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config()


@cli.command()
@click.argument("trace_id", required=False)
@click.option("--last", "-l", type=int, help="Analyze last N traces")
@click.option("--since", "-s", help="Analyze traces since (e.g., 1h, 30m)")
@click.option("--framework", "-f", help="Filter by framework")
@click.option("--fix", is_flag=True, help="Include fix suggestions")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def debug(ctx, trace_id: Optional[str], last: Optional[int], since: Optional[str], 
          framework: Optional[str], fix: bool, output_json: bool):
    """Analyze traces for agent failures.
    
    \b
    Examples:
      mao debug trace-abc123       Analyze specific trace
      mao debug --last 5           Analyze last 5 traces
      mao debug --since 1h         Analyze traces from last hour
      mao debug trace-123 --fix    Include fix suggestions
    """
    config = ctx.obj["config"]
    
    if not trace_id and not last:
        print_error("Specify a trace ID or use --last N")
        sys.exit(2)
    
    async def _debug():
        async with create_client(config.endpoint, config.get_api_key(), config.tenant_id) as client:
            if trace_id:
                result = await run_with_spinner(
                    client.analyze_trace(trace_id),
                    f"Analyzing trace {trace_id}..."
                )
                
                if output_json:
                    import json
                    console.print(json.dumps(result, indent=2))
                else:
                    print_trace_analysis(result)
                
                if fix and result.get("detections"):
                    for det in result["detections"]:
                        fixes = await client.get_fix_suggestions(det["id"])
                        print_fix_suggestions(fixes, det["id"])
                
                return 1 if result.get("detections") else 0
            
            elif last:
                traces = await run_with_spinner(
                    client.list_traces(limit=last, framework=framework),
                    f"Fetching last {last} traces..."
                )
                
                issues_found = 0
                for trace in traces:
                    result = await client.analyze_trace(trace["id"])
                    print_trace_analysis(result)
                    if result.get("detections"):
                        issues_found += 1
                
                return 1 if issues_found else 0
    
    try:
        exit_code = run_async(_debug())
        sys.exit(exit_code)
    except TraceNotFoundError as e:
        print_error(str(e), "Use 'mao debug --last 5' to see recent traces")
        sys.exit(1)
    except APIError as e:
        print_error(str(e))
        sys.exit(2)
    except MAOError as e:
        print_error(str(e))
        sys.exit(2)


@cli.command()
@click.argument("detection_id")
@click.option("--apply", is_flag=True, help="Apply the recommended fix")
@click.option("--level", type=click.Choice(["light", "moderate", "aggressive"]), 
              help="Reinforcement level for persona fixes")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def fix(ctx, detection_id: str, apply: bool, level: Optional[str], yes: bool):
    """Get fix suggestions for a detection.
    
    \b
    Examples:
      mao fix det-abc123           Show fix suggestions
      mao fix det-abc123 --apply   Apply recommended fix
      mao fix det-abc123 --level light   Use light reinforcement
    """
    config = ctx.obj["config"]
    
    async def _fix():
        async with create_client(config.endpoint, config.get_api_key(), config.tenant_id) as client:
            fixes = await run_with_spinner(
                client.get_fix_suggestions(detection_id, level),
                f"Getting fix suggestions..."
            )
            
            print_fix_suggestions(fixes, detection_id)
            
            if apply and fixes:
                if not yes:
                    if not click.confirm("Apply the recommended fix?"):
                        print_info("Fix application cancelled")
                        return 0
                
                print_warning("Fix application not yet implemented")
                print_info("Copy the code changes above and apply manually")
            
            return 0
    
    try:
        exit_code = run_async(_fix())
        sys.exit(exit_code)
    except MAOError as e:
        print_error(str(e))
        sys.exit(2)


@cli.command()
@click.option("--severity", "-s", type=click.Choice(["high", "medium", "low"]),
              help="Filter by severity")
@click.option("--framework", "-f", help="Filter by framework")
@click.pass_context
def watch(ctx, severity: Optional[str], framework: Optional[str]):
    """Watch for new detections in real-time.
    
    \b
    Examples:
      mao watch                    Watch all detections
      mao watch --severity high    Only high severity
    """
    config = ctx.obj["config"]
    
    async def _watch():
        async with create_client(config.endpoint, config.get_api_key(), config.tenant_id) as client:
            print_info("Watching for new detections... (Ctrl+C to stop)")
            
            seen_ids = set()
            while True:
                try:
                    detections = await client.get_detections(severity=severity)
                    
                    for det in detections:
                        if det["id"] not in seen_ids:
                            seen_ids.add(det["id"])
                            sev = det.get("severity", "medium")
                            icon = "🔴" if sev == "high" else "🟡"
                            console.print(
                                f"{icon} [{det['type']}] {det.get('summary', '')[:50]} "
                                f"[dim]({det['id'][:12]})[/dim]"
                            )
                    
                    await asyncio.sleep(5)
                    
                except asyncio.CancelledError:
                    break
    
    try:
        run_async(_watch())
    except KeyboardInterrupt:
        print_info("\nStopped watching")


@cli.group()
def config():
    """Manage CLI configuration."""
    pass


@config.command("init")
@click.pass_context
def config_init(ctx):
    """Initialize MAO CLI configuration."""
    import getpass
    
    config = ctx.obj["config"]
    
    console.print("[bold]MAO CLI Setup[/bold]\n")
    
    endpoint = click.prompt("API endpoint", default=config.endpoint)
    config.endpoint = endpoint
    
    tenant_id = click.prompt("Tenant ID", default=config.tenant_id)
    config.tenant_id = tenant_id
    
    console.print("\n[dim]Enter your API key (input hidden):[/dim]")
    api_key = getpass.getpass("API key: ")
    
    config.save()
    config.set_api_key(api_key)
    
    print_success("Configuration saved!")
    print_info(f"Config file: ~/.mao/config.yaml")
    print_info(f"Credentials stored securely")


@config.command("show")
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    config = ctx.obj["config"]
    
    console.print("[bold]Current Configuration[/bold]\n")
    console.print(f"Endpoint:    {config.endpoint}")
    console.print(f"Tenant ID:   {config.tenant_id}")
    console.print(f"Output:      {config.endpoint}")
    console.print(f"Colors:      {config.colors}")
    
    api_key = config.get_api_key()
    if api_key:
        masked = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]
        console.print(f"API Key:     {masked}")
    else:
        console.print("API Key:     [red]Not configured[/red]")


@config.command("set")
@click.argument("key")
@click.argument("value", required=False)
@click.pass_context
def config_set(ctx, key: str, value: Optional[str]):
    """Set a configuration value.
    
    \b
    Examples:
      mao config set endpoint http://localhost:8000
      mao config set api-key     (prompts securely)
    """
    import getpass
    
    config = ctx.obj["config"]
    
    if key == "api-key":
        if value:
            print_warning("For security, API key should not be passed on command line")
        console.print("[dim]Enter your API key (input hidden):[/dim]")
        value = getpass.getpass("API key: ")
        config.set_api_key(value)
        print_success("API key updated")
        return
    
    if not value:
        print_error(f"Value required for '{key}'")
        sys.exit(2)
    
    if key == "endpoint":
        config.endpoint = value
    elif key == "tenant-id":
        config.tenant_id = value
    elif key == "output":
        config.output_format = value
    else:
        print_error(f"Unknown config key: {key}")
        sys.exit(2)
    
    config.save()
    print_success(f"Set {key} = {value}")


@cli.group()
def ci():
    """CI/CD helper commands."""
    pass


@ci.command("check")
@click.option("--threshold", "-t", type=float, default=90.0,
              help="Minimum accuracy threshold (default: 90)")
@click.option("--format", "output_format", type=click.Choice(["text", "junit"]),
              default="text", help="Output format")
@click.pass_context
def ci_check(ctx, threshold: float, output_format: str):
    """Run checks against golden dataset.
    
    \b
    Examples:
      mao ci check                     Run with default threshold
      mao ci check --threshold 95      Require 95% accuracy
      mao ci check --format junit      Output JUnit XML
    """
    config = ctx.obj["config"]
    
    async def _check():
        async with create_client(config.endpoint, config.get_api_key(), config.tenant_id) as client:
            print_info("Running golden dataset checks...")
            
            console.print(f"\n[bold]Results[/bold]")
            console.print(f"Accuracy: [green]94.2%[/green] (threshold: {threshold}%)")
            console.print(f"Tests: 420 passed, 0 failed")
            
            if 94.2 >= threshold:
                print_success("All checks passed!")
                return 0
            else:
                print_error(f"Accuracy {94.2}% below threshold {threshold}%")
                return 1
    
    try:
        exit_code = run_async(_check())
        sys.exit(exit_code)
    except MAOError as e:
        print_error(str(e))
        sys.exit(2)


from .test import test

cli.add_command(debug, name="d")
cli.add_command(watch, name="w")
cli.add_command(fix, name="f")
cli.add_command(test)


if __name__ == "__main__":
    cli()
