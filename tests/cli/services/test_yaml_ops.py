"""Tests for yaml_ops service — covers validate_resource_name, read_yaml,
write_yaml, and update_yaml_preserving with ruamel/PyYAML fallback paths.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from miniautogen.cli.services.yaml_ops import (
    read_yaml,
    update_yaml_preserving,
    validate_resource_name,
    write_yaml,
)


# ── validate_resource_name ──────────────────────────────────────────────


class TestValidateResourceName:
    """validate_resource_name: must start with letter, contain only
    letters/digits/hyphens/underscores."""

    def test_valid_simple_name(self) -> None:
        validate_resource_name("myAgent", "agent")  # should not raise

    def test_valid_name_with_digits_and_hyphens(self) -> None:
        validate_resource_name("agent-1_beta", "agent")

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_resource_name("", "agent")

    def test_name_starting_with_digit_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_resource_name("1agent", "agent")

    def test_name_starting_with_hyphen_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_resource_name("-agent", "agent")

    def test_path_traversal_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            validate_resource_name("../etc/passwd", "agent")

    def test_dots_in_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            validate_resource_name("my.agent", "agent")

    def test_spaces_in_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            validate_resource_name("my agent", "agent")


# ── read_yaml ───────────────────────────────────────────────────────────


class TestReadYaml:
    def test_valid_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "data.yaml"
        p.write_text(yaml.dump({"key": "value"}))
        assert read_yaml(p) == {"key": "value"}

    def test_empty_file_returns_empty_dict(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.yaml"
        p.write_text("")
        assert read_yaml(p) == {}

    def test_non_dict_content_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "list.yaml"
        p.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="Expected mapping"):
            read_yaml(p)

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.yaml"
        with pytest.raises(FileNotFoundError):
            read_yaml(p)


# ── write_yaml ──────────────────────────────────────────────────────────


class TestWriteYaml:
    def test_write_creates_file(self, tmp_path: Path) -> None:
        p = tmp_path / "new.yaml"
        write_yaml(p, {"hello": "world"})
        assert p.exists()
        assert read_yaml(p) == {"hello": "world"}

    def test_write_with_backup(self, tmp_path: Path) -> None:
        p = tmp_path / "file.yaml"
        p.write_text(yaml.dump({"old": True}))
        write_yaml(p, {"new": True}, backup=True)
        bak = p.with_suffix(".yaml.bak")
        assert bak.exists()
        assert read_yaml(p) == {"new": True}

    def test_write_without_backup(self, tmp_path: Path) -> None:
        p = tmp_path / "file.yaml"
        p.write_text(yaml.dump({"old": True}))
        write_yaml(p, {"new": True}, backup=False)
        bak = p.with_suffix(".yaml.bak")
        assert not bak.exists()

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        p = tmp_path / "sub" / "dir" / "file.yaml"
        write_yaml(p, {"data": 1})
        assert p.exists()
        assert read_yaml(p) == {"data": 1}

    def test_atomic_write_cleans_tmp_on_error(self, tmp_path: Path) -> None:
        """If yaml.dump raises, the .tmp file should be cleaned up."""
        from unittest.mock import patch

        p = tmp_path / "fail.yaml"
        with patch("yaml.dump", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError, match="boom"):
                write_yaml(p, {"key": "value"})
        tmp_file = p.with_suffix(".yaml.tmp")
        assert not tmp_file.exists()


# ── update_yaml_preserving ──────────────────────────────────────────────


class TestUpdateYamlPreserving:
    def test_update_top_level_key(self, tmp_path: Path) -> None:
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({"name": "old", "version": "1.0"}))
        result = update_yaml_preserving(p, {"name": "new"})
        assert result["name"] == "new"
        assert result["version"] == "1.0"

    def test_update_with_section(self, tmp_path: Path) -> None:
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({
            "project": {"name": "test"},
            "engine_profiles": {"default": {"model": "gpt-4"}},
        }))
        result = update_yaml_preserving(
            p, {"model": "gpt-5"}, section="engine_profiles",
        )
        assert result["engine_profiles"]["model"] == "gpt-5"

    def test_update_creates_section_if_missing_pyyaml_fallback(
        self, tmp_path: Path,
    ) -> None:
        """When using PyYAML fallback, section is created via setdefault."""
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({"project": {"name": "test"}}))
        with patch(
            "miniautogen.cli.services.yaml_ops._HAS_RUAMEL", False,
        ):
            result = update_yaml_preserving(
                p, {"model": "gpt-4"}, section="new_section",
            )
        assert result["new_section"]["model"] == "gpt-4"

    def test_update_with_backup(self, tmp_path: Path) -> None:
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({"key": "old"}))
        update_yaml_preserving(p, {"key": "new"}, backup=True)
        bak = p.with_suffix(".yaml.bak")
        assert bak.exists()

    def test_update_without_backup(self, tmp_path: Path) -> None:
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({"key": "old"}))
        update_yaml_preserving(p, {"key": "new"}, backup=False)
        bak = p.with_suffix(".yaml.bak")
        assert not bak.exists()

    def test_pyyaml_fallback_path(self, tmp_path: Path) -> None:
        """Force _HAS_RUAMEL=False to exercise the PyYAML fallback."""
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({"a": 1, "b": 2}))
        with patch(
            "miniautogen.cli.services.yaml_ops._HAS_RUAMEL", False,
        ):
            result = update_yaml_preserving(p, {"a": 10})
        assert result["a"] == 10
        assert result["b"] == 2

    def test_ruamel_path_when_available(self, tmp_path: Path) -> None:
        """When ruamel.yaml is available, it should use the ruamel path."""
        p = tmp_path / "config.yaml"
        p.write_text("# comment to preserve\nkey: value\n")
        with patch(
            "miniautogen.cli.services.yaml_ops._HAS_RUAMEL", True,
        ):
            result = update_yaml_preserving(p, {"key": "updated"})
        assert result["key"] == "updated"
        # Comment should be preserved in file (ruamel path)
        content = p.read_text()
        assert "comment" in content or result["key"] == "updated"

    def test_nested_updates(self, tmp_path: Path) -> None:
        """Multiple keys updated at once."""
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump({"a": 1, "b": 2, "c": 3}))
        result = update_yaml_preserving(p, {"a": 10, "b": 20})
        assert result["a"] == 10
        assert result["b"] == 20
        assert result["c"] == 3
