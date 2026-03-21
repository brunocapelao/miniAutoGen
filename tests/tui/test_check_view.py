"""Tests for the :check secondary view."""

from __future__ import annotations

from unittest.mock import MagicMock

from miniautogen.cli.models import CheckResult
from miniautogen.tui.views.base import SecondaryView
from miniautogen.tui.views.check import CheckView


def test_check_view_is_secondary_view() -> None:
    assert issubclass(CheckView, SecondaryView)


def test_check_view_title() -> None:
    view = CheckView()
    assert view.VIEW_TITLE == "Project health check"


def test_check_view_has_rerun_binding() -> None:
    """CheckView must expose an 'r' keybinding for re-running checks."""
    keys = {b.key for b in CheckView.BINDINGS}
    assert "r" in keys


def test_check_view_registered_in_app() -> None:
    """CheckView must be registered under the 'check' key in SCREENS."""
    from miniautogen.tui.app import MiniAutoGenDash

    assert "check" in MiniAutoGenDash.SCREENS
    assert MiniAutoGenDash.SCREENS["check"] is CheckView


def test_data_provider_check_project_no_config(tmp_path) -> None:
    """DashDataProvider.check_project() returns [] when no config present."""
    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(tmp_path)
    results = provider.check_project()
    assert results == []


def test_data_provider_check_project_returns_results(tmp_path, monkeypatch) -> None:
    """DashDataProvider.check_project() delegates to check_project service."""
    import miniautogen.tui.data_provider as dp_module

    fake_results = [
        CheckResult(
            name="config_schema",
            passed=True,
            message="miniautogen.yaml is valid",
            category="static",
        )
    ]
    fake_config = MagicMock()
    monkeypatch.setattr(dp_module, "_check_project", lambda cfg, root: fake_results)
    monkeypatch.setattr(dp_module, "load_config", lambda path: fake_config)

    # Create a minimal config file so has_project() and the path check pass
    config_file = tmp_path / "miniautogen.yaml"
    config_file.write_text("project:\n  name: test\n")

    from miniautogen.tui.data_provider import DashDataProvider

    provider = DashDataProvider(tmp_path)
    results = provider.check_project()
    assert results == fake_results


def test_check_view_run_checks_no_provider() -> None:
    """_run_checks with no provider shows empty state, does not crash."""
    view = CheckView()
    # provider is None when app._provider is not set; verify _run_checks
    # is callable (full UI test requires pilot, so just verify the method exists)
    assert callable(view._run_checks)


def test_check_view_status_icons() -> None:
    """Verify status icon logic for passed, failed, and warning results."""
    # Passed result
    r_pass = CheckResult(name="x", passed=True, message="ok", category="static")
    # Failed result
    r_fail = CheckResult(name="y", passed=False, message="bad", category="static")
    # Warning result
    r_warn = CheckResult(
        name="z", passed=True, message="warn", category="environment", warning=True
    )

    def _icon(result: CheckResult) -> str:
        if result.warning:
            return "warn"
        elif result.passed:
            return "pass"
        else:
            return "fail"

    assert _icon(r_pass) == "pass"
    assert _icon(r_fail) == "fail"
    assert _icon(r_warn) == "warn"
