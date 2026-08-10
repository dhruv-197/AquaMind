"""Shared pytest fixtures for FastAPI endpoint tests.

Most routers now require a bearer token (see fastapi_app/core/security.py —
previously only /auth/* was protected). Tests that exercise the HTTP layer
via TestClient need an authenticated client instead of a bare one.
"""
from __future__ import annotations

import base64
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest
from fastapi.testclient import TestClient

from fastapi_app.main import app

TEST_USER_EMAIL = "pytest-runner@aquamind.test"
TEST_USER_PASSWORD = "PytestRunner123"

# 1x1 PNG — used wherever vision upload validation requires real image bytes.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def _clear_process_caches():
    """L1 TTL caches must not leak hits across tests in the same process."""
    from fastapi_app.core.ttl_cache import (
        model_status_cache,
        recommendation_cache,
        vision_history_cache,
        weather_cache,
        wi_cache,
    )

    for cache in (
        wi_cache,
        weather_cache,
        recommendation_cache,
        model_status_cache,
        vision_history_cache,
    ):
        cache.clear()
    yield
    for cache in (
        wi_cache,
        weather_cache,
        recommendation_cache,
        model_status_cache,
        vision_history_cache,
    ):
        cache.clear()


@pytest.fixture(scope="session")
def api_client() -> TestClient:
    """Bare (unauthenticated) TestClient — use for /auth/* and public routes.

    Deliberately a distinct instance from `auth_client` below (not mutated
    in place) so tests asserting "this must be unauthenticated" can't be
    silently broken by another test having attached a bearer token to a
    shared client first.
    """
    return TestClient(app)


@pytest.fixture(scope="session")
def _test_user_token(api_client: TestClient) -> str:
    """Signs up a dedicated pytest user once per session (idempotent — falls
    back to login if it already exists from a previous run against the same DB)."""
    signup = api_client.post(
        "/auth/signup",
        json={
            "username": "pytest_runner",
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "role": "user",
        },
    )
    if signup.status_code == 201:
        return signup.json()["data"]["access_token"]

    login = api_client.post(
        "/auth/login", json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
    )
    assert login.status_code == 200, f"Test-user login failed: {login.text}"
    return login.json()["data"]["access_token"]


@pytest.fixture(scope="session")
def auth_client(_test_user_token: str) -> TestClient:
    """A separate TestClient instance with a valid bearer token attached to every request."""
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {_test_user_token}"})
    return client
