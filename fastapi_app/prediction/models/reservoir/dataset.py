"""Dataset loader and validation for reservoir level forecasting."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from fastapi_app.prediction.framework.datasets.base import TrainingDataset
from fastapi_app.prediction.models.reservoir.constants import (
    DEFAULT_RESERVOIRS,
    OPTIONAL_RAW_FEATURES,
    REQUIRED_COLUMNS,
    SAMPLE_CSV_PATH,
)


class ReservoirDatasetValidationError(ValueError):
    """Raised when reservoir dataset fails validation gates."""


class ReservoirDatasetLoader:
    """
    Load reservoir history from CSV, Parquet, or a pandas DataFrame.

    Validates missing values, duplicate dates (per reservoir), bad timestamps,
    and outliers. Missing optional features are tolerated.
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
                "Run generate_sample_dataset() or place sample_reservoir.csv."
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
        # enforced at the router boundary (see routers/reservoir_forecast.py),
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
        rename: dict[str, str] = {}
        for required in REQUIRED_COLUMNS:
            if required in cols:
                rename[cols[required]] = required
            elif required not in frame.columns:
                issues.append(f"Missing required column: {required}")
        for optional in OPTIONAL_RAW_FEATURES:
            if optional in cols and cols[optional] != optional:
                rename[cols[optional]] = optional

        alias_map = {
            "level_pct": "storage_pct",
            "storage": "storage_pct",
            "reservoir_level_pct": "storage_pct",
            "current_level_pct": "storage_pct",
            "inflow": "inflow_mcm",
            "outflow": "outflow_mcm",
            "rainfall": "rainfall_mm",
            "precip": "rainfall_mm",
            "precipitation_mm": "rainfall_mm",
            "temp": "temperature_c",
            "temperature": "temperature_c",
            "evaporation": "evaporation_mm",
            "catchment_rainfall": "catchment_rainfall_mm",
            "capacity": "capacity_mcm",
            "dam_release": "dam_release_mcm",
            "release_mcm": "dam_release_mcm",
            "gw_recharge": "groundwater_recharge_mcm",
            "groundwater_recharge": "groundwater_recharge_mcm",
            "lat": "location_lat",
            "lng": "location_lng",
            "lon": "location_lng",
            "id": "reservoir_id",
            "name": "reservoir_name",
        }
        for raw, target in alias_map.items():
            if raw in cols and target not in frame.columns and target not in rename.values():
                rename[cols[raw]] = target

        if issues:
            raise ReservoirDatasetValidationError("; ".join(issues))

        cleaned = frame.rename(columns=rename).copy()

        try:
            cleaned["date"] = pd.to_datetime(cleaned["date"], errors="raise")
        except Exception as exc:
            raise ReservoirDatasetValidationError(f"Incorrect timestamps in date column: {exc}") from exc

        if cleaned["date"].isna().any():
            bad = int(cleaned["date"].isna().sum())
            raise ReservoirDatasetValidationError(f"Incorrect timestamps: {bad} unparseable date(s)")

        if "reservoir_id" not in cleaned.columns:
            cleaned["reservoir_id"] = "RES-DEFAULT"

        # Duplicate dates per reservoir
        dup_mask = cleaned.duplicated(subset=["reservoir_id", "date"], keep="first")
        dup_count = int(dup_mask.sum())
        if dup_count:
            cleaned = cleaned.loc[~dup_mask].copy()

        cleaned = cleaned.sort_values(["reservoir_id", "date"]).reset_index(drop=True)

        cleaned["storage_pct"] = pd.to_numeric(cleaned["storage_pct"], errors="coerce")
        missing_storage = int(cleaned["storage_pct"].isna().sum())
        if missing_storage:
            cleaned = cleaned.dropna(subset=["storage_pct"]).reset_index(drop=True)
        cleaned["storage_pct"] = cleaned["storage_pct"].clip(0, 100)

        for col in OPTIONAL_RAW_FEATURES:
            if col in cleaned.columns and col not in {"season", "reservoir_id", "reservoir_name"}:
                cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

        outlier_count = 0
        if len(cleaned) >= 10 and self.outlier_zscore > 0:
            kept_parts: list[pd.DataFrame] = []
            for _, group in cleaned.groupby("reservoir_id", sort=False):
                series = group["storage_pct"]
                mu, sigma = float(series.mean()), float(series.std(ddof=0) or 0.0)
                if sigma > 0:
                    z = (series - mu).abs() / sigma
                    outlier_mask = z > self.outlier_zscore
                    outlier_count += int(outlier_mask.sum())
                    if self.drop_outliers:
                        group = group.loc[~outlier_mask]
                kept_parts.append(group)
            cleaned = pd.concat(kept_parts, ignore_index=True)

        if cleaned.empty:
            raise ReservoirDatasetValidationError("Dataset empty after validation")

        cleaned = cleaned.sort_values(["reservoir_id", "date"]).reset_index(drop=True)
        cleaned.attrs["validation"] = {
            "source": source,
            "duplicate_dates_dropped": dup_count,
            "missing_storage_dropped": missing_storage,
            "outliers_dropped": outlier_count if self.drop_outliers else 0,
            "outliers_flagged": outlier_count,
            "rows": len(cleaned),
            "reservoirs": sorted(cleaned["reservoir_id"].astype(str).unique().tolist()),
        }
        return cleaned

    def to_training_dataset(
        self,
        frame: pd.DataFrame,
        *,
        feature_columns: Sequence[str],
        name: str = "reservoir_training",
    ) -> TrainingDataset:
        return TrainingDataset(
            frame,
            feature_columns=list(feature_columns),
            target_column="storage_pct",
            name=name,
            source="reservoir_loader",
        )

    @staticmethod
    def catalog_from_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
        """Build a multi-reservoir catalog from cleaned history."""
        if frame.empty:
            return []
        catalog: list[dict[str, Any]] = []
        for rid, group in frame.groupby("reservoir_id", sort=True):
            last = group.sort_values("date").iloc[-1]
            capacity = float(last.get("capacity_mcm") or group["capacity_mcm"].dropna().iloc[-1]) if "capacity_mcm" in group.columns and group["capacity_mcm"].notna().any() else None
            name = None
            if "reservoir_name" in group.columns and group["reservoir_name"].notna().any():
                name = str(group["reservoir_name"].dropna().iloc[-1])
            lat = float(last["location_lat"]) if "location_lat" in group.columns and pd.notna(last.get("location_lat")) else None
            lng = float(last["location_lng"]) if "location_lng" in group.columns and pd.notna(last.get("location_lng")) else None
            catalog.append(
                {
                    "reservoir_id": str(rid),
                    "reservoir_name": name or str(rid),
                    "capacity_mcm": capacity,
                    "current_storage_pct": round(float(last["storage_pct"]), 2),
                    "location_lat": lat,
                    "location_lng": lng,
                    "observed_at": pd.to_datetime(last["date"]).date().isoformat(),
                }
            )
        return catalog


def generate_sample_dataset(
    path: Path | None = None,
    *,
    days: int = 730,
    seed: int = 42,
) -> Path:
    """Create a synthetic multi-reservoir CSV for training demos / tests."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2023-01-01")
    dates = pd.date_range(start, periods=days, freq="D")
    frames: list[pd.DataFrame] = []

    for meta in DEFAULT_RESERVOIRS:
        month = dates.month.to_numpy()
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
        temperature = 28 + 8 * np.sin(2 * np.pi * (month - 1) / 12) + rng.normal(0, 1.2, days)
        rainfall = np.clip(
            np.where(
                np.isin(month, [6, 7, 8, 9]),
                rng.gamma(1.4, 5.0, days),
                rng.exponential(0.5, days),
            ),
            0,
            None,
        )
        catchment = rainfall * (1.1 + 0.15 * rng.random(days))
        evaporation = np.clip(3.5 + 0.12 * (temperature - 25) + rng.normal(0, 0.3, days), 0.5, None)
        inflow = np.clip(
            0.08 * catchment + 0.4 * rainfall + rng.normal(0.8, 0.35, days),
            0.05,
            None,
        )
        release = np.clip(0.9 + 0.25 * np.sin(2 * np.pi * np.arange(days) / 30) + rng.normal(0, 0.15, days), 0.2, None)
        outflow = release + np.clip(rng.normal(0.15, 0.05, days), 0, None)
        gw_recharge = np.clip(0.05 * rainfall + rng.normal(0.08, 0.03, days), 0, None)

        storage = np.zeros(days)
        storage[0] = float(meta["base_level"])
        capacity = float(meta["capacity_mcm"])
        for i in range(1, days):
            delta_pct = (
                (inflow[i] - outflow[i] - evaporation[i] * 0.02 + gw_recharge[i] * 0.5)
                / capacity
                * 100.0
            )
            storage[i] = np.clip(
                storage[i - 1] + delta_pct + rng.normal(0, 0.35),
                8.0,
                98.0,
            )

        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "reservoir_id": meta["reservoir_id"],
                    "reservoir_name": meta["reservoir_name"],
                    "storage_pct": np.round(storage, 3),
                    "inflow_mcm": np.round(inflow, 3),
                    "outflow_mcm": np.round(outflow, 3),
                    "rainfall_mm": np.round(rainfall, 2),
                    "temperature_c": np.round(temperature, 2),
                    "evaporation_mm": np.round(evaporation, 2),
                    "catchment_rainfall_mm": np.round(catchment, 2),
                    "capacity_mcm": capacity,
                    "dam_release_mcm": np.round(release, 3),
                    "groundwater_recharge_mcm": np.round(gw_recharge, 3),
                    "season": season,
                    "month": month,
                    "location_lat": meta["location_lat"],
                    "location_lng": meta["location_lng"],
                }
            )
        )

    frame = pd.concat(frames, ignore_index=True)
    out = path or SAMPLE_CSV_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    return out
