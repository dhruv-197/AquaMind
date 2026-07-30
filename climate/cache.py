"""Short-TTL disk cache for Open-Meteo upstream responses."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path(__file__).resolve().parent / ".om_cache"
CACHE_TTL_SEC = int(os.getenv("AQUAMIND_CLIMATE_CACHE_TTL", "1800"))  # 30 min
# Unauthenticated (pre-auth-wiring) callers could vary lat/lon to grow this
# directory indefinitely since expired entries were only ever skipped on
# read, never deleted. Cap total cached files and evict on write.
MAX_CACHE_FILES = int(os.getenv("AQUAMIND_CLIMATE_CACHE_MAX_FILES", "2000"))


def _key(namespace: str, payload: dict) -> str:
    raw = json.dumps({"ns": namespace, **payload}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:28]


def read_cache(namespace: str, payload: dict) -> Optional[dict]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_key(namespace, payload)}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(data.get("_cached_at", 0)) > CACHE_TTL_SEC:
            return None
        return data.get("body")
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _evict_if_needed() -> None:
    try:
        entries = list(CACHE_DIR.glob("*.json"))
    except OSError:
        return
    now = time.time()
    # Always drop entries stale beyond 4x TTL — cheap, bounded first pass.
    for entry in entries:
        try:
            if now - entry.stat().st_mtime > CACHE_TTL_SEC * 4:
                entry.unlink(missing_ok=True)
        except OSError:
            continue
    remaining = [e for e in entries if e.exists()]
    if len(remaining) <= MAX_CACHE_FILES:
        return
    # Still over budget: evict oldest-first until back under the cap.
    remaining.sort(key=lambda e: e.stat().st_mtime)
    for entry in remaining[: len(remaining) - MAX_CACHE_FILES]:
        try:
            entry.unlink(missing_ok=True)
        except OSError:
            continue


def write_cache(namespace: str, payload: dict, body: Any) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_key(namespace, payload)}.json"
    path.write_text(
        json.dumps({"_cached_at": time.time(), "body": body}, ensure_ascii=False),
        encoding="utf-8",
    )
    _evict_if_needed()
