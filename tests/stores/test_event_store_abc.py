"""Tests for EventStore abstract base class."""

from __future__ import annotations

from abc import ABC

import pytest


class TestEventStoreABC:
    def test_import(self) -> None:
        from miniautogen.stores.event_store import EventStore  # noqa: F401

    def test_is_abstract(self) -> None:
        from miniautogen.stores.event_store import EventStore

        assert issubclass(EventStore, ABC)

    def test_cannot_instantiate(self) -> None:
        from miniautogen.stores.event_store import EventStore

        with pytest.raises(TypeError):
            EventStore()  # type: ignore[abstract]

    def test_has_append_method(self) -> None:
        from miniautogen.stores.event_store import EventStore

        assert hasattr(EventStore, "append")

    def test_has_list_events_method(self) -> None:
        from miniautogen.stores.event_store import EventStore

        assert hasattr(EventStore, "list_events")

    def test_has_count_events_method(self) -> None:
        from miniautogen.stores.event_store import EventStore

        assert hasattr(EventStore, "count_events")
