"""miniautogen init command."""

from __future__ import annotations

from pathlib import Path

import click

from miniautogen.cli.output import echo_error, echo_info, echo_success
from miniautogen.cli.services.init_project import scaffold_project


@click.command("init")
@click.argument("name")
@click.option(
    "--model",
    default="gpt-4o-mini",
    help="Default LLM model.",
)
@click.option(
    "--provider",
    default="litellm",
    help="Default LLM provider.",
)
@click.option(
    "--no-examples",
    is_flag=True,
    default=False,
    help="Skip example agent, skill, and tool.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Add missing files to existing non-empty directory.",
)
def init_command(
    name: str,
    model: str,
    provider: str,
    no_examples: bool,
    force: bool,
) -> None:
    """Create a new MiniAutoGen project."""
    try:
        project_dir = scaffold_project(
            name,
            Path.cwd(),
            model=model,
            provider=provider,
            include_examples=not no_examples,
            force=force,
        )
        echo_success(f"Workspace created: {project_dir}\n")

        # Next steps guidance
        echo_info("Next steps:")
        echo_info(f"  cd {name}")
        echo_info(f"  miniautogen engine create default --provider openai --model gpt-4o")
        echo_info(f"  miniautogen agent create researcher --engine default --role \"Researcher\"")
        echo_info(f"  miniautogen flow create main --mode workflow")
        echo_info(f"  miniautogen check")
        echo_info(f"  miniautogen run main")
    except FileExistsError:
        echo_error(
            f"Directory '{name}' already exists and is not empty. "
            f"Use --force to add missing files without overwriting."
        )
        raise SystemExit(1)
    except ValueError as exc:
        echo_error(str(exc))
        raise SystemExit(1)
