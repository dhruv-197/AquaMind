"""
AquaMind FastAPI entrypoint — Water Decision Intelligence Platform.

Two prediction surfaces are mounted:
  - `/api/v1/predictions/{reservoir,demand}` and `/api/v1/water-stress` — the
    trained-model framework (ModelRegistry + joblib artifacts under
    fastapi_app/prediction/models/).
  - Legacy compatibility routers (`/predict-shortage`, `/predict-groundwater-well`,
    `/detect-leak-signal`, ...) — the original ai/*.pkl sklearn models via
    fastapi_app/services/model_service.py, still the backbone of the Water
    Stress Index fusion and the primary dashboard/telemetry UI.
Real-time telemetry is treated as one data source among several.
"""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

# Load local configuration before importing routes / vision keys.
load_dotenv(Path(__file__).resolve().parents[1] / ".env.local")

from fastapi_app.core.config import get_settings
from fastapi_app.core.rate_limit import limiter
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
    recommendations,
    reports,
    reservoir_forecast,
    water_stress_forecast,
    telemetry,
    vision_routes,
    water_intelligence,
    weather,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    try:
        from fastapi_app.services.model_service import model_service

        _ = (
            model_service.shortage_model,
            model_service.groundwater_model,
            model_service.demand_model,
            model_service.leak_model,
        )
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
        "Real-time monitoring remains available as one of several data sources. "
        "Legacy ML diagnostic routes are retained for compatibility."
    ),
    version=_settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_env:
    origins = [origin.strip() for origin in allowed_origins_env.split(",")]
else:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
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
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Avoid leaking internals to clients in production-like demos.
    print(f"[Unhandled] {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error. Check FastAPI logs for details.",
            "timestamp": datetime.utcnow().isoformat(),
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
    }


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
