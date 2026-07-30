"""Sample unused 6-hourly GWL telemetry and enrich SQLite groundwater rows.

Scalable pattern: read a bounded row budget per file (not full multi-GB load),
compute per-station depletion rates, upsert into aquamind.db.

Usage:
  py ai\\process_gwl_telemetry.py
  py ai\\process_gwl_telemetry.py --max-files 3 --max-rows-per-file 80000
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

AI_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AI_DIR.parent
GWL_DIR = PROJECT_DIR / "Aqua Dataset" / "Ground Water Level"
sys.path.insert(0, str(PROJECT_DIR))

from fastapi_app.database.connection import SessionLocal  # noqa: E402
from fastapi_app.database.models import Groundwater  # noqa: E402
from fastapi_app.services.groundwater_metrics import (  # noqa: E402
    classify_trend,
    days_to_critical_threshold,
    depletion_rate_m_year,
)


DEPTH_COL_CANDIDATES = (
    "Groundwater Level Telemetry Quadridaily (meter)",
    "Groundwater Level Telemetry 6 Hourly (meter)",
)


def _pick_depth_column(columns: list[str]) -> str | None:
    for name in DEPTH_COL_CANDIDATES:
        if name in columns:
            return name
    for col in columns:
        lower = col.lower()
        if "groundwater level" in lower and "meter" in lower:
            return col
    return None


def _station_id(state: str, station: str, idx: int) -> str:
    raw = re.sub(r"[^A-Za-z0-9_-]", "", f"TEL_{state}_{station}")[:48]
    return raw or f"TEL{idx}"


def process_file(
    path: Path,
    *,
    max_rows: int,
    max_stations: int,
) -> list[dict]:
    depth_col = None
    # Read header first to resolve depth column name.
    header = pd.read_csv(path, nrows=0)
    depth_col = _pick_depth_column(list(header.columns))
    if not depth_col:
        print(f"[skip] no depth column in {path.name}")
        return []

    usecols = ["Station", "State", "Latitude", "Longitude", "Data Acquisition Time", depth_col]
    usecols = [c for c in usecols if c in header.columns]
    df = pd.read_csv(path, usecols=usecols, nrows=max_rows)
    if df.empty:
        return []

    df["Data Acquisition Time"] = pd.to_datetime(
        df["Data Acquisition Time"], dayfirst=True, errors="coerce"
    )
    df[depth_col] = pd.to_numeric(df[depth_col], errors="coerce")
    df = df.dropna(subset=["Station", "Data Acquisition Time", depth_col])
    df = df[df[depth_col] > 0]

    results: list[dict] = []
    for station, group in df.groupby("Station"):
        if len(results) >= max_stations:
            break
        group = group.sort_values("Data Acquisition Time")
        if len(group) < 4:
            continue
        # Downsample long series to endpoints + quarterly-ish points.
        if len(group) > 60:
            idx = list(range(0, len(group), max(1, len(group) // 50)))
            if idx[-1] != len(group) - 1:
                idx.append(len(group) - 1)
            group = group.iloc[idx]

        depths = group[depth_col].astype(float).tolist()
        t0 = group["Data Acquisition Time"].iloc[0]
        days = [(ts - t0).total_seconds() / 86400.0 for ts in group["Data Acquisition Time"]]
        rate = depletion_rate_m_year(depths, timestamps_days=days)
        lat = float(group["Latitude"].iloc[-1]) if "Latitude" in group.columns else None
        lng = float(group["Longitude"].iloc[-1]) if "Longitude" in group.columns else None
        state = str(group["State"].iloc[-1]) if "State" in group.columns else ""
        current = float(depths[-1])
        results.append(
            {
                "station": str(station),
                "state": state,
                "lat": lat,
                "lng": lng,
                "depth_m": round(current, 2),
                "depletion_rate_m_year": rate,
                "trend": classify_trend(rate),
                "days_to_critical": days_to_critical_threshold(current, rate),
                "samples": len(depths),
                "source_file": path.name,
            }
        )
    return results


def upsert_groundwater(rows: list[dict], *, replace_existing_tel: bool = True) -> int:
    db = SessionLocal()
    try:
        if replace_existing_tel:
            db.query(Groundwater).filter(Groundwater.data_source.like("GWL telemetry%")).delete(
                synchronize_session=False
            )
        used: set[str] = set()
        added = 0
        for idx, row in enumerate(rows):
            sid = _station_id(row.get("state") or "", row["station"], idx)
            if sid in used:
                sid = f"{sid}_{idx}"
            used.add(sid)
            rate = float(row["depletion_rate_m_year"])
            depth = float(row["depth_m"])
            status_year = 2030 if rate > 4 else 2050 if rate > 2 else 2075
            db.merge(
                Groundwater(
                    id=sid,
                    name=f"{row['station']} ({row.get('state') or 'TEL'})",
                    depth_to_water_m=depth,
                    depletion_rate_m_year=rate,
                    recharge_rate_m_year=round(max(0.05, 1.2 - rate * 0.15), 2),
                    storage_volume_mcm=round(max(1.0, depth + 20.0), 1),
                    safe_yield_mcm=round(max(0.5, (depth + 20.0) * 0.1), 1),
                    projected_depletion_year=status_year,
                    soil_moisture_index=round(max(0.05, min(0.95, 1.0 - depth / 200.0)), 2),
                    location_lat=row.get("lat"),
                    location_lng=row.get("lng"),
                    state=row.get("state") or None,
                    data_source=f"GWL telemetry 6h sample ({row['source_file']})",
                    observed_at=None,
                )
            )
            added += 1
        db.commit()
        return added
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process bounded GWL telemetry into SQLite")
    parser.add_argument("--max-files", type=int, default=4, help="Max CSV files to sample")
    parser.add_argument("--max-rows-per-file", type=int, default=80_000)
    parser.add_argument("--max-stations-per-file", type=int, default=40)
    parser.add_argument(
        "--prefer",
        default="cgwb_dl,assam_as,cgwb_ch",
        help="Comma substrings to prefer when choosing files (smaller/relevant first)",
    )
    args = parser.parse_args()

    if not GWL_DIR.exists():
        raise SystemExit(f"GWL directory not found: {GWL_DIR}")

    files = sorted(GWL_DIR.glob("gwl_tel_6_hourly_*.csv"), key=lambda p: p.stat().st_size)
    # Prefer smaller, recent, or named files; skip empty stubs (<1 KB).
    files = [f for f in files if f.stat().st_size > 1000]
    prefer = [p.strip() for p in args.prefer.split(",") if p.strip()]
    ranked: list[Path] = []
    for token in prefer:
        for f in files:
            if token in f.name and f not in ranked:
                ranked.append(f)
    for f in files:
        if f not in ranked:
            ranked.append(f)
    selected = ranked[: args.max_files]

    print(f"[gwl] sampling {len(selected)} files from {GWL_DIR}")
    all_rows: list[dict] = []
    for path in selected:
        rows = process_file(
            path,
            max_rows=args.max_rows_per_file,
            max_stations=args.max_stations_per_file,
        )
        print(f"  {path.name}: {len(rows)} stations")
        all_rows.extend(rows)

    # Deduplicate by station name keeping highest |rate|.
    best: dict[str, dict] = {}
    for row in all_rows:
        key = f"{row.get('state')}|{row['station']}"
        prev = best.get(key)
        if prev is None or abs(row["depletion_rate_m_year"]) > abs(prev["depletion_rate_m_year"]):
            best[key] = row
    unique = list(best.values())
    n = upsert_groundwater(unique)
    print(f"[gwl] upserted {n} telemetry wells into aquamind.db")
    if unique:
        top = sorted(unique, key=lambda r: r["depletion_rate_m_year"], reverse=True)[:5]
        print("[gwl] top depletion rates:")
        for row in top:
            print(
                f"  {row['station']} ({row.get('state')}): "
                f"{row['depletion_rate_m_year']} m/yr — {row['trend']}"
            )


if __name__ == "__main__":
    main()
