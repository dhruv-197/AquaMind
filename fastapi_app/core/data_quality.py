"""Internal normalized data-quality contract.

AquaMind fuses several very different upstreams — SQLite telemetry, trained
sklearn models, engineering heuristics, and live weather providers. Each of
those answers "what is the number?" but none of them answered "how much should
an operator trust it?" in a consistent shape.

This module is the single place that decides:

* how a raw value is normalized (percentage, probability, non-negative volume),
* which vocabulary describes where the value came from (`method`),
* how fresh the value is (`observed_at` → `data_age_seconds` → `freshness`),
* what quality band results (`data_quality`).

Routers and services build metadata through :func:`build_metadata` instead of
hand-rolling `{"source": ...}` dictionaries, so the vocabulary cannot drift
between endpoints.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

# ----------------------------------------------------------------------
# Vocabulary
# ----------------------------------------------------------------------


class Method(str, Enum):
    """How a value was produced. Normalized across every module."""

    TRAINED_MODEL = "trained_model"
    DATABASE_TELEMETRY = "database_telemetry"
    WEATHER_PROVIDER = "weather_provider"
    ENGINEERING_ESTIMATE = "engineering_estimate"
    RULES_ENGINE = "rules_engine"
    VISION_MODEL = "vision_model"
    REMOTE_AI = "remote_ai"
    FALLBACK = "fallback"


class DataQuality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class Freshness(str, Enum):
    FRESH = "fresh"
    RECENT = "recent"
    STALE = "stale"
    UNKNOWN = "unknown"


class Availability(str, Enum):
    """Distinguishes a valid zero from "we could not get this at all"."""

    AVAILABLE = "available"
    STALE = "stale"
    MISSING = "missing"          # nothing recorded for this component yet
    UNAVAILABLE = "unavailable"  # upstream model / provider call failed


# Age bands. Deliberately generous: reservoir and CGWB well observations are
# published daily-to-weekly, so a 6h "fresh" window is already optimistic for
# the slowest feeds and appropriate for the fastest ones.
FRESH_MAX_AGE_SECONDS = 6 * 3600
RECENT_MAX_AGE_SECONDS = 48 * 3600

_METHOD_BASE_QUALITY: dict[Method, DataQuality] = {
    Method.TRAINED_MODEL: DataQuality.HIGH,
    Method.DATABASE_TELEMETRY: DataQuality.HIGH,
    Method.WEATHER_PROVIDER: DataQuality.HIGH,
    Method.ENGINEERING_ESTIMATE: DataQuality.MEDIUM,
    Method.RULES_ENGINE: DataQuality.MEDIUM,
    Method.VISION_MODEL: DataQuality.MEDIUM,
    # A hosted LLM narrating already-validated numeric telemetry: no worse than
    # the rules engine it replaces, no better than the numbers it was handed.
    Method.REMOTE_AI: DataQuality.MEDIUM,
    Method.FALLBACK: DataQuality.LOW,
}

_QUALITY_ORDER = {
    DataQuality.UNKNOWN: 0,
    DataQuality.LOW: 1,
    DataQuality.MEDIUM: 2,
    DataQuality.HIGH: 3,
}


def _worst(*qualities: DataQuality) -> DataQuality:
    return min(qualities, key=lambda q: _QUALITY_ORDER[q])


# ----------------------------------------------------------------------
# Numeric normalization
# ----------------------------------------------------------------------


def is_finite_number(value: Any) -> bool:
    """True only for real, finite numbers (rejects None, bool, NaN, ±inf, text)."""
    if value is None or isinstance(value, bool):
        return False
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(as_float)


def to_float(value: Any) -> float | None:
    """Coerce to a finite float, or None when the value is unusable."""
    return float(value) if is_finite_number(value) else None


def clamp_confidence(value: Any) -> float | None:
    """Normalize any confidence-like number to 0.0–1.0.

    Values expressed as a 0–100 percentage are *not* auto-converted: silently
    rescaling would hide an upstream unit bug, so anything above 1 clamps to 1.
    """
    number = to_float(value)
    if number is None:
        return None
    return max(0.0, min(1.0, number))


def clamp_percentage(value: Any, *, allow_negative: bool = False) -> float | None:
    """Normalize a percentage to 0–100 (or -100–100 for signed anomalies)."""
    number = to_float(value)
    if number is None:
        return None
    low = -100.0 if allow_negative else 0.0
    return max(low, min(100.0, number))


def non_negative(value: Any) -> float | None:
    """Reject negatives for physical quantities that cannot be below zero.

    Returns None rather than 0.0 — a rejected reading must not look like a
    measured "no loss" / "no demand".
    """
    number = to_float(value)
    if number is None or number < 0:
        return None
    return number


def plausible_temperature_c(value: Any) -> float | None:
    """Ambient temperature in °C, rejecting physically impossible readings."""
    number = to_float(value)
    if number is None or not (-90.0 <= number <= 60.0):
        return None
    return number


# ----------------------------------------------------------------------
# Timestamps and freshness
# ----------------------------------------------------------------------


def parse_timestamp(value: Any) -> datetime | None:
    """Parse ISO-8601 strings, dates, and datetimes into aware UTC datetimes."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: Any) -> str | None:
    parsed = parse_timestamp(value)
    return parsed.isoformat() if parsed else None


def data_age_seconds(observed_at: Any, *, now: datetime | None = None) -> float | None:
    """Seconds between `observed_at` and now. None when the timestamp is missing.

    Clock skew (an observation stamped in the future) yields 0.0 rather than a
    negative age, so downstream consumers never see an impossible duration.
    """
    parsed = parse_timestamp(observed_at)
    if parsed is None:
        return None
    delta = ((now or utc_now()) - parsed).total_seconds()
    return round(max(0.0, delta), 3)


def freshness_from_age(age_seconds: float | None) -> Freshness:
    if age_seconds is None:
        return Freshness.UNKNOWN
    if age_seconds <= FRESH_MAX_AGE_SECONDS:
        return Freshness.FRESH
    if age_seconds <= RECENT_MAX_AGE_SECONDS:
        return Freshness.RECENT
    return Freshness.STALE


def newest_timestamp(values: Iterable[Any]) -> str | None:
    """Most recent parseable timestamp in an iterable, as an ISO string."""
    parsed = [ts for ts in (parse_timestamp(v) for v in values) if ts is not None]
    return max(parsed).isoformat() if parsed else None


# ----------------------------------------------------------------------
# Model versions
# ----------------------------------------------------------------------

_AI_DIR = Path(__file__).resolve().parents[2] / "ai"


@lru_cache(maxsize=32)
def resolve_model_version(artifact_stem: str) -> str | None:
    """Version label for a trained artifact, from its tracked model card.

    Model cards carry no explicit semantic version, so the artifact date is
    used — it is what actually changes when `ai/train.py` reruns.
    """
    card = _AI_DIR / f"{artifact_stem}.metadata.json"
    try:
        if not card.is_file():
            return None
        payload = json.loads(card.read_text(encoding="utf-8"))
        model_type = payload.get("model_type") or "model"
        trained_at = payload.get("trained_at") or datetime.fromtimestamp(
            card.stat().st_mtime, tz=timezone.utc
        ).strftime("%Y-%m-%d")
        return f"{artifact_stem}:{model_type}@{trained_at}"
    except Exception:
        return None


# ----------------------------------------------------------------------
# Metadata construction
# ----------------------------------------------------------------------


def build_metadata(
    *,
    source: str,
    method: Method | str,
    confidence: Any = None,
    observed_at: Any = None,
    generated_at: Any = None,
    model_version: str | None = None,
    unit: str | None = None,
    availability: Availability | str = Availability.AVAILABLE,
    quality_hint: DataQuality | str | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build one normalized metadata block.

    Quality is derived, never asserted by the caller alone: the method sets a
    ceiling, an unverifiable `observed_at` caps it at medium, staleness drops
    it to low, and missing/unavailable data forces `unknown`.
    """
    method_enum = Method(method) if not isinstance(method, Method) else method
    availability_enum = (
        availability if isinstance(availability, Availability) else Availability(availability)
    )
    reference_now = now or utc_now()

    age = data_age_seconds(observed_at, now=reference_now)
    freshness = freshness_from_age(age)
    if freshness is Freshness.STALE and availability_enum is Availability.AVAILABLE:
        availability_enum = Availability.STALE

    quality = _METHOD_BASE_QUALITY[method_enum]
    if quality_hint is not None:
        hint = quality_hint if isinstance(quality_hint, DataQuality) else DataQuality(quality_hint)
        quality = _worst(quality, hint)
    if freshness is Freshness.UNKNOWN:
        # Cannot verify freshness → cannot claim high quality.
        quality = _worst(quality, DataQuality.MEDIUM)
    elif freshness is Freshness.STALE:
        quality = _worst(quality, DataQuality.LOW)

    normalized_confidence = clamp_confidence(confidence)
    if availability_enum in (Availability.MISSING, Availability.UNAVAILABLE):
        quality = DataQuality.UNKNOWN
        normalized_confidence = None

    metadata: dict[str, Any] = {
        "source": source,
        "method": method_enum.value,
        "confidence": normalized_confidence,
        "data_quality": quality.value,
        "freshness": freshness.value,
        "availability": availability_enum.value,
        "is_stale": freshness is Freshness.STALE,
        "observed_at": isoformat(observed_at),
        "generated_at": (parse_timestamp(generated_at) or reference_now).isoformat(),
        "data_age_seconds": age,
        "model_version": model_version,
    }
    if unit:
        metadata["unit"] = unit
    if note:
        metadata["note"] = note
    return metadata


def measurement(value: Any, *, unit: str, **metadata_kwargs: Any) -> dict[str, Any]:
    """A single normalized value carrying its own provenance metadata.

    Used where a component exposes one headline number; the fused endpoints
    attach :func:`build_metadata` per component instead, to stay backward
    compatible with existing response fields.
    """
    meta = build_metadata(unit=unit, **metadata_kwargs)
    if value is None:
        meta["data_quality"] = DataQuality.UNKNOWN.value
        meta["availability"] = Availability.MISSING.value
        meta["confidence"] = None
    return {"value": to_float(value) if is_finite_number(value) else None, "unit": unit, **meta}


# ----------------------------------------------------------------------
# Declarative field normalization
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSpec:
    """How one response field must be normalized, and in which unit."""

    kind: str  # percentage | signed_percentage | probability | non_negative | temperature_c
    unit: str


PERCENT = "percent_0_100"
SIGNED_PERCENT = "percent_-100_100"
RATIO = "ratio_0_1"
MGD = "million_gallons_per_day"
LPM = "litres_per_minute"
MLD = "million_litres_per_day"
METRES = "metres"
METRES_PER_YEAR = "metres_per_year"
CELSIUS = "degrees_celsius"
INDEX_0_100 = "index_0_100"

#: Unit + range contract per fused component field. Values outside the contract
#: are normalized (clamped) or rejected (set to None) — never silently rescaled.
COMPONENT_FIELD_SPECS: dict[str, dict[str, FieldSpec]] = {
    "shortage": {
        "predicted_risk_score": FieldSpec("percentage", INDEX_0_100),
        "confidence": FieldSpec("probability", RATIO),
        "reservoir_capacity_pct": FieldSpec("percentage", PERCENT),
        "min_reservoir_pct": FieldSpec("percentage", PERCENT),
        "pct_reservoirs_critical": FieldSpec("percentage", PERCENT),
        "forecast_storage_pct": FieldSpec("percentage", PERCENT),
    },
    "leak": {
        "leak_probability": FieldSpec("probability", RATIO),
        "estimated_water_loss_lpm": FieldSpec("non_negative", LPM),
        "daily_loss_mld": FieldSpec("non_negative", MLD),
        "confidence": FieldSpec("probability", RATIO),
        "loss_confidence": FieldSpec("probability", RATIO),
    },
    "groundwater": {
        "projected_depth_m": FieldSpec("non_negative", METRES),
        "current_depth_m": FieldSpec("non_negative", METRES),
        "critical_depth_m": FieldSpec("non_negative", METRES),
        "depletion_rate_m_year": FieldSpec("numeric", METRES_PER_YEAR),
        "drawdown_rate_m": FieldSpec("numeric", METRES_PER_YEAR),
        "confidence": FieldSpec("probability", RATIO),
        "latitude": FieldSpec("numeric", "degrees_latitude"),
        "longitude": FieldSpec("numeric", "degrees_longitude"),
    },
    "demand": {
        "forecasted_demand_mgd": FieldSpec("non_negative", MGD),
        "forecasted_demand_mld": FieldSpec("non_negative", MLD),
        "predicted_demand_mgd": FieldSpec("non_negative", MGD),
        "daily_demand_mgd": FieldSpec("non_negative", MGD),
        "peak_hour_demand_mgd": FieldSpec("non_negative", MGD),
        "climate_base_mgd": FieldSpec("non_negative", MGD),
        "baseline_consumption_mgd": FieldSpec("non_negative", MGD),
        "confidence": FieldSpec("probability", RATIO),
    },
    "climate": {
        "rainfall_deficit_pct": FieldSpec("signed_percentage", SIGNED_PERCENT),
        "dry_anomaly_pct": FieldSpec("signed_percentage", SIGNED_PERCENT),
        "temperature_c": FieldSpec("temperature_c", CELSIUS),
    },
}


def _normalize_field(value: Any, spec: FieldSpec) -> float | None:
    if spec.kind == "percentage":
        return clamp_percentage(value)
    if spec.kind == "signed_percentage":
        return clamp_percentage(value, allow_negative=True)
    if spec.kind == "probability":
        return clamp_confidence(value)
    if spec.kind == "non_negative":
        return non_negative(value)
    if spec.kind == "temperature_c":
        return plausible_temperature_c(value)
    if spec.unit == "degrees_latitude":
        number = to_float(value)
        if number is None or not (-90.0 <= number <= 90.0):
            return None
        return number
    if spec.unit == "degrees_longitude":
        number = to_float(value)
        if number is None or not (-180.0 <= number <= 180.0):
            return None
        return number
    return to_float(value)


def normalize_component(component: str, payload: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Apply the unit/range contract to one component payload.

    Returns a copy plus the list of fields that had to be corrected, so the
    caller can downgrade `data_quality` instead of hiding the problem. Fields
    already inside their contract are returned untouched (bit-identical), so
    valid predictions are never rounded or rewritten.
    """
    clean = dict(payload or {})
    issues: list[str] = []
    for field, spec in COMPONENT_FIELD_SPECS.get(component, {}).items():
        if field not in clean:
            continue
        original = clean[field]
        if original is None:
            continue
        normalized = _normalize_field(original, spec)
        if normalized is None:
            clean[field] = None
            issues.append(f"{field}: rejected (not a valid {spec.unit} value)")
        elif not is_finite_number(original) or float(original) != normalized:
            clean[field] = normalized
            issues.append(f"{field}: normalized to {spec.unit}")
    return clean, issues


def quality_from_issues(issues: list[str]) -> DataQuality | None:
    """Corrected values are still usable, but no longer 'high' quality."""
    return DataQuality.LOW if issues else None


# ----------------------------------------------------------------------
# Water-intelligence component provenance
# ----------------------------------------------------------------------

WSI_FUSION_VERSION = "weighted_multi_source_wsi_v1"

_MODEL_ARTIFACTS = {
    "shortage": "water_shortage_model",
    "groundwater": "groundwater_model",
    "demand": "water_demand_model",
    "leak": "leak_detection_model",
}

#: Which override keys, when supplied, mean a component ran on user scenario
#: inputs rather than on observed telemetry.
_OVERRIDE_KEYS: dict[str, tuple[str, ...]] = {
    "shortage": ("reservoir_capacity_pct", "daily_demand_mgd", "day_of_month"),
    "leak": ("leak_probability", "estimated_water_loss_lpm", "is_leak_detected"),
    "groundwater": ("current_depth_m", "depletion_rate_m_year"),
    "demand": ("population_thousands", "industrial_activity_idx", "is_weekend", "is_heatwave"),
    "climate": ("rainfall_deficit_pct", "spi3_proxy", "heatwave_warning", "temperature_c"),
}


@dataclass(frozen=True)
class ModelAvailability:
    """Which trained artifacts actually loaded in this process."""

    shortage: bool = False
    groundwater: bool = False
    demand: bool = False
    leak: bool = False


def _is_overridden(component: str, overrides: Mapping[str, Any] | None) -> bool:
    if not overrides:
        return False
    return any(overrides.get(key) is not None for key in _OVERRIDE_KEYS.get(component, ()))


def _component_source(base: str, overridden: bool) -> str:
    return f"scenario_override:{base}" if overridden else base


def build_water_intelligence_metadata(
    *,
    water_stress: Mapping[str, Any] | None,
    shortage: Mapping[str, Any] | None,
    leak: Mapping[str, Any] | None,
    groundwater: Mapping[str, Any] | None,
    demand: Mapping[str, Any] | None,
    climate: Mapping[str, Any] | None,
    models: ModelAvailability | None = None,
    overrides: Mapping[str, Any] | None = None,
    issues: Mapping[str, list[str]] | None = None,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """Normalized metadata for all six fused water-intelligence components.

    Every branch here is the single source of truth for `source` / `method`
    wording — routers never spell these out themselves.
    """
    models = models or ModelAvailability()
    issues = issues or {}
    reference_now = now or utc_now()

    def hint(component: str) -> DataQuality | None:
        return quality_from_issues(list(issues.get(component) or []))

    def missing(component: str, source: str) -> dict[str, Any]:
        return build_metadata(
            source=source,
            method=Method.FALLBACK,
            availability=Availability.MISSING,
            note=f"No {component} telemetry available for this request.",
            now=reference_now,
        )

    metadata: dict[str, dict[str, Any]] = {}

    # --- shortage -----------------------------------------------------
    shortage = dict(shortage or {})
    overridden = _is_overridden("shortage", overrides)
    if not shortage:
        metadata["shortage"] = missing("reservoir shortage", "reservoirs_table")
    else:
        model_backed = models.shortage and shortage.get("forecast_storage_pct") is not None
        metadata["shortage"] = build_metadata(
            source=_component_source(
                "water_shortage_model + reservoirs_table" if model_backed else "reservoirs_table",
                overridden,
            ),
            method=Method.TRAINED_MODEL if model_backed else Method.DATABASE_TELEMETRY,
            confidence=shortage.get("confidence"),
            observed_at=None if overridden else shortage.get("observed_at"),
            model_version=resolve_model_version(_MODEL_ARTIFACTS["shortage"]) if model_backed else None,
            unit=INDEX_0_100,
            quality_hint=hint("shortage"),
            note=(
                "predicted_risk_score is a 0–100 operational index; storage inputs are "
                "percentages of live capacity."
            ),
            now=reference_now,
        )

    # --- leak ---------------------------------------------------------
    leak = dict(leak or {})
    overridden = _is_overridden("leak", overrides)
    if not leak:
        metadata["leak"] = missing("leak", "acoustic_model_predictions")
    elif leak.get("demo"):
        metadata["leak"] = build_metadata(
            source=_component_source("demo_seeded_alerts", overridden),
            method=Method.FALLBACK,
            confidence=leak.get("loss_confidence") or leak.get("confidence"),
            observed_at=None if overridden else leak.get("observed_at"),
            unit=LPM,
            quality_hint=DataQuality.LOW,
            note=(
                "Seeded alerts only — muted inside the index. Upload an acoustic CSV to "
                "produce a model-backed leak component."
            ),
            now=reference_now,
        )
    else:
        model_backed = str(leak.get("source") or "") == "acoustic_model"
        metadata["leak"] = build_metadata(
            source=_component_source(
                "acoustic_leak_model + orifice_loss_estimate"
                if model_backed
                else "orifice_loss_estimate",
                overridden,
            ),
            method=Method.TRAINED_MODEL if model_backed else Method.ENGINEERING_ESTIMATE,
            confidence=leak.get("loss_confidence") or leak.get("confidence"),
            observed_at=None if overridden else (leak.get("observed_at") or leak.get("inferred_at")),
            model_version=resolve_model_version(_MODEL_ARTIFACTS["leak"]) if model_backed else None,
            unit=LPM,
            quality_hint=_worst(hint("leak") or DataQuality.HIGH, DataQuality.MEDIUM),
            note=(
                "Leak probability is classifier output; estimated_water_loss_lpm is an "
                "orifice engineering estimate in L/min, not a metered water balance."
            ),
            now=reference_now,
        )

    # --- groundwater --------------------------------------------------
    groundwater = dict(groundwater or {})
    overridden = _is_overridden("groundwater", overrides)
    if not groundwater:
        metadata["groundwater"] = missing("groundwater", "groundwater_table")
    else:
        model_backed = models.groundwater and groundwater.get("days_to_critical_threshold") is not None
        metadata["groundwater"] = build_metadata(
            source=_component_source(
                "groundwater_model + groundwater_table" if model_backed else "groundwater_table",
                overridden,
            ),
            method=Method.TRAINED_MODEL if model_backed else Method.DATABASE_TELEMETRY,
            confidence=groundwater.get("confidence"),
            observed_at=None if overridden else groundwater.get("observed_at"),
            model_version=resolve_model_version(_MODEL_ARTIFACTS["groundwater"]) if model_backed else None,
            unit=METRES,
            quality_hint=hint("groundwater"),
            note="Depth to water table in metres below ground; depletion rate in m/year.",
            now=reference_now,
        )

    # --- demand -------------------------------------------------------
    demand = dict(demand or {})
    overridden = _is_overridden("demand", overrides)
    if not demand:
        metadata["demand"] = missing("demand", "consumption_series")
    else:
        model_backed = models.demand and demand.get("forecasted_demand_mld") is not None
        metadata["demand"] = build_metadata(
            source=_component_source(
                "water_demand_model + consumption_series" if model_backed else "consumption_series",
                overridden,
            ),
            method=Method.TRAINED_MODEL if model_backed else Method.DATABASE_TELEMETRY,
            confidence=demand.get("confidence"),
            observed_at=None if overridden else demand.get("observed_at"),
            model_version=resolve_model_version(_MODEL_ARTIFACTS["demand"]) if model_backed else None,
            unit=MGD,
            # Demand labels are synthetic in this pilot, so the component never
            # claims high quality regardless of freshness.
            quality_hint=_worst(hint("demand") or DataQuality.HIGH, DataQuality.MEDIUM),
            note="Forecast in MGD (million gallons/day); pilot model trained on synthetic labels.",
            now=reference_now,
        )

    # --- climate ------------------------------------------------------
    climate = dict(climate or {})
    overridden = _is_overridden("climate", overrides)
    climate_source = str(climate.get("climate_source") or "")
    if not climate:
        metadata["climate"] = missing("climate", "weather_table")
    else:
        if climate_source == "open_meteo_sync":
            method, source = Method.WEATHER_PROVIDER, "open_meteo"
        elif climate_source == "db_weather":
            method, source = Method.DATABASE_TELEMETRY, "weather_table"
        else:
            method, source = Method.FALLBACK, climate_source or "weather_defaults"
        metadata["climate"] = build_metadata(
            source=_component_source(source, overridden),
            method=method,
            observed_at=None if overridden else climate.get("observed_at"),
            unit=CELSIUS,
            quality_hint=hint("climate"),
            note=(
                "Temperature in °C, rainfall anomaly as signed percent "
                "(negative = drier than normal); SPI-3 is a z-score proxy."
            ),
            now=reference_now,
        )

    # --- fused index --------------------------------------------------
    component_meta = list(metadata.values())
    observed_candidates = [m["observed_at"] for m in component_meta if m.get("observed_at")]
    # The index is only as fresh as its stalest contributing input.
    oldest_observed = (
        min(parse_timestamp(ts) for ts in observed_candidates).isoformat()
        if observed_candidates
        else None
    )
    weights = dict((water_stress or {}).get("weights") or {})
    # Component key → WSI weight key (the index calls the leak component "leakage").
    weight_for = {
        "shortage": "shortage",
        "groundwater": "groundwater",
        "leak": "leakage",
        "demand": "demand",
        "climate": "climate",
    }
    weighted_sum = 0.0
    weight_total = 0.0
    for component, weight_key in weight_for.items():
        confidence = metadata[component].get("confidence")
        weight = float(weights.get(weight_key) or 0.0)
        if confidence is not None and weight > 0:
            weighted_sum += float(confidence) * weight
            weight_total += weight
    fused_confidence = round(weighted_sum / weight_total, 4) if weight_total else None
    worst_quality = _worst(*(DataQuality(m["data_quality"]) for m in component_meta))

    metadata["water_stress"] = build_metadata(
        source="aquamind_wsi_fusion",
        method=Method.RULES_ENGINE,
        confidence=fused_confidence,
        observed_at=oldest_observed,
        model_version=str((water_stress or {}).get("method") or WSI_FUSION_VERSION),
        unit=INDEX_0_100,
        availability=Availability.MISSING if not water_stress else Availability.AVAILABLE,
        quality_hint=worst_quality,
        note=(
            "Weighted fusion of the five components. Confidence is the weight-averaged "
            "confidence of contributing components; freshness follows the stalest input."
        ),
        now=reference_now,
    )
    return metadata
