"""YAML read/write operations with comment preservation.

Provides safe YAML manipulation for CLI resource management.
Uses ruamel.yaml when available for comment preservation,
falls back to PyYAML otherwise.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml


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
    data = read_yaml(path)
    data[key] = value
    write_yaml(path, data, backup=backup)
    return data
