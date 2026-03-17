"""miniautogen engine command group.

CRUD operations for LLM engine profiles in miniautogen.yaml.
"""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import (
    echo_error,
    echo_json,
    echo_success,
    echo_table,
)


@click.group("engine")
def engine_group() -> None:
    """Manage LLM engine profiles."""


@engine_group.command("create")
@click.argument("name")
@click.option("--provider", default=None, help="LLM provider (e.g. openai, gemini, vllm).")
@click.option("--model", default=None, help="Model identifier.")
@click.option("--kind", default="api", help="Engine kind (api or cli).")
@click.option("--temperature", type=float, default=0.2, help="Sampling temperature.")
@click.option("--api-key-env", default=None, help="Environment variable name for API key.")
@click.option("--endpoint", default=None, help="Custom API endpoint URL.")
@click.option(
    "--capabilities",
    default=None,
    help="Comma-separated capabilities (chat,completion,embedding).",
)
def engine_create(
    name: str,
    provider: str | None,
    model: str | None,
    kind: str,
    temperature: float,
    api_key_env: str | None,
    endpoint: str | None,
    capabilities: str | None,
) -> None:
    """Create a new engine profile."""
    from miniautogen.cli.services.engine_ops import create_engine

    # Interactive mode: prompt for missing required fields
    if provider is None:
        provider = click.prompt("Provider", type=str)
    if model is None:
        model = click.prompt("Model", type=str)

    root, _config = require_project_config()

    caps = [c.strip() for c in capabilities.split(",")] if capabilities else None

    try:
        engine = run_async(
            create_engine,
            root,
            name,
            provider=provider,
            model=model,
            kind=kind,
            temperature=temperature,
            api_key_env=api_key_env,
            endpoint=endpoint,
            capabilities=caps,
        )
        echo_success(f"Engine '{name}' created: provider={engine['provider']}, model={engine['model']}")
    except ValueError as exc:
        echo_error(str(exc))
        raise SystemExit(1)


@engine_group.command("list")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def engine_list(output_format: str) -> None:
    """List all engine profiles."""
    from miniautogen.cli.services.engine_ops import list_engines

    root, _config = require_project_config()
    engines = run_async(list_engines, root)

    if output_format == "json":
        echo_json(engines)
    elif not engines:
        click.echo("No engine profiles configured.")
    else:
        rows = [
            [e["name"], e["provider"], e["model"], e["kind"]]
            for e in engines
        ]
        echo_table(["Name", "Provider", "Model", "Kind"], rows)


@engine_group.command("show")
@click.argument("name")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def engine_show(name: str, output_format: str) -> None:
    """Show details for a specific engine profile."""
    from miniautogen.cli.services.engine_ops import show_engine

    root, _config = require_project_config()

    try:
        engine = run_async(show_engine, root, name)
    except KeyError as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    if output_format == "json":
        echo_json(engine)
    else:
        for key, value in engine.items():
            click.echo(f"{key}: {value}")


@engine_group.command("update")
@click.argument("name")
@click.option("--provider", default=None, help="New provider.")
@click.option("--model", default=None, help="New model.")
@click.option("--temperature", type=float, default=None, help="New temperature.")
@click.option("--endpoint", default=None, help="New endpoint URL.")
@click.option("--dry-run", is_flag=True, default=False, help="Show changes without applying.")
def engine_update(
    name: str,
    provider: str | None,
    model: str | None,
    temperature: float | None,
    endpoint: str | None,
    dry_run: bool,
) -> None:
    """Update an existing engine profile."""
    from miniautogen.cli.services.engine_ops import update_engine

    root, _config = require_project_config()

    updates = {}
    if provider is not None:
        updates["provider"] = provider
    if model is not None:
        updates["model"] = model
    if temperature is not None:
        updates["temperature"] = temperature
    if endpoint is not None:
        updates["endpoint"] = endpoint

    if not updates:
        echo_error("No updates specified.")
        raise SystemExit(1)

    try:
        result = run_async(
            update_engine, root, name, dry_run=dry_run, **updates,
        )
    except KeyError as exc:
        echo_error(str(exc))
        raise SystemExit(1)

    if dry_run:
        click.echo("Dry run — changes not applied:")
        for key in updates:
            before_val = result["before"].get(key, "(unset)")
            after_val = result["after"].get(key)
            click.echo(f"  {key}: {before_val} -> {after_val}")
    else:
        echo_success(f"Engine '{name}' updated.")
