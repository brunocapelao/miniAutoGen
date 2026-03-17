"""miniautogen engine command group.

CRUD operations for LLM engine profiles in miniautogen.yaml.
Supports dual mode: interactive wizard when flags missing,
silent mode when all flags provided (for CI/CD).
"""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.output import (
    echo_error,
    echo_info,
    echo_json,
    echo_success,
    echo_table,
    echo_warning,
)

_PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1",
    "vllm": "http://localhost:8000/v1",
    "gemini-cli": "http://localhost:8080/v1",
}

_PROVIDER_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


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

    root, _config = require_project_config()

    # Interactive wizard for missing required fields
    if provider is None:
        provider = click.prompt(
            "Provider (openai, gemini, vllm, anthropic, other)",
            type=str,
        )
    if model is None:
        model = click.prompt("Model", type=str)

    # Interactive: prompt for endpoint with provider-specific default
    if endpoint is None:
        default_ep = _PROVIDER_DEFAULTS.get(provider, "")
        if default_ep:
            endpoint = click.prompt(
                "Endpoint",
                default=default_ep,
                type=str,
            )
        else:
            raw_ep = click.prompt("Endpoint (leave empty for default)", default="", type=str)
            endpoint = raw_ep if raw_ep.strip() else None

    # Interactive: prompt for API key env var
    if api_key_env is None:
        default_env = _PROVIDER_ENV_VARS.get(provider, "")
        if default_env:
            api_key_env = click.prompt(
                "API key env var",
                default=default_env,
                type=str,
            )
        else:
            raw_env = click.prompt(
                "API key env var (leave empty to skip)",
                default="",
                type=str,
            )
            api_key_env = raw_env if raw_env.strip() else None

    # Interactive: prompt for capabilities
    if capabilities is None:
        raw_caps = click.prompt(
            "Capabilities (comma-separated: chat,completion,embedding)",
            default="chat",
            type=str,
        )
        capabilities = raw_caps if raw_caps.strip() else None

    caps = [c.strip() for c in capabilities.split(",")] if capabilities else None

    # Confirmation summary
    echo_info(f"\nEngine '{name}' will be created:")
    echo_info(f"  provider: {provider}")
    echo_info(f"  model: {model}")
    echo_info(f"  kind: {kind}")
    echo_info(f"  temperature: {temperature}")
    if endpoint:
        echo_info(f"  endpoint: {endpoint}")
    if api_key_env:
        echo_info(f"  api_key: ${{{api_key_env}}}")
    if caps:
        echo_info(f"  capabilities: {', '.join(caps)}")

    if not click.confirm("\nConfirm?", default=True):
        echo_warning("Cancelled.")
        return

    try:
        engine = create_engine(
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
    engines = list_engines(root)

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
        engine = show_engine(root, name)
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
        result = update_engine(root, name, dry_run=dry_run, **updates)
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


@engine_group.command("delete")
@click.argument("name")
@click.option("--yes", "skip_confirm", is_flag=True, default=False, help="Skip confirmation.")
def engine_delete(name: str, skip_confirm: bool) -> None:
    """Delete an engine profile."""
    from miniautogen.cli.services.engine_ops import delete_engine

    root, _config = require_project_config()

    if not skip_confirm:
        if not click.confirm(f"Delete engine '{name}'?"):
            click.echo("Cancelled.")
            return

    try:
        result = delete_engine(root, name)
        echo_success(f"Engine '{result['deleted']}' deleted.")
    except (KeyError, ValueError) as exc:
        echo_error(str(exc))
        raise SystemExit(1)
