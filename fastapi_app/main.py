"""
AquaMind FastAPI entrypoint — Water Decision Intelligence Platform.

Two prediction surfaces are mounted (paths do not collide, but values can differ):

  Preferred for the Operations Dashboard / demo telemetry
    Legacy routers via model_service + ai/*.pkl:
    `/predict-shortage`, `/predict-groundwater-well`, `/detect-leak-signal`,
    `/analytics/water-stress`, `/ai/recommendation-engine/live`.
    The dashboard (`src/services/telemetry.ts`) uses this stack.

  Preferred for dedicated forecast / decision pages
    Framework ModelRegistry + joblib under fastapi_app/prediction/models/:
    `/api/v1/predictions/{demand,reservoir,stress}`, `/api/v1/decision`.
    Demand / Reservoir / Water Stress / Decision Intelligence pages use these.

Do not call both stacks for the same operator view — pick one source of truth
per screen. Compatibility aliases (e.g. `/api/vision/...` and `/vision/...`)
exist so the Express `/api` strip still reaches FastAPI.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

# Load local configuration before importing routes / vision keys.
load_dotenv(Path(__file__).resolve().parents[1] / ".env.local")

from fastapi_app.core.config import get_settings
from fastapi_app.core.rate_limit import limiter
from fastapi_app.core.security import get_current_user
from fastapi_app.core.startup_checks import parse_allowed_origins, validate_runtime_config
from fastapi_app.database.connection import SessionLocal, engine
from fastapi_app.database.models import Base
from fastapi_app.database.seeder import seed_database
from fastapi_app.routers import (
    auth,
    climate_risk,
    copilot,
    data_management,
    demand_forecast,
    decision_optimization,
    geospatial,
    predictions,
    recommendation_feedback,
    recommendations,
    reports,
    reservoir_forecast,
    water_stress_forecast,
    telemetry,
    vision_routes,
    water_intelligence,
    weather,
)

logger = logging.getLogger("aquamind.request")

# JSON/body ceiling for non-multipart requests (multipart routes enforce their own caps).
MAX_JSON_BYTES = int(os.getenv("AQUAMIND_MAX_JSON_BYTES", str(2 * 1024 * 1024)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_config()
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    # Demo seeding (including the well-known admin/password123 pilot account)
    # must never run in a persistent/production deployment. Opt-in explicitly
    # with AQUAMIND_SEED_DEMO_DATA=true if a non-dev environment genuinely
    # wants the seeded dataset (e.g. a public read-only demo).
    seed_opt_in = os.getenv("AQUAMIND_SEED_DEMO_DATA", "").strip().lower() in ("1", "true", "yes")
    if settings.environment == "development" or seed_opt_in:
        db = SessionLocal()
        try:
            seed_database(db)
        finally:
            db.close()
    else:
        print(
            f"[Startup] Demo seeding skipped (AQUAMIND_ENVIRONMENT={settings.environment!r}). "
            "Set AQUAMIND_SEED_DEMO_DATA=true to force-seed a non-development deployment."
        )
    # Warm sklearn models once at startup (singleton model_service).
    # Touching attributes alone does not load .pkl bytes — call load_model().
    try:
        from fastapi_app.services.model_service import model_service

        for label, model in (
            ("shortage", model_service.shortage_model),
            ("groundwater", model_service.groundwater_model),
            ("demand", model_service.demand_model),
            ("leak", model_service.leak_model),
        ):
            if model is None:
                continue
            try:
                if hasattr(model, "load_model"):
                    model.load_model()
            except Exception as model_exc:
                print(f"[Startup] {label} model warm-up skipped: {model_exc}")
        print("[Startup] ModelService warm-up complete")
    except Exception as exc:
        print(f"[Startup] ModelService warm-up skipped: {exc}")
    yield


_settings = get_settings()

app = FastAPI(
    title=_settings.app_name,
    description=(
        "AI-powered Water Decision Intelligence Platform. "
        "Prediction pipelines, decision recommendations, and scenario simulation. "
        "Telemetry and monitoring remain available as one of several data sources. "
        "Legacy ML diagnostic routes are retained for compatibility."
    ),
    version=_settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

origins = parse_allowed_origins(
    os.getenv("ALLOWED_ORIGINS"),
    environment=_settings.environment,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _failure_category(status_code: int) -> str:
    if status_code < 400:
        return "ok"
    if status_code == 429:
        return "rate_limit"
    if status_code < 500:
        return "client_error"
    return "server_error"


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "success": False,
            "message": "Too many requests. Please wait briefly and try again.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
        },
        headers={"Retry-After": "60"},
    )


@app.middleware("http")
async def security_and_observability(request: Request, call_next):
    from fastapi_app.core.ttl_cache import get_cache_status, reset_cache_status

    reset_cache_status()
    request_id = request.headers.get("x-request-id") or request.headers.get("X-Request-Id")
    if not request_id:
        request_id = uuid.uuid4().hex[:16]
    request.state.request_id = request_id

    content_type = (request.headers.get("content-type") or "").lower()
    content_length = request.headers.get("content-length")
    if (
        content_length
        and "multipart/form-data" not in content_type
        and request.method in {"POST", "PUT", "PATCH"}
    ):
        try:
            if int(content_length) > MAX_JSON_BYTES:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "success": False,
                        "message": "Request body too large.",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "request_id": request_id,
                    },
                    headers={"X-Request-Id": request_id},
                )
        except ValueError:
            pass

    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception:
        process_time = (time.time() - start_time) * 1000
        logger.exception(
            "ts=%s request_id=%s method=%s path=%s status=%s duration_ms=%.1f category=%s",
            datetime.now(timezone.utc).isoformat(),
            request_id,
            request.method,
            request.url.path,
            500,
            process_time,
            "server_error",
        )
        raise

    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    if request.url.scheme == "https" or forwarded_proto == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    cache_status = get_cache_status()
    if cache_status and cache_status != "SKIP":
        response.headers["X-Cache"] = cache_status

    logger.info(
        "ts=%s request_id=%s method=%s path=%s status=%s duration_ms=%.1f category=%s",
        datetime.now(timezone.utc).isoformat(),
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        process_time,
        _failure_category(response.status_code),
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation error: Input data failed schema validation.",
            "timestamp": datetime.utcnow().isoformat(),
            "errors": exc.errors(),
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Avoid echoing nested objects that might include internal paths.
    detail = exc.detail
    if not isinstance(detail, (str, int, float, bool)) and detail is not None:
        detail = "Request failed."
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": detail,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log type/message server-side only — never echo exception text to clients.
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "[Unhandled] request_id=%s type=%s",
        request_id,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error.",
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
        },
    )


@app.get("/", summary="Root Index", include_in_schema=False)
async def root():
    return {
        "service": _settings.app_name,
        "version": _settings.app_version,
        "status": "online",
        "architecture": [
            "data_sources",
            "processing",
            "prediction",
            "decision_engine",
            "water_intelligence_fusion",
        ],
        "documentation": "/docs",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health", summary="Health Check", tags=["System Health"])
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": _settings.app_name,
        "version": _settings.app_version,
        "prediction_backend": _settings.prediction_backend,
        "decision_engine_backend": _settings.decision_engine_backend,
        "demo_mode": _settings.demo_mode,
    }


@app.get(
    "/readiness",
    summary="Technical readiness",
    tags=["System Health"],
    description=(
        "Authenticated dependency-level readiness for demo and deployment checks: "
        "database latency, trained model artifacts, optional provider configuration, "
        "CLIPSeg state, and demo mode. Reports configured/unavailable only - no keys, "
        "tokens, filesystem paths, or secret values are returned. Does not call remote AI "
        "or weather providers."
    ),
)
async def readiness(_user=Depends(get_current_user)):
    from fastapi_app.services.readiness_service import build_readiness

    return build_readiness()


@app.get(
    "/ready",
    summary="Readiness Check (alias)",
    tags=["System Health"],
    include_in_schema=False,
    description="Alias for GET /readiness. Requires authentication.",
)
async def ready(_user=Depends(get_current_user)):
    from fastapi_app.services.readiness_service import build_readiness

    return build_readiness()


# Production prediction models
app.include_router(demand_forecast.router)
app.include_router(reservoir_forecast.router)
app.include_router(water_stress_forecast.router)
app.include_router(decision_optimization.router)
app.include_router(geospatial.router)

# Legacy / compatibility routers (real-time monitoring + existing ML façades)
app.include_router(auth.router)
app.include_router(telemetry.router)
app.include_router(predictions.router)
app.include_router(recommendations.router)
app.include_router(recommendation_feedback.router)
app.include_router(weather.router)
app.include_router(reports.router)
app.include_router(data_management.router)
app.include_router(vision_routes.router)
app.include_router(climate_risk.router)
app.include_router(copilot.router)
app.include_router(water_intelligence.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("fastapi_app.main:app", host="0.0.0.0", port=8000, reload=True)
