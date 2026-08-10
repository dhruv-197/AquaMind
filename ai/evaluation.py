"""Shared evaluation helpers for AquaMind pilot models.

Pure functions used by training scripts, model-card status endpoints, and tests.
Does not invent metrics — callers supply observed numbers or confusion matrices
already produced by training.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def chronological_date_split(
    frame: pd.DataFrame,
    *,
    date_col: str,
    train_frac: float = 0.70,
    val_frac: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split rows by unique calendar dates (chronological), never by shuffled rows."""
    if not 0 < train_frac < 1 or not 0 < val_frac < 1 or train_frac + val_frac >= 1:
        raise ValueError("train_frac and val_frac must be positive and sum to < 1")
    dates = np.array(sorted(pd.to_datetime(frame[date_col]).dt.normalize().unique()))
    if len(dates) < 3:
        raise ValueError("Need at least 3 unique dates for a chronological split")
    n = len(dates)
    train_end = max(1, int(n * train_frac))
    val_end = max(train_end + 1, int(n * (train_frac + val_frac)))
    val_end = min(val_end, n - 1)
    train_dates = set(dates[:train_end])
    val_dates = set(dates[train_end:val_end])
    test_dates = set(dates[val_end:])
    stamps = pd.to_datetime(frame[date_col]).dt.normalize()
    train = frame[stamps.isin(train_dates)]
    val = frame[stamps.isin(val_dates)]
    test = frame[stamps.isin(test_dates)]
    return train, val, test


def chronological_year_split(
    frame: pd.DataFrame,
    *,
    year_col: str = "Year",
    train_end_year: int = 2019,
    validation_end_year: int = 2022,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Year-based chronological partitions (groundwater-style)."""
    years = frame[year_col].astype(int)
    train = frame[years <= train_end_year]
    validation = frame[(years > train_end_year) & (years <= validation_end_year)]
    test = frame[years > validation_end_year]
    return train, validation, test


def assert_no_future_leakage(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    *,
    time_col: str,
) -> None:
    """Raise if any validation/test timestamp precedes the previous partition's max."""
    t_train = pd.to_datetime(train[time_col])
    t_val = pd.to_datetime(validation[time_col])
    t_test = pd.to_datetime(test[time_col])
    if len(t_train) and len(t_val) and t_val.min() < t_train.max():
        raise AssertionError("Validation contains rows earlier than train max — future leakage")
    if len(t_val) and len(t_test) and t_test.min() < t_val.max():
        raise AssertionError("Test contains rows earlier than validation max — future leakage")
    if len(t_train) and len(t_test) and t_test.min() < t_train.max():
        raise AssertionError("Test overlaps train temporally — future leakage")


def regression_metrics(y_true, y_pred, *, unit_key: str) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    out = {
        f"mae_{unit_key}": round(float(mean_absolute_error(y_true, y_pred)), 4),
        f"rmse_{unit_key}": round(float(mean_squared_error(y_true, y_pred) ** 0.5), 4),
        "rows": int(len(y_true)),
    }
    if len(y_true) > 1:
        out["r2"] = round(float(r2_score(y_true, y_pred)), 4)
    return out


def persistence_baseline(y_true, y_persist, *, unit_key: str, method: str) -> dict[str, Any]:
    """Compare a persistence (or other simple) baseline against held-out targets."""
    metrics = regression_metrics(y_true, y_persist, unit_key=unit_key)
    metrics["method"] = method
    return metrics


def mean_baseline_r2() -> dict[str, Any]:
    """Predicting the training mean yields R² = 0 by definition."""
    return {
        "r2": 0.0,
        "method": "predict training-set mean",
        "note": "R² of the mean predictor is 0 by definition; use MAE/RMSE from a retrain when available.",
    }


def majority_class_baseline_from_cm(confusion_matrix: list[list[int]]) -> dict[str, Any]:
    """
    Derive a majority-class baseline from a published [[TN, FP], [FN, TP]] matrix.

    This does not invent labels — it uses the same held-out counts already stored
    in model metadata.
    """
    tn, fp = int(confusion_matrix[0][0]), int(confusion_matrix[0][1])
    fn, tp = int(confusion_matrix[1][0]), int(confusion_matrix[1][1])
    n = tn + fp + fn + tp
    n_pos = tp + fn
    n_neg = tn + fp
    if n <= 0:
        raise ValueError("Empty confusion matrix")
    if n_pos >= n_neg:
        # Always predict positive (leak)
        precision = n_pos / n
        recall = 1.0
        accuracy = n_pos / n
        method = "always_predict_positive (majority class)"
    else:
        precision = 0.0
        recall = 0.0
        accuracy = n_neg / n
        method = "always_predict_negative (majority class)"
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "method": method,
        "rows": n,
    }


def strip_filesystem_paths(value: Any) -> Any:
    """Recursively remove absolute / user-home path strings from a metadata tree."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            lower = str(key).lower()
            if lower in {"artifact_uri", "absolute_path", "local_path"}:
                continue
            if lower in {"source", "data_path", "weather_source"} and isinstance(item, str):
                out[key] = _repo_relative_display(item)
            else:
                out[key] = strip_filesystem_paths(item)
        return out
    if isinstance(value, list):
        return [strip_filesystem_paths(v) for v in value]
    if isinstance(value, str):
        return _repo_relative_display(value) if _looks_like_abs_path(value) else value
    return value


def _looks_like_abs_path(text: str) -> bool:
    if len(text) < 3:
        return False
    if text[1:3] in {":\\", ":/"}:
        return True
    if text.startswith("/Users/") or text.startswith("/home/"):
        return True
    return False


def _repo_relative_display(text: str) -> str:
    """Best-effort: drop drive letters / user dirs; keep Aqua Dataset / ai / data tails."""
    normalized = text.replace("\\", "/")
    for marker in ("Aqua Dataset/", "ai/", "data/", "fastapi_app/"):
        idx = normalized.find(marker)
        if idx >= 0:
            return normalized[idx:]
    if _looks_like_abs_path(text):
        return normalized.rsplit("/", 1)[-1]
    return text.replace("\\", "/")
