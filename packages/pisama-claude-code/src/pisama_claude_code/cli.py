"""PISAMA Claude Code CLI - Trace capture for Claude Code.

Command-line interface for capturing Claude Code traces and syncing
to the PISAMA platform for analysis and self-healing.

Usage:
    pisama-cc install     Install hooks to ~/.claude/
    pisama-cc uninstall   Remove hooks
    pisama-cc status      Show current status (incl. token/cost totals)
    pisama-cc traces      View recent traces (-v for token usage)
    pisama-cc usage       Show token usage and cost breakdown
    pisama-cc export      Export traces to file
    pisama-cc connect     Connect to PISAMA platform
    pisama-cc sync        Sync traces to platform
    pisama-cc analyze     Analyze traces (requires platform)
"""

import click
import json
import gzip
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None


# Config paths
CLAUDE_DIR = Path.home() / ".claude"
CONFIG_DIR = CLAUDE_DIR / "pisama"
CONFIG_FILE = CONFIG_DIR / "config.json"
TRACES_DIR = CONFIG_DIR / "traces"
HOOKS_DIR = CLAUDE_DIR / "hooks"


def get_config() -> dict:
    """Load PISAMA config."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_config(config: dict):
    """Save PISAMA config."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


@click.group()
@click.version_option(version="0.3.1")
def main():
    """PISAMA Claude Code - Trace capture and sync."""
    pass


@main.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing hooks")
def install(force: bool):
    """Install PISAMA hooks to ~/.claude/hooks/."""
    from pisama_claude_code.install import install as do_install
    do_install(force=force)


@main.command()
def uninstall():
    """Remove PISAMA hooks from ~/.claude/hooks/."""
    from pisama_claude_code.install import uninstall as do_uninstall
    do_uninstall()


@main.command()
@click.option("--last", default=20, help="Number of traces to show")
@click.option("--tool", help="Filter by tool name")
@click.option("--session", help="Filter by session ID")
@click.option("--verbose", "-v", is_flag=True, help="Show token usage and cost")
def traces(last: int, tool: Optional[str], session: Optional[str], verbose: bool):
    """View recent traces."""
    all_traces = load_recent_traces(last * 3)  # Load extra for filtering

    # Apply filters
    if tool:
        all_traces = [t for t in all_traces if t.get("tool_name") == tool]
    if session:
        all_traces = [t for t in all_traces if t.get("session_id") == session]

    traces_to_show = all_traces[-last:]

    if not traces_to_show:
        click.echo("No traces found")
        return

    # Calculate totals
    total_input = sum(t.get("input_tokens", 0) for t in traces_to_show)
    total_output = sum(t.get("output_tokens", 0) for t in traces_to_show)
    total_cost = sum(t.get("cost_usd", 0) for t in traces_to_show)

    click.echo(f"📋 Recent Traces ({len(traces_to_show)} shown)")
    click.echo("=" * 70)

    for t in traces_to_show:
        ts = t.get("timestamp", "")[:19]
        tool_name = t.get("tool_name", "?")[:12].ljust(12)
        sess = t.get("session_id", "?")[:8]
        hook = t.get("hook_type", "?")[:4]

        if verbose:
            inp = t.get("input_tokens", 0)
            out = t.get("output_tokens", 0)
            cost = t.get("cost_usd", 0)
            tokens = f"{inp:>6}i {out:>5}o" if inp or out else "       -      "
            cost_str = f"${cost:.4f}" if cost else "  -    "
            click.echo(f"{ts} | {tool_name} | {sess} | {hook} | {tokens} | {cost_str}")
        else:
            click.echo(f"{ts} | {tool_name} | {sess} | {hook}")

    # Show totals if we have usage data
    if verbose and (total_input or total_output or total_cost):
        click.echo("─" * 70)
        click.echo(f"Totals: {total_input:,} input + {total_output:,} output tokens = ${total_cost:.4f}")


@main.command()
@click.option("--api-key", required=True, help="Your PISAMA API key")
@click.option("--api-url", default="https://api.maotesting.com", help="API base URL")
@click.option("--auto-sync/--no-auto-sync", default=True, help="Enable auto-sync")
def connect(api_key: str, api_url: str, auto_sync: bool):
    """Connect to PISAMA platform."""
    if httpx is None:
        click.echo("❌ httpx required. Run: pip install httpx")
        return

    click.echo("🔗 Connecting to PISAMA platform...")

    # Validate API key
    try:
        response = httpx.get(
            f"{api_url}/v1/health",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if response.status_code == 401:
            click.echo("❌ Invalid API key")
            return
    except httpx.ConnectError:
        click.echo(f"⚠️  Could not reach {api_url} - saving config for later")

    # Save config
    config = get_config()
    config["api_key"] = api_key
    config["api_url"] = api_url
    config["auto_sync"] = auto_sync
    config["connected_at"] = datetime.now(timezone.utc).isoformat()
    save_config(config)

    click.echo("✅ Connected to PISAMA platform")
    click.echo(f"   API URL: {api_url}")
    click.echo(f"   Auto-sync: {'enabled' if auto_sync else 'disabled'}")

    click.echo("\n📡 You can now:")
    click.echo("   pisama-cc sync      - Upload traces to platform")
    click.echo("   pisama-cc analyze   - Run failure detection")


@main.command()
@click.option("--last", default=100, help="Number of recent traces to sync")
@click.option("--include-outputs/--no-outputs", default=False, help="Include tool outputs")
def sync(last: int, include_outputs: bool):
    """Sync traces to PISAMA platform."""
    if httpx is None:
        click.echo("❌ httpx required. Run: pip install httpx")
        return

    config = get_config()

    if not config.get("api_key"):
        click.echo("❌ Not connected. Run 'pisama-cc connect --api-key <key>' first")
        return

    click.echo(f"📤 Syncing last {last} traces...")

    # Load traces
    traces_list = load_recent_traces(last)
    if not traces_list:
        click.echo("No traces found to sync")
        return

    # Prepare payload (redact sensitive data)
    payload = prepare_sync_payload(traces_list, include_outputs)

    click.echo(f"   Found {len(traces_list)} traces")
    click.echo(f"   Payload size: {len(json.dumps(payload)) // 1024} KB")

    # Upload
    try:
        response = httpx.post(
            f"{config['api_url']}/v1/traces/claude-code/ingest",
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        if response.status_code in (200, 201, 202):
            result = response.json()
            click.echo(f"✅ Synced {result.get('traces_received', len(traces_list))} traces")
            click.echo(f"   View at: {config['api_url'].replace('api.', 'app.')}/traces")

            # Mark as synced
            mark_synced(traces_list)
        else:
            click.echo(f"❌ Sync failed: {response.status_code}")
            click.echo(f"   {response.text[:200]}")
    except httpx.ConnectError:
        click.echo(f"❌ Could not connect to {config['api_url']}")
        click.echo("   Traces saved locally, will retry on next sync")


@main.command()
@click.option("--last", default=50, help="Number of recent traces to analyze")
def analyze(last: int):
    """Analyze traces for failures (requires platform connection)."""
    if httpx is None:
        click.echo("❌ httpx required. Run: pip install httpx")
        return

    config = get_config()

    if not config.get("api_key"):
        click.echo("❌ Analysis requires platform connection")
        click.echo("")
        click.echo("Connect to get:")
        click.echo("   • Failure detection (28 MAST modes)")
        click.echo("   • Severity scores & explanations")
        click.echo("   • Fix suggestions")
        click.echo("   • Self-healing capabilities")
        click.echo("")
        click.echo("Run: pisama-cc connect --api-key <your-key>")
        click.echo("Get your key at: https://app.maotesting.com/settings/api")
        return

    click.echo(f"🔍 Analyzing last {last} traces...")

    # Load and sync traces first
    traces_list = load_recent_traces(last)
    if not traces_list:
        click.echo("No traces found")
        return

    # Send to platform for analysis
    try:
        payload = prepare_sync_payload(traces_list, include_outputs=False)
        response = httpx.post(
            f"{config['api_url']}/v1/traces/claude-code/analyze",
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )

        if response.status_code == 200:
            results = response.json()
            display_analysis_results(results)
        else:
            click.echo(f"❌ Analysis failed: {response.status_code}")
            click.echo(f"   {response.text[:200]}")
    except httpx.ConnectError:
        click.echo(f"❌ Could not connect to {config['api_url']}")


def display_analysis_results(results: dict):
    """Display analysis results from platform."""
    detections = results.get("detections", [])
    trace_count = results.get("trace_count", 0)

    click.echo(f"\n📊 Analysis Results ({trace_count} traces)")
    click.echo("=" * 50)

    if not detections:
        click.echo("✅ No issues detected")
        return

    for d in detections:
        severity = d.get("severity", 0)
        if severity >= 70:
            icon = "🔴"
        elif severity >= 40:
            icon = "🟡"
        else:
            icon = "🟢"

        click.echo(f"\n{icon} {d.get('type', 'Unknown')} (severity: {severity}/100)")
        click.echo(f"   {d.get('explanation', '')}")
        if d.get("fix"):
            click.echo(f"   💡 Fix: {d['fix']}")

    # Summary
    click.echo("\n" + "─" * 50)
    click.echo(f"Found {len(detections)} issue(s)")
    click.echo(f"View details at: {results.get('dashboard_url', 'https://app.maotesting.com')}")


@main.command()
def status():
    """Show PISAMA installation and connection status."""
    config_data = get_config()

    click.echo("📊 PISAMA Status")
    click.echo("=" * 40)

    # Check hook installation
    click.echo("\n🔧 Hook Installation:")
    hook_files = [
        "pisama-capture.py",
        "pisama-pre.sh",
        "pisama-post.sh",
    ]
    hooks_installed = 0
    for hf in hook_files:
        hook_path = HOOKS_DIR / hf
        if hook_path.exists():
            hooks_installed += 1
            click.echo(f"   ✅ {hf}")
        else:
            click.echo(f"   ❌ {hf} (missing)")

    if hooks_installed == len(hook_files):
        click.echo("   All hooks installed")
    elif hooks_installed == 0:
        click.echo("   Run 'pisama-cc install' to install hooks")
    else:
        click.echo("   Run 'pisama-cc install --force' to reinstall")

    # Check platform connection
    click.echo("\n🔗 Platform Connection:")
    if config_data.get("api_key"):
        click.echo(f"   ✅ Connected to: {config_data.get('api_url', 'unknown')}")
        connected_at = config_data.get("connected_at", "")
        if connected_at:
            click.echo(f"   Connected at: {connected_at[:19]}")
        click.echo(f"   Auto-sync: {'enabled' if config_data.get('auto_sync') else 'disabled'}")
    else:
        click.echo("   ❌ Not connected")
        click.echo("   Run 'pisama-cc connect --api-key <key>'")

    # Count local traces and calculate totals
    trace_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    models_used = set()

    if TRACES_DIR.exists():
        for tf in TRACES_DIR.glob("traces-*.jsonl"):
            with open(tf) as f:
                for line in f:
                    trace_count += 1
                    try:
                        t = json.loads(line)
                        usage = t.get("usage", {})
                        if usage:
                            total_input_tokens += usage.get("input_tokens", 0)
                            total_output_tokens += usage.get("output_tokens", 0)
                        total_cost += t.get("cost_usd", 0) or 0
                        if t.get("model"):
                            models_used.add(t.get("model"))
                    except json.JSONDecodeError:
                        pass

    click.echo(f"\n📁 Local Traces: {trace_count}")
    if total_input_tokens or total_output_tokens:
        click.echo(f"   Input tokens:  {total_input_tokens:,}")
        click.echo(f"   Output tokens: {total_output_tokens:,}")
        click.echo(f"   Total cost:    ${total_cost:.4f}")
    if models_used:
        click.echo(f"   Models: {', '.join(sorted(models_used))}")

    # Check Claude Code settings for hook integration
    settings_file = Path.home() / ".claude" / "settings.local.json"
    if not settings_file.exists():
        settings_file = Path.home() / ".claude" / "settings.json"

    click.echo("\n📝 Claude Code Settings:")
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
            hooks = settings.get("hooks", {})
            pre_hooks = hooks.get("PreToolCall", [])
            post_hooks = hooks.get("PostToolCall", [])

            pisama_in_pre = any("pisama" in str(h).lower() for h in pre_hooks)
            pisama_in_post = any("pisama" in str(h).lower() for h in post_hooks)

            if pisama_in_pre and pisama_in_post:
                click.echo("   ✅ PISAMA hooks configured in settings")
            elif pisama_in_pre or pisama_in_post:
                click.echo("   ⚠️  PISAMA hooks partially configured")
            else:
                click.echo("   ❌ PISAMA hooks not in settings")
                click.echo("   Add hooks to settings.local.json (see 'pisama-cc install' output)")
        except json.JSONDecodeError:
            click.echo("   ⚠️  Could not parse settings file")
    else:
        click.echo("   ❌ No settings file found")


@main.command()
@click.option("--last", default=100, help="Number of traces to analyze")
@click.option("--by-model", is_flag=True, help="Group by model")
@click.option("--by-tool", is_flag=True, help="Group by tool")
def usage(last: int, by_model: bool, by_tool: bool):
    """Show token usage and cost breakdown."""
    traces_list = load_recent_traces(last)

    if not traces_list:
        click.echo("No traces found")
        return

    # Calculate totals
    total_input = sum(t.get("input_tokens", 0) for t in traces_list)
    total_output = sum(t.get("output_tokens", 0) for t in traces_list)
    total_cache = sum(t.get("cache_read_tokens", 0) for t in traces_list)
    total_cost = sum(t.get("cost_usd", 0) for t in traces_list)

    click.echo(f"📊 Token Usage Summary (last {len(traces_list)} traces)")
    click.echo("=" * 50)
    click.echo(f"Input tokens:      {total_input:>12,}")
    click.echo(f"Output tokens:     {total_output:>12,}")
    click.echo(f"Cache read tokens: {total_cache:>12,}")
    click.echo(f"Total tokens:      {total_input + total_output:>12,}")
    click.echo(f"Total cost:        ${total_cost:>11.4f}")

    if by_model:
        click.echo("\n📈 By Model:")
        click.echo("-" * 50)
        model_stats = {}
        for t in traces_list:
            model = t.get("model") or "unknown"
            if model not in model_stats:
                model_stats[model] = {"input": 0, "output": 0, "cost": 0}
            model_stats[model]["input"] += t.get("input_tokens", 0)
            model_stats[model]["output"] += t.get("output_tokens", 0)
            model_stats[model]["cost"] += t.get("cost_usd", 0)

        for model, stats in sorted(model_stats.items(), key=lambda x: -x[1]["cost"]):
            if stats["cost"] > 0:
                click.echo(f"  {model[:35]:<35} ${stats['cost']:.4f}")

    if by_tool:
        click.echo("\n🔧 By Tool:")
        click.echo("-" * 50)
        tool_stats = {}
        for t in traces_list:
            tool = t.get("tool_name") or "unknown"
            if tool not in tool_stats:
                tool_stats[tool] = {"count": 0, "cost": 0}
            tool_stats[tool]["count"] += 1
            tool_stats[tool]["cost"] += t.get("cost_usd", 0)

        for tool, stats in sorted(tool_stats.items(), key=lambda x: -x[1]["count"]):
            click.echo(f"  {tool:<20} {stats['count']:>5} calls  ${stats['cost']:.4f}")


@main.command()
@click.option("--last", default=50, help="Number of traces to export")
@click.option("--output", "-o", default="traces-export.jsonl", help="Output file")
@click.option("--compress", is_flag=True, help="Gzip compress output")
def export(last: int, output: str, compress: bool):
    """Export traces to a file."""
    traces_list = load_recent_traces(last)

    if not traces_list:
        click.echo("No traces to export")
        return

    # Prepare export (redact sensitive data)
    export_data = []
    for t in traces_list:
        clean = {
            "timestamp": t.get("timestamp"),
            "tool_name": t.get("tool_name"),
            "hook_type": t.get("hook_type"),
            "session_id": t.get("session_id"),
            # New fields
            "model": t.get("model"),
            "input_tokens": t.get("input_tokens"),
            "output_tokens": t.get("output_tokens"),
            "cache_read_tokens": t.get("cache_read_tokens"),
            "cost_usd": t.get("cost_usd"),
        }
        # Include sanitized input
        inp = t.get("tool_input", {})
        if isinstance(inp, dict):
            clean["tool_input"] = sanitize_input(inp)
        export_data.append(clean)

    output_path = Path(output)

    # Ensure parent directory exists
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        click.echo(f"❌ Cannot create directory: {e}")
        return

    if compress or output.endswith(".gz"):
        if not output.endswith(".gz"):
            output_path = Path(output + ".gz")
        with gzip.open(output_path, "wt") as f:
            for trace in export_data:
                f.write(json.dumps(trace) + "\n")
    else:
        with open(output_path, "w") as f:
            for trace in export_data:
                f.write(json.dumps(trace) + "\n")

    size_kb = output_path.stat().st_size // 1024
    click.echo(f"✅ Exported {len(export_data)} traces to {output_path} ({size_kb} KB)")


# Helper functions

def normalize_trace(t: dict) -> dict:
    """Normalize trace to consistent format (handles old and new formats)."""
    # New format uses 'name', old uses 'tool_name'
    tool_name = t.get("tool_name") or t.get("name")

    # New format uses 'start_time', old uses 'timestamp'
    timestamp = t.get("timestamp") or t.get("start_time")

    # New format puts hook_type in attributes, old has it at top level
    attrs = t.get("attributes", {})
    hook_type = t.get("hook_type") or attrs.get("hook_type", "")

    # Normalize hook_type (pre -> PreToolUse, post -> PostToolUse)
    if hook_type == "pre":
        hook_type = "PreToolUse"
    elif hook_type == "post":
        hook_type = "PostToolUse"

    # New format uses 'input_data', old uses 'tool_input'
    tool_input = t.get("tool_input") or t.get("input_data", {})

    # Session ID might be in different places
    session_id = t.get("session_id") or t.get("trace_id", "")[:8]

    # Extract usage data (new fields)
    usage = t.get("usage", {})
    input_tokens = usage.get("input_tokens", 0) if usage else 0
    output_tokens = usage.get("output_tokens", 0) if usage else 0
    cache_read = usage.get("cache_read_input_tokens", 0) if usage else 0

    return {
        "tool_name": tool_name,
        "timestamp": timestamp,
        "hook_type": hook_type,
        "session_id": session_id,
        "tool_input": tool_input,
        "working_dir": t.get("working_dir") or attrs.get("working_dir", ""),
        # New fields
        "model": t.get("model"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read,
        "cost_usd": t.get("cost_usd", 0.0),
        "ai_response": t.get("ai_response"),
        "_raw": t,
    }


def load_recent_traces(n: int) -> list:
    """Load recent traces from local storage."""
    if n <= 0:
        return []

    traces = []
    if not TRACES_DIR.exists():
        return traces

    for tf in sorted(TRACES_DIR.glob("traces-*.jsonl"), reverse=True):
        try:
            with open(tf) as f:
                for line in f:
                    try:
                        raw = json.loads(line)
                        traces.append(normalize_trace(raw))
                    except json.JSONDecodeError:
                        continue  # Skip invalid JSON lines
        except OSError:
            continue  # Skip files that can't be read
        if len(traces) >= n:
            break

    return traces[-n:]


def prepare_sync_payload(traces: list, include_outputs: bool) -> dict:
    """Prepare traces for sync, redacting sensitive data."""
    clean_traces = []

    for t in traces:
        clean = {
            "timestamp": t.get("timestamp"),
            "tool_name": t.get("tool_name"),
            "hook_type": t.get("hook_type"),
            "session_id": t.get("session_id"),
            "working_dir": anonymize_path(t.get("working_dir", "")),
        }

        # Sanitize input
        inp = t.get("tool_input", {})
        if isinstance(inp, dict):
            clean["tool_input"] = sanitize_input(inp)

        # Optionally include output
        if include_outputs:
            out = t.get("tool_output")
            if out and len(str(out)) < 1000:
                clean["tool_output"] = out

        clean_traces.append(clean)

    return {
        "source": "claude-code",
        "version": "0.3.0",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "trace_count": len(clean_traces),
        "traces": clean_traces,
    }


def sanitize_input(inp: dict) -> dict:
    """Remove sensitive data from tool input."""
    clean = {}
    sensitive_keys = {"api_key", "password", "secret", "token", "credential"}

    for k, v in inp.items():
        # Skip sensitive keys
        if any(s in k.lower() for s in sensitive_keys):
            clean[k] = "[REDACTED]"
        # Anonymize file paths
        elif k in ("file_path", "path"):
            clean[k] = anonymize_path(str(v))
        # Truncate large values
        elif isinstance(v, str) and len(v) > 500:
            clean[k] = v[:500] + "...[truncated]"
        else:
            clean[k] = v

    return clean


def anonymize_path(path: str) -> str:
    """Anonymize user-specific parts of paths."""
    if not path:
        return path
    # Replace home directory with ~
    home = str(Path.home())
    return path.replace(home, "~")


def mark_synced(traces: list):
    """Mark traces as synced (for deduplication)."""
    sync_log = CONFIG_DIR / "sync_log.jsonl"
    with open(sync_log, "a") as f:
        for t in traces:
            f.write(json.dumps({
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "timestamp": t.get("timestamp"),
                "session_id": t.get("session_id"),
            }) + "\n")


if __name__ == "__main__":
    main()
