"""Tests for the 'miniautogen engine discover' CLI command."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from miniautogen.cli.config import EngineProfileConfig
from miniautogen.cli.main import cli


class TestEngineDiscoverCommand:
    def test_discover_command_output_with_env(self) -> None:
        """Verify CLI output format when env vars are set."""
        env_engines = {
            "openai": EngineProfileConfig(
                provider="openai",
                model="gpt-4o-mini",
                api_key="${OPENAI_API_KEY}",
            ),
            "anthropic": EngineProfileConfig(
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                api_key="${ANTHROPIC_API_KEY}",
            ),
        }

        with (
            patch(
                "miniautogen.backends.discovery.EngineDiscovery.discover_from_env",
                return_value=env_engines,
            ),
            patch(
                "miniautogen.backends.discovery.EngineDiscovery.discover_local_servers",
                return_value={},
            ),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["engine", "discover"])

        assert result.exit_code == 0, result.output
        assert "Discovered engines" in result.output
        assert "openai" in result.output
        assert "anthropic" in result.output
        assert "2 engine(s) discovered" in result.output

    def test_discover_command_no_engines(self) -> None:
        """Verify output when nothing is discovered."""
        with (
            patch(
                "miniautogen.backends.discovery.EngineDiscovery.discover_from_env",
                return_value={},
            ),
            patch(
                "miniautogen.backends.discovery.EngineDiscovery.discover_local_servers",
                return_value={},
            ),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["engine", "discover"])

        assert result.exit_code == 0, result.output
        assert "No engines discovered" in result.output

    def test_discover_command_json_format(self) -> None:
        """Verify JSON output format."""
        env_engines = {
            "openai": EngineProfileConfig(
                provider="openai",
                model="gpt-4o-mini",
                api_key="${OPENAI_API_KEY}",
            ),
        }

        with (
            patch(
                "miniautogen.backends.discovery.EngineDiscovery.discover_from_env",
                return_value=env_engines,
            ),
            patch(
                "miniautogen.backends.discovery.EngineDiscovery.discover_local_servers",
                return_value={},
            ),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["engine", "discover", "--format", "json"])

        assert result.exit_code == 0, result.output
        assert '"source"' in result.output
        assert '"name"' in result.output

    def test_discover_command_shows_local_servers(self) -> None:
        """Verify local server engines appear in output."""
        local_engines = {
            "ollama": EngineProfileConfig(
                provider="openai-compat",
                endpoint="http://localhost:11434/v1",
                model="auto",
            ),
        }

        with (
            patch(
                "miniautogen.backends.discovery.EngineDiscovery.discover_from_env",
                return_value={},
            ),
            patch(
                "miniautogen.backends.discovery.EngineDiscovery.discover_local_servers",
                return_value=local_engines,
            ),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["engine", "discover"])

        assert result.exit_code == 0, result.output
        assert "ollama" in result.output
        assert "local" in result.output
        assert "1 engine(s) discovered" in result.output
