"""Tests for RunDetailView widget."""

import pytest
from textual.app import App, ComposeResult

from miniautogen.tui.content.run_detail import RunDetailView


def test_run_detail_is_widget() -> None:
    """Test that RunDetailView is a valid Textual widget."""
    rdv = RunDetailView(flow_name="test-flow", flow_mode="workflow")
    assert rdv.flow_name == "test-flow"


def test_run_detail_starts_at_step_zero() -> None:
    """Test that RunDetailView starts with no steps."""
    rdv = RunDetailView(flow_name="test", flow_mode="workflow")
    assert rdv.current_step == 0
    assert rdv.total_steps == 0


class RunDetailTestApp(App):
    """Test application containing RunDetailView."""

    def compose(self) -> ComposeResult:
        yield RunDetailView(flow_name="research-flow", flow_mode="workflow")


@pytest.mark.asyncio
async def test_run_detail_renders() -> None:
    """Test that RunDetailView renders without error."""
    app = RunDetailTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        rdv = app.query_one(RunDetailView)
        assert rdv is not None


@pytest.mark.asyncio
async def test_run_detail_update_progress() -> None:
    """Test that update_progress updates internal state."""
    app = RunDetailTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        rdv = app.query_one(RunDetailView)
        rdv.update_progress(current=2, total=5, label="Research")
        assert rdv.current_step == 2
        assert rdv.total_steps == 5


@pytest.mark.asyncio
async def test_run_detail_has_flow_title() -> None:
    """Test that RunDetailView displays flow title."""
    app = RunDetailTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        rdv = app.query_one(RunDetailView)
        title = rdv.query_one("#flow-title")
        assert title is not None
        content = str(title.render())
        assert "research-flow" in content


@pytest.mark.asyncio
async def test_run_detail_has_progress_bar() -> None:
    """Test that RunDetailView has a progress bar."""
    app = RunDetailTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        rdv = app.query_one(RunDetailView)
        progress = rdv.query_one("#run-progress")
        assert progress is not None


@pytest.mark.asyncio
async def test_run_detail_set_completed() -> None:
    """Test that set_completed updates final status."""
    app = RunDetailTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        rdv = app.query_one(RunDetailView)
        rdv.set_completed(status="completed", duration="2.5s")
        assert rdv._final_status == "completed"
        meta = rdv.query_one("#flow-meta")
        content = str(meta.render())
        assert "completed" in content or "✓" in content
