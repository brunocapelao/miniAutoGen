"""Extended tests for run.py and run_pipeline.py to reach ~95% coverage.

Covers: _resolve_input, _Spinner, run_command options, execute_pipeline paths.
"""

from __future__ import annotations

import io
import json
import sys
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from miniautogen.cli.commands.run import _Spinner, _resolve_input, run_command
from miniautogen.cli.config import PipelineConfig, ProjectConfig, ProjectMeta
from miniautogen.cli.main import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(pipelines: dict[str, str] | None = None) -> ProjectConfig:
    """Build a minimal ProjectConfig with given pipeline targets."""
    pips = {}
    if pipelines:
        for name, target in pipelines.items():
            pips[name] = PipelineConfig(target=target)
    return ProjectConfig(
        project=ProjectMeta(name="test-proj"),
        pipelines=pips,
    )


# ---------------------------------------------------------------------------
# _resolve_input tests
# ---------------------------------------------------------------------------

class TestResolveInput:
    """Tests for the _resolve_input helper function."""

    def test_inline_text(self):
        assert _resolve_input("hello world") == "hello world"

    def test_none_with_tty(self, monkeypatch):
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        assert _resolve_input(None) is None

    def test_none_reads_stdin(self, monkeypatch):
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        monkeypatch.setattr(sys.stdin, "read", lambda: "piped data")
        assert _resolve_input(None) == "piped data"

    def test_file_reference_within_project(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "input.txt"
        f.write_text("file content")
        result = _resolve_input(f"@{f}")
        assert result == "file content"

    def test_file_reference_outside_project_rejected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        outside = Path("/tmp/outside_file.txt")
        with pytest.raises(click.BadParameter, match="within the project directory"):
            _resolve_input(f"@{outside}")

    def test_file_reference_not_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        missing = tmp_path / "no_such_file.txt"
        with pytest.raises(click.BadParameter, match="not found"):
            _resolve_input(f"@{missing}")

    def test_file_reference_os_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "bad.txt"
        target.write_text("x")

        def _raise(*a, **kw):
            raise OSError("disk error")

        monkeypatch.setattr("builtins.open", _raise)
        with pytest.raises(click.BadParameter, match="Cannot read"):
            _resolve_input(f"@{target}")


# ---------------------------------------------------------------------------
# _Spinner tests
# ---------------------------------------------------------------------------

class TestSpinner:
    """Tests for the _Spinner helper."""

    def test_start_stop(self):
        sp = _Spinner("working...")
        sp.start()
        assert sp._thread is not None
        assert sp._thread.is_alive()
        sp.stop()
        assert not sp._thread.is_alive()

    def test_update_message(self):
        sp = _Spinner("initial")
        assert sp._message == "initial"
        sp.update("updated")
        assert sp._message == "updated"

    def test_stop_with_final_message(self, capsys):
        sp = _Spinner("msg")
        sp.start()
        sp.stop(final="Done!")
        # Thread should be stopped
        assert sp._stop.is_set()

    def test_stop_without_thread(self):
        """stop() is safe even if start() was never called."""
        sp = _Spinner("msg")
        sp.stop()  # Should not raise

    def test_spin_loop_runs(self):
        """Verify the _spin method iterates frames."""
        sp = _Spinner("test")
        sp.start()
        # Give the spinner a moment to iterate
        import time
        time.sleep(0.2)
        sp.stop()
        # If we got here without error, the spin loop worked


# ---------------------------------------------------------------------------
# run_command tests (via CliRunner)
# ---------------------------------------------------------------------------

class TestRunCommand:
    """Integration tests for the 'run' Click command."""

    def _invoke(self, runner, args, monkeypatch, execute_return=None):
        """Helper to invoke run_command with execute_pipeline mocked."""
        if execute_return is None:
            execute_return = {"status": "completed", "events": 3}

        async def fake_execute(*a, **kw):
            return execute_return

        config = _make_config({"main": "pipelines.main:build"})

        monkeypatch.setattr(
            "miniautogen.cli.commands.run.require_project_config",
            lambda: (Path.cwd(), config),
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.execute_pipeline",
            fake_execute,
        )
        return runner.invoke(cli, ["run", *args])

    def test_basic_success(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = self._invoke(runner, [], monkeypatch)
        assert result.exit_code == 0
        assert "completed" in result.output.lower()

    def test_with_inline_input(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = self._invoke(runner, ["--input", "my data"], monkeypatch)
        assert result.exit_code == 0

    def test_with_json_output(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        ret = {"status": "completed", "events": 5}
        result = self._invoke(
            runner, ["--format", "json"], monkeypatch, execute_return=ret,
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["status"] == "completed"

    def test_pipeline_not_found(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        config = _make_config({"main": "pipelines.main:build"})
        monkeypatch.setattr(
            "miniautogen.cli.commands.run.require_project_config",
            lambda: (Path.cwd(), config),
        )
        result = runner.invoke(cli, ["run", "nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_execution_failure_text_format(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        fail_result = {"status": "failed", "error": "something broke"}
        result = self._invoke(
            runner, [], monkeypatch, execute_return=fail_result,
        )
        assert result.exit_code != 0

    def test_execution_failure_json_format(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        fail_result = {"status": "failed", "error": "something broke"}
        result = self._invoke(
            runner, ["--format", "json"], monkeypatch, execute_return=fail_result,
        )
        assert result.exit_code == 0  # JSON output doesn't raise SystemExit
        parsed = json.loads(result.output)
        assert parsed["status"] == "failed"

    def test_with_explain_flag(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        config = _make_config({"main": "pipelines.main:build"})

        async def fake_execute(*a, **kw):
            return {"status": "completed", "events": 1}

        pdata = {
            "mode": "sequential",
            "participants": ["agent1", "agent2"],
            "leader": "agent1",
            "max_rounds": 5,
        }

        monkeypatch.setattr(
            "miniautogen.cli.commands.run.require_project_config",
            lambda: (Path.cwd(), config),
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.execute_pipeline",
            fake_execute,
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.pipeline_ops.show_pipeline",
            lambda root, name: pdata,
        )
        result = runner.invoke(cli, ["run", "--explain"])
        assert result.exit_code == 0
        assert "sequential" in result.output.lower()
        assert "agent1" in result.output
        assert "Max rounds" in result.output

    def test_explain_with_input_and_timeout(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        config = _make_config({"main": "pipelines.main:build"})

        async def fake_execute(*a, **kw):
            return {"status": "completed", "events": 0}

        long_input = "A" * 100  # > 80 chars to trigger truncation

        monkeypatch.setattr(
            "miniautogen.cli.commands.run.require_project_config",
            lambda: (Path.cwd(), config),
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.execute_pipeline",
            fake_execute,
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.pipeline_ops.show_pipeline",
            lambda root, name: {},
        )
        result = runner.invoke(cli, [
            "run", "--explain", "--input", long_input, "--timeout", "30",
        ])
        assert result.exit_code == 0
        assert "..." in result.output  # truncated preview
        assert "30" in result.output  # timeout displayed

    def test_explain_with_resume(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        config = _make_config({"main": "pipelines.main:build"})

        async def fake_execute(*a, **kw):
            return {"status": "completed", "events": 0}

        monkeypatch.setattr(
            "miniautogen.cli.commands.run.require_project_config",
            lambda: (Path.cwd(), config),
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.execute_pipeline",
            fake_execute,
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.pipeline_ops.show_pipeline",
            lambda root, name: {},
        )
        result = runner.invoke(cli, [
            "run", "--explain", "--resume", "run-abc",
        ])
        # Should show "Resuming from checkpoint" in explain output
        assert "checkpoint" in result.output.lower() or "resum" in result.output.lower()

    def test_explain_show_pipeline_key_error(self, monkeypatch, tmp_path):
        """When show_pipeline raises KeyError, explain continues with empty data."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        config = _make_config({"main": "pipelines.main:build"})

        async def fake_execute(*a, **kw):
            return {"status": "completed", "events": 0}

        def raise_key_error(root, name):
            raise KeyError("not found")

        monkeypatch.setattr(
            "miniautogen.cli.commands.run.require_project_config",
            lambda: (Path.cwd(), config),
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.execute_pipeline",
            fake_execute,
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.pipeline_ops.show_pipeline",
            raise_key_error,
        )
        result = runner.invoke(cli, ["run", "--explain"])
        assert result.exit_code == 0

    def test_resume_flag_shows_info(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        config = _make_config({"main": "pipelines.main:build"})

        async def fake_execute(*a, **kw):
            return {"status": "completed", "events": 0}

        monkeypatch.setattr(
            "miniautogen.cli.commands.run.require_project_config",
            lambda: (Path.cwd(), config),
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.execute_pipeline",
            fake_execute,
        )
        result = runner.invoke(cli, ["run", "--resume", "run-xyz"])
        assert "resum" in result.output.lower()

    def test_spinner_used_on_tty(self, monkeypatch, tmp_path):
        """Spinner is started when stderr is a TTY and format is text."""
        monkeypatch.chdir(tmp_path)
        config = _make_config({"main": "pipelines.main:build"})

        monkeypatch.setattr(
            "miniautogen.cli.commands.run.require_project_config",
            lambda: (Path.cwd(), config),
        )
        monkeypatch.setattr(
            "miniautogen.cli.commands.run.run_async",
            lambda func, *a, **kw: {"status": "completed", "events": 0},
        )

        spinner_calls = {"start": 0, "stop": 0}

        class MockSpinner:
            def __init__(self, msg):
                pass

            def start(self):
                spinner_calls["start"] += 1

            def stop(self, final=""):
                spinner_calls["stop"] += 1

        monkeypatch.setattr("miniautogen.cli.commands.run._Spinner", MockSpinner)

        import miniautogen.cli.commands.run as run_mod

        fake_stderr = type("FakeTTY", (), {"isatty": lambda self: True})()
        monkeypatch.setattr(run_mod.sys, "stderr", fake_stderr)

        fake_stdin = type("FakeTTY", (), {"isatty": lambda self: True})()
        monkeypatch.setattr(run_mod.sys, "stdin", fake_stdin)

        # Call the underlying callback directly (unwrap the click decorator)
        run_command.callback(
            pipeline_name="main",
            timeout=None,
            output_format="text",
            verbose=False,
            input_value=None,
            resume=None,
            explain=False,
        )

        assert spinner_calls["start"] == 1
        assert spinner_calls["stop"] == 1

    def test_completed_with_events(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = self._invoke(
            runner, [], monkeypatch,
            execute_return={"status": "completed", "events": 7},
        )
        assert result.exit_code == 0
        assert "7" in result.output

    def test_completed_without_events(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = self._invoke(
            runner, [], monkeypatch,
            execute_return={"status": "completed", "events": 0},
        )
        assert result.exit_code == 0

    def test_input_file_bad_parameter_shows_error(self, monkeypatch, tmp_path):
        """When _resolve_input raises BadParameter, run_command echoes error and exits 1."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        config = _make_config({"main": "pipelines.main:build"})
        monkeypatch.setattr(
            "miniautogen.cli.commands.run.require_project_config",
            lambda: (Path.cwd(), config),
        )
        # Use a file path outside project to trigger BadParameter
        result = runner.invoke(cli, ["run", "--input", "@/etc/passwd"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# execute_pipeline tests
# ---------------------------------------------------------------------------

class TestExecutePipeline:
    """Tests for the execute_pipeline service function."""

    @pytest.fixture
    def config_with_pipeline(self):
        return _make_config({"main": "my_module:build_pipeline"})

    @pytest.mark.anyio
    async def test_success_path(self, monkeypatch, tmp_path, config_with_pipeline):
        from miniautogen.cli.services.run_pipeline import execute_pipeline

        # Create a fake module file
        mod_file = tmp_path / "my_module.py"
        mod_file.write_text("def build_pipeline(): return []")

        mock_runner = MagicMock()

        async def fake_run(pipeline, context):
            return {"output": "done"}

        mock_runner.run_pipeline = fake_run

        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.resolve_pipeline_target",
            lambda target, root: lambda: [],
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.PipelineRunner",
            lambda **kw: mock_runner,
        )

        result = await execute_pipeline(
            config_with_pipeline, "main", tmp_path,
        )
        assert result["status"] == "completed"
        assert result["input_provided"] is False

    @pytest.mark.anyio
    async def test_success_with_input(self, monkeypatch, tmp_path, config_with_pipeline):
        from miniautogen.cli.services.run_pipeline import execute_pipeline

        mock_runner = MagicMock()

        async def fake_run(pipeline, context):
            assert context["input"] == "my input"
            return {}

        mock_runner.run_pipeline = fake_run

        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.resolve_pipeline_target",
            lambda target, root: lambda: [],
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.PipelineRunner",
            lambda **kw: mock_runner,
        )

        result = await execute_pipeline(
            config_with_pipeline, "main", tmp_path, pipeline_input="my input",
        )
        assert result["status"] == "completed"
        assert result["input_provided"] is True

    @pytest.mark.anyio
    async def test_success_with_timeout(self, monkeypatch, tmp_path, config_with_pipeline):
        from miniautogen.cli.services.run_pipeline import execute_pipeline

        captured_policy = {}
        mock_runner = MagicMock()

        async def fake_run(pipeline, context):
            return {}

        mock_runner.run_pipeline = fake_run

        def make_runner(**kw):
            captured_policy["policy"] = kw.get("execution_policy")
            return mock_runner

        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.resolve_pipeline_target",
            lambda target, root: lambda: [],
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.PipelineRunner",
            make_runner,
        )

        result = await execute_pipeline(
            config_with_pipeline, "main", tmp_path, timeout=10.0,
        )
        assert result["status"] == "completed"
        assert captured_policy["policy"] is not None

    @pytest.mark.anyio
    async def test_pipeline_not_in_config(self, tmp_path, config_with_pipeline):
        from miniautogen.cli.services.run_pipeline import execute_pipeline

        with pytest.raises(KeyError, match="not found"):
            await execute_pipeline(config_with_pipeline, "nonexistent", tmp_path)

    @pytest.mark.anyio
    async def test_negative_timeout_rejected(self, tmp_path, config_with_pipeline):
        from miniautogen.cli.services.run_pipeline import execute_pipeline

        with pytest.raises(ValueError, match="positive"):
            await execute_pipeline(
                config_with_pipeline, "main", tmp_path, timeout=-5.0,
            )

    @pytest.mark.anyio
    async def test_import_error_returns_failure(self, monkeypatch, tmp_path, config_with_pipeline):
        from miniautogen.cli.services.run_pipeline import execute_pipeline

        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.resolve_pipeline_target",
            lambda target, root: (_ for _ in ()).throw(ImportError("no module")),
        )

        result = await execute_pipeline(config_with_pipeline, "main", tmp_path)
        assert result["status"] == "failed"
        assert result["error_type"] == "ImportError"

    @pytest.mark.anyio
    async def test_general_exception_returns_failure(self, monkeypatch, tmp_path, config_with_pipeline):
        from miniautogen.cli.services.run_pipeline import execute_pipeline

        mock_runner = MagicMock()

        async def raise_runtime(pipeline, context):
            raise RuntimeError("boom")

        mock_runner.run_pipeline = raise_runtime

        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.resolve_pipeline_target",
            lambda target, root: lambda: [],
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.PipelineRunner",
            lambda **kw: mock_runner,
        )

        result = await execute_pipeline(config_with_pipeline, "main", tmp_path)
        assert result["status"] == "failed"
        assert "boom" in result["error"]
        assert result["error_type"] == "RuntimeError"

    @pytest.mark.anyio
    async def test_click_exception_reraises(self, monkeypatch, tmp_path, config_with_pipeline):
        from miniautogen.cli.services.run_pipeline import execute_pipeline

        mock_runner = MagicMock()

        async def raise_click(pipeline, context):
            raise click.ClickException("click error")

        mock_runner.run_pipeline = raise_click

        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.resolve_pipeline_target",
            lambda target, root: lambda: [],
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.PipelineRunner",
            lambda **kw: mock_runner,
        )

        with pytest.raises(click.ClickException):
            await execute_pipeline(config_with_pipeline, "main", tmp_path)

    @pytest.mark.anyio
    async def test_resume_raises_execution_error(self, monkeypatch, tmp_path, config_with_pipeline):
        from miniautogen.cli.errors import ExecutionError
        from miniautogen.cli.services.run_pipeline import execute_pipeline

        mock_runner = MagicMock()
        mock_runner.run_pipeline = MagicMock()

        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.resolve_pipeline_target",
            lambda target, root: lambda: [],
        )
        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.PipelineRunner",
            lambda **kw: mock_runner,
        )

        with pytest.raises(ExecutionError, match="checkpoint"):
            await execute_pipeline(
                config_with_pipeline, "main", tmp_path,
                resume_run_id="run-123",
            )

    @pytest.mark.anyio
    async def test_sys_path_cleanup(self, monkeypatch, tmp_path, config_with_pipeline):
        """Project root is removed from sys.path after execution."""
        from miniautogen.cli.services.run_pipeline import execute_pipeline

        project_str = str(tmp_path)
        # Ensure it's not already there
        if project_str in sys.path:
            sys.path.remove(project_str)

        monkeypatch.setattr(
            "miniautogen.cli.services.run_pipeline.resolve_pipeline_target",
            lambda target, root: (_ for _ in ()).throw(ImportError("no mod")),
        )

        await execute_pipeline(config_with_pipeline, "main", tmp_path)
        assert project_str not in sys.path


# ---------------------------------------------------------------------------
# resolve_pipeline_target tests
# ---------------------------------------------------------------------------

class TestResolvePipelineTarget:
    """Tests for resolve_pipeline_target."""

    def test_invalid_format_no_colon(self, tmp_path):
        from miniautogen.cli.services.run_pipeline import resolve_pipeline_target

        with pytest.raises(ValueError, match="expected"):
            resolve_pipeline_target("no_colon_here", tmp_path)

    def test_module_not_found(self, tmp_path):
        from miniautogen.cli.services.run_pipeline import resolve_pipeline_target

        with pytest.raises(ImportError, match="not found"):
            resolve_pipeline_target("nonexistent.module:func", tmp_path)

    def test_file_outside_project(self, tmp_path, monkeypatch):
        from miniautogen.cli.services.run_pipeline import resolve_pipeline_target

        # Create a symlink pointing outside
        outside_dir = Path("/tmp/test_outside_miniautogen")
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "evil.py"
        outside_file.write_text("def func(): pass")

        link = tmp_path / "evil.py"
        try:
            link.symlink_to(outside_file)
        except OSError:
            pytest.skip("Cannot create symlink")

        with pytest.raises((ValueError, ImportError)):
            resolve_pipeline_target("evil:func", tmp_path)

    def test_package_init_resolution(self, tmp_path, monkeypatch):
        from miniautogen.cli.services.run_pipeline import resolve_pipeline_target

        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()
        init_file = pkg_dir / "__init__.py"
        init_file.write_text("def build(): return 'ok'")

        monkeypatch.syspath_prepend(str(tmp_path))

        result = resolve_pipeline_target("mypkg:build", tmp_path)
        assert callable(result)
