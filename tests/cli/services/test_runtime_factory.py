"""Tests for CLI runtime factory helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    config_data = {
        "project": {"name": "test-project", "version": "0.1.0"},
        "defaults": {"engine": "openai"},
        "engines": {
            "openai": {
                "provider": "openai",
                "model": "gpt-4o-mini",
            }
        },
        "flows": {},
    }
    (tmp_path / "miniautogen.yaml").write_text(yaml.dump(config_data))

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "coder.yaml").write_text(
        yaml.dump({
            "id": "coder",
            "name": "coder",
            "role": "assistant",
            "goal": "Write clean code",
            "engine_profile": "openai",
        })
    )

    return tmp_path


@pytest.mark.anyio
async def test_create_runtime_raises_value_error_for_unknown_agent(workspace: Path) -> None:
    from miniautogen.cli.services.runtime_factory import create_runtime

    with pytest.raises(ValueError, match="Agent 'missing' not found. Available: coder"):
        await create_runtime(workspace, "missing")


@pytest.mark.anyio
async def test_create_runtime_uses_null_event_sink_by_default(workspace: Path) -> None:
    from miniautogen.api import NullEventSink
    from miniautogen.cli.services.runtime_factory import create_runtime

    captured: dict[str, object] = {}

    class _StubRuntime:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        async def initialize(self) -> None:
            return None

    with (
        patch(
            "miniautogen.cli.services.runtime_factory.AgentRuntime",
            _StubRuntime,
        ),
        patch(
            "miniautogen.cli.services.runtime_factory.EngineResolver"
        ) as mock_resolver,
    ):
        mock_resolver.return_value.create_fresh_driver.return_value = object()
        await create_runtime(workspace, "coder")

    assert isinstance(captured["event_sink"], NullEventSink)


@pytest.mark.anyio
async def test_create_runtime_accepts_custom_event_sink(workspace: Path) -> None:
    from miniautogen.api import InMemoryEventSink
    from miniautogen.cli.services.runtime_factory import create_runtime

    captured: dict[str, object] = {}

    class _StubRuntime:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        async def initialize(self) -> None:
            return None

    sink = InMemoryEventSink()

    with (
        patch(
            "miniautogen.cli.services.runtime_factory.AgentRuntime",
            _StubRuntime,
        ),
        patch(
            "miniautogen.cli.services.runtime_factory.EngineResolver"
        ) as mock_resolver,
    ):
        mock_resolver.return_value.create_fresh_driver.return_value = object()
        await create_runtime(workspace, "coder", event_sink=sink)

    assert captured["event_sink"] is sink
