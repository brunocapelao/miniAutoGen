"""EventBus: async event bus with typed and global subscriptions.

Implements the EventSink protocol (publish) and adds subscribe/unsubscribe.
Subscribers are async callables: Callable[[ExecutionEvent], Awaitable[None]].
Handler exceptions are caught and logged (fire-and-forget semantics).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Awaitable, Callable

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.observability import get_logger

_logger = get_logger(__name__)

# Type alias for event handlers
EventHandler = Callable[[ExecutionEvent], Awaitable[None]]


class EventBus:
    """Async event bus that allows subscribers to react to events.

    Implements EventSink protocol (publish) + adds subscribe capability.
    Subscribers are async callables: Callable[[ExecutionEvent], Awaitable[None]]
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._global_subscribers: list[EventHandler] = []

    def subscribe(self, event_type: str | None, handler: EventHandler) -> None:
        """Subscribe to a specific event type (or all events if None).

        Args:
            event_type: The event type to subscribe to, or None for all events.
            handler: Async callable that receives the event.
        """
        if event_type is None:
            self._global_subscribers.append(handler)
        else:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str | None, handler: EventHandler) -> None:
        """Remove a subscription.

        Args:
            event_type: The event type to unsubscribe from, or None for global.
            handler: The handler to remove.
        """
        if event_type is None:
            try:
                self._global_subscribers.remove(handler)
            except ValueError:
                pass
        else:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass

    async def publish(self, event: ExecutionEvent) -> None:
        """Publish event to all matching subscribers.

        Calls type-specific handlers + global handlers.
        Catches and logs exceptions from handlers (fire-and-forget).

        Args:
            event: The execution event to publish.
        """
        handlers: list[EventHandler] = []

        # Collect type-specific handlers
        if event.type in self._subscribers:
            handlers.extend(self._subscribers[event.type])

        # Collect global handlers
        handlers.extend(self._global_subscribers)

        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                _logger.warning(
                    "event_handler_error",
                    event_type=event.type,
                    handler=getattr(handler, "__name__", repr(handler)),
                    exc_info=True,
                )
