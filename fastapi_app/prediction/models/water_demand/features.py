"""Demand-specific feature pipeline stages (framework FeatureStage subclasses)."""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from fastapi_app.prediction.framework.features.pipeline import FeaturePipeline
from fastapi_app.prediction.framework.features.stages import (
    FeatureExtractionStage,
    FeatureNormalizationStage,
    FeatureValidationStage,
    MissingValueStage,
    TimeSeriesWindowStage,
)
from fastapi_app.prediction.models.water_demand.constants import (
    ENGINEERED_FEATURES,
    OPTIONAL_RAW_FEATURES,
    SEASON_MAP,
)


class DemandFeatureExtraction(FeatureExtractionStage):
    """Derive calendar / season codes; keep raw climate columns when present."""

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        if "date" in out.columns:
            dates = pd.to_datetime(out["date"], errors="coerce")
            if "day_of_week" not in out.columns:
                out["day_of_week"] = dates.dt.dayofweek
            if "month" not in out.columns:
                out["month"] = dates.dt.month

        if "season" in out.columns and "season_code" not in out.columns:
            out["season_code"] = (
                out["season"]
                .astype(str)
                .str.lower()
                .map(SEASON_MAP)
                .fillna(-1)
                .astype(float)
            )
        elif "month" in out.columns and "season_code" not in out.columns:
            # Infer season from month when explicit season missing
            month = out["month"].astype(float)
            season_code = np.full(len(out), -1.0)
            season_code[month.isin([12, 1, 2])] = 0
            season_code[month.isin([3, 4, 5])] = 2
            season_code[month.isin([6, 7, 8, 9])] = 3
            season_code[month.isin([10, 11])] = 4
            out["season_code"] = season_code

        for flag in ("is_public_holiday", "is_festival"):
            if flag in out.columns:
                out[flag] = out[flag].fillna(0).astype(float)

        return out


class DemandMissingValueHandler(MissingValueStage):
    """Median-impute numeric features; leave target untouched when present."""

    def __init__(self) -> None:
        self._medians: dict[str, float] = {}

    def fit(self, frame: pd.DataFrame) -> DemandMissingValueHandler:
        numeric = frame.select_dtypes(include=[np.number])
        self._medians = {c: float(numeric[c].median()) for c in numeric.columns if c != "demand_mgd"}
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        for col, median in self._medians.items():
            if col in out.columns:
                out[col] = out[col].fillna(median)
        # For unseen columns during predict, fill with column median or 0
        for col in out.select_dtypes(include=[np.number]).columns:
            if col == "demand_mgd":
                continue
            if out[col].isna().any():
                fill = self._medians.get(col, float(out[col].median() if out[col].notna().any() else 0.0))
                out[col] = out[col].fillna(fill)
        return out


class DemandTimeSeriesWindows(TimeSeriesWindowStage):
    """Lag / rolling demand features — historical consumption trend."""

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if "demand_mgd" not in frame.columns:
            return frame.copy()
        out = frame.copy()
        demand = out["demand_mgd"].astype(float)
        out["demand_lag_1"] = demand.shift(1)
        out["demand_lag_7"] = demand.shift(7)
        out["demand_roll_mean_7"] = demand.shift(1).rolling(7, min_periods=1).mean()
        out["demand_roll_mean_30"] = demand.shift(1).rolling(30, min_periods=1).mean()
        out["demand_roll_std_7"] = demand.shift(1).rolling(7, min_periods=2).std()
        out["consumption_trend_7"] = out["demand_lag_1"] - out["demand_roll_mean_7"]
        return out


class DemandFeatureNormalizer(FeatureNormalizationStage):
    """Optional z-score normalizer — fit on training features only."""

    def __init__(self, columns: Sequence[str] | None = None, enabled: bool = False) -> None:
        self.columns = list(columns or [])
        self.enabled = enabled
        self._means: dict[str, float] = {}
        self._stds: dict[str, float] = {}

    def fit(self, frame: pd.DataFrame) -> DemandFeatureNormalizer:
        cols = self.columns or [
            c
            for c in frame.select_dtypes(include=[np.number]).columns
            if c != "demand_mgd"
        ]
        self.columns = cols
        for col in cols:
            if col not in frame.columns:
                continue
            series = frame[col].astype(float)
            self._means[col] = float(series.mean())
            std = float(series.std(ddof=0) or 0.0)
            self._stds[col] = std if std > 1e-9 else 1.0
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not self.enabled:
            return frame.copy()
        out = frame.copy()
        for col in self.columns:
            if col not in out.columns or col not in self._means:
                continue
            out[col] = (out[col].astype(float) - self._means[col]) / self._stds[col]
        return out


class DemandFeatureValidator(FeatureValidationStage):
    """Keep only available engineered features; drop all-null columns."""

    def __init__(self, candidate_features: Sequence[str] | None = None) -> None:
        self.candidate_features = list(candidate_features or ENGINEERED_FEATURES)
        self.active_features: list[str] = []

    def fit(self, frame: pd.DataFrame) -> DemandFeatureValidator:
        active: list[str] = []
        for col in self.candidate_features:
            if col not in frame.columns:
                continue
            if frame[col].isna().all():
                continue
            active.append(col)
        if not active:
            # Fall back to whatever numeric non-target columns exist
            active = [
                c
                for c in frame.select_dtypes(include=[np.number]).columns
                if c != "demand_mgd"
            ]
        self.active_features = active
        return self

    def validate(self, frame: pd.DataFrame) -> list[str]:
        issues: list[str] = []
        for col in self.active_features:
            if col not in frame.columns:
                issues.append(f"Missing active feature: {col}")
        return issues

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not self.active_features:
            self.fit(frame)
        cols = [c for c in self.active_features if c in frame.columns]
        keep = cols + (["demand_mgd"] if "demand_mgd" in frame.columns else [])
        if "date" in frame.columns:
            keep = ["date"] + keep
        return frame.loc[:, keep].copy()


class DemandFeaturePipelineBuilder:
    """Assemble a fitted FeaturePipeline; unavailable features are ignored."""

    def __init__(self) -> None:
        self.extraction = DemandFeatureExtraction()
        self.missing = DemandMissingValueHandler()
        self.windows = DemandTimeSeriesWindows()
        self.normalizer = DemandFeatureNormalizer(enabled=False)
        self.validator = DemandFeatureValidator()

    def fit(self, frame: pd.DataFrame) -> FeaturePipeline:
        step1 = self.extraction.transform(frame)
        step2 = self.windows.transform(step1)
        self.missing.fit(step2)
        step3 = self.missing.transform(step2)
        self.normalizer.fit(step3)
        step4 = self.normalizer.transform(step3)
        self.validator.fit(step4)
        return self.build_pipeline()

    def build_pipeline(self) -> FeaturePipeline:
        return FeaturePipeline(
            [
                self.extraction,
                self.windows,
                self.missing,
                self.normalizer,
                self.validator,
            ]
        )

    @property
    def active_features(self) -> list[str]:
        return list(self.validator.active_features)

    def state_dict(self) -> dict:
        return {
            "missing_medians": dict(self.missing._medians),
            "normalizer_enabled": self.normalizer.enabled,
            "normalizer_means": dict(self.normalizer._means),
            "normalizer_stds": dict(self.normalizer._stds),
            "normalizer_columns": list(self.normalizer.columns),
            "active_features": list(self.validator.active_features),
            "optional_raw_features": list(OPTIONAL_RAW_FEATURES),
        }

    def load_state(self, state: dict) -> FeaturePipeline:
        self.missing._medians = dict(state.get("missing_medians") or {})
        self.normalizer.enabled = bool(state.get("normalizer_enabled", False))
        self.normalizer._means = dict(state.get("normalizer_means") or {})
        self.normalizer._stds = dict(state.get("normalizer_stds") or {})
        self.normalizer.columns = list(state.get("normalizer_columns") or [])
        self.validator.active_features = list(state.get("active_features") or [])
        return self.build_pipeline()
