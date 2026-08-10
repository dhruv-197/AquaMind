"""Scenario / What-If simulation helpers for Water Stress Intelligence."""
from __future__ import annotations

from typing import Any


# Product presets reuse existing fusion knobs only — no new model formulas.
# Leakage maps to demand_delta_pct as an effective-demand proxy (documented in UI).
WHAT_IF_PRESETS: list[dict[str, Any]] = [
    {
        "id": "baseline",
        "label": "Baseline (no stress change)",
        "category": "baseline",
        "description": "Clear scenario knobs and re-run the live fusion.",
        "scenario": {},
    },
    {
        "id": "drought_rainfall_deficit",
        "label": "Drought / rainfall deficit (−35%)",
        "category": "drought",
        "description": "Projects a dry spell by reducing rainfall input to the fusion.",
        "scenario": {"rainfall_delta_pct": -35},
    },
    {
        "id": "heatwave",
        "label": "Heatwave (+4°C, demand +10%)",
        "category": "heatwave",
        "description": "Warmer temperatures with a modest demand uplift.",
        "scenario": {"temperature_delta_c": 4, "demand_delta_pct": 10},
    },
    {
        "id": "increased_demand",
        "label": "Increased demand (+20%)",
        "category": "demand",
        "description": "Higher municipal / industrial demand pressure.",
        "scenario": {"demand_delta_pct": 20},
    },
    {
        "id": "leakage_increase",
        "label": "Leakage increase (as +15% demand)",
        "category": "leakage",
        "description": (
            "Models elevated non-revenue water as additional system demand. "
            "This is a projection proxy — not a measured leak volume."
        ),
        "scenario": {"demand_delta_pct": 15},
    },
    {
        "id": "conservation",
        "label": "Conservation intervention (−15% demand)",
        "category": "conservation",
        "description": "Demand-side conservation reducing effective consumption.",
        "scenario": {"demand_delta_pct": -15},
    },
    {
        "id": "reservoir_a_15",
        "label": "Critical storage (Reservoir A at 15%)",
        "category": "storage",
        "description": "Absolute storage override for a named reservoir.",
        "scenario": {"reservoir_level_pct": 15, "reservoir_id": "RES-A"},
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


def preset_catalog() -> list[dict[str, Any]]:
    """Public preset list for status / UI (includes description metadata)."""
    return [
        {
            "id": p["id"],
            "label": p["label"],
            "category": p.get("category"),
            "description": p.get("description"),
            "scenario": p["scenario"],
        }
        for p in WHAT_IF_PRESETS
    ]
