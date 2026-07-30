"""Dataset loader and validation for water demand forecasting."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from fastapi_app.prediction.framework.datasets.base import TrainingDataset
from fastapi_app.prediction.models.water_demand.constants import (
    OPTIONAL_RAW_FEATURES,
    REQUIRED_COLUMNS,
    SAMPLE_CSV_PATH,
)


class DemandDatasetValidationError(ValueError):
    """Raised when demand dataset fails validation gates."""


class DemandDatasetLoader:
    """
    Load demand history from CSV, Parquet, or a pandas DataFrame.

    Validates missing values, duplicate dates, bad timestamps, and outliers.
    """

    def __init__(
        self,
        *,
        outlier_zscore: float = 4.0,
        drop_outliers: bool = True,
    ) -> None:
        self.outlier_zscore = outlier_zscore
        self.drop_outliers = drop_outliers

    def load_csv(self, path: str | Path) -> pd.DataFrame:
        frame = pd.read_csv(path)
        return self.validate_and_clean(frame, source=str(path))

    def load_parquet(self, path: str | Path) -> pd.DataFrame:
        frame = pd.read_parquet(path)
        return self.validate_and_clean(frame, source=str(path))

    def load_dataframe(self, frame: pd.DataFrame, *, source: str = "dataframe") -> pd.DataFrame:
        return self.validate_and_clean(frame.copy(), source=source)

    def load_sample(self) -> pd.DataFrame:
        if not SAMPLE_CSV_PATH.exists():
            raise FileNotFoundError(
                f"Sample dataset not found at {SAMPLE_CSV_PATH}. "
                "Run generate_sample_dataset() or place sample_demand.csv."
            )
        return self.load_csv(SAMPLE_CSV_PATH)

    def load_any(self, source: str | Path | pd.DataFrame | None = None) -> pd.DataFrame:
        if source is None:
            return self.load_sample()
        if isinstance(source, pd.DataFrame):
            return self.load_dataframe(source)
        # NOTE: this loader is used both by trusted internal callers (tests,
        # scripts) with arbitrary local paths and by the HTTP training
        # endpoints — path containment for the untrusted HTTP case is
        # enforced at the router boundary (see routers/demand_forecast.py),
        # not here, so trusted callers aren't restricted to data/imports/.
        path = Path(source)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return self.load_csv(path)
        if suffix in {".parquet", ".pq"}:
            return self.load_parquet(path)
        raise ValueError(f"Unsupported dataset source: {source!r}")

    def validate_and_clean(self, frame: pd.DataFrame, *, source: str = "unknown") -> pd.DataFrame:
        issues: list[str] = []
        cols = {c.lower().strip(): c for c in frame.columns}
        rename = {}
        for required in REQUIRED_COLUMNS:
            if required in cols:
                rename[cols[required]] = required
            elif required not in frame.columns:
                issues.append(f"Missing required column: {required}")
        for optional in OPTIONAL_RAW_FEATURES:
            if optional in cols and cols[optional] != optional:
                rename[cols[optional]] = optional
        # Common aliases
        alias_map = {
            "demand": "demand_mgd",
            "water_demand": "demand_mgd",
            "demand_mld": None,  # handled below
            "temp": "temperature_c",
            "temperature": "temperature_c",
            "humidity": "humidity_pct",
            "rainfall": "rainfall_mm",
            "precip": "rainfall_mm",
            "precipitation_mm": "rainfall_mm",
            "population": "population_thousands",
            "storage_pct": "reservoir_storage_pct",
            "gw_level": "groundwater_level_m",
            "holiday": "is_public_holiday",
            "festival": "is_festival",
        }
        for raw, target in alias_map.items():
            if target and raw in cols and target not in frame.columns and target not in rename.values():
                rename[cols[raw]] = target

        if issues:
            raise DemandDatasetValidationError("; ".join(issues))

        cleaned = frame.rename(columns=rename).copy()

        # Timestamps
        try:
            cleaned["date"] = pd.to_datetime(cleaned["date"], errors="raise")
        except Exception as exc:
            raise DemandDatasetValidationError(f"Incorrect timestamps in date column: {exc}") from exc

        if cleaned["date"].isna().any():
            bad = int(cleaned["date"].isna().sum())
            raise DemandDatasetValidationError(f"Incorrect timestamps: {bad} unparseable date(s)")

        # Duplicate dates
        dup_mask = cleaned["date"].duplicated(keep="first")
        dup_count = int(dup_mask.sum())
        if dup_count:
            cleaned = cleaned.loc[~dup_mask].copy()

        cleaned = cleaned.sort_values("date").reset_index(drop=True)

        # Demand numeric
        cleaned["demand_mgd"] = pd.to_numeric(cleaned["demand_mgd"], errors="coerce")
        missing_demand = int(cleaned["demand_mgd"].isna().sum())
        if missing_demand:
            cleaned = cleaned.dropna(subset=["demand_mgd"]).reset_index(drop=True)

        # Coerce optional numerics; leave missing for feature pipeline to handle
        for col in OPTIONAL_RAW_FEATURES:
            if col in cleaned.columns and col not in {"season"}:
                cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

        # Outliers on demand (z-score)
        outlier_count = 0
        if len(cleaned) >= 10 and self.outlier_zscore > 0:
            series = cleaned["demand_mgd"]
            mu, sigma = float(series.mean()), float(series.std(ddof=0) or 0.0)
            if sigma > 0:
                z = (series - mu).abs() / sigma
                outlier_mask = z > self.outlier_zscore
                outlier_count = int(outlier_mask.sum())
                if self.drop_outliers and outlier_count:
                    cleaned = cleaned.loc[~outlier_mask].reset_index(drop=True)

        if cleaned.empty:
            raise DemandDatasetValidationError("Dataset empty after validation")

        cleaned.attrs["validation"] = {
            "source": source,
            "duplicate_dates_dropped": dup_count,
            "missing_demand_dropped": missing_demand,
            "outliers_dropped": outlier_count if self.drop_outliers else 0,
            "outliers_flagged": outlier_count,
            "rows": len(cleaned),
        }
        return cleaned

    def to_training_dataset(
        self,
        frame: pd.DataFrame,
        *,
        feature_columns: Sequence[str],
        name: str = "water_demand_training",
    ) -> TrainingDataset:
        return TrainingDataset(
            frame,
            feature_columns=list(feature_columns),
            target_column="demand_mgd",
            name=name,
            source="demand_loader",
        )


def generate_sample_dataset(
    path: Path | None = None,
    *,
    days: int = 730,
    seed: int = 42,
) -> Path:
    """Create a synthetic municipal demand CSV for training demos / tests."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2023-01-01")
    dates = pd.date_range(start, periods=days, freq="D")

    day_of_week = dates.dayofweek.to_numpy()
    month = dates.month.to_numpy()
    # Rough India-like season encoding via month
    season = np.array(
        [
            "winter"
            if m in (12, 1, 2)
            else "summer"
            if m in (3, 4, 5)
            else "monsoon"
            if m in (6, 7, 8, 9)
            else "autumn"
            for m in month
        ]
    )

    temperature = 28 + 8 * np.sin(2 * np.pi * (month - 1) / 12) + rng.normal(0, 1.5, days)
    humidity = 55 + 20 * np.sin(2 * np.pi * (month - 6) / 12) + rng.normal(0, 5, days)
    humidity = np.clip(humidity, 20, 99)
    rainfall = np.clip(
        np.where(
            np.isin(month, [6, 7, 8, 9]),
            rng.gamma(1.2, 4.0, days),
            rng.exponential(0.6, days),
        ),
        0,
        None,
    )

    population = 820 + np.linspace(0, 40, days) + rng.normal(0, 1.0, days)
    is_weekend = (day_of_week >= 5).astype(int)
    # Sparse holidays / festivals
    is_public_holiday = (rng.random(days) < 0.03).astype(int)
    is_festival = (rng.random(days) < 0.02).astype(int)

    reservoir = np.clip(
        55 + 20 * np.sin(2 * np.pi * (np.arange(days) / 365.0)) + rng.normal(0, 3, days),
        15,
        98,
    )
    groundwater = np.clip(28 + 0.004 * np.arange(days) + rng.normal(0, 0.4, days), 10, 60)

    # Demand generative process (MGD)
    base = 95.0
    demand = (
        base
        + 0.045 * population
        + 0.55 * (temperature - 28)
        - 0.08 * humidity
        - 0.35 * rainfall
        + 6.0 * is_weekend
        + 8.0 * is_public_holiday
        + 12.0 * is_festival
        + 0.05 * (100 - reservoir)
        + 0.15 * groundwater
        + rng.normal(0, 2.5, days)
    )
    # Mild autocorrelation
    for i in range(1, days):
        demand[i] = 0.35 * demand[i - 1] + 0.65 * demand[i]

    frame = pd.DataFrame(
        {
            "date": dates,
            "demand_mgd": np.round(demand, 3),
            "temperature_c": np.round(temperature, 2),
            "humidity_pct": np.round(humidity, 2),
            "rainfall_mm": np.round(rainfall, 2),
            "day_of_week": day_of_week,
            "month": month,
            "is_public_holiday": is_public_holiday,
            "is_festival": is_festival,
            "population_thousands": np.round(population, 2),
            "season": season,
            "reservoir_storage_pct": np.round(reservoir, 2),
            "groundwater_level_m": np.round(groundwater, 2),
        }
    )

    out = path or SAMPLE_CSV_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    return out
