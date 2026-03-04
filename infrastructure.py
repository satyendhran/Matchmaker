"""
Infrastructure Abstractions
=============================
Interfaces and in-memory implementations for:
- Pagination        (cursor / offset-based)
- Distributed Lock  (in-process default, Redis-ready interface)
- Response Cache    (in-memory LRU with TTL, Redis-ready interface)
- Enhanced Event Dispatcher (async-capable, multi-server-ready interface)
"""

import asyncio
import hashlib
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Protocol
from collections.abc import Callable,Coroutine
from matchmaker.domain.events import DomainEvent






@dataclass
class Page:
    """A page of results."""

    items: list[Any]
    total: int  
    page: int  
    page_size: int
    has_next: bool
    has_prev: bool

    @property
    def total_pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)


class Paginator:
    """Utility to paginate any list."""

    @staticmethod
    def paginate(
        items: list[Any],
        page: int = 1,
        page_size: int = 20,
    ) -> Page:
        """Return a Page slice from a list.

        Args:
            items: Full list of items
            page: 1-indexed page number
            page_size: Number of items per page
        """
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        sliced = items[start:end]

        return Page(
            items=sliced,
            total=total,
            page=page,
            page_size=page_size,
            has_next=end < total,
            has_prev=page > 1,
        )

    @staticmethod
    def sql_offset_limit(page: int, page_size: int) -> tuple[int, int]:
        """Return (offset, limit) for SQL queries."""
        offset = (max(1, page) - 1) * page_size
        return (offset, page_size)






class IDistributedLock(ABC):
    """Interface for distributed locking.

    Implementations:
    - InProcessLock      (default — single-instance)
    - Future: RedisLock  (multi-instance, requires redis-py)
    """

    @abstractmethod
    def acquire(self, key: str, ttl_seconds: int = 30) -> bool:
        """Acquire a lock.  Returns True if acquired."""
        ...

    @abstractmethod
    def release(self, key: str) -> None:
        """Release a previously acquired lock."""
        ...

    @abstractmethod
    def is_locked(self, key: str) -> bool:
        """Check if a key is currently locked."""
        ...


class InProcessLock(IDistributedLock):
    """Thread-safe in-process lock (not distributed, but API-compatible).

    Use this as the default implementation when running a single instance.
    Swap to RedisLock when scaling to multiple instances.
    """

    def __init__(self):
        self._locks: dict[str, float] = {}  
        self._mutex = threading.Lock()

    def acquire(self, key: str, ttl_seconds: int = 30) -> bool:
        with self._mutex:
            now = time.time()
            
            if key in self._locks and self._locks[key] > now:
                return False  
            self._locks[key] = now + ttl_seconds
            return True

    def release(self, key: str) -> None:
        with self._mutex:
            self._locks.pop(key, None)

    def is_locked(self, key: str) -> bool:
        with self._mutex:
            expiry = self._locks.get(key, 0)
            if expiry > time.time():
                return True
            
            self._locks.pop(key, None)
            return False






class ICache(ABC):
    """Interface for response caching.

    Implementations:
    - InMemoryCache  (default — LRU with TTL)
    - Future: RedisCache
    """

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Get a cached value.  Returns None on miss."""
        ...

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Set a cached value with TTL."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a cached value."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached values."""
        ...


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class InMemoryCache(ICache):
    """LRU cache with per-entry TTL.

    Thread-safe.  Suitable for single-instance deployments.
    """

    def __init__(self, max_size: int = 512):
        self._max_size = max_size
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._mutex = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._mutex:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() > entry.expires_at:
                self._store.pop(key, None)
                return None
            
            self._store.move_to_end(key)
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        with self._mutex:
            self._store[key] = _CacheEntry(
                value=value, expires_at=time.time() + ttl_seconds
            )
            self._store.move_to_end(key)
            
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._mutex:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._mutex:
            self._store.clear()


def cache_key(*parts: Any) -> str:
    """Generate a deterministic cache key from parts."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]






class IAsyncEventDispatcher(ABC):
    """Async-capable event dispatcher interface.

    Supports:
    - Sync handlers  (fire-and-forget in a thread)
    - Async handlers (awaited on the event loop)
    - Subscriber patterns  (subscribe to specific event types or all)
    """

    @abstractmethod
    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Callable[[DomainEvent], Any],
    ) -> None:
        ...

    @abstractmethod
    def subscribe_all(self, handler: Callable[[DomainEvent], Any]) -> None:
        ...

    @abstractmethod
    def dispatch(self, event: DomainEvent) -> None:
        """Fire-and-forget dispatch (sync or async internally)."""
        ...


class EnhancedEventDispatcher(IAsyncEventDispatcher):
    """In-process dispatcher with optional async support.

    When an asyncio event loop is running, async handlers are scheduled
    on it.  Otherwise, all handlers are called synchronously.

    For multi-server deployment, replace this with an adapter that
    publishes to Redis Pub/Sub, RabbitMQ, or similar.
    """

    def __init__(self):
        self._handlers: dict[type, list[Callable]] = {}
        self._global_handlers: list[Callable] = []

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Callable[[DomainEvent], Any],
    ) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def subscribe_all(self, handler: Callable[[DomainEvent], Any]) -> None:
        self._global_handlers.append(handler)

    def dispatch(self, event: DomainEvent) -> None:
        handlers = list(self._global_handlers)
        handlers.extend(self._handlers.get(type(event), []))

        for handler in handlers:
            try:
                result = handler(event)
                
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        
                        asyncio.run(result)
            except Exception:
                
                pass
