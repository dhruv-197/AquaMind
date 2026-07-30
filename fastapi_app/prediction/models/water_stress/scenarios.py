"""Scenario / What-If simulation helpers for Water Stress Intelligence."""
from __future__ import annotations

from typing import Any


WHAT_IF_PRESETS: list[dict[str, Any]] = [
    {
        "id": "rainfall_drop_30",
        "label": "What if rainfall drops 30%?",
        "scenario": {"rainfall_delta_pct": -30},
    },
    {
        "id": "demand_up_20",
        "label": "What if demand increases 20%?",
        "scenario": {"demand_delta_pct": 20},
    },
    {
        "id": "reservoir_a_15",
        "label": "What if Reservoir A reaches 15%?",
        "scenario": {"reservoir_level_pct": 15, "reservoir_id": "RES-A"},
    },
    {
        "id": "population_up_10",
        "label": "What if population grows 10%?",
        "scenario": {"population_delta_pct": 10},
    },
    {
        "id": "temp_up_3",
        "label": "What if temperature rises 3°C?",
        "scenario": {"temperature_delta_c": 3},
    },
]


def normalize_scenario(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Clamp and sanitize scenario knobs."""
    raw = raw or {}
    out: dict[str, Any] = {}
    if "rainfall_delta_pct" in raw and raw["rainfall_delta_pct"] is not None:
        out["rainfall_delta_pct"] = max(-80.0, min(80.0, float(raw["rainfall_delta_pct"])))
    if "population_delta_pct" in raw and raw["population_delta_pct"] is not None:
        out["population_delta_pct"] = max(-50.0, min(100.0, float(raw["population_delta_pct"])))
    if "demand_delta_pct" in raw and raw["demand_delta_pct"] is not None:
        out["demand_delta_pct"] = max(-50.0, min(100.0, float(raw["demand_delta_pct"])))
    if "temperature_delta_c" in raw and raw["temperature_delta_c"] is not None:
        out["temperature_delta_c"] = max(-10.0, min(15.0, float(raw["temperature_delta_c"])))
    if "reservoir_delta_pct" in raw and raw["reservoir_delta_pct"] is not None:
        out["reservoir_delta_pct"] = max(-80.0, min(80.0, float(raw["reservoir_delta_pct"])))
    if "reservoir_level_pct" in raw and raw["reservoir_level_pct"] is not None:
        out["reservoir_level_pct"] = max(0.0, min(100.0, float(raw["reservoir_level_pct"])))
    if raw.get("reservoir_id"):
        out["reservoir_id"] = str(raw["reservoir_id"])
    return out


def delay_days_from_delta(baseline_wsi: float, scenario_wsi: float) -> int:
    """Rough heuristic: how many days shortage is delayed/advanced vs baseline."""
    delta = float(baseline_wsi) - float(scenario_wsi)
    # Each WSI point ≈ ~1.2 days of buffer
    return int(round(delta * 1.2))
