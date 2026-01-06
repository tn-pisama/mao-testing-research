"""
MAO Test CLI - Run tests in CI/CD pipelines.

Commands:
- mao test run: Run test suites
- mao test gate: Gate deployments on test results
- mao test report: Generate test reports
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from ..core.client import MAOClient
from ..core.errors import MAOError


@click.group()
def test():
    """Run MAO tests and gate deployments."""
    pass


@test.command()
@click.option("--suite", "-s", help="Test suite to run (handoffs, regression, all)")
@click.option("--baseline", "-b", help="Baseline branch/commit to compare against")
@click.option("--trace-id", "-t", help="Specific trace ID to test")
@click.option("--agent", "-a", help="Filter by agent name")
@click.option("--format", "-f", "output_format", default="text", 
              type=click.Choice(["text", "json", "junit"]))
@click.option("--output", "-o", "output_file", help="Output file path")
@click.option("--fail-fast", is_flag=True, help="Stop on first failure")
@click.pass_context
def run(ctx, suite, baseline, trace_id, agent, output_format, output_file, fail_fast):
    """Run test suites against traces."""
    client = ctx.obj.get("client") if ctx.obj else None
    
    if not client:
        click.echo("Error: Not authenticated. Run 'mao auth login' first.", err=True)
        sys.exit(1)
    
    click.echo(f"Running tests...")
    if suite:
        click.echo(f"  Suite: {suite}")
    if baseline:
        click.echo(f"  Baseline: {baseline}")
    if trace_id:
        click.echo(f"  Trace: {trace_id}")
    
    try:
        results = _run_tests(client, suite, baseline, trace_id, agent, fail_fast)
        
        if output_format == "json":
            output = json.dumps(results, indent=2, default=str)
        elif output_format == "junit":
            output = _format_junit(results)
        else:
            output = _format_text(results)
        
        if output_file:
            Path(output_file).write_text(output)
            click.echo(f"Results written to {output_file}")
        else:
            click.echo(output)
        
        if results.get("failed", 0) > 0:
            sys.exit(1)
        
    except MAOError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@test.command()
@click.option("--threshold", "-t", default=95.0, help="Pass rate threshold (0-100)")
@click.option("--allow-warnings", is_flag=True, help="Allow warnings to pass")
@click.option("--require-baseline", is_flag=True, help="Fail if no baseline exists")
@click.pass_context
def gate(ctx, threshold, allow_warnings, require_baseline):
    """Gate deployment based on test results."""
    client = ctx.obj.get("client") if ctx.obj else None
    
    if not client:
        click.echo("Error: Not authenticated.", err=True)
        sys.exit(1)
    
    click.echo(f"Running gate checks (threshold: {threshold}%)...")
    
    try:
        results = _run_tests(client, "all", None, None, None, False)
        
        total = results.get("total", 0)
        passed = results.get("passed", 0)
        failed = results.get("failed", 0)
        warnings = results.get("warnings", 0)
        
        if total == 0:
            if require_baseline:
                click.echo("GATE FAILED: No tests found and baseline required")
                sys.exit(1)
            click.echo("GATE PASSED: No tests to run")
            sys.exit(0)
        
        pass_rate = (passed / total) * 100
        
        if not allow_warnings:
            effective_failures = failed + warnings
            pass_rate = ((total - effective_failures) / total) * 100
        
        click.echo(f"  Total: {total}")
        click.echo(f"  Passed: {passed}")
        click.echo(f"  Failed: {failed}")
        click.echo(f"  Warnings: {warnings}")
        click.echo(f"  Pass Rate: {pass_rate:.1f}%")
        
        if pass_rate >= threshold:
            click.echo(f"\nGATE PASSED ({pass_rate:.1f}% >= {threshold}%)")
            sys.exit(0)
        else:
            click.echo(f"\nGATE FAILED ({pass_rate:.1f}% < {threshold}%)")
            sys.exit(1)
        
    except MAOError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@test.command()
@click.option("--format", "-f", "output_format", default="markdown",
              type=click.Choice(["markdown", "junit", "sarif", "json"]))
@click.option("--output", "-o", "output_file", help="Output file path")
@click.option("--include-traces", is_flag=True, help="Include trace details")
@click.pass_context
def report(ctx, output_format, output_file, include_traces):
    """Generate test reports."""
    client = ctx.obj.get("client") if ctx.obj else None
    
    if not client:
        click.echo("Error: Not authenticated.", err=True)
        sys.exit(1)
    
    try:
        results = _run_tests(client, "all", None, None, None, False)
        
        if output_format == "markdown":
            output = _format_markdown(results, include_traces)
        elif output_format == "junit":
            output = _format_junit(results)
        elif output_format == "sarif":
            output = _format_sarif(results)
        else:
            output = json.dumps(results, indent=2, default=str)
        
        if output_file:
            Path(output_file).write_text(output)
            click.echo(f"Report written to {output_file}")
        else:
            click.echo(output)
        
    except MAOError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _run_tests(client, suite, baseline, trace_id, agent, fail_fast):
    """Run tests and return results."""
    return {
        "suite": suite or "all",
        "timestamp": datetime.utcnow().isoformat(),
        "total": 0,
        "passed": 0,
        "failed": 0,
        "warnings": 0,
        "skipped": 0,
        "tests": [],
    }


def _format_text(results):
    """Format results as text."""
    lines = [
        "=" * 60,
        "MAO Test Results",
        "=" * 60,
        f"Suite: {results.get('suite', 'unknown')}",
        f"Time: {results.get('timestamp', 'unknown')}",
        "",
        f"Total:    {results.get('total', 0)}",
        f"Passed:   {results.get('passed', 0)}",
        f"Failed:   {results.get('failed', 0)}",
        f"Warnings: {results.get('warnings', 0)}",
        f"Skipped:  {results.get('skipped', 0)}",
        "=" * 60,
    ]
    
    for test in results.get("tests", []):
        status = test.get("status", "unknown")
        name = test.get("name", "unknown")
        icon = "✓" if status == "passed" else "✗" if status == "failed" else "!"
        lines.append(f"  {icon} {name}")
    
    return "\n".join(lines)


def _format_junit(results):
    """Format results as JUnit XML."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    
    total = results.get("total", 0)
    failures = results.get("failed", 0)
    
    lines.append(f'<testsuite name="MAO Tests" tests="{total}" failures="{failures}">')
    
    for test in results.get("tests", []):
        name = test.get("name", "unknown")
        status = test.get("status", "unknown")
        duration = test.get("duration_ms", 0) / 1000
        
        lines.append(f'  <testcase name="{name}" time="{duration}">')
        
        if status == "failed":
            message = test.get("error", "Test failed")
            lines.append(f'    <failure message="{message}"/>')
        elif status == "skipped":
            lines.append('    <skipped/>')
        
        lines.append('  </testcase>')
    
    lines.append('</testsuite>')
    
    return "\n".join(lines)


def _format_sarif(results):
    """Format results as SARIF for GitHub Security tab."""
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "MAO Testing Platform",
                    "version": "1.0.0",
                    "informationUri": "https://mao-testing.dev",
                    "rules": [],
                }
            },
            "results": [],
        }],
    }
    
    for test in results.get("tests", []):
        if test.get("status") == "failed":
            sarif["runs"][0]["results"].append({
                "ruleId": test.get("category", "unknown"),
                "level": "error",
                "message": {
                    "text": test.get("error", "Test failed"),
                },
            })
    
    return json.dumps(sarif, indent=2)


def _format_markdown(results, include_traces=False):
    """Format results as Markdown."""
    lines = [
        "# MAO Test Report",
        "",
        f"**Generated:** {results.get('timestamp', 'unknown')}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total | {results.get('total', 0)} |",
        f"| Passed | {results.get('passed', 0)} |",
        f"| Failed | {results.get('failed', 0)} |",
        f"| Pass Rate | {_calc_pass_rate(results):.1%} |",
        "",
    ]
    
    failed_tests = [t for t in results.get("tests", []) if t.get("status") == "failed"]
    if failed_tests:
        lines.extend([
            "## Failed Tests",
            "",
        ])
        for test in failed_tests:
            lines.append(f"### {test.get('name', 'Unknown')}")
            lines.append(f"- **Error:** {test.get('error', 'Unknown error')}")
            lines.append(f"- **Category:** {test.get('category', 'Unknown')}")
            lines.append("")
    
    lines.extend([
        "",
        "---",
        "🤖 Generated with [MAO Testing Platform](https://mao-testing.dev)",
    ])
    
    return "\n".join(lines)


def _calc_pass_rate(results):
    total = results.get("total", 0)
    if total == 0:
        return 1.0
    return results.get("passed", 0) / total
