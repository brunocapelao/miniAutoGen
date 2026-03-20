"""Tests for load_agent_specs() agent YAML discovery (Task 5)."""

from __future__ import annotations

import logging

import pytest
import yaml

from miniautogen.cli.services.agent_ops import load_agent_specs
from miniautogen.core.contracts.agent_spec import AgentSpec


class TestLoadAgentSpecsBasic:
    def test_loads_agents_from_yaml_files(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "alice.yaml").write_text(
            yaml.dump({"id": "alice", "name": "Alice"})
        )
        (agents_dir / "bob.yaml").write_text(
            yaml.dump({"id": "bob", "name": "Bob"})
        )

        specs = load_agent_specs(tmp_path)

        assert set(specs.keys()) == {"alice", "bob"}
        assert isinstance(specs["alice"], AgentSpec)
        assert specs["alice"].id == "alice"
        assert specs["alice"].name == "Alice"
        assert specs["bob"].id == "bob"

    def test_empty_agents_dir_returns_empty_dict(self, tmp_path):
        (tmp_path / "agents").mkdir()

        specs = load_agent_specs(tmp_path)

        assert specs == {}

    def test_no_agents_dir_returns_empty_dict(self, tmp_path):
        specs = load_agent_specs(tmp_path)

        assert specs == {}

    def test_agent_name_comes_from_filename_stem(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        # File named "researcher.yaml" — id defaults to "researcher" from stem
        (agents_dir / "researcher.yaml").write_text(
            yaml.dump({"name": "Research Agent"})
        )

        specs = load_agent_specs(tmp_path)

        assert "researcher" in specs
        assert specs["researcher"].id == "researcher"

    def test_explicit_id_in_yaml_takes_precedence(self, tmp_path):
        """setdefault means explicit id in YAML wins over stem."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "myfile.yaml").write_text(
            yaml.dump({"id": "custom-id", "name": "Custom Agent"})
        )

        specs = load_agent_specs(tmp_path)

        # Key is still the stem, but id is from YAML
        assert "myfile" in specs
        assert specs["myfile"].id == "custom-id"

    def test_results_are_sorted_by_filename(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        for name in ["zebra", "alpha", "middle"]:
            (agents_dir / f"{name}.yaml").write_text(
                yaml.dump({"name": name.capitalize()})
            )

        specs = load_agent_specs(tmp_path)

        assert list(specs.keys()) == ["alpha", "middle", "zebra"]


class TestLoadAgentSpecsErrorHandling:
    def test_invalid_yaml_skips_file_and_logs(self, tmp_path, caplog):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "bad.yaml").write_text("{{invalid: yaml: :")
        (agents_dir / "good.yaml").write_text(
            yaml.dump({"name": "Good Agent"})
        )

        with caplog.at_level(logging.ERROR):
            specs = load_agent_specs(tmp_path)

        assert "good" in specs
        assert "bad" not in specs
        assert any("bad.yaml" in r.message for r in caplog.records)

    def test_invalid_agent_spec_skips_file_and_logs(self, tmp_path, caplog):
        """AgentSpec with invalid id should be skipped."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        # id with invalid chars causes AgentSpec to fail
        (agents_dir / "invalid_spec.yaml").write_text(
            yaml.dump({"id": "!invalid!", "name": "Bad"})
        )
        (agents_dir / "valid_spec.yaml").write_text(
            yaml.dump({"name": "Valid"})
        )

        with caplog.at_level(logging.ERROR):
            specs = load_agent_specs(tmp_path)

        assert "valid_spec" in specs
        assert "invalid_spec" not in specs

    def test_empty_yaml_file_returns_empty_spec(self, tmp_path):
        """Empty YAML produces empty dict; id/name default from stem."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        # Empty file → yaml.safe_load returns None → {} → needs name
        # AgentSpec requires 'name' field so this should be skipped
        (agents_dir / "empty_agent.yaml").write_text("")

        specs = load_agent_specs(tmp_path)

        # AgentSpec requires name, so empty file should be skipped with log
        assert "empty_agent" not in specs
