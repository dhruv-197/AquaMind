"""Single gate for demo-mode fixture fallbacks.

Every "should we serve a fixture?" decision in the codebase routes through
`should_use_fixture()` here, so the answer is decided in one place from one
setting rather than scattered `os.getenv("DEMO")` checks.

Fixtures exist so a live demo survives an unreachable Gemini/Qwen/CLIPSeg or a
captive-portal Wi-Fi network. They are **not** a production fallback:

* `demo_mode` is off unless `AQUAMIND_DEMO_MODE=true` is set explicitly.
* With demo mode off, an unavailable provider raises — callers surface a clear
  error instead of a fabricated analysis.
* A fixture is validated against its required fields before it is returned, and
  is stamped with `source="demo_fixture"` plus a fixed `observed_at` in the past,
  so it can never be mistaken for current live telemetry.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable

from fastapi_app.core.config import get_settings
from fastapi_app.core.data_quality import DataQuality, Freshness, Method, isoformat, utc_now

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "demo_fixtures"

#: Normalized provenance vocabulary shared by every resilient synthesis path.
SOURCE_REMOTE_AI = "remote_ai"
SOURCE_RULES_FALLBACK = "rules_fallback"
SOURCE_DEMO_FIXTURE = "demo_fixture"
KNOWN_SOURCES = (SOURCE_REMOTE_AI, SOURCE_RULES_FALLBACK, SOURCE_DEMO_FIXTURE)


class FixtureValidationError(RuntimeError):
    """A fixture on disk does not match the response schema it stands in for."""


class ProviderUnavailableError(RuntimeError):
    """An optional remote provider failed and no fixture fallback is permitted.

    Carries a caller-safe message; never contains keys, tokens, or raw provider
    payloads.
    """

    def __init__(self, message: str, *, provider_errors: Iterable[str] = ()) -> None:
        super().__init__(message)
        self.provider_errors = [str(e) for e in provider_errors]


#: Fields each fixture must carry to be a drop-in for the real response.
FIXTURE_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "water_intelligence": (
        "water_stress",
        "shortage",
        "leak",
        "groundwater",
        "demand",
        "climate",
        "context",
    ),
    "recommendations": ("recommendations", "expected_saving", "text_summary"),
    "vision_reservoir": (
        "reservoir_health",
        "water_spread",
        "vegetation",
        "sedimentation",
        "dry_shoreline",
        "encroachment",
        "water_stress",
        "overall_risk",
        "turbidity_index",
        "algae_bloom_risk",
        "shoreline_exposure_pct",
        "confidence",
        "summary",
        "recommendations",
        "segmentation",
    ),
    "leak_detection": (
        "is_leak_detected",
        "leak_probability",
        "estimated_water_loss_lpm",
        "severity",
        "zone",
    ),
}

_cache: dict[str, dict[str, Any]] = {}


def demo_mode_enabled() -> bool:
    return get_settings().demo_mode


def fixtures_forced() -> bool:
    return get_settings().fixtures_forced


def should_use_fixture(*, provider_failed: bool) -> bool:
    """The one predicate that authorizes a fixture response.

    A fixture is served only in demo mode, and then only when the real
    dependency actually failed — or when fixtures were deliberately forced.
    """
    settings = get_settings()
    if not settings.fixtures_enabled:
        return False
    return settings.fixtures_forced or provider_failed


def validate_fixture(name: str, payload: Any) -> dict[str, Any]:
    """Reject a fixture that has drifted from the schema it must satisfy."""
    if not isinstance(payload, dict):
        raise FixtureValidationError(f"Demo fixture {name!r} must be a JSON object.")
    required = FIXTURE_REQUIRED_FIELDS.get(name)
    if required is None:
        raise FixtureValidationError(f"Unknown demo fixture {name!r}.")
    missing = [field for field in required if field not in payload]
    if missing:
        raise FixtureValidationError(
            f"Demo fixture {name!r} is missing required field(s): {', '.join(missing)}."
        )
    return payload


def load_fixture(name: str) -> dict[str, Any]:
    """Read, validate, and return a deep copy so callers cannot mutate the cache."""
    if name not in _cache:
        path = FIXTURE_DIR / f"{name}.json"
        if not path.exists():
            raise FixtureValidationError(f"Demo fixture file not found: {path.name}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            raise FixtureValidationError(f"Demo fixture {name!r} is not valid JSON: {err}") from err
        _cache[name] = validate_fixture(name, payload)
    return copy.deepcopy(_cache[name])


def fixture_metadata(
    name: str,
    *,
    observed_at: str | None = None,
    model_version: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Provenance block marking a payload as a fixture rather than a reading.

    `observed_at` stays at the fixture's own capture time (a fixed date in the
    past), so freshness derivation reports it as stale instead of letting it
    pass as a current measurement.
    """
    return {
        "source": SOURCE_DEMO_FIXTURE,
        "method": Method.FALLBACK.value,
        "data_quality": DataQuality.LOW.value,
        "freshness": Freshness.STALE.value,
        "is_stale": True,
        "confidence": None,
        "observed_at": observed_at,
        "generated_at": isoformat(utc_now()),
        "model_version": model_version or f"demo_fixture:{name}",
        "note": note or "Captured demo fixture served because the live provider was unavailable.",
    }


def clear_fixture_cache() -> None:
    """Test seam — drop parsed fixtures so an edited file is re-read."""
    _cache.clear()
