"""Pisama CLI entry point."""

from __future__ import annotations

import click

from pisama import __version__
from pisama.cli.analyze_cmd import analyze_cmd
from pisama.cli.detectors_cmd import detectors_cmd
from pisama.cli.mcp_cmd import mcp_server_cmd


@click.group()
@click.version_option(version=__version__, prog_name="pisama")
def main() -> None:
    """Pisama -- Multi-agent failure detection for production AI systems."""


main.add_command(analyze_cmd, name="analyze")
main.add_command(detectors_cmd, name="detectors")
main.add_command(mcp_server_cmd, name="mcp-server")

# Import commands that register themselves on the `main` group.
# These modules call @main.command() at import time.
import pisama.cli.watch  # noqa: F401, E402
import pisama.cli.replay  # noqa: F401, E402
import pisama.cli.smoke  # noqa: F401, E402
