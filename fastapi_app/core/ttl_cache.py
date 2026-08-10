"""Short-lived in-memory TTL cache with single-flight coalescing.

Used for dashboard-critical responses (water intelligence, weather, model
status, recommendation envelopes) so concurrent identical requests share one
computation instead of stampeding sklearn / Open-Meteo / Gemini.

Disk caches (``ai/.rec_cache``, ``climate/.om_cache``) remain the durable
layer for provider results; this module is the process-local L1.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")

# Middleware reads this to set X-Cache: HIT|MISS|BYPASS|SKIP
_cache_status: ContextVar[str] = ContextVar("aquamind_cache_status", default="SKIP")


def get_cache_status() -> str:
    return _cache_status.get()


def set_cache_status(status: str) -> None:
    _cache_status.set(status)


def reset_cache_status() -> None:
    _cache_status.set("SKIP")


def stable_key(*parts: Any) -> str:
    """Hash arbitrary JSON-serializable parts into a short cache key."""
    raw = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


@dataclass
class _Entry:
    value: Any
    expires_at: float


class TTLCache:
    """Thread-safe process-local TTL map with optional max size."""

    def __init__(self, *, max_entries: int = 256) -> None:
        self._max = max_entries
        self._store: dict[str, _Entry] = {}
        self._lock = threading.RLock()
        self._inflight_sync: dict[str, threading.Event] = {}
        self._inflight_errors: dict[str, BaseException] = {}

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at <= time.monotonic():
                self._store.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            return
        with self._lock:
            if len(self._store) >= self._max and key not in self._store:
                oldest = min(self._store.items(), key=lambda kv: kv[1].expires_at)
                self._store.pop(oldest[0], None)
            self._store[key] = _Entry(value=value, expires_at=time.monotonic() + ttl_seconds)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def get_or_set_sync(
        self,
        key: str,
        factory: Callable[[], T],
        *,
        ttl_seconds: float,
        force_refresh: bool = False,
    ) -> tuple[T, bool]:
        """Return ``(value, cache_hit)``. Coalesces concurrent misses for ``key``."""
        if force_refresh:
            set_cache_status("BYPASS")
            value = factory()
            self.set(key, value, ttl_seconds)
            return value, False

        cached = self.get(key)
        if cached is not None:
            set_cache_status("HIT")
            return cached, True

        leader = False
        event: threading.Event
        with self._lock:
            cached = self.get(key)
            if cached is not None:
                set_cache_status("HIT")
                return cached, True
            if key in self._inflight_sync:
                event = self._inflight_sync[key]
            else:
                event = threading.Event()
                self._inflight_sync[key] = event
                leader = True

        if not leader:
            event.wait(timeout=max(120.0, ttl_seconds))
            with self._lock:
                err = self._inflight_errors.pop(key, None)
            if err is not None:
                raise err
            cached = self.get(key)
            if cached is not None:
                set_cache_status("HIT")
                return cached, True
            set_cache_status("MISS")
            value = factory()
            self.set(key, value, ttl_seconds)
            return value, False

        set_cache_status("MISS")
        try:
            value = factory()
            self.set(key, value, ttl_seconds)
            return value, False
        except BaseException as exc:
            with self._lock:
                self._inflight_errors[key] = exc
            raise
        finally:
            with self._lock:
                self._inflight_sync.pop(key, None)
            event.set()


# Shared named caches (one process).
wi_cache = TTLCache(max_entries=64)
weather_cache = TTLCache(max_entries=32)
recommendation_cache = TTLCache(max_entries=32)
model_status_cache = TTLCache(max_entries=32)
vision_history_cache = TTLCache(max_entries=64)

WI_TTL_SEC = 45.0
WEATHER_TTL_SEC = 120.0
RECOMMENDATION_TTL_SEC = 60.0
MODEL_STATUS_TTL_SEC = 60.0
VISION_HISTORY_TTL_SEC = 30.0


async def run_in_thread(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Bound blocking work off the event loop (default asyncio thread pool)."""
    return await asyncio.to_thread(func, *args, **kwargs)


async def cached_threaded(
    cache: TTLCache,
    key: str,
    factory: Callable[[], T],
    *,
    ttl_seconds: float,
    force_refresh: bool = False,
) -> T:
    """Async wrapper: TTL + single-flight + ``asyncio.to_thread`` for ``factory``.

    Cache status is set on the async task (not the worker thread) so middleware
    can read it via ContextVar.
    """
    if not force_refresh:
        cached = cache.get(key)
        if cached is not None:
            set_cache_status("HIT")
            return cached

    def _guarded() -> tuple[T, bool]:
        return cache.get_or_set_sync(
            key, factory, ttl_seconds=ttl_seconds, force_refresh=force_refresh
        )

    value, hit = await run_in_thread(_guarded)
    if force_refresh:
        set_cache_status("BYPASS")
    else:
        set_cache_status("HIT" if hit else "MISS")
    return value
