"""Sample regional GIS catalog (Ward / District / Zone / Municipality)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi_app.prediction.models.water_stress.constants import SAMPLE_REGIONS_PATH

RegionType = Literal["ward", "district", "zone", "municipality"]

# Spread across major Indian metros so the national stress map shows distinct
# pins (not one Mumbai cluster of 6 overlapping sample wards).
DEFAULT_REGIONS: list[dict[str, Any]] = [
    {
        "region_id": "WARD-03",
        "name": "Ahmedabad Central",
        "region_type": "ward",
        "population": 125000,
        "lat": 23.0225,
        "lng": 72.5714,
        "reservoir_id": "RES-A",
        "demand_share": 0.18,
        "industrial_share": 0.22,
        "baseline_stress": 38.0,
        "polygon": [
            [23.00, 72.55],
            [23.04, 72.55],
            [23.04, 72.59],
            [23.00, 72.59],
        ],
    },
    {
        "region_id": "WARD-08",
        "name": "Mumbai Island City",
        "region_type": "ward",
        "population": 210000,
        "lat": 19.076,
        "lng": 72.8777,
        "reservoir_id": "RES-A",
        "demand_share": 0.24,
        "industrial_share": 0.35,
        "baseline_stress": 52.0,
        "polygon": [
            [19.05, 72.85],
            [19.10, 72.85],
            [19.10, 72.90],
            [19.05, 72.90],
        ],
    },
    {
        "region_id": "ZONE-NORTH",
        "name": "Delhi NCR North",
        "region_type": "zone",
        "population": 480000,
        "lat": 28.7041,
        "lng": 77.1025,
        "reservoir_id": "RES-B",
        "demand_share": 0.30,
        "industrial_share": 0.18,
        "baseline_stress": 44.0,
        "polygon": [
            [28.66, 77.06],
            [28.74, 77.06],
            [28.74, 77.14],
            [28.66, 77.14],
        ],
    },
    {
        "region_id": "ZONE-EAST",
        "name": "Kolkata East",
        "region_type": "zone",
        "population": 390000,
        "lat": 22.5726,
        "lng": 88.3639,
        "reservoir_id": "RES-B",
        "demand_share": 0.22,
        "industrial_share": 0.40,
        "baseline_stress": 48.0,
        "polygon": [
            [22.53, 88.32],
            [22.61, 88.32],
            [22.61, 88.40],
            [22.53, 88.40],
        ],
    },
    {
        "region_id": "DIST-CENTRAL",
        "name": "Hyderabad Central",
        "region_type": "district",
        "population": 620000,
        "lat": 17.385,
        "lng": 78.4867,
        "reservoir_id": "RES-C",
        "demand_share": 0.35,
        "industrial_share": 0.28,
        "baseline_stress": 41.0,
        "polygon": [
            [17.35, 78.45],
            [17.42, 78.45],
            [17.42, 78.52],
            [17.35, 78.52],
        ],
    },
    {
        "region_id": "MUNI-PILOT",
        "name": "Chennai Metro Pilot",
        "region_type": "municipality",
        "population": 1850000,
        "lat": 13.0827,
        "lng": 80.2707,
        "reservoir_id": "RES-A",
        "demand_share": 1.0,
        "industrial_share": 0.30,
        "baseline_stress": 46.0,
        "polygon": [
            [13.04, 80.22],
            [13.12, 80.22],
            [13.12, 80.32],
            [13.04, 80.32],
        ],
    },
]


def ensure_sample_regions(path: Path | None = None) -> Path:
    out = path or SAMPLE_REGIONS_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        out.write_text(json.dumps(DEFAULT_REGIONS, indent=2), encoding="utf-8")
    return out


def load_regions(path: Path | None = None) -> list[dict[str, Any]]:
    target = ensure_sample_regions(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass
    return list(DEFAULT_REGIONS)


def get_region(
    region_id: str | None, regions: list[dict[str, Any]] | None = None
) -> dict[str, Any] | None:
    catalog = regions or load_regions()
    if not catalog and not region_id:
        return None
    if not region_id:
        return catalog[0] if catalog else None
    for r in catalog:
        if str(r.get("region_id")) == str(region_id):
            return r
    # National geospatial assets (reservoirs, GW stations, …) become on-the-fly
    # stress regions so every map pin can drive a distinct fusion run.
    try:
        from fastapi_app.geospatial.repository import get_repository

        asset = get_repository().by_id(str(region_id))
        if asset is not None:
            return region_from_asset(asset)
    except Exception:
        pass
    return None


def region_from_asset(asset: Any) -> dict[str, Any]:
    """Build a fusion region dict from a national WaterAsset pin."""
    asset_id = str(getattr(asset, "id", "") or "asset")
    asset_type = getattr(getattr(asset, "type", None), "value", None) or str(
        getattr(asset, "type", "region")
    )
    name = str(getattr(asset, "name", None) or asset_id)
    lat = float(getattr(asset, "lat"))
    lng = float(getattr(asset, "lng"))
    storage = getattr(asset, "current_storage_pct", None)
    risk = str(getattr(asset, "risk_level", None) or "moderate").lower()
    meta = getattr(asset, "meta", None) or {}

    risk_baseline = {
        "critical": 72.0,
        "high": 58.0,
        "warning": 48.0,
        "moderate": 42.0,
        "medium": 42.0,
        "low": 28.0,
        "healthy": 22.0,
        "ok": 22.0,
    }.get(risk, 40.0)
    jitter = (abs(hash(asset_id)) % 110) / 10.0  # 0.0–10.9
    if storage is not None and str(storage).strip() != "":
        try:
            storage_f = float(storage)
            baseline = max(15.0, min(88.0, (100.0 - storage_f) * 0.65 + jitter * 0.35))
        except (TypeError, ValueError):
            baseline = risk_baseline + jitter * 0.5
    else:
        baseline = risk_baseline + jitter * 0.5

    pop_meta = meta.get("population") if isinstance(meta, dict) else None
    try:
        population = int(float(pop_meta)) if pop_meta is not None else 80_000 + (abs(hash(asset_id)) % 420_000)
    except (TypeError, ValueError):
        population = 80_000 + (abs(hash(asset_id)) % 420_000)

    parent = None
    if isinstance(meta, dict):
        parent = meta.get("forecast_proxy_id") or meta.get("parent_reservoir_id")
    reservoir_id = (
        asset_id
        if asset_type in {"reservoir", "dam"}
        else (str(parent) if parent else "RES-A")
    )

    region_type = {
        "reservoir": "district",
        "dam": "district",
        "groundwater_station": "zone",
        "demand_region": "municipality",
        "water_stress_region": "ward",
        "leak_zone": "ward",
    }.get(asset_type, "district")

    return {
        "region_id": asset_id,
        "name": name,
        "region_type": region_type,
        "population": population,
        "lat": lat,
        "lng": lng,
        "reservoir_id": reservoir_id,
        "demand_share": 0.10 + (abs(hash(asset_id + ":d")) % 45) / 100.0,
        "industrial_share": 0.12 + (abs(hash(asset_id + ":i")) % 40) / 100.0,
        "baseline_stress": round(float(baseline), 1),
        "polygon": None,
        "source_asset_type": asset_type,
    }
