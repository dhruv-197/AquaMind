"""Sample regional GIS catalog (Ward / District / Zone / Municipality)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi_app.prediction.models.water_stress.constants import SAMPLE_REGIONS_PATH

RegionType = Literal["ward", "district", "zone", "municipality"]

DEFAULT_REGIONS: list[dict[str, Any]] = [
    {
        "region_id": "WARD-03",
        "name": "Ward 3",
        "region_type": "ward",
        "population": 125000,
        "lat": 19.12,
        "lng": 72.85,
        "reservoir_id": "RES-A",
        "demand_share": 0.18,
        "industrial_share": 0.22,
        "baseline_stress": 38.0,
        "polygon": [[19.10, 72.83], [19.14, 72.83], [19.14, 72.88], [19.10, 72.88]],
    },
    {
        "region_id": "WARD-08",
        "name": "Ward 8",
        "region_type": "ward",
        "population": 210000,
        "lat": 19.05,
        "lng": 72.90,
        "reservoir_id": "RES-A",
        "demand_share": 0.24,
        "industrial_share": 0.35,
        "baseline_stress": 52.0,
        "polygon": [[19.03, 72.88], [19.07, 72.88], [19.07, 72.93], [19.03, 72.93]],
    },
    {
        "region_id": "ZONE-NORTH",
        "name": "North Zone",
        "region_type": "zone",
        "population": 480000,
        "lat": 19.20,
        "lng": 72.95,
        "reservoir_id": "RES-B",
        "demand_share": 0.30,
        "industrial_share": 0.18,
        "baseline_stress": 44.0,
        "polygon": [[19.16, 72.90], [19.24, 72.90], [19.24, 73.00], [19.16, 73.00]],
    },
    {
        "region_id": "ZONE-EAST",
        "name": "East Zone",
        "region_type": "zone",
        "population": 390000,
        "lat": 19.08,
        "lng": 73.05,
        "reservoir_id": "RES-B",
        "demand_share": 0.22,
        "industrial_share": 0.40,
        "baseline_stress": 48.0,
        "polygon": [[19.04, 73.00], [19.12, 73.00], [19.12, 73.10], [19.04, 73.10]],
    },
    {
        "region_id": "DIST-CENTRAL",
        "name": "Central District",
        "region_type": "district",
        "population": 620000,
        "lat": 18.96,
        "lng": 72.82,
        "reservoir_id": "RES-C",
        "demand_share": 0.35,
        "industrial_share": 0.28,
        "baseline_stress": 41.0,
        "polygon": [[18.92, 72.78], [19.00, 72.78], [19.00, 72.88], [18.92, 72.88]],
    },
    {
        "region_id": "MUNI-PILOT",
        "name": "Pilot Municipality",
        "region_type": "municipality",
        "population": 1850000,
        "lat": 19.08,
        "lng": 72.92,
        "reservoir_id": "RES-A",
        "demand_share": 1.0,
        "industrial_share": 0.30,
        "baseline_stress": 46.0,
        "polygon": [[18.90, 72.75], [19.26, 72.75], [19.26, 73.12], [18.90, 73.12]],
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
    if not region_id:
        return catalog[0] if catalog else None
    for r in catalog:
        if str(r.get("region_id")) == str(region_id):
            return r
    return catalog[0] if catalog else None
