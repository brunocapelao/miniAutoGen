"""Tests for the MiniAutoGen Dash app shell."""

from __future__ import annotations

import pytest

from textual.app import App

from miniautogen.tui.app import MiniAutoGenDash


def test_app_is_textual_app() -> None:
    assert issubclass(MiniAutoGenDash, App)


def test_app_has_title() -> None:
    app = MiniAutoGenDash()
    assert app.TITLE == "MiniAutoGen Dash"


def test_app_has_subtitle() -> None:
    app = MiniAutoGenDash()
    assert "team" in app.SUB_TITLE.lower() or "agent" in app.SUB_TITLE.lower()


def test_app_has_key_bindings() -> None:
    app = MiniAutoGenDash()
    binding_keys = {b.key for b in app.BINDINGS}
    # Core navigation keys from the design spec
    assert "question_mark" in binding_keys or "?" in binding_keys
    assert "escape" in binding_keys
    assert "f" in binding_keys
    assert "t" in binding_keys


def test_app_has_css() -> None:
    """App must define CSS (inline or file)."""
    app = MiniAutoGenDash()
    assert app.CSS or app.CSS_PATH


@pytest.mark.asyncio
async def test_app_populates_sidebar_on_mount(tmp_path) -> None:
    """TeamSidebar should be populated with agents from data provider on mount."""
    import yaml

    # Create a minimal project with one agent
    config = {
        "project": {"name": "test", "version": "0.1.0"},
        "defaults": {"engine_profile": "default_api", "memory_profile": "default"},
        "engine_profiles": {
            "default_api": {
                "kind": "api",
                "provider": "litellm",
                "model": "gpt-4o-mini",
                "temperature": 0.2,
            },
        },
        "pipelines": {},
    }
    (tmp_path / "miniautogen.yaml").write_text(yaml.dump(config))
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    agent_data = {
        "id": "researcher",
        "version": "1.0.0",
        "name": "researcher",
        "role": "researcher",
        "goal": "Research topics",
        "engine_profile": "default_api",
    }
    (agents_dir / "researcher.yaml").write_text(yaml.dump(agent_data))

    app = MiniAutoGenDash(project_root=str(tmp_path))
    async with app.run_test(size=(120, 40)) as pilot:
        from miniautogen.tui.widgets.team_sidebar import TeamSidebar
        sidebar = app.query_one(TeamSidebar)
        assert sidebar.agent_count >= 1
        await pilot.press("q")


@pytest.mark.asyncio
async def test_app_has_event_sink_after_mount() -> None:
    """App should create a TuiEventSink on mount."""
    app = MiniAutoGenDash()
    async with app.run_test(size=(120, 40)) as pilot:
        assert hasattr(app, "_event_sink")
        assert app._event_sink is not None
        await pilot.press("q")


@pytest.mark.asyncio
async def test_events_flow_to_interaction_log() -> None:
    """Events published to TuiEventSink should reach InteractionLog via EventBridge."""
    from miniautogen.core.contracts.events import ExecutionEvent
    from miniautogen.core.events.types import EventType
    from miniautogen.tui.widgets.work_panel import WorkPanel

    app = MiniAutoGenDash()
    async with app.run_test(size=(120, 40)) as pilot:
        # Publish an event to the sink
        assert app._event_sink is not None
        event = ExecutionEvent(
            type=EventType.COMPONENT_STARTED.value,
            run_id="test-run",
            payload={"component_name": "Planning", "step_number": 1},
        )
        await app._event_sink.publish(event)

        # Give the bridge worker time to process (batch interval is 100ms)
        import asyncio
        await asyncio.sleep(0.3)

        # Verify the interaction log received the event
        work_panel = app.query_one(WorkPanel)
        assert work_panel.interaction_log.entry_count >= 1
        await pilot.press("q")


def test_app_has_run_completed_handler() -> None:
    """App must have an on_run_completed handler method."""
    assert hasattr(MiniAutoGenDash, "on_run_completed")
    assert callable(MiniAutoGenDash.on_run_completed)


@pytest.mark.asyncio
async def test_app_mounts_without_error() -> None:
    """Smoke test: the app mounts and can be started in headless mode."""
    app = MiniAutoGenDash()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.is_running
        await pilot.press("q")
