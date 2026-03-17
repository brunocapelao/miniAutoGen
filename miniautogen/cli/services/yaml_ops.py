"""YAML read/write operations with comment preservation.

Uses ruamel.yaml for comment-preserving round-trips when updating
existing files. Falls back to PyYAML for simple writes.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

try:
    from ruamel.yaml import YAML as RuamelYAML

    _HAS_RUAMEL = True
except ImportError:
    _HAS_RUAMEL = False


def read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file and return its contents as a dict."""
    with path.open() as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        msg = f"Expected mapping in {path}, got {type(data).__name__}"
        raise ValueError(msg)
    return data


def _read_ruamel(path: Path) -> Any:
    """Read YAML preserving comments via ruamel.yaml."""
    ry = RuamelYAML()
    ry.preserve_quotes = True
    with path.open() as f:
        return ry.load(f)


def _write_ruamel(path: Path, data: Any) -> None:
    """Write YAML preserving comments via ruamel.yaml."""
    ry = RuamelYAML()
    ry.preserve_quotes = True
    ry.default_flow_style = False
    tmp = path.with_suffix(".yaml.tmp")
    try:
        with tmp.open("w") as f:
            ry.dump(data, f)
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def write_yaml(path: Path, data: dict[str, Any], *, backup: bool = True) -> None:
    """Write data to a YAML file with optional backup.

    Creates parent directories if needed. Creates a .bak backup
    of the existing file before overwriting.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if backup and path.is_file():
        shutil.copy2(path, path.with_suffix(".yaml.bak"))

    tmp = path.with_suffix(".yaml.tmp")
    try:
        with tmp.open("w") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def update_yaml_preserving(
    path: Path,
    updates: dict[str, Any],
    *,
    section: str | None = None,
    backup: bool = True,
) -> dict[str, Any]:
    """Update specific keys in a YAML file preserving comments.

    If ruamel.yaml is available, preserves comments and formatting.
    Otherwise, falls back to standard PyYAML round-trip.

    Args:
        path: YAML file path.
        updates: Dict of key-value pairs to update.
        section: Optional nested section key (e.g. "engine_profiles").
        backup: Whether to create a .bak backup.

    Returns:
        The updated data dict.
    """
    if backup and path.is_file():
        shutil.copy2(path, path.with_suffix(".yaml.bak"))

    if _HAS_RUAMEL:
        data = _read_ruamel(path)
        target = data
        if section and section in data:
            target = data[section]
        for k, v in updates.items():
            target[k] = v
        _write_ruamel(path, data)
        # Return plain dict for callers
        return read_yaml(path)
    else:
        data = read_yaml(path)
        target = data
        if section:
            target = data.setdefault(section, {})
        for k, v in updates.items():
            target[k] = v
        write_yaml(path, data, backup=False)
        return data


def update_yaml_key(
    path: Path,
    key: str,
    value: Any,
    *,
    backup: bool = True,
) -> dict[str, Any]:
    """Update a single top-level key in a YAML file.

    Returns the updated data dict.
    """
    return update_yaml_preserving(path, {key: value}, backup=backup)
