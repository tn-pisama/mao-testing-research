#!/usr/bin/env python3
"""PISAMA Claude Code Installer.

Installs PISAMA hooks and configuration into ~/.claude/.
"""

import json
import shutil
import stat
from pathlib import Path


HOOK_TEMPLATE = '''#!/usr/bin/env python3
"""Auto-generated PISAMA hook wrapper."""

import sys
sys.path.insert(0, "{packages_path}")

from pisama_claude_code.hooks.{hook_module} import main
main()
'''


def install(force: bool = False):
    """Install PISAMA hooks to ~/.claude/hooks/.

    Args:
        force: Overwrite existing hooks if True
    """
    claude_dir = Path.home() / ".claude"
    hooks_dir = claude_dir / "hooks"
    pisama_dir = claude_dir / "pisama"

    # Ensure directories exist
    hooks_dir.mkdir(parents=True, exist_ok=True)
    pisama_dir.mkdir(parents=True, exist_ok=True)
    (pisama_dir / "traces").mkdir(exist_ok=True)

    # Find packages path
    packages_path = Path(__file__).parent.parent.parent
    if not packages_path.exists():
        # Try to find in common locations
        for path in [
            Path.home() / "mao-testing-research" / "packages",
            Path.home() / "code" / "mao-testing-research" / "packages",
        ]:
            if path.exists():
                packages_path = path
                break

    # Install hooks
    hooks = [
        ("pisama-guardian-hook.py", "guardian_hook"),
        ("pisama-capture.py", "capture_hook"),
    ]

    for filename, module in hooks:
        hook_path = hooks_dir / filename

        if hook_path.exists() and not force:
            print(f"Skipping {filename} (exists, use --force to overwrite)")
            continue

        # Write hook wrapper
        content = HOOK_TEMPLATE.format(
            packages_path=str(packages_path),
            hook_module=module,
        )
        hook_path.write_text(content)

        # Make executable
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"Installed {filename}")

    # Install shell wrappers
    _install_shell_hooks(hooks_dir, force)

    # Install default config if not exists
    config_path = pisama_dir / "config.json"
    if not config_path.exists() or force:
        default_config = {
            "self_healing": {
                "enabled": True,
                "mode": "manual",
                "severity_threshold": 40,
                "auto_fix_types": ["break_loop", "add_delay", "switch_strategy"],
                "blocked_fixes": ["delete_file", "git_push", "external_api"],
                "max_auto_fixes": 10,
                "cooldown_seconds": 30
            },
            "monitoring": {
                "enabled": True,
                "pattern_window": 10,
                "alert_on_warning": False
            },
            "ignored_patterns": []
        }
        config_path.write_text(json.dumps(default_config, indent=2))
        print(f"Installed default config")

    # Update settings.local.json
    _update_settings(claude_dir, hooks_dir)

    print("\nPISAMA installation complete!")
    print(f"Hooks installed to: {hooks_dir}")
    print(f"Config at: {config_path}")
    print("\nTo enable, ensure your settings.local.json has the hooks configured.")


def _install_shell_hooks(hooks_dir: Path, force: bool):
    """Install shell wrapper hooks."""
    # Pre-hook shell script
    pre_script = '''#!/bin/bash
# PISAMA Pre-hook wrapper
# Runs capture and guardian before tool calls

PISAMA_HOOK_TYPE=pre ~/.claude/hooks/pisama-capture.py
~/.claude/hooks/pisama-guardian-hook.py
'''

    pre_path = hooks_dir / "pisama-pre.sh"
    if not pre_path.exists() or force:
        pre_path.write_text(pre_script)
        pre_path.chmod(pre_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("Installed pisama-pre.sh")

    # Post-hook shell script
    post_script = '''#!/bin/bash
# PISAMA Post-hook wrapper
PISAMA_HOOK_TYPE=post ~/.claude/hooks/pisama-capture.py
'''

    post_path = hooks_dir / "pisama-post.sh"
    if not post_path.exists() or force:
        post_path.write_text(post_script)
        post_path.chmod(post_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("Installed pisama-post.sh")


def _update_settings(claude_dir: Path, hooks_dir: Path):
    """Update settings.local.json with hook configuration."""
    settings_path = claude_dir / "settings.local.json"

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    # Check if hooks already configured
    hooks = settings.get("hooks", {})

    if "PreToolCall" not in hooks:
        print("\nNote: Add the following to your settings.local.json hooks:")
        print('''
  "hooks": {
    "PreToolCall": [
      {
        "command": "~/.claude/hooks/pisama-pre.sh",
        "timeout": 5000
      }
    ],
    "PostToolCall": [
      {
        "command": "~/.claude/hooks/pisama-post.sh",
        "timeout": 2000
      }
    ]
  }
''')


def uninstall():
    """Uninstall PISAMA hooks from ~/.claude/hooks/."""
    hooks_dir = Path.home() / ".claude" / "hooks"

    hooks = [
        "pisama-guardian-hook.py",
        "pisama-capture.py",
        "pisama-pre.sh",
        "pisama-post.sh",
    ]

    for filename in hooks:
        hook_path = hooks_dir / filename
        if hook_path.exists():
            hook_path.unlink()
            print(f"Removed {filename}")

    print("\nPISAMA hooks uninstalled.")
    print("Note: Config and traces in ~/.claude/pisama/ were preserved.")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="PISAMA Claude Code Installer")
    parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing hooks")
    parser.add_argument("--uninstall", "-u", action="store_true", help="Uninstall hooks")

    args = parser.parse_args()

    if args.uninstall:
        uninstall()
    else:
        install(force=args.force)


if __name__ == "__main__":
    main()
