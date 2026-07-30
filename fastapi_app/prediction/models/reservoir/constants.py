"""Constants for the Reservoir Level Forecast model."""
from __future__ import annotations

from pathlib import Path

MODEL_KEY = "reservoir_forecast"
MODEL_VERSION = "1.0.0"

HORIZONS: tuple[int, ...] = (1, 7, 15, 30)

REQUIRED_COLUMNS: tuple[str, ...] = ("date", "storage_pct")

OPTIONAL_RAW_FEATURES: tuple[str, ...] = (
    "reservoir_id",
    "reservoir_name",
    "inflow_mcm",
    "outflow_mcm",
    "rainfall_mm",
    "temperature_c",
    "evaporation_mm",
    "catchment_rainfall_mm",
    "capacity_mcm",
    "dam_release_mcm",
    "groundwater_recharge_mcm",
    "season",
    "month",
    "location_lat",
    "location_lng",
)

ENGINEERED_FEATURES: tuple[str, ...] = (
    "inflow_mcm",
    "outflow_mcm",
    "rainfall_mm",
    "temperature_c",
    "evaporation_mm",
    "catchment_rainfall_mm",
    "capacity_mcm",
    "dam_release_mcm",
    "groundwater_recharge_mcm",
    "month",
    "season_code",
    "reservoir_code",
    "storage_lag_1",
    "storage_lag_7",
    "storage_roll_mean_7",
    "storage_roll_mean_30",
    "storage_roll_std_7",
    "storage_trend_7",
    "net_inflow_mcm",
)

DEFAULT_CAPACITY_MCM = 250.0
CRITICAL_STORAGE_PCT = 20.0
HIGH_STORAGE_PCT = 40.0
MODERATE_STORAGE_PCT = 60.0

ARTIFACTS_DIR = Path(__file__).resolve().parents[4] / "data" / "reservoir" / "artifacts"
SAMPLE_CSV_PATH = Path(__file__).resolve().parents[4] / "data" / "reservoir" / "sample_reservoir.csv"

SEASON_MAP = {
    "winter": 0,
    "spring": 1,
    "summer": 2,
    "monsoon": 3,
    "autumn": 4,
    "fall": 4,
}

# Default multi-reservoir catalog used when generating sample data
DEFAULT_RESERVOIRS: tuple[dict, ...] = (
    {
        "reservoir_id": "RES-A",
        "reservoir_name": "Reservoir A",
        "capacity_mcm": 320.0,
        "location_lat": 19.0760,
        "location_lng": 72.8777,
        "base_level": 62.0,
    },
    {
        "reservoir_id": "RES-B",
        "reservoir_name": "Reservoir B",
        "capacity_mcm": 210.0,
        "location_lat": 18.5204,
        "location_lng": 73.8567,
        "base_level": 48.0,
    },
    {
        "reservoir_id": "RES-C",
        "reservoir_name": "Reservoir C",
        "capacity_mcm": 180.0,
        "location_lat": 21.1458,
        "location_lng": 79.0882,
        "base_level": 55.0,
    },
)
