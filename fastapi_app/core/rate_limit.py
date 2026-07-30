"""Shared slowapi Limiter instance.

Defined separately from main.py so routers can import it directly for
per-route `@limiter.limit(...)` decorators without a circular import.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["240/minute"])
