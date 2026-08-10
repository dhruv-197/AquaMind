"""Application settings for the Water Decision Intelligence Platform."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except (TypeError, ValueError):
        return default


class Settings(BaseModel):
    """Runtime configuration. ML backends plug in via env without code changes."""

    app_name: str = "AquaMind Water Decision Intelligence Platform"
    app_version: str = "2.0.0"
    environment: str = Field(default="development", description="development | staging | production")

    # Prediction layer: "stub" returns structured placeholders; "ml" will wire trained models.
    prediction_backend: str = Field(
        default="stub",
        description="Active prediction backend identifier (stub | ml).",
    )

    # Decision engine: rule-based today; scoring models can replace later.
    decision_engine_backend: str = Field(
        default="rules",
        description="Active decision engine backend (rules | ml).",
    )

    default_region_id: str = "REG-1"
    default_forecast_horizon_days: int = 7

    # --- Demo resilience -------------------------------------------------
    # Off unless explicitly enabled, so a production deployment can never
    # silently serve a fixture in place of a failed model or provider.
    demo_mode: bool = Field(
        default=False,
        description=(
            "Allow checked-in demo fixtures to stand in for an unavailable optional "
            "provider (Gemini, Qwen, CLIPSeg). Never enable in production."
        ),
    )
    demo_force_fixtures: bool = Field(
        default=False,
        description=(
            "Serve demo fixtures without attempting the remote provider at all. "
            "Only honoured while demo_mode is enabled."
        ),
    )

    # --- Remote provider budgets ----------------------------------------
    remote_ai_timeout_seconds: float = Field(
        default=10.0,
        description="Per-attempt deadline for remote text AI (recommendation synthesis).",
    )
    remote_ai_total_budget_seconds: float = Field(
        default=15.0,
        description="Total wall-clock budget across all remote text AI attempts in one request.",
    )
    vision_provider_timeout_seconds: float = Field(
        default=45.0,
        description=(
            "Per-provider deadline for a remote vision-language model call. A full-resolution "
            "image through a hosted VLM routinely takes 20-35s, so this is deliberately well "
            "above the text-AI deadline."
        ),
    )
    vision_total_budget_seconds: float = Field(
        default=75.0,
        description=(
            "Total wall-clock budget across the whole vision provider chain — enough for a "
            "slow first provider plus one retry elsewhere, not for all three in series."
        ),
    )
    clipseg_timeout_seconds: float = Field(
        default=60.0,
        description=(
            "Deadline for the optional CLIPSeg overlay. Generous because the first upload "
            "of a process also pays the one-time weight load; later uploads take seconds. "
            "Exceeding it never fails the analysis."
        ),
    )

    @property
    def fixtures_enabled(self) -> bool:
        """Fixtures are only ever reachable through demo mode."""
        return self.demo_mode

    @property
    def fixtures_forced(self) -> bool:
        """Skip the real provider entirely — a deliberate, separately-gated choice."""
        return self.demo_mode and self.demo_force_fixtures


@lru_cache
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("AQUAMIND_ENVIRONMENT", "development"),
        prediction_backend=os.getenv("AQUAMIND_PREDICTION_BACKEND", "stub"),
        decision_engine_backend=os.getenv("AQUAMIND_DECISION_ENGINE_BACKEND", "rules"),
        default_region_id=os.getenv("AQUAMIND_DEFAULT_REGION_ID", "REG-1"),
        default_forecast_horizon_days=int(os.getenv("AQUAMIND_DEFAULT_FORECAST_HORIZON_DAYS", "7")),
        demo_mode=_env_flag("AQUAMIND_DEMO_MODE", False),
        demo_force_fixtures=_env_flag("AQUAMIND_DEMO_FORCE_FIXTURES", False),
        remote_ai_timeout_seconds=_env_float("AQUAMIND_REMOTE_AI_TIMEOUT_SEC", 10.0),
        remote_ai_total_budget_seconds=_env_float("AQUAMIND_REMOTE_AI_BUDGET_SEC", 15.0),
        vision_provider_timeout_seconds=_env_float("AQUAMIND_VISION_TIMEOUT_SEC", 45.0),
        vision_total_budget_seconds=_env_float("AQUAMIND_VISION_BUDGET_SEC", 75.0),
        clipseg_timeout_seconds=_env_float("AQUAMIND_CLIPSEG_TIMEOUT_SEC", 60.0),
    )
