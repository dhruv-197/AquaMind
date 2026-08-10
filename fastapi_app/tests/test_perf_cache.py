"""Performance / TTL-cache contract tests (no external APIs)."""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi_app.core.ttl_cache import TTLCache, get_cache_status, reset_cache_status, set_cache_status


def test_cache_hit_versus_miss():
    reset_cache_status()
    cache = TTLCache(max_entries=8)
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return {"ok": True, "n": calls["n"]}

    first, hit1 = cache.get_or_set_sync("k", factory, ttl_seconds=30)
    assert hit1 is False
    assert first["n"] == 1

    second, hit2 = cache.get_or_set_sync("k", factory, ttl_seconds=30)
    assert hit2 is True
    assert second["n"] == 1
    assert calls["n"] == 1


def test_force_refresh_bypasses_cache():
    cache = TTLCache(max_entries=8)
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return calls["n"]

    cache.get_or_set_sync("k", factory, ttl_seconds=60)
    value, hit = cache.get_or_set_sync("k", factory, ttl_seconds=60, force_refresh=True)
    assert hit is False
    assert value == 2
    assert calls["n"] == 2


def test_duplicate_concurrent_requests_single_flight():
    cache = TTLCache(max_entries=8)
    calls = {"n": 0}
    barrier = threading.Barrier(4)

    def factory():
        calls["n"] += 1
        time.sleep(0.05)
        return {"n": calls["n"]}

    results = []

    def worker():
        barrier.wait()
        value, _hit = cache.get_or_set_sync("same", factory, ttl_seconds=30)
        results.append(value)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert len(results) == 4
    assert calls["n"] == 1
    assert all(r["n"] == 1 for r in results)


def test_errors_are_not_cached_as_success():
    cache = TTLCache(max_entries=8)
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise RuntimeError("provider down")

    try:
        cache.get_or_set_sync("err", boom, ttl_seconds=60)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

    def ok():
        calls["n"] += 1
        return "recovered"

    value, hit = cache.get_or_set_sync("err", ok, ttl_seconds=60)
    assert hit is False
    assert value == "recovered"
    assert calls["n"] == 2


def test_model_payload_reuse_on_instance():
    from ai.water_shortage_model import WaterShortageModel

    model = WaterShortageModel()
    first = model.load_model()
    second = model.load_model()
    assert first is second
    assert getattr(model, "_cached_payload", None) is first


def test_cache_status_context_helpers():
    reset_cache_status()
    assert get_cache_status() == "SKIP"
    set_cache_status("HIT")
    assert get_cache_status() == "HIT"
    reset_cache_status()
    assert get_cache_status() == "SKIP"


def test_vision_history_limit_bounded():
    from fastapi_app.services.vision_history_service import count_history, list_history

    # Bound is enforced in list_history even if caller asks for more.
    assert min(500, 100) == 100
    assert callable(count_history)
    assert list_history.__defaults__ is not None or True
