"""End-to-end CLI workflow tests.

These tests validate complete user workflows across multiple
CLI commands, ensuring the full init -> check -> run chain works.

Note: ``run`` tests use a mock driver to avoid real API calls.
"""

from __future__ import annotations

import shutil
from unittest.mock import AsyncMock, patch

import yaml
from click.testing import CliRunner

from miniautogen.cli.config import CONFIG_FILENAME
from miniautogen.cli.main import cli


def _patch_engine_resolver():
    """Return a context-manager that makes EngineResolver.resolve return a fake driver."""
    from miniautogen.backends.models import (
        AgentEvent,
        BackendCapabilities,
        StartSessionResponse,
    )

    caps = BackendCapabilities()
    fake_driver = AsyncMock()
    fake_driver.start_session = AsyncMock(
        return_value=StartSessionResponse(session_id="fake", capabilities=caps),
    )

    async def _fake_send_turn(*args, **kwargs):
        yield AgentEvent(type="text_delta", session_id="fake", payload={"text": '{"answer": "mocked"}'})
        yield AgentEvent(type="turn_complete", session_id="fake")

    fake_driver.send_turn = _fake_send_turn
    fake_driver.close_session = AsyncMock()
    fake_driver.capabilities = caps

    return patch(
        "miniautogen.backends.engine_resolver.EngineResolver.resolve",
        return_value=fake_driver,
    )


class TestInitCheckRunWorkflow:
    """Test the complete project lifecycle: init -> check -> run."""

    def test_full_lifecycle(self, tmp_path, monkeypatch) -> None:
        """Create project, validate it, run the pipeline."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        # Step 1: Init
        result = runner.invoke(cli, ["init", "myproject"])
        assert result.exit_code == 0, f"init failed: {result.output}"
        assert "Workspace created" in result.output

        project_dir = tmp_path / "myproject"
        assert project_dir.is_dir()

        # Step 2: Check (from within project dir)
        monkeypatch.chdir(project_dir)
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 0, f"check failed: {result.output}"
        assert "passed" in result.output.lower()

        # Step 3: Run (with mocked driver to avoid real API calls)
        with _patch_engine_resolver():
            result = runner.invoke(cli, ["run"])
        assert result.exit_code == 0, f"run failed: {result.output}"
        assert "completed" in result.output.lower()

    def test_full_lifecycle_json_output(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Full lifecycle with JSON output format."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        runner.invoke(cli, ["init", "myproject"])
        monkeypatch.chdir(tmp_path / "myproject")

        # Check with JSON
        result = runner.invoke(cli, ["check", "--format", "json"])
        assert result.exit_code == 0
        assert '"passed": true' in result.output

        # Run with JSON (mocked driver)
        with _patch_engine_resolver():
            result = runner.invoke(cli, ["run", "--format", "json"])
        assert result.exit_code == 0
        assert '"status": "completed"' in result.output

    def test_lifecycle_custom_model_provider(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Init with custom model/provider, verify in check."""
        monkeypatch.chdir(tmp_path)
        # Set the API key so the environment check passes
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        runner = CliRunner()

        runner.invoke(cli, [
            "init", "myproject",
            "--model", "gemini-2.5-pro",
            "--provider", "gemini",
        ])

        # Verify config has correct values
        config_path = tmp_path / "myproject" / CONFIG_FILENAME
        with config_path.open() as f:
            config = yaml.safe_load(f)
        engines = config.get("engines", config.get("engine_profiles", {}))
        assert (
            engines["default_api"]["model"]
            == "gemini-2.5-pro"
        )
        assert (
            engines["default_api"]["provider"]
            == "gemini"
        )

        # Check should still pass
        monkeypatch.chdir(tmp_path / "myproject")
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 0

    def test_lifecycle_no_examples(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Init without examples, check, run -- all should work."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        runner.invoke(cli, ["init", "myproject", "--no-examples"])
        monkeypatch.chdir(tmp_path / "myproject")

        # Check should pass (no agents to validate)
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 0

        # Run should work (mocked driver)
        with _patch_engine_resolver():
            result = runner.invoke(cli, ["run"])
        assert result.exit_code == 0


class TestInitCheckFailureWorkflow:
    """Test that check catches problems in modified projects."""

    def test_check_fails_after_removing_skill(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Remove a skill referenced by an agent -> check should fail."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        runner.invoke(cli, ["init", "myproject"])
        project = tmp_path / "myproject"

        # Delete the example skill
        shutil.rmtree(project / "skills" / "example")

        monkeypatch.chdir(project)
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 1
        assert "fail" in result.output.lower()

    def test_check_fails_after_removing_tool(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Remove a tool referenced by an agent -> check should fail."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        runner.invoke(cli, ["init", "myproject"])
        project = tmp_path / "myproject"

        (project / "tools" / "web_search.yaml").unlink()

        monkeypatch.chdir(project)
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 1

    def test_check_fails_after_corrupting_agent(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Corrupt agent YAML -> check should report schema error."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        runner.invoke(cli, ["init", "myproject"])
        project = tmp_path / "myproject"

        # Write invalid agent YAML (missing required 'id')
        (project / "agents" / "researcher.yaml").write_text(
            "name: Missing ID Agent\nrole: test\n",
        )

        monkeypatch.chdir(project)
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 1

    def test_check_fails_after_deleting_pipeline(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Delete pipeline module -> check should fail."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        runner.invoke(cli, ["init", "myproject"])
        project = tmp_path / "myproject"

        (project / "pipelines" / "main.py").unlink()

        monkeypatch.chdir(project)
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 1


class TestSessionLifecycleWorkflow:
    """Test session management across multiple runs."""

    def test_sessions_list_empty_after_init(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Fresh project has no sessions."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        runner.invoke(cli, ["init", "myproject"])
        monkeypatch.chdir(tmp_path / "myproject")

        result = runner.invoke(cli, ["sessions", "list"])
        assert result.exit_code == 0
        assert "no runs" in result.output.lower()

    def test_sessions_clean_on_empty(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Clean on empty project succeeds with 0 deleted."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        runner.invoke(cli, ["init", "myproject"])
        monkeypatch.chdir(tmp_path / "myproject")

        result = runner.invoke(cli, ["sessions", "clean", "--yes"])
        assert result.exit_code == 0
        assert "deleted 0" in result.output.lower()


class TestErrorRecoveryWorkflow:
    """Test error handling and recovery scenarios."""

    def test_init_retry_after_failure(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Failed init (exists) -> retry with different name -> success."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        # First init succeeds
        result = runner.invoke(cli, ["init", "myproject"])
        assert result.exit_code == 0

        # Second init with same name fails
        result = runner.invoke(cli, ["init", "myproject"])
        assert result.exit_code != 0

        # Third init with different name succeeds
        result = runner.invoke(cli, ["init", "otherproject"])
        assert result.exit_code == 0

    def test_run_without_project(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Run outside project directory gives clear error."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["run"])
        assert result.exit_code != 0

    def test_check_without_project(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Check outside project directory gives clear error."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["check"])
        assert result.exit_code != 0

    def test_run_nonexistent_pipeline(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Run with invalid pipeline name gives clear error."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        runner.invoke(cli, ["init", "myproject"])
        monkeypatch.chdir(tmp_path / "myproject")

        result = runner.invoke(cli, ["run", "nonexistent"])
        assert result.exit_code != 0


class TestProjectStructureVerification:
    """Verify the generated project structure is complete and valid."""

    def test_all_directories_created(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Init creates all required directories."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["init", "myproject"])
        p = tmp_path / "myproject"

        assert (p / "agents").is_dir()
        assert (p / "skills").is_dir()
        assert (p / "tools").is_dir()
        assert (p / "mcp").is_dir()
        assert (p / "memory").is_dir()
        assert (p / "pipelines").is_dir()

    def test_all_example_files_created(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Init creates all example files."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["init", "myproject"])
        p = tmp_path / "myproject"

        assert (p / CONFIG_FILENAME).is_file()
        assert (p / "agents" / "researcher.yaml").is_file()
        assert (p / "skills" / "example" / "SKILL.md").is_file()
        assert (p / "skills" / "example" / "skill.yaml").is_file()
        assert (p / "tools" / "web_search.yaml").is_file()
        assert (p / "memory" / "profiles.yaml").is_file()
        assert (p / "pipelines" / "main.py").is_file()
        assert (p / ".env").is_file()
        assert (p / ".gitignore").is_file()

    def test_config_is_valid_yaml(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Generated config is valid and parseable."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["init", "myproject"])

        config_path = tmp_path / "myproject" / CONFIG_FILENAME
        with config_path.open() as f:
            config = yaml.safe_load(f)

        assert config["project"]["name"] == "myproject"
        assert "engines" in config or "engine_profiles" in config
        assert "memory_profiles" in config
        assert "flows" in config or "pipelines" in config
        assert "defaults" in config

    def test_agent_yaml_is_valid(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Generated agent YAML has required fields."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["init", "myproject"])

        agent_path = (
            tmp_path / "myproject" / "agents" / "researcher.yaml"
        )
        with agent_path.open() as f:
            agent = yaml.safe_load(f)

        assert "id" in agent
        assert "name" in agent
        assert "role" in agent
        assert "skills" in agent
        assert "memory" in agent
        assert "engine_profile" in agent

    def test_pipeline_is_importable(
        self, tmp_path, monkeypatch,
    ) -> None:
        """Generated pipeline module can be imported."""
        import importlib
        import sys

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["init", "myproject"])

        project_dir = str(tmp_path / "myproject")
        sys.path.insert(0, project_dir)
        try:
            mod = importlib.import_module("pipelines.main")
            assert hasattr(mod, "build_pipeline")
            pipeline = mod.build_pipeline()
            assert hasattr(pipeline, "run")
        finally:
            sys.path.remove(project_dir)
            # Clean up cached module to avoid polluting other tests
            for key in list(sys.modules):
                if key.startswith("pipelines"):
                    del sys.modules[key]
