"""
In-process event dispatcher.

Simple pub/sub for domain events. Easily replaceable with
Kafka, RabbitMQ, or any async event bus.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable

from matchmaker.domain.events import DomainEvent
from matchmaker.domain.interfaces import IEventDispatcher

logger = logging.getLogger(__name__)


class InProcessEventDispatcher(IEventDispatcher):
    """Synchronous in-process event dispatcher.

    Good enough for monolith; swap for async bus when scaling.
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._global_handlers: list[Callable] = []

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to a specific event type."""
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: Callable) -> None:
        """Subscribe to ALL events (e.g., audit logger)."""
        self._global_handlers.append(handler)

    def dispatch(self, events: list[DomainEvent]) -> None:
        """Dispatch events to all registered handlers."""
        for event in events:
            # Type-specific handlers
            for handler in self._handlers.get(event.event_type, []):
                try:
                    handler(event)
                except Exception as e:
                    logger.error(
                        "Event handler error for %s: %s",
                        event.event_type,
                        e,
                        exc_info=True,
                    )

            # Global handlers (audit, logging)
            for handler in self._global_handlers:
                try:
                    handler(event)
                except Exception as e:
                    logger.error("Global event handler error: %s", e, exc_info=True)


def audit_log_handler(event: DomainEvent) -> None:
    """Default audit handler — logs all events."""
    logger.info(
        "AUDIT | %s | %s | %s",
        event.event_type,
        event.occurred_at,
        {k: v for k, v in event.__dict__.items() if k != "metadata"},
    )
