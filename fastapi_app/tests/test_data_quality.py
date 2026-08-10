"""Tests for the internal normalized data-quality / provenance contract."""
from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest

from fastapi_app.core.data_quality import (
    Availability,
    DataQuality,
    Freshness,
    Method,
    ModelAvailability,
    build_metadata,
    build_water_intelligence_metadata,
    clamp_confidence,
    clamp_percentage,
    data_age_seconds,
    freshness_from_age,
    measurement,
    newest_timestamp,
    non_negative,
    normalize_component,
    plausible_temperature_c,
)
from fastapi_app.services.water_stress_service import compute_water_stress_index

COMPONENTS = ("water_stress", "shortage", "leak", "groundwater", "demand", "climate")


# ----------------------------------------------------------------------
# Confidence normalization
# ----------------------------------------------------------------------


def test_confidence_below_zero_becomes_zero():
    assert clamp_confidence(-0.4) == 0.0
    assert clamp_confidence(-1000) == 0.0


def test_confidence_above_one_becomes_one():
    assert clamp_confidence(1.4) == 1.0
    assert clamp_confidence(88) == 1.0  # a 0–100 style value clamps, never rescales


def test_confidence_passes_through_valid_range():
    assert clamp_confidence(0.0) == 0.0
    assert clamp_confidence(0.73) == 0.73
    assert clamp_confidence(1.0) == 1.0


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), float("-inf"), "high", True])
def test_confidence_rejects_non_numeric_and_non_finite(bad):
    assert clamp_confidence(bad) is None


# ----------------------------------------------------------------------
# Percentages, non-negative quantities, temperature
# ----------------------------------------------------------------------


def test_percentages_are_clamped_to_zero_hundred():
    assert clamp_percentage(-5) == 0.0
    assert clamp_percentage(140) == 100.0
    assert clamp_percentage(42.5) == 42.5


def test_signed_percentage_allows_negative_anomalies():
    assert clamp_percentage(-30, allow_negative=True) == -30.0
    assert clamp_percentage(-400, allow_negative=True) == -100.0
    assert clamp_percentage(400, allow_negative=True) == 100.0


def test_non_negative_rejects_negative_rather_than_zeroing():
    assert non_negative(-12.0) is None, "a rejected reading must not look like a measured zero"
    assert non_negative(0.0) == 0.0
    assert non_negative(41.5) == 41.5
    assert non_negative(float("nan")) is None


def test_temperature_rejects_impossible_values():
    assert plausible_temperature_c(32.0) == 32.0
    assert plausible_temperature_c(-273.15) is None
    assert plausible_temperature_c(500) is None


# ----------------------------------------------------------------------
# Component field contract
# ----------------------------------------------------------------------


def test_valid_component_values_pass_through_untouched():
    payload = {
        "predicted_risk_score": 48.5,
        "confidence": 0.85,
        "reservoir_capacity_pct": 34.2,
        "risk_label": "Moderate Risk",
    }
    clean, issues = normalize_component("shortage", payload)
    assert issues == []
    assert clean == payload


def test_negative_demand_is_rejected_and_flagged():
    clean, issues = normalize_component("demand", {"forecasted_demand_mgd": -20.0})
    assert clean["forecasted_demand_mgd"] is None
    assert any("forecasted_demand_mgd" in issue for issue in issues)


def test_negative_leak_volume_is_rejected_and_flagged():
    clean, issues = normalize_component(
        "leak", {"leak_probability": 1.8, "estimated_water_loss_lpm": -5.0}
    )
    assert clean["leak_probability"] == 1.0
    assert clean["estimated_water_loss_lpm"] is None
    assert len(issues) == 2


def test_non_finite_values_never_reach_the_index():
    clean, issues = normalize_component(
        "shortage", {"predicted_risk_score": float("nan"), "reservoir_capacity_pct": float("inf")}
    )
    # Non-finite values are rejected outright rather than clamped to a bound
    # that would read as a real measurement.
    assert clean["predicted_risk_score"] is None
    assert clean["reservoir_capacity_pct"] is None
    assert len(issues) == 2


def test_missing_fields_are_not_invented():
    clean, issues = normalize_component("demand", {"peak_surge_risk": "Normal Baseline"})
    assert "forecasted_demand_mgd" not in clean
    assert issues == []


# ----------------------------------------------------------------------
# Freshness
# ----------------------------------------------------------------------


def test_missing_timestamp_does_not_crash():
    assert data_age_seconds(None) is None
    assert data_age_seconds("") is None
    assert data_age_seconds("not-a-date") is None
    assert freshness_from_age(None) is Freshness.UNKNOWN

    meta = build_metadata(source="reservoirs_table", method=Method.DATABASE_TELEMETRY)
    assert meta["observed_at"] is None
    assert meta["data_age_seconds"] is None
    assert meta["freshness"] == Freshness.UNKNOWN.value
    # Freshness cannot be verified, so quality must not claim "high".
    assert meta["data_quality"] == DataQuality.MEDIUM.value


def test_future_timestamp_clamps_to_zero_age():
    ahead = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    assert data_age_seconds(ahead) == 0.0


def test_stale_timestamp_yields_age_and_low_quality():
    observed = datetime.now(timezone.utc) - timedelta(days=9)
    meta = build_metadata(
        source="groundwater_table",
        method=Method.DATABASE_TELEMETRY,
        confidence=0.9,
        observed_at=observed,
    )
    assert meta["data_age_seconds"] == pytest.approx(9 * 86400, rel=0.01)
    assert meta["freshness"] == Freshness.STALE.value
    assert meta["is_stale"] is True
    assert meta["data_quality"] == DataQuality.LOW.value
    assert meta["availability"] == Availability.STALE.value


def test_fresh_observation_keeps_high_quality():
    observed = datetime.now(timezone.utc) - timedelta(minutes=20)
    meta = build_metadata(
        source="water_demand_model",
        method=Method.TRAINED_MODEL,
        confidence=0.82,
        observed_at=observed,
        model_version="water_demand_model:RandomForestRegressor@2026-01-01",
    )
    assert meta["freshness"] == Freshness.FRESH.value
    assert meta["data_quality"] == DataQuality.HIGH.value
    assert meta["is_stale"] is False
    assert meta["model_version"].startswith("water_demand_model")


def test_unavailable_component_is_not_a_believable_zero():
    meta = build_metadata(
        source="acoustic_model",
        method=Method.FALLBACK,
        confidence=0.9,
        availability=Availability.UNAVAILABLE,
    )
    assert meta["data_quality"] == DataQuality.UNKNOWN.value
    assert meta["confidence"] is None
    assert meta["availability"] == Availability.UNAVAILABLE.value


def test_measurement_preserves_valid_zero_but_flags_missing():
    zero = measurement(0.0, unit="litres_per_minute", source="dma", method=Method.DATABASE_TELEMETRY)
    assert zero["value"] == 0.0
    assert zero["availability"] == Availability.AVAILABLE.value

    absent = measurement(None, unit="litres_per_minute", source="dma", method=Method.DATABASE_TELEMETRY)
    assert absent["value"] is None
    assert absent["availability"] == Availability.MISSING.value
    assert absent["data_quality"] == DataQuality.UNKNOWN.value


def test_newest_timestamp_picks_latest_and_ignores_junk():
    latest = newest_timestamp(["2024-03-01", None, "bad", "2024-03-30"])
    assert latest is not None and latest.startswith("2024-03-30")
    assert newest_timestamp([None, "", "nope"]) is None


# ----------------------------------------------------------------------
# Fused water-intelligence metadata
# ----------------------------------------------------------------------


def _fused_metadata(**kwargs):
    observed = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    defaults = dict(
        water_stress=compute_water_stress_index(
            shortage={"predicted_risk_score": 55},
            climate={"spi3_proxy": -1.0},
        ),
        shortage={"predicted_risk_score": 55, "confidence": 0.8, "observed_at": observed},
        leak={"leak_probability": 0.2, "demo": True, "observed_at": observed},
        groundwater={"projected_depth_m": 22, "observed_at": observed},
        demand={"forecasted_demand_mgd": 90, "confidence": 0.7, "observed_at": observed},
        climate={"spi3_proxy": -1.0, "climate_source": "open_meteo_sync", "observed_at": observed},
        models=ModelAvailability(shortage=True, groundwater=True, demand=True, leak=True),
    )
    defaults.update(kwargs)
    return build_water_intelligence_metadata(**defaults)


def test_fused_metadata_covers_all_six_components():
    metadata = _fused_metadata()
    assert set(metadata) == set(COMPONENTS)
    for component, meta in metadata.items():
        assert meta["source"], component
        assert meta["method"] in {m.value for m in Method}, component
        assert meta["data_quality"] in {q.value for q in DataQuality}, component
        assert meta["generated_at"], component
        assert meta["confidence"] is None or 0.0 <= meta["confidence"] <= 1.0, component


def test_fused_metadata_uses_normalized_vocabulary_per_source():
    metadata = _fused_metadata()
    assert metadata["climate"]["method"] == Method.WEATHER_PROVIDER.value
    assert metadata["water_stress"]["method"] == Method.RULES_ENGINE.value
    # Seeded demo alerts must never present as a measured leak signal.
    assert metadata["leak"]["method"] == Method.FALLBACK.value
    assert metadata["leak"]["data_quality"] == DataQuality.LOW.value


def test_fused_index_is_only_as_fresh_as_its_stalest_input():
    stale = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
    metadata = _fused_metadata(
        groundwater={"projected_depth_m": 22, "observed_at": stale},
    )
    assert metadata["groundwater"]["is_stale"] is True
    assert metadata["water_stress"]["is_stale"] is True
    assert metadata["water_stress"]["data_quality"] == DataQuality.LOW.value


def test_missing_component_reports_unknown_not_zero_quality():
    metadata = _fused_metadata(demand={})
    assert metadata["demand"]["availability"] == Availability.MISSING.value
    assert metadata["demand"]["data_quality"] == DataQuality.UNKNOWN.value
    assert metadata["demand"]["confidence"] is None


def test_scenario_overrides_are_labelled_and_not_treated_as_observations():
    metadata = _fused_metadata(overrides={"reservoir_capacity_pct": 12.0})
    assert metadata["shortage"]["source"].startswith("scenario_override:")
    assert metadata["shortage"]["observed_at"] is None
    assert metadata["groundwater"]["source"].startswith("scenario_override:") is False


def test_normalization_issues_downgrade_quality():
    clean, issues = normalize_component("demand", {"forecasted_demand_mgd": -3.0})
    metadata = _fused_metadata(demand={**clean, "confidence": 0.9}, issues={"demand": issues})
    assert metadata["demand"]["data_quality"] == DataQuality.LOW.value


def test_metadata_without_timestamps_does_not_crash():
    metadata = _fused_metadata(
        shortage={"predicted_risk_score": 55},
        leak={"leak_probability": 0.2},
        groundwater={"projected_depth_m": 22},
        demand={"forecasted_demand_mgd": 90},
        climate={"spi3_proxy": -1.0},
    )
    assert set(metadata) == set(COMPONENTS)
    assert all(meta["data_age_seconds"] is None for meta in metadata.values())


# ----------------------------------------------------------------------
# End-to-end through the fusion service + router mapper
# ----------------------------------------------------------------------


def test_build_water_intelligence_attaches_metadata_without_a_database():
    from fastapi_app.routers.water_intelligence import _to_response_data
    from fastapi_app.services.model_service import model_service

    payload = model_service.build_water_intelligence(db=None)

    assert set(payload["metadata"]) == set(COMPONENTS)
    # Existing fields stay exactly where consumers expect them.
    assert "water_stress_index" in payload["water_stress"]
    assert math.isfinite(payload["water_stress"]["water_stress_index"])

    data = _to_response_data(payload)
    assert set(data.metadata) == set(COMPONENTS)
    assert data.metadata["water_stress"].method == Method.RULES_ENGINE.value


def test_response_mapper_stays_compatible_without_metadata():
    """Older payloads (no metadata key) must still serialize."""
    from fastapi_app.routers.water_intelligence import _to_response_data

    data = _to_response_data(
        {
            "water_stress": compute_water_stress_index(shortage={"predicted_risk_score": 55}),
            "shortage": {"predicted_risk_score": 55},
            "leak": {},
            "groundwater": {},
            "demand": {},
            "climate": {},
        }
    )
    assert data.metadata == {}
