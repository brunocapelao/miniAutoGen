from __future__ import annotations

from pathlib import Path

from miniautogen._json import dumps, loads
from typing import Any


class ResponseCache:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self, key: str) -> dict[str, Any] | None:
        data = self._load()
        value = data.get(key)
        return value if isinstance(value, dict) else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        data = self._load()
        data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(dumps(data, indent=True), encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        loaded = loads(self.path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
