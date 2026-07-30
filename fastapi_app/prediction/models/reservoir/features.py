"""Reservoir-specific feature pipeline stages (framework FeatureStage subclasses)."""
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
from fastapi_app.prediction.models.reservoir.constants import (
    ENGINEERED_FEATURES,
    OPTIONAL_RAW_FEATURES,
    SEASON_MAP,
)


class ReservoirFeatureExtraction(FeatureExtractionStage):
    """Derive calendar / season / reservoir codes; keep hydro-climate columns when present."""

    def __init__(self) -> None:
        self.reservoir_codes: dict[str, float] = {}

    def fit(self, frame: pd.DataFrame) -> ReservoirFeatureExtraction:
        if "reservoir_id" in frame.columns:
            ids = sorted(frame["reservoir_id"].astype(str).unique().tolist())
            self.reservoir_codes = {rid: float(i) for i, rid in enumerate(ids)}
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        if "date" in out.columns:
            dates = pd.to_datetime(out["date"], errors="coerce")
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
            month = out["month"].astype(float)
            season_code = np.full(len(out), -1.0)
            season_code[month.isin([12, 1, 2])] = 0
            season_code[month.isin([3, 4, 5])] = 2
            season_code[month.isin([6, 7, 8, 9])] = 3
            season_code[month.isin([10, 11])] = 4
            out["season_code"] = season_code

        if "reservoir_id" in out.columns:
            out["reservoir_code"] = (
                out["reservoir_id"].astype(str).map(self.reservoir_codes).fillna(-1.0)
            )
        elif "reservoir_code" not in out.columns:
            out["reservoir_code"] = 0.0

        if "inflow_mcm" in out.columns and "outflow_mcm" in out.columns:
            out["net_inflow_mcm"] = (
                out["inflow_mcm"].astype(float).fillna(0)
                - out["outflow_mcm"].astype(float).fillna(0)
            )
        return out


class ReservoirMissingValueHandler(MissingValueStage):
    """Median-impute numeric features; leave storage target untouched when present."""

    def __init__(self) -> None:
        self._medians: dict[str, float] = {}

    def fit(self, frame: pd.DataFrame) -> ReservoirMissingValueHandler:
        numeric = frame.select_dtypes(include=[np.number])
        self._medians = {
            c: float(numeric[c].median()) for c in numeric.columns if c != "storage_pct"
        }
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        for col, median in self._medians.items():
            if col in out.columns:
                out[col] = out[col].fillna(median)
        for col in out.select_dtypes(include=[np.number]).columns:
            if col == "storage_pct":
                continue
            if out[col].isna().any():
                fill = self._medians.get(
                    col,
                    float(out[col].median() if out[col].notna().any() else 0.0),
                )
                out[col] = out[col].fillna(fill)
        return out


class ReservoirTimeSeriesWindows(TimeSeriesWindowStage):
    """Lag / rolling storage features — historical reservoir trends (per reservoir)."""

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if "storage_pct" not in frame.columns:
            return frame.copy()
        out = frame.copy()
        group_key = "reservoir_id" if "reservoir_id" in out.columns else None

        def _windows(g: pd.DataFrame) -> pd.DataFrame:
            storage = g["storage_pct"].astype(float)
            g = g.copy()
            g["storage_lag_1"] = storage.shift(1)
            g["storage_lag_7"] = storage.shift(7)
            g["storage_roll_mean_7"] = storage.shift(1).rolling(7, min_periods=1).mean()
            g["storage_roll_mean_30"] = storage.shift(1).rolling(30, min_periods=1).mean()
            g["storage_roll_std_7"] = storage.shift(1).rolling(7, min_periods=2).std()
            g["storage_trend_7"] = g["storage_lag_1"] - g["storage_roll_mean_7"]
            return g

        if group_key:
            parts = [_windows(g) for _, g in out.groupby(group_key, sort=False)]
            out = pd.concat(parts, ignore_index=True)
        else:
            out = _windows(out)
        return out


class ReservoirFeatureNormalizer(FeatureNormalizationStage):
    def __init__(self, columns: Sequence[str] | None = None, enabled: bool = False) -> None:
        self.columns = list(columns or [])
        self.enabled = enabled
        self._means: dict[str, float] = {}
        self._stds: dict[str, float] = {}

    def fit(self, frame: pd.DataFrame) -> ReservoirFeatureNormalizer:
        cols = self.columns or [
            c
            for c in frame.select_dtypes(include=[np.number]).columns
            if c != "storage_pct"
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


class ReservoirFeatureValidator(FeatureValidationStage):
    def __init__(self, candidate_features: Sequence[str] | None = None) -> None:
        self.candidate_features = list(candidate_features or ENGINEERED_FEATURES)
        self.active_features: list[str] = []

    def fit(self, frame: pd.DataFrame) -> ReservoirFeatureValidator:
        active: list[str] = []
        for col in self.candidate_features:
            if col not in frame.columns:
                continue
            if frame[col].isna().all():
                continue
            active.append(col)
        if not active:
            active = [
                c
                for c in frame.select_dtypes(include=[np.number]).columns
                if c != "storage_pct"
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
        keep = cols + (["storage_pct"] if "storage_pct" in frame.columns else [])
        for extra in ("date", "reservoir_id", "reservoir_name"):
            if extra in frame.columns:
                keep = [extra] + keep if extra not in keep else keep
        # Preserve order uniqueness
        seen: set[str] = set()
        ordered = []
        for c in keep:
            if c not in seen:
                seen.add(c)
                ordered.append(c)
        return frame.loc[:, ordered].copy()


class ReservoirFeaturePipelineBuilder:
    """Assemble a fitted FeaturePipeline; unavailable features are ignored."""

    def __init__(self) -> None:
        self.extraction = ReservoirFeatureExtraction()
        self.missing = ReservoirMissingValueHandler()
        self.windows = ReservoirTimeSeriesWindows()
        self.normalizer = ReservoirFeatureNormalizer(enabled=False)
        self.validator = ReservoirFeatureValidator()

    def fit(self, frame: pd.DataFrame) -> FeaturePipeline:
        self.extraction.fit(frame)
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
            "reservoir_codes": dict(self.extraction.reservoir_codes),
            "optional_raw_features": list(OPTIONAL_RAW_FEATURES),
        }

    def load_state(self, state: dict) -> FeaturePipeline:
        self.missing._medians = dict(state.get("missing_medians") or {})
        self.normalizer.enabled = bool(state.get("normalizer_enabled", False))
        self.normalizer._means = dict(state.get("normalizer_means") or {})
        self.normalizer._stds = dict(state.get("normalizer_stds") or {})
        self.normalizer.columns = list(state.get("normalizer_columns") or [])
        self.validator.active_features = list(state.get("active_features") or [])
        self.extraction.reservoir_codes = dict(state.get("reservoir_codes") or {})
        return self.build_pipeline()
