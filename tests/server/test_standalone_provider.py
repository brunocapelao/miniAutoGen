"""Tests for StandaloneProvider — store-backed ConsoleDataProvider."""

from __future__ import annotations

import pytest

from miniautogen.server.provider_protocol import ConsoleDataProvider


def test_protocol_has_async_query_methods():
    """ConsoleDataProvider protocol must define async store-backed query methods."""
    assert hasattr(ConsoleDataProvider, "query_runs")
    assert hasattr(ConsoleDataProvider, "query_run")
    assert hasattr(ConsoleDataProvider, "query_run_events")


from unittest.mock import MagicMock

from miniautogen.stores.in_memory_event_store import InMemoryEventStore
from miniautogen.stores.in_memory_run_store import InMemoryRunStore


@pytest.fixture
def run_store():
    return InMemoryRunStore()


@pytest.fixture
def event_store():
    return InMemoryEventStore()


@pytest.fixture
def base_provider():
    """Mock base provider for config/agents/flows."""
    p = MagicMock()
    p.get_config.return_value = {"project_name": "test"}
    p.get_agents.return_value = [{"name": "a1"}]
    p.get_agent.return_value = {"name": "a1"}
    p.get_pipelines.return_value = [{"name": "flow1"}]
    p.get_pipeline.return_value = {"name": "flow1"}
    return p


@pytest.mark.anyio
async def test_standalone_provider_satisfies_protocol(
    run_store, event_store, base_provider
):
    from miniautogen.server.standalone_provider import StandaloneProvider

    sp = StandaloneProvider(
        base_provider=base_provider,
        run_store=run_store,
        event_store=event_store,
    )
    assert isinstance(sp, ConsoleDataProvider)


@pytest.mark.anyio
async def test_query_runs_returns_from_store(run_store, event_store, base_provider):
    from miniautogen.server.standalone_provider import StandaloneProvider

    await run_store.save_run("r1", {"run_id": "r1", "status": "completed"})
    await run_store.save_run("r2", {"run_id": "r2", "status": "running"})

    sp = StandaloneProvider(
        base_provider=base_provider,
        run_store=run_store,
        event_store=event_store,
    )
    items, total = await sp.query_runs(offset=0, limit=10)
    assert total == 2
    assert len(items) == 2


@pytest.mark.anyio
async def test_query_run_returns_single(run_store, event_store, base_provider):
    from miniautogen.server.standalone_provider import StandaloneProvider

    await run_store.save_run("r1", {"run_id": "r1", "status": "completed"})

    sp = StandaloneProvider(
        base_provider=base_provider,
        run_store=run_store,
        event_store=event_store,
    )
    result = await sp.query_run("r1")
    assert result is not None
    assert result["run_id"] == "r1"


@pytest.mark.anyio
async def test_query_run_events_returns_from_store(
    run_store, event_store, base_provider
):
    from miniautogen.server.standalone_provider import StandaloneProvider
    from miniautogen.core.contracts.events import ExecutionEvent
    from datetime import datetime, timezone

    evt = ExecutionEvent(
        type="run_started",
        timestamp=datetime.now(timezone.utc),
        run_id="r1",
        correlation_id="c1",
        scope="test",
        payload={},
    )
    await event_store.append("r1", evt)

    sp = StandaloneProvider(
        base_provider=base_provider,
        run_store=run_store,
        event_store=event_store,
    )
    items, total = await sp.query_run_events("r1", offset=0, limit=100)
    assert total == 1
    assert len(items) == 1
    assert items[0]["type"] == "run_started"


@pytest.mark.anyio
async def test_config_delegates_to_base(run_store, event_store, base_provider):
    from miniautogen.server.standalone_provider import StandaloneProvider

    sp = StandaloneProvider(
        base_provider=base_provider,
        run_store=run_store,
        event_store=event_store,
    )
    assert sp.get_config() == {"project_name": "test"}
    assert sp.get_agents() == [{"name": "a1"}]
