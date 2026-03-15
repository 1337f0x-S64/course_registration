"""
application/services/event_publisher.py — EventPublisher.

The EventPublisher decouples domain event production (inside aggregates) from
event consumption (in presentation layers or external systems).

Before this refactoring, the Application Service called print() directly
when events fired.  That hardcoded the system to a terminal and made it
impossible to add a GUI without modifying the service.

With EventPublisher, any presentation layer registers its own handler:
  - The CLI registers a function that prints to stdout.
  - A GUI registers a function that appends to a log widget or triggers
    a UI refresh.
  - A test registers nothing, so events are silently discarded.

The Application Service calls publish_all() after every command and never
needs to know who — if anyone — is listening.
"""

from __future__ import annotations
from typing import Callable, List
from course_registration.domain.events import DomainEvent

# A Handler is any callable that accepts a DomainEvent and returns nothing.
Handler = Callable[[DomainEvent], None]


class EventPublisher:
    """
    Simple synchronous in-process event bus.

    Multiple handlers can be registered and will all be called in order
    for every published event.  Handlers should be fast and non-blocking;
    for heavy work (sending email, writing to an external log) they should
    schedule the work asynchronously rather than doing it inline.
    """

    def __init__(self) -> None:
        self._handlers: List[Handler] = []

    def subscribe(self, handler: Handler) -> None:
        """Register a callback to be invoked for every published event."""
        self._handlers.append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Dispatch a single event to all registered handlers."""
        for handler in self._handlers:
            handler(event)

    def publish_all(self, events: List[DomainEvent]) -> None:
        """Dispatch a batch of events — called after each aggregate command."""
        for event in events:
            self.publish(event)
