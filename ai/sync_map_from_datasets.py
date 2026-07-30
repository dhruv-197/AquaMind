"""
Load CWC reservoir + CGWB well points from Aqua Dataset into SQLite for the map.

Usage (from repo root):
  py ai\\sync_map_from_datasets.py

Does NOT require Bhuvan. Sensors/leak alerts stay as demo seed unless you replace them later.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from fastapi_app.database.connection import SessionLocal, engine
from fastapi_app.database.models import Base, Groundwater, Reservoir

AQUA = ROOT / "Aqua Dataset"
RESERVOIR_CSV = (
    AQUA
    / "Reservoir level datase"
    / "Daily_data_of_reservoir_level_of_Central_Water_Commission_(CWC)_Agency_during_March_2024.csv"
)
WELLS_CSV = (
    AQUA
    / "Quality_controlled_groundwater_levels_over_India"
    / "Input"
    / "1_India_GWLs_2000_2024_wells_within_India.csv"
)

# Prefer recent seasonal columns when estimating depth / trend
DEPTH_COLS = [
    "Nov-24", "Aug-24", "May-24", "Jan-24",
    "Nov-23", "Aug-23", "May-23", "Jan-23",
    "Nov-22", "May-22", "Nov-21", "May-21",
]
MAX_WELLS = 400  # Leaflet-friendly sample across India


def _f(val: str | None) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.upper() in {"NA", "N/A", "NULL", "-"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def ensure_columns() -> None:
    Base.metadata.create_all(bind=engine)
    alters = [
        ("reservoirs", "data_source", "VARCHAR(255)"),
        ("reservoirs", "observed_at", "VARCHAR(32)"),
        ("groundwater", "location_lat", "FLOAT"),
        ("groundwater", "location_lng", "FLOAT"),
        ("groundwater", "state", "VARCHAR(100)"),
        ("groundwater", "data_source", "VARCHAR(255)"),
        ("groundwater", "observed_at", "VARCHAR(32)"),
    ]
    with engine.begin() as conn:
        for table, col, typ in alters:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            existing = {r[1] for r in rows}
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
                print(f"[migrate] added {table}.{col}")


def load_reservoirs(db) -> int:
    if not RESERVOIR_CSV.exists():
        raise FileNotFoundError(f"Missing reservoir CSV: {RESERVOIR_CSV}")

    by_name: dict[str, list[dict]] = defaultdict(list)
    with open(RESERVOIR_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("Reservoir_name") or "").strip()
            if name:
                by_name[name].append(row)

    db.query(Reservoir).delete()
    count = 0
    for name, rows in by_name.items():
        rows_sorted = sorted(rows, key=lambda r: r.get("Date") or "")
        latest = rows_sorted[-1]
        lat = _f(latest.get("Lat"))
        lng = _f(latest.get("Long"))
        if lat is None or lng is None:
            continue

        capacity_bcm = _f(latest.get("Live_capacity_FRL")) or 0.0
        capacity_mcm = capacity_bcm * 1000.0
        storage_bcm = _f(latest.get("Storage"))
        level_m = _f(latest.get("Level"))
        frl = _f(latest.get("Full_reservoir_level"))

        if storage_bcm is not None and capacity_bcm > 0:
            pct = max(0.0, min(100.0, (storage_bcm / capacity_bcm) * 100.0))
        elif level_m is not None and frl and frl > 0:
            # Rough level-vs-FRL proxy when storage is missing
            pct = max(0.0, min(100.0, (level_m / frl) * 100.0))
        else:
            pct = 50.0

        db.add(
            Reservoir(
                name=name,
                capacity_mcm=capacity_mcm if capacity_mcm > 0 else 1.0,
                current_level_pct=round(pct, 1),
                location_lat=lat,
                location_lng=lng,
                data_source="CWC daily reservoir levels (March 2024 CSV)",
                observed_at=latest.get("Date") or "2024-03",
            )
        )
        count += 1

    db.commit()
    print(f"[reservoirs] loaded {count} unique CWC reservoirs")
    return count


def _latest_depth(row: dict) -> tuple[float | None, str | None]:
    for col in DEPTH_COLS:
        v = _f(row.get(col))
        if v is not None and v >= 0:
            return v, col
    # fall back: scan any month-like column
    for key, raw in row.items():
        if re.match(r"^(Jan|May|Aug|Nov)-\d{2}$", key or ""):
            v = _f(raw)
            if v is not None and v >= 0:
                return v, key
    return None, None


def _depletion_proxy(row: dict, latest_depth: float) -> float:
    older = None
    for col in ("May-21", "Nov-20", "May-20", "Nov-19", "May-19"):
        older = _f(row.get(col))
        if older is not None:
            break
    if older is None:
        return round(min(8.0, max(0.1, latest_depth / 40.0)), 2)
    # positive = deepening (worse)
    return round(min(12.0, max(-2.0, latest_depth - older) / 3.0), 2)


def load_groundwater_wells(db, max_wells: int = MAX_WELLS) -> int:
    if not WELLS_CSV.exists():
        raise FileNotFoundError(f"Missing wells CSV: {WELLS_CSV}")

    candidates: list[dict] = []
    with open(WELLS_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            lat = _f(row.get("Latitude"))
            lng = _f(row.get("Longitude"))
            depth, period = _latest_depth(row)
            if lat is None or lng is None or depth is None:
                continue
            if not (6.0 <= lat <= 37.5 and 68.0 <= lng <= 98.0):
                continue
            candidates.append(
                {
                    "code": str(row.get("Station Code") or "").strip(),
                    "name": str(row.get("Station Name") or "CGWB well").strip(),
                    "state": str(row.get("State") or "").strip(),
                    "lat": lat,
                    "lng": lng,
                    "depth": depth,
                    "period": period,
                    "well_depth": _f(row.get("Well Depth")) or max(depth * 1.5, 10.0),
                    "row": row,
                }
            )

    # Stratify: take wells evenly from each state
    by_state: dict[str, list] = defaultdict(list)
    for c in candidates:
        by_state[c["state"] or "Unknown"].append(c)

    selected: list[dict] = []
    states = sorted(by_state.keys())
    if not states:
        raise RuntimeError("No valid groundwater wells found in CSV")

    per_state = max(1, max_wells // len(states))
    for state in states:
        wells = by_state[state]
        step = max(1, len(wells) // per_state)
        selected.extend(wells[::step][:per_state])

    # Trim / top-up to max_wells
    if len(selected) > max_wells:
        selected = selected[:max_wells]
    elif len(selected) < max_wells:
        seen = {w["code"] for w in selected}
        for c in candidates:
            if c["code"] in seen:
                continue
            selected.append(c)
            seen.add(c["code"])
            if len(selected) >= max_wells:
                break

    db.query(Groundwater).delete()
    used_ids: set[str] = set()
    for idx, w in enumerate(selected):
        dep = _depletion_proxy(w["row"], w["depth"])
        status_year = 2030 if dep > 4 else 2050 if dep > 2 else 2075
        raw = re.sub(r"[^A-Za-z0-9_-]", "", w["code"] or "")[:48]
        sid = raw or f"GW{idx}"
        if sid in used_ids:
            sid = f"{sid}_{idx}"
        used_ids.add(sid)
        db.add(
            Groundwater(
                id=sid,
                name=f"{w['name']} ({w['state']})" if w["state"] else w["name"],
                depth_to_water_m=round(w["depth"], 2),
                depletion_rate_m_year=dep,
                recharge_rate_m_year=round(max(0.05, 1.2 - dep * 0.15), 2),
                storage_volume_mcm=round(max(1.0, w["well_depth"]), 1),
                safe_yield_mcm=round(max(0.5, w["well_depth"] * 0.1), 1),
                projected_depletion_year=status_year,
                soil_moisture_index=round(max(0.05, min(0.95, 1.0 - w["depth"] / 200.0)), 2),
                location_lat=w["lat"],
                location_lng=w["lng"],
                state=w["state"] or None,
                data_source="CGWB QC wells (India GWLs 2000–2024)",
                observed_at=w["period"],
            )
        )

    db.commit()
    print(f"[groundwater] loaded {len(selected)} CGWB wells (sampled from {len(candidates)})")
    return len(selected)


def main() -> None:
    print(f"[sync] Aqua Dataset root: {AQUA}")
    if not AQUA.exists():
        raise SystemExit("Aqua Dataset folder not found next to the repo root.")

    ensure_columns()
    db = SessionLocal()
    try:
        n_res = load_reservoirs(db)
        n_gw = load_groundwater_wells(db)
        print(f"[sync] done at {datetime.utcnow().isoformat()}Z — reservoirs={n_res}, wells={n_gw}")
        print("[sync] Note: pipe sensors / leak alerts remain demo-seeded. Bhuvan not required.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
