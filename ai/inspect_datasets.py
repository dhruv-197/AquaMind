"""Reproducible dataset inventory for AquaMind's local training data."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Aqua Dataset"
OUT = Path(__file__).resolve().parent / "dataset_inventory.json"

def csv_summary(path: Path, skiprows: int = 0) -> dict:
    data = pd.read_csv(path, skiprows=skiprows)
    summary = {"path": str(path.relative_to(ROOT)), "rows": len(data), "columns": list(data.columns), "missing_values": data.isna().sum().astype(int).to_dict()}
    if {"YEAR", "MO", "DY"}.issubset(data.columns):
        dates = pd.to_datetime(data[["YEAR", "MO", "DY"]].rename(columns={"YEAR": "year", "MO": "month", "DY": "day"}))
        summary["date_range"] = {"start": str(dates.min().date()), "end": str(dates.max().date())}
    elif "Date" in data.columns:
        dates = pd.to_datetime(data["Date"], errors="coerce")
        summary["date_range"] = {"start": str(dates.min().date()), "end": str(dates.max().date())}
    return summary

def main() -> None:
    reservoir = next((DATA / "Reservoir level datase").glob("*.csv"))
    weather = next((DATA / "Historical India weather CSV").glob("*.csv"))
    groundwater = DATA / "Quality_controlled_groundwater_levels_over_India" / "Input" / "1_India_GWLs_2000_2024_wells_within_India.csv"
    report = {"reservoir": csv_summary(reservoir), "weather_delhi": csv_summary(weather, skiprows=12), "groundwater_wells": csv_summary(groundwater)}
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved {OUT}")

if __name__ == "__main__":
    main()
