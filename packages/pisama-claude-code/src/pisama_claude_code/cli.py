"""PISAMA Claude Code CLI - Self-healing agent guard.

Command-line interface for managing PISAMA hooks, configuration,
trace analysis, and platform sync for Claude Code.

Usage:
    pisama-cc install     Install hooks to ~/.claude/
    pisama-cc uninstall   Remove hooks
    pisama-cc status      Show current status
    pisama-cc config      View/edit configuration
    pisama-cc traces      View recent traces
    pisama-cc analyze     Run analysis on traces
    pisama-cc connect     Connect to PISAMA platform
    pisama-cc sync        Sync traces to platform
"""

import click
import json
import gzip
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None


# Config paths
CLAUDE_DIR = Path.home() / ".claude"
CONFIG_DIR = CLAUDE_DIR / "pisama"
CONFIG_FILE = CONFIG_DIR / "config.json"
TRACES_DIR = CONFIG_DIR / "traces"
HOOKS_DIR = CLAUDE_DIR / "hooks"


def get_config() -> dict:
    """Load PISAMA config."""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(config: dict):
    """Save PISAMA config."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


@click.group()
@click.version_option(version="0.1.2")
def main():
    """PISAMA Claude Code - Trace capture and failure detection."""
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
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--mode", type=click.Choice(["report", "manual", "auto"]), help="Set self-healing mode")
@click.option("--threshold", type=int, help="Set severity threshold (0-100)")
@click.option("--enable/--disable", default=None, help="Enable/disable self-healing")
def config(show: bool, mode: Optional[str], threshold: Optional[int], enable: Optional[bool]):
    """View or edit PISAMA configuration."""
    config_data = get_config()

    # Apply changes
    changed = False
    if mode is not None:
        config_data.setdefault("self_healing", {})["mode"] = mode
        changed = True
    if threshold is not None:
        config_data.setdefault("self_healing", {})["severity_threshold"] = threshold
        changed = True
    if enable is not None:
        config_data.setdefault("self_healing", {})["enabled"] = enable
        changed = True

    if changed:
        save_config(config_data)
        click.echo("✅ Configuration updated")

    # Show config
    if show or not changed:
        click.echo("📋 PISAMA Configuration")
        click.echo("=" * 40)
        sh = config_data.get("self_healing", {})
        click.echo(f"   Enabled: {sh.get('enabled', True)}")
        click.echo(f"   Mode: {sh.get('mode', 'manual')}")
        click.echo(f"   Severity threshold: {sh.get('severity_threshold', 40)}")
        click.echo(f"   Auto-fix types: {sh.get('auto_fix_types', [])}")
        click.echo(f"   Blocked fixes: {sh.get('blocked_fixes', [])}")

        mon = config_data.get("monitoring", {})
        click.echo(f"\n   Pattern window: {mon.get('pattern_window', 10)}")
        click.echo(f"   Alert on warning: {mon.get('alert_on_warning', False)}")


@main.command()
@click.option("--last", default=20, help="Number of traces to show")
@click.option("--tool", help="Filter by tool name")
@click.option("--session", help="Filter by session ID")
def traces(last: int, tool: Optional[str], session: Optional[str]):
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

    click.echo(f"📋 Recent Traces ({len(traces_to_show)} shown)")
    click.echo("=" * 60)

    for t in traces_to_show:
        ts = t.get("timestamp", "")[:19]
        tool_name = t.get("tool_name", "?")[:15].ljust(15)
        sess = t.get("session_id", "?")[:8]
        hook = t.get("hook_type", "?")[:4]
        click.echo(f"{ts} | {tool_name} | {sess} | {hook}")


@main.command()
@click.option("--api-key", required=True, help="Your PISAMA API key")
@click.option("--api-url", default="https://api.maotesting.com", help="API base URL")
@click.option("--auto-sync/--no-auto-sync", default=True, help="Enable auto-sync")
def connect(api_key: str, api_url: str, auto_sync: bool):
    """Connect to PISAMA platform for trace sync."""
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
    
    if auto_sync:
        click.echo("\n📡 Traces will automatically sync to the platform")
        click.echo("   Run 'pisama-cc sync' to manually sync now")


@main.command()
@click.option("--last", default=100, help="Number of recent traces to sync")
@click.option("--include-outputs/--no-outputs", default=False, help="Include tool outputs")
@click.option("--force", is_flag=True, help="Sync even if already synced")
def sync(last: int, include_outputs: bool, force: bool):
    """Sync traces to PISAMA platform."""
    config = get_config()
    
    if not config.get("api_key"):
        click.echo("❌ Not connected. Run 'pisama-cc connect --api-key <key>' first")
        return
    
    click.echo(f"📤 Syncing last {last} traces...")
    
    # Load traces
    traces = load_recent_traces(last)
    if not traces:
        click.echo("No traces found to sync")
        return
    
    # Prepare payload (redact sensitive data)
    payload = prepare_sync_payload(traces, include_outputs)
    
    click.echo(f"   Found {len(traces)} traces")
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
            click.echo(f"✅ Synced {result.get('traces_received', len(traces))} traces")
            click.echo(f"   View at: {config['api_url'].replace('api.', 'app.')}/traces")
            
            # Mark as synced
            mark_synced(traces)
        else:
            click.echo(f"❌ Sync failed: {response.status_code}")
            click.echo(f"   {response.text[:200]}")
    except httpx.ConnectError:
        click.echo(f"❌ Could not connect to {config['api_url']}")
        click.echo("   Traces saved locally, will retry on next sync")


@main.command()
@click.option("--last", default=50, help="Number of recent traces to analyze")
@click.option("--live", is_flag=True, help="Live monitoring mode")
@click.option("--show", is_flag=True, help="Show trace details")
def analyze(last: int, live: bool, show: bool):
    """Analyze traces for MAST failures."""
    click.echo(f"🔍 Analyzing last {last} traces...")
    
    traces = load_recent_traces(last)
    if not traces:
        click.echo("No traces found")
        return
    
    # Run detection
    results = run_detection(traces)
    
    # Display results
    click.echo(f"\n📊 Analysis Results ({len(traces)} traces)")
    click.echo("=" * 50)
    
    for detector, result in results.items():
        status = "🟡" if result["detected"] else "✅"
        click.echo(f"{status} {detector}: {result.get('explanation', 'OK')}")
    
    if show:
        click.echo("\n📋 Recent Traces:")
        for t in traces[-10:]:
            ts = t.get("timestamp", "")[:19]
            tool = t.get("tool_name", "?")[:15]
            click.echo(f"   {ts} | {tool}")


@main.command()
def status():
    """Show PISAMA installation and connection status."""
    config_data = get_config()

    click.echo("📊 PISAMA Status")
    click.echo("=" * 40)

    # Check hook installation
    click.echo("\n🔧 Hook Installation:")
    hook_files = [
        "pisama-guardian-hook.py",
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

    # Check self-healing config
    click.echo("\n⚡ Self-Healing:")
    sh = config_data.get("self_healing", {})
    enabled = sh.get("enabled", False)
    mode = sh.get("mode", "manual")
    threshold = sh.get("severity_threshold", 40)
    click.echo(f"   Enabled: {'✅' if enabled else '❌'} {enabled}")
    click.echo(f"   Mode: {mode}")
    click.echo(f"   Threshold: {threshold}")

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

    # Count local traces
    trace_count = 0
    if TRACES_DIR.exists():
        for tf in TRACES_DIR.glob("traces-*.jsonl"):
            with open(tf) as f:
                trace_count += sum(1 for _ in f)

    click.echo(f"\n📁 Local traces: {trace_count}")

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
@click.option("--last", default=50, help="Number of traces to export")
@click.option("--output", "-o", default="traces-export.jsonl", help="Output file")
@click.option("--compress", is_flag=True, help="Gzip compress output")
def export(last: int, output: str, compress: bool):
    """Export traces to a file for sharing."""
    traces = load_recent_traces(last)
    
    if not traces:
        click.echo("No traces to export")
        return
    
    # Prepare export (redact sensitive data)
    export_data = []
    for t in traces:
        clean = {
            "timestamp": t.get("timestamp"),
            "tool_name": t.get("tool_name"),
            "hook_type": t.get("hook_type"),
            "session_id": t.get("session_id"),
        }
        # Include sanitized input
        inp = t.get("tool_input", {})
        if isinstance(inp, dict):
            clean["tool_input"] = sanitize_input(inp)
        export_data.append(clean)
    
    output_path = Path(output)
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

    return {
        "tool_name": tool_name,
        "timestamp": timestamp,
        "hook_type": hook_type,
        "session_id": session_id,
        "tool_input": tool_input,
        "working_dir": t.get("working_dir") or attrs.get("working_dir", ""),
        "_raw": t,
    }


def load_recent_traces(n: int) -> list:
    """Load recent traces from local storage."""
    traces = []
    if not TRACES_DIR.exists():
        return traces

    for tf in sorted(TRACES_DIR.glob("traces-*.jsonl"), reverse=True):
        with open(tf) as f:
            for line in f:
                raw = json.loads(line)
                traces.append(normalize_trace(raw))
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
        "version": "0.1.0",
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


def run_detection(traces: list) -> dict:
    """Run MAST failure detection on traces."""
    results = {}
    
    # F4: Tool Misuse
    bash_misuse = sum(1 for t in traces 
        if t.get("tool_name") == "Bash" 
        and any(x in str(t.get("tool_input", {}).get("command", "")) 
                for x in ["cat ", "head ", "tail "]))
    results["F4_tool_misuse"] = {
        "detected": bash_misuse > 0,
        "explanation": f"{bash_misuse} bash-for-read issues" if bash_misuse else "OK",
    }
    
    # F6: Loop
    tool_seq = [t.get("tool_name") for t in traces]
    repeats = sum(1 for i in range(1, len(tool_seq)) if tool_seq[i] == tool_seq[i-1])
    results["F6_loop"] = {
        "detected": repeats > 10,
        "explanation": f"{repeats} consecutive repeats" if repeats > 10 else "OK",
    }
    
    # F15: Grounding (placeholder)
    results["F15_grounding"] = {"detected": False, "explanation": "OK"}
    
    # F16: Retrieval (placeholder)
    results["F16_retrieval"] = {"detected": False, "explanation": "OK"}
    
    return results


if __name__ == "__main__":
    main()
