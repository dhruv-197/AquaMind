"""Rule-engine government / ops recommendations from climate + flood + ponding."""
from __future__ import annotations

from typing import Any


def build_recommendations(
    climate: dict[str, Any],
    flood: dict[str, Any],
    waterlogging: dict[str, Any],
    heat: dict[str, Any],
) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    spi = climate.get("spi3_proxy") or {}
    deficit = climate.get("rainfall_deficit") or {}
    spi_z = spi.get("spi3_proxy")
    deficit_pct = deficit.get("deficit_pct")

    if spi_z is not None and spi_z <= -1.0:
        recs.append(
            {
                "priority": 1 if spi_z <= -1.5 else 2,
                "action": "Activate drought watch for reservoir allocation and demand curtailment",
                "rationale": f"SPI-3 proxy={spi_z} ({spi.get('class')})",
                "module": "shortage",
                "href": "/shortage",
            }
        )
    if deficit_pct is not None and deficit_pct >= 25:
        recs.append(
            {
                "priority": 2,
                "action": "Review groundwater extraction limits in stressed blocks",
                "rationale": f"Rainfall deficit ≈ {deficit_pct}% vs climatology",
                "module": "groundwater",
                "href": "/groundwater",
            }
        )

    if heat.get("active") or (heat.get("intensity_score") or 0) >= 1.5:
        recs.append(
            {
                "priority": 2,
                "action": "Increase leak patrol priority in heat-affected distribution zones",
                "rationale": (
                    f"Heat intensity={heat.get('intensity_score')}; "
                    f"leak priority ×{heat.get('leak_priority_multiplier')}"
                ),
                "module": "leak",
                "href": "/leak-detection",
            }
        )

    risk = flood.get("risk_class")
    if risk in ("elevated", "high", "extreme"):
        recs.append(
            {
                "priority": 1 if risk in ("high", "extreme") else 2,
                "action": "Issue fluvial flood watch; clear drains near river corridors",
                "rationale": f"GloFAS discharge risk={risk} (p{flood.get('percentile')} peak)",
                "module": "flood",
                "href": "/map",
            }
        )

    band = waterlogging.get("duration_band")
    depth = waterlogging.get("potential_depth_mm") or 0
    if band and band != "none" and depth >= 5:
        recs.append(
            {
                "priority": 1 if depth >= 30 or band in ("1-3d", ">3d") else 2,
                "action": "Pre-deploy pumping / clear storm drains for pluvial waterlogging",
                "rationale": (
                    f"Potential ponding ≈ {depth} mm; duration band {band} "
                    f"(indicative water-balance, not DEM inundation)"
                ),
                "module": "waterlogging",
                "href": "/map",
            }
        )

    if not recs:
        recs.append(
            {
                "priority": 3,
                "action": "Maintain routine monitoring; no climate extreme triggers",
                "rationale": "SPI/deficit/heat/GloFAS/ponding within watch thresholds",
                "module": "dashboard",
                "href": "/dashboard",
            }
        )

    recs.sort(key=lambda r: r["priority"])
    # priority queue score for UI
    for i, r in enumerate(recs):
        r["queue_score"] = round(100 - r["priority"] * 15 - i * 3, 1)
    return recs
