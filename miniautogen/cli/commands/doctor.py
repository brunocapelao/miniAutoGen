"""miniautogen doctor command.

Validates the development environment beyond project config:
Python version, dependencies, API keys, gateway accessibility.
"""

from __future__ import annotations

import importlib
import os
import sys

import click

from miniautogen.cli.output import echo_error, echo_info, echo_json, echo_success, echo_table, echo_warning


def _check_python_version() -> tuple[bool, str]:
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor >= 10:
        return True, f"Python {version_str}"
    return False, f"Python {version_str} (requires >=3.10)"


def _check_dependency(name: str, import_name: str | None = None) -> tuple[bool, str]:
    mod = import_name or name
    try:
        importlib.import_module(mod)
        try:
            from importlib.metadata import version as _get_version
            version = _get_version(name.replace(".", "-"))
        except Exception:
            version = "installed"
        return True, f"{name} {version}"
    except ImportError:
        return False, f"{name} not installed. Run: pip install {name}"


def _check_api_key(env_var: str, provider: str) -> tuple[bool, str]:
    val = os.environ.get(env_var)
    if val:
        return True, f"{provider}: {env_var} is set"
    return False, f"{provider}: {env_var} not set"


def _check_gateway(port: int = 8080) -> tuple[bool, str]:
    import urllib.error
    import urllib.request

    try:
        url = f"http://127.0.0.1:{port}/health"
        req = urllib.request.Request(url, method="GET")
        urllib.request.urlopen(req, timeout=2)
        return True, f"Gateway at localhost:{port} is accessible"
    except (urllib.error.URLError, OSError):
        return False, f"Gateway at localhost:{port} is not accessible. Run: miniautogen server start"


@click.command("doctor")
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def doctor_command(output_format: str) -> None:
    """Check development environment health."""
    checks: list[tuple[str, bool, str]] = []

    # Python version
    passed, msg = _check_python_version()
    checks.append(("python", passed, msg))

    # Core dependencies
    for name, import_name in [
        ("click", None),
        ("pydantic", None),
        ("jinja2", None),
        ("pyyaml", "yaml"),
        ("ruamel.yaml", "ruamel.yaml"),
        ("anyio", None),
        ("structlog", None),
        ("uvicorn", None),
        ("fastapi", None),
        ("httpx", None),
    ]:
        passed, msg = _check_dependency(name, import_name)
        checks.append(("dependency", passed, msg))

    # API keys
    for env_var, provider in [
        ("OPENAI_API_KEY", "OpenAI"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("GEMINI_API_KEY", "Gemini"),
    ]:
        passed, msg = _check_api_key(env_var, provider)
        checks.append(("api_key", passed, msg))

    # Gateway
    passed, msg = _check_gateway()
    checks.append(("gateway", passed, msg))

    if output_format == "json":
        echo_json([
            {"category": c, "passed": p, "message": m}
            for c, p, m in checks
        ])
    else:
        rows = [
            ["PASS" if p else "WARN" if c in ("api_key", "gateway") else "FAIL", c, m]
            for c, p, m in checks
        ]
        echo_table(["Status", "Category", "Message"], rows)

    failed = [(c, m) for c, p, m in checks if not p]
    critical = [m for c, p, m in checks if not p and c in ("python", "dependency")]

    if critical:
        echo_error(f"\n{len(critical)} critical issue(s) found")
        raise SystemExit(1)
    elif failed:
        echo_warning(f"\n{len(failed)} warning(s) — non-critical")
    else:
        echo_success("\nAll checks passed")
