"""Focused reliability/security hardening regressions."""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from fastapi_app.core.config import get_settings
from fastapi_app.database import connection as db_connection
from fastapi_app.routers import vision_routes
from fastapi_app.tests.conftest import TINY_PNG, TEST_USER_EMAIL


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


def test_vision_rejects_corrupt_bytes(auth_client):
    payload = {"file": ("demo.png", b"not-an-image", "image/png")}
    response = auth_client.post("/api/vision/analyze", files=payload, data={"mode": "reservoir"})
    assert response.status_code == 400
    body = response.json()
    detail = body.get("detail") or body.get("message") or ""
    assert "corrupt" in detail.lower() or "unsupported" in detail.lower()
    assert "Traceback" not in detail


def test_vision_rejects_empty_upload(auth_client):
    payload = {"file": ("empty.png", b"", "image/png")}
    response = auth_client.post("/api/vision/analyze", files=payload, data={"mode": "reservoir"})
    assert response.status_code == 400


def test_vision_rejects_oversized_upload(auth_client, monkeypatch):
    monkeypatch.setattr(vision_routes, "MAX_UPLOAD_BYTES", 64)
    oversized = TINY_PNG + (b"x" * 128)
    payload = {"file": ("big.png", oversized, "image/png")}
    response = auth_client.post("/api/vision/analyze", files=payload, data={"mode": "reservoir"})
    assert response.status_code == 413


def test_forgot_password_does_not_reveal_unknown_email(api_client):
    response = api_client.post(
        "/auth/forgot-password",
        json={
            "email": "definitely-missing@example.com",
            "reset_token": "not-a-real-token",
            "new_password": "NewPassword123!",
        },
    )
    assert response.status_code == 400
    detail = response.json().get("detail") or response.json().get("message") or ""
    assert "not found" not in detail.lower()
    assert "invalid or expired" in detail.lower()


def test_password_reset_token_hashed_and_not_logged_in_production(api_client, caplog):
    from fastapi_app.database.connection import SessionLocal
    from fastapi_app.database.models import PasswordResetToken

    with env(AQUAMIND_ENVIRONMENT="production", AQUAMIND_DEMO_MODE="false"):
        with caplog.at_level(logging.INFO):
            response = api_client.post(
                "/auth/request-password-reset",
                json={"email": TEST_USER_EMAIL},
            )
        assert response.status_code == 200
        body = response.json()
        assert "token" not in body
        assert "reset_token" not in body
        for record in caplog.records:
            if "[PasswordReset] token for" in record.getMessage():
                pytest.fail("plaintext reset token logged outside development/demo")

    db = SessionLocal()
    try:
        row = (
            db.query(PasswordResetToken)
            .order_by(PasswordResetToken.created_at.desc())
            .first()
        )
        assert row is not None
        assert len(row.token_hash) == 64
        assert all(c in "0123456789abcdef" for c in row.token_hash)
    finally:
        db.close()


def test_get_db_rolls_back_on_error(monkeypatch):
    mock_db = MagicMock()
    mock_session_local = MagicMock(return_value=mock_db)
    monkeypatch.setattr(db_connection, "SessionLocal", mock_session_local)

    gen = db_connection.get_db()
    session = next(gen)
    assert session is mock_db

    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("force rollback"))

    mock_db.rollback.assert_called()
    mock_db.close.assert_called()


def test_prediction_error_hides_exception_text(auth_client, monkeypatch):
    from fastapi_app.services import model_service as ms

    def boom(**kwargs):
        raise RuntimeError(r"secret path C:\ai\train.py leaked")

    monkeypatch.setattr(ms.model_service, "predict_shortage", boom)
    response = auth_client.post(
        "/predict-shortage",
        json={
            "reservoir_capacity_pct": 40,
            "rainfall_deficit_pct": 10,
            "temperature_c": 30,
            "daily_demand_mgd": 50,
        },
    )
    assert response.status_code == 500
    detail = response.json().get("detail") or response.json().get("message") or ""
    assert "train.py" not in detail
    assert "C:\\" not in detail
    assert "Shortage model inference failed" in detail


def test_legacy_detect_leak_does_not_fake_success(auth_client, monkeypatch):
    from fastapi_app.services import model_service as ms

    monkeypatch.setattr(ms.model_service, "leak_model", None)
    with env(AQUAMIND_DEMO_MODE="false"):
        response = auth_client.post(
            "/detect-leak",
            json={
                "pressure_bar": 3.0,
                "pressure_drop_bar": 0.5,
                "acoustic_vibration_db": 40,
                "flow_velocity_m_s": 1.2,
                "frequency_spike_hz": 100,
            },
        )
    assert response.status_code == 500
    body = response.json()
    assert body.get("data") in (None, {})
    detail = body.get("detail") or body.get("message") or ""
    assert "train.py" not in detail
