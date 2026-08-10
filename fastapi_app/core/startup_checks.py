"""Fail-closed startup checks for staging/production.

Local development and pytest keep convenient defaults. Staging and production
must set secrets and CORS explicitly — never ship with development fallbacks.
"""
from __future__ import annotations

import os
import re

from fastapi_app.core.config import get_settings

_DEV_FALLBACK_SECRET = "development-only-change-before-deployment"
_PLACEHOLDER_SECRETS = frozenset(
    {
        "",
        _DEV_FALLBACK_SECRET,
        "replace-with-a-long-random-secret",
        "changeme",
        "secret",
        "your-secret-here",
        "MY_APP_URL",
    }
)

_DEFAULT_DEV_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
)

_ORIGIN_RE = re.compile(r"^https?://[^/\s]+$", re.IGNORECASE)


def is_production_like(environment: str | None = None) -> bool:
    env = (environment or get_settings().environment or "development").strip().lower()
    return env in {"staging", "production"}


def assert_jwt_secret_safe(secret: str | None, environment: str) -> str:
    """Return a usable JWT secret or raise before the app serves traffic."""
    value = (secret or "").strip()
    if is_production_like(environment):
        if value in _PLACEHOLDER_SECRETS or len(value) < 32:
            raise RuntimeError(
                "JWT_SECRET_KEY must be set to a long random secret (≥32 chars) "
                f"when AQUAMIND_ENVIRONMENT={environment!r}. "
                "Do not use the development fallback or .env.example placeholders."
            )
        return value
    return value or _DEV_FALLBACK_SECRET


def parse_allowed_origins(
    raw: str | None,
    *,
    environment: str | None = None,
) -> list[str]:
    """Parse CORS origins. Staging/production require an explicit non-wildcard list."""
    env = (environment or get_settings().environment or "development").strip().lower()
    text = (raw or "").strip()

    if is_production_like(env):
        if not text:
            raise RuntimeError(
                "ALLOWED_ORIGINS must be set explicitly for staging/production "
                "(comma-separated https://… origins). Wildcard '*' is not allowed "
                "when credentials are enabled."
            )
        origins = [part.strip() for part in text.split(",") if part.strip()]
        if not origins:
            raise RuntimeError("ALLOWED_ORIGINS is empty after trimming.")
        if any(origin == "*" for origin in origins):
            raise RuntimeError(
                "ALLOWED_ORIGINS must not include '*' when allow_credentials=True."
            )
        for origin in origins:
            if not _ORIGIN_RE.match(origin):
                raise RuntimeError(
                    f"Invalid ALLOWED_ORIGINS entry {origin!r}. "
                    "Use full origins like https://app.example.com (no path)."
                )
        return origins

    if text:
        origins = [part.strip() for part in text.split(",") if part.strip() and part.strip() != "*"]
        return origins or list(_DEFAULT_DEV_ORIGINS)
    return list(_DEFAULT_DEV_ORIGINS)


def validate_runtime_config() -> None:
    """Raise at startup when production-like config is unsafe."""
    settings = get_settings()
    env = (settings.environment or "development").strip().lower()

    assert_jwt_secret_safe(os.getenv("JWT_SECRET_KEY"), env)
    parse_allowed_origins(os.getenv("ALLOWED_ORIGINS"), environment=env)

    if is_production_like(env):
        if settings.demo_mode:
            raise RuntimeError(
                "AQUAMIND_DEMO_MODE must be false in staging/production. "
                "Fixtures must never stand in for live providers outside demos."
            )
        database_url = os.getenv("DATABASE_URL")
        if not database_url or not database_url.strip():
            raise RuntimeError(
                "DATABASE_URL must be set explicitly for staging/production. "
                "Silent SQLite defaults are development-only."
            )
        seed_opt_in = os.getenv("AQUAMIND_SEED_DEMO_DATA", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if seed_opt_in:
            # Allowed but noisy — operators must know they opted into demo data.
            print(
                "[Startup] WARNING: AQUAMIND_SEED_DEMO_DATA=true in a production-like "
                "environment. Demo accounts will be seeded."
            )
