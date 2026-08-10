"""Security and production-operation hardening regressions."""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fastapi_app.core.config import get_settings
from fastapi_app.core.safe_paths import UnsafeDatasetPathError, resolve_dataset_path
from fastapi_app.core.startup_checks import (
    assert_jwt_secret_safe,
    parse_allowed_origins,
    validate_runtime_config,
)
from fastapi_app.main import app
from fastapi_app.services.auth_service import AuthService
from fastapi_app.tests.conftest import TEST_USER_EMAIL, TEST_USER_PASSWORD


@contextmanager
def env(**overrides: str | None):
    previous = {key: os.environ.get(key) for key in overrides}
    for key, value in overrides.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_parse_allowed_origins_dev_defaults():
    origins = parse_allowed_origins(None, environment="development")
    assert "http://localhost:3000" in origins
    assert "*" not in origins


def test_parse_allowed_origins_production_requires_explicit():
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        parse_allowed_origins(None, environment="production")
    with pytest.raises(RuntimeError, match="\\*"):
        parse_allowed_origins("*", environment="staging")
    with pytest.raises(RuntimeError, match="Invalid"):
        parse_allowed_origins("not-a-url", environment="production")
    origins = parse_allowed_origins(
        " https://app.example.com ,https://www.example.com ",
        environment="production",
    )
    assert origins == ["https://app.example.com", "https://www.example.com"]


def test_jwt_secret_rejects_placeholders_in_production():
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        assert_jwt_secret_safe("replace-with-a-long-random-secret", "production")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        assert_jwt_secret_safe("development-only-change-before-deployment", "staging")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        assert_jwt_secret_safe("short", "production")
    ok = assert_jwt_secret_safe("x" * 32, "production")
    assert ok == "x" * 32


def test_validate_runtime_config_blocks_demo_mode_in_production():
    with env(
        AQUAMIND_ENVIRONMENT="production",
        JWT_SECRET_KEY="x" * 32,
        ALLOWED_ORIGINS="https://app.example.com",
        DATABASE_URL="sqlite:///aquamind.db",
        AQUAMIND_DEMO_MODE="true",
    ):
        with pytest.raises(RuntimeError, match="DEMO_MODE"):
            validate_runtime_config()


def test_validate_runtime_config_requires_database_url():
    with env(
        AQUAMIND_ENVIRONMENT="production",
        JWT_SECRET_KEY="x" * 32,
        ALLOWED_ORIGINS="https://app.example.com",
        DATABASE_URL=None,
        AQUAMIND_DEMO_MODE="false",
    ):
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            validate_runtime_config()


def test_path_traversal_rejected():
    with pytest.raises(UnsafeDatasetPathError):
        resolve_dataset_path("../.env.local")
    with pytest.raises(UnsafeDatasetPathError):
        resolve_dataset_path(str(Path.cwd() / ".env.local"))
    with pytest.raises(UnsafeDatasetPathError):
        resolve_dataset_path("notes.txt")


def test_unauthenticated_sensitive_routes_return_401(api_client):
    for path, method in (
        ("/recommendation", "get"),
        ("/api/vision/history", "get"),
        ("/reports", "get"),
        ("/imports/reservoir", "post"),
        ("/auth/promote", "post"),
        ("/readiness", "get"),
    ):
        if method == "get":
            response = api_client.get(path)
        else:
            response = api_client.post(path, json={})
        assert response.status_code == 401, path
        detail = response.json().get("detail") or response.json().get("message") or ""
        assert "not found" not in str(detail).lower()


def test_malformed_and_expired_tokens_return_generic_401(api_client):
    bad = api_client.get(
        "/reports",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert bad.status_code == 401
    detail = bad.json().get("detail") or bad.json().get("message") or ""
    assert detail == "Invalid or expired credentials"

    expired = AuthService.create_access_token(
        {"sub": TEST_USER_EMAIL, "role": "user"},
        expires_delta=timedelta(seconds=-5),
    )
    expired_resp = api_client.get(
        "/reports",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert expired_resp.status_code == 401
    expired_detail = expired_resp.json().get("detail") or expired_resp.json().get("message") or ""
    assert expired_detail == "Invalid or expired credentials"


def test_login_does_not_reveal_unknown_email(api_client):
    response = api_client.post(
        "/auth/login",
        json={"email": "missing-user@example.com", "password": "whatever"},
    )
    assert response.status_code == 401
    detail = response.json().get("detail") or response.json().get("message") or ""
    assert detail == "Invalid email or password credentials"


def test_non_admin_cannot_promote_or_import(auth_client):
    promote = auth_client.post(
        "/auth/promote",
        json={"email": TEST_USER_EMAIL, "role": "admin"},
    )
    assert promote.status_code == 403
    assert (promote.json().get("detail") or promote.json().get("message")) == "Access denied."

    import_resp = auth_client.post(
        "/imports/reservoir",
        files={"file": ("bad.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert import_resp.status_code == 403


def test_admin_can_reach_promote_endpoint():
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        json={"email": "admin@centralvalleywater.gov", "password": "password123"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    # Promote a known test user to government_officer then back to user.
    promote = client.post(
        "/auth/promote",
        json={"email": TEST_USER_EMAIL, "role": "government_officer"},
    )
    assert promote.status_code == 200
    assert promote.json()["data"]["role"] == "government_officer"

    restore = client.post(
        "/auth/promote",
        json={"email": TEST_USER_EMAIL, "role": "user"},
    )
    assert restore.status_code == 200


def test_vision_history_is_user_scoped(auth_client):
    from fastapi_app.database.connection import SessionLocal
    from fastapi_app.database.models import User, VisionAnalysis
    from fastapi_app.services import vision_history_service

    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.email == TEST_USER_EMAIL).first()
        assert owner is not None
        other = db.query(User).filter(User.email == "admin@centralvalleywater.gov").first()
        assert other is not None

        vision_history_service.persist_analysis(
            db,
            user_id=other.id,
            asset_label="secret-reservoir",
            vision_mode="reservoir",
            result={
                "provider": "test",
                "reservoir_health": 55,
                "confidence": 0.9,
                "summary": "other user scan",
            },
        )
        vision_history_service.persist_analysis(
            db,
            user_id=owner.id,
            asset_label="my-reservoir",
            vision_mode="reservoir",
            result={
                "provider": "test",
                "reservoir_health": 70,
                "confidence": 0.8,
                "summary": "owner scan",
            },
        )
    finally:
        db.close()

    response = auth_client.get("/api/vision/history", params={"force_refresh": True})
    assert response.status_code == 200
    labels = {row["asset_label"] for row in response.json().get("history", [])}
    assert "my-reservoir" in labels
    assert "secret-reservoir" not in labels


def test_security_headers_present(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in (response.headers.get("content-security-policy") or "")
    assert response.headers.get("x-request-id")


def test_oversized_json_rejected_by_content_length(auth_client, monkeypatch):
    monkeypatch.setattr("fastapi_app.main.MAX_JSON_BYTES", 128)
    payload = b'{"region_id":"' + (b"x" * 200) + b'"}'
    response = auth_client.post(
        "/recommendation",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    body = response.json()
    assert "too large" in (body.get("message") or "").lower()


def test_malformed_csv_import_rejected_for_admin():
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        json={"email": "admin@centralvalleywater.gov", "password": "password123"},
    )
    assert login.status_code == 200
    client.headers.update({"Authorization": f"Bearer {login.json()['data']['access_token']}"})
    response = client.post(
        "/imports/reservoir",
        files={"file": ("bad.csv", b"this is not,csv\x00binary", "text/csv")},
    )
    assert response.status_code in (400, 422)
    detail = response.json().get("detail") or response.json().get("message") or ""
    assert "Traceback" not in detail
    assert "C:\\" not in detail


def test_health_does_not_echo_secrets(api_client):
    response = api_client.get("/health")
    text = response.text.lower()
    assert "jwt" not in text
    assert "gemini" not in text
    assert "password" not in text
    for secret_name in ("GEMINI_API_KEY", "JWT_SECRET_KEY"):
        value = os.getenv(secret_name)
        if value:
            assert value not in response.text
