"""miniautogen check command."""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_json, echo_success, echo_table


@click.command("check")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def check_command(output_format: str) -> None:
    """Validate project configuration and environment."""
    from miniautogen.cli.services.check_project import check_project

    root, config = require_project_config()
    results = run_async(check_project, config, root)

    if output_format == "json":
        echo_json([
            {
                "name": r.name,
                "passed": r.passed,
                "message": r.message,
                "category": r.category,
            }
            for r in results
        ])
    else:
        rows = [
            [
                "PASS" if r.passed else "FAIL",
                r.name,
                r.message,
            ]
            for r in results
        ]
        echo_table(["Status", "Check", "Message"], rows)

    failed = [r for r in results if not r.passed]
    if failed:
        echo_error(f"\n{len(failed)} check(s) failed")
        raise SystemExit(1)
    else:
        echo_success(f"\nAll {len(results)} check(s) passed")
