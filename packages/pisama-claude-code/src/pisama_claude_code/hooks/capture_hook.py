#!/usr/bin/env python3
"""PISAMA Trace Capture Hook - Captures all Claude Code tool calls for forensics.

This hook runs on tool calls to capture trace data for analysis.
It stores traces in both SQLite (for querying) and JSONL (for archival).

Usage:
    Install in ~/.claude/hooks/ and configure in settings.local.json
"""

import json
import os
import sys


def main():
    """Main hook entry point."""
    # Determine hook type from environment or argv
    hook_type = os.environ.get("PISAMA_HOOK_TYPE", "unknown")
    if len(sys.argv) > 1:
        hook_type = sys.argv[1]

    # Read hook input from stdin
    try:
        raw_input = sys.stdin.read()
        if raw_input.strip():
            hook_data = json.loads(raw_input)
        else:
            hook_data = {}
    except json.JSONDecodeError:
        hook_data = {"raw": raw_input}
    except Exception as e:
        hook_data = {"error": str(e)}

    try:
        # Import and use pisama_claude_code for capture
        from pisama_claude_code.adapter import ClaudeCodeAdapter

        adapter = ClaudeCodeAdapter()
        span = adapter.capture_span(hook_data)
        adapter.store_span(span, hook_data)

    except ImportError:
        # Fall back to basic capture
        _fallback_capture(hook_data, hook_type)
    except Exception as e:
        # Log error but don't fail
        print(f"PISAMA capture error: {e}", file=sys.stderr)

    # Always exit successfully (don't block)
    sys.exit(0)


def _fallback_capture(hook_data: dict, hook_type: str) -> None:
    """Fallback capture when pisama_claude_code is not installed.

    Provides basic trace storage without the full pisama-core stack.
    """
    import sqlite3
    from datetime import datetime, timezone
    from pathlib import Path

    traces_dir = Path.home() / ".claude" / "pisama" / "traces"
    db_path = traces_dir / "pisama.db"

    # Ensure directory exists
    traces_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()
    session_id = hook_data.get("session_id", os.environ.get("CLAUDE_SESSION_ID", "unknown"))
    tool_name = hook_data.get("tool_name", hook_data.get("tool", "unknown"))
    tool_input = hook_data.get("tool_input", hook_data.get("input", {}))
    tool_output = hook_data.get("tool_output", hook_data.get("output"))

    # Write to JSONL
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    jsonl_path = traces_dir / f"traces-{date_str}.jsonl"

    trace = {
        "session_id": session_id,
        "timestamp": timestamp,
        "hook_type": hook_type,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_output": tool_output,
        "working_dir": os.getcwd(),
        "raw": hook_data,
    }

    with open(jsonl_path, "a") as f:
        f.write(json.dumps(trace) + "\n")

    # Write to SQLite
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TEXT,
                hook_type TEXT,
                tool_name TEXT,
                tool_input TEXT,
                tool_output TEXT,
                working_dir TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON traces(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tool ON traces(tool_name)")

        conn.execute("""
            INSERT INTO traces (session_id, timestamp, hook_type, tool_name, tool_input, tool_output, working_dir)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            timestamp,
            hook_type,
            tool_name,
            json.dumps(tool_input) if tool_input else None,
            json.dumps(tool_output) if tool_output else None,
            os.getcwd(),
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
