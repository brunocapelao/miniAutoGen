"""Extended tests for doctor CLI command — covers missing dependencies,
Python version check, API keys, and gateway checks.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from miniautogen.cli.commands.doctor import (
    _check_api_key,
    _check_dependency,
    _check_gateway,
    _check_python_version,
    doctor_command,
)


# ── _check_python_version ──────────────────────────────────────────────


class TestCheckPythonVersion:
    @staticmethod
    def _mock_version(major: int, minor: int, micro: int):
        """Create a mock version_info with the needed attributes."""
        m = MagicMock()
        m.major = major
        m.minor = minor
        m.micro = micro
        return m

    def test_valid_python_310(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "version_info", self._mock_version(3, 10, 0))
        passed, msg = _check_python_version()
        assert passed is True
        assert "3.10.0" in msg

    def test_valid_python_312(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "version_info", self._mock_version(3, 12, 1))
        passed, msg = _check_python_version()
        assert passed is True

    def test_old_python_39(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "version_info", self._mock_version(3, 9, 7))
        passed, msg = _check_python_version()
        assert passed is False
        assert "requires" in msg


# ── _check_dependency ───────────────────────────────────────────────────


class TestCheckDependency:
    def test_installed_dependency(self) -> None:
        """click is installed in the test env."""
        passed, msg = _check_dependency("click")
        assert passed is True
        assert "click" in msg

    def test_missing_dependency(self) -> None:
        passed, msg = _check_dependency(
            "nonexistent_pkg_xyz", "nonexistent_pkg_xyz",
        )
        assert passed is False
        assert "not installed" in msg
        assert "pip install" in msg

    def test_installed_but_version_unknown(self) -> None:
        """Module importable but importlib.metadata can't find version."""
        with patch("importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            with patch(
                "miniautogen.cli.commands.doctor._get_version",
                side_effect=Exception("not found"),
                create=True,
            ):
                passed, msg = _check_dependency("some_pkg")
        assert passed is True


# ── _check_api_key ──────────────────────────────────────────────────────


class TestCheckApiKey:
    def test_key_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_API_KEY", "sk-test123")
        passed, msg = _check_api_key("TEST_API_KEY", "TestProvider")
        assert passed is True
        assert "is set" in msg

    def test_key_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TEST_API_KEY", raising=False)
        passed, msg = _check_api_key("TEST_API_KEY", "TestProvider")
        assert passed is False
        assert "not set" in msg


# ── _check_gateway ─────────────────────────────────────────────────────


class TestCheckGateway:
    def test_gateway_running(self) -> None:
        with patch("urllib.request.urlopen"):
            passed, msg = _check_gateway(port=8080)
        assert passed is True
        assert "accessible" in msg

    def test_gateway_not_running(self) -> None:
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ):
            passed, msg = _check_gateway(port=8080)
        assert passed is False
        assert "not accessible" in msg


# ── doctor_command (integration) ────────────────────────────────────────


class TestDoctorCommand:
    def test_all_checks_pass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All checks pass — should print 'All checks passed'."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("GEMINI_API_KEY", "test")

        with patch(
            "miniautogen.cli.commands.doctor._check_gateway",
            return_value=(True, "Gateway accessible"),
        ):
            runner = CliRunner()
            result = runner.invoke(doctor_command)
        assert "All checks passed" in result.output or result.exit_code == 0

    def test_critical_dependency_failure_exits_1(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing critical dependency should exit with code 1."""
        with patch(
            "miniautogen.cli.commands.doctor._check_dependency",
            return_value=(False, "click not installed"),
        ):
            runner = CliRunner()
            result = runner.invoke(doctor_command)
        assert result.exit_code == 1

    def test_api_key_missing_is_warning_not_critical(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing API key is a warning, not a critical failure."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with patch(
            "miniautogen.cli.commands.doctor._check_gateway",
            return_value=(False, "Gateway not running"),
        ):
            runner = CliRunner()
            result = runner.invoke(doctor_command)
        # Should NOT exit 1 (api_key/gateway are warnings)
        assert result.exit_code == 0
        assert "warning" in result.output.lower()

    def test_json_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """JSON format includes category and passed fields."""
        with patch(
            "miniautogen.cli.commands.doctor._check_gateway",
            return_value=(True, "ok"),
        ):
            runner = CliRunner()
            result = runner.invoke(doctor_command, ["--format", "json"])
        assert '"category"' in result.output
        assert '"passed"' in result.output

    def test_gateway_not_running_shown_as_warn(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Gateway not running should show WARN, not FAIL."""
        import urllib.error

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("GEMINI_API_KEY", "test")

        with patch(
            "miniautogen.cli.commands.doctor._check_gateway",
            return_value=(False, "Gateway not accessible"),
        ):
            runner = CliRunner()
            result = runner.invoke(doctor_command)
        # Should still exit 0 (gateway is non-critical)
        assert result.exit_code == 0
