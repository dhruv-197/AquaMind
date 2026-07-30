"""Constants for the Water Demand Forecast model."""
from __future__ import annotations

from pathlib import Path

MODEL_KEY = "water_demand"
MODEL_VERSION = "1.0.0"

# Supported forecast horizons (days)
HORIZONS: tuple[int, ...] = (1, 7, 15, 30)

# Raw / optional input columns (gracefully ignored when missing)
OPTIONAL_RAW_FEATURES: tuple[str, ...] = (
    "temperature_c",
    "humidity_pct",
    "rainfall_mm",
    "day_of_week",
    "month",
    "is_public_holiday",
    "is_festival",
    "population_thousands",
    "season",
    "reservoir_storage_pct",
    "groundwater_level_m",
)

REQUIRED_COLUMNS: tuple[str, ...] = ("date", "demand_mgd")

# Engineered feature names produced by the demand feature pipeline
ENGINEERED_FEATURES: tuple[str, ...] = (
    "temperature_c",
    "humidity_pct",
    "rainfall_mm",
    "day_of_week",
    "month",
    "is_public_holiday",
    "is_festival",
    "population_thousands",
    "season_code",
    "reservoir_storage_pct",
    "groundwater_level_m",
    "demand_lag_1",
    "demand_lag_7",
    "demand_roll_mean_7",
    "demand_roll_mean_30",
    "demand_roll_std_7",
    "consumption_trend_7",
)

DEFAULT_CAPACITY_MGD = 150.0

ARTIFACTS_DIR = Path(__file__).resolve().parents[4] / "data" / "water_demand" / "artifacts"
SAMPLE_CSV_PATH = Path(__file__).resolve().parents[4] / "data" / "water_demand" / "sample_demand.csv"

SEASON_MAP = {
    "winter": 0,
    "spring": 1,
    "summer": 2,
    "monsoon": 3,
    "autumn": 4,
    "fall": 4,
}
