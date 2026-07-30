"""Generate accuracy graphs for every trained AquaMind model.

Models (RandomForest — no neural epochs):
  1. Water shortage (reservoir storage) — R² accuracy + MAE
  2. Groundwater depth — R² accuracy + MAE
  3. Acoustic leak detection — classification accuracy + F1
  4. Water demand (CWC drawdown proxy) — R² accuracy + MAE

Curves grow the forest with warm_start and record train/val metrics after
each batch of trees (honest analogue of epoch curves).

Run from project root:
  py ai\\plot_training_curves.py
"""
from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    r2_score,
)

AI_DIR = Path(__file__).resolve().parent
OUT_DIR = AI_DIR / "training_curves"
sys.path.insert(0, str(AI_DIR))

from water_shortage_model import FEATURES as RES_FEATURES, WaterShortageModel
from groundwater_model import FEATURES as GW_FEATURES, GroundwaterModel
from leak_detection_model import FEATURES as LEAK_FEATURES, collect_all_recordings
from water_demand_model import FEATURES as DEMAND_FEATURES, WaterDemandModel


def clear_old_graphs() -> None:
    if OUT_DIR.exists():
        for path in OUT_DIR.iterdir():
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".json", ".svg"}:
                path.unlink()
                print(f"  Removed old {path.name}")
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)


def _style_axes(ax, title: str, ylabel: str, xlabel: str = "Trees in ensemble"):
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.35)
    ax.legend(loc="best", frameon=True)


def _save(fig, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved {path.name}")
    return path


def plot_regressor_accuracy(
    name: str,
    file_stem: str,
    X_train,
    y_train,
    X_val,
    y_val,
    n_estimators: int,
    max_depth,
    min_samples_leaf: int,
    unit: str,
    stages: int = 20,
    max_features="sqrt",
):
    """Grow RF regressor; save accuracy (R²) + error (MAE) graphs."""
    step = max(1, n_estimators // stages)
    tree_counts = list(range(step, n_estimators + 1, step))
    if tree_counts[-1] != n_estimators:
        tree_counts.append(n_estimators)

    train_mae, val_mae, train_r2, val_r2 = [], [], [], []
    model = RandomForestRegressor(
        n_estimators=step,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        max_features=max_features,
        random_state=42,
        n_jobs=1,
        warm_start=True,
    )

    for i, n in enumerate(tree_counts):
        model.set_params(n_estimators=n)
        model.fit(X_train, y_train)
        pred_tr = model.predict(X_train)
        pred_va = model.predict(X_val)
        train_mae.append(float(mean_absolute_error(y_train, pred_tr)))
        val_mae.append(float(mean_absolute_error(y_val, pred_va)))
        train_r2.append(float(r2_score(y_train, pred_tr)))
        val_r2.append(float(r2_score(y_val, pred_va)))
        print(f"  [{name}] stage {i + 1}/{len(tree_counts)} trees={n}  val R²={val_r2[-1]:.4f}")

    # Primary accuracy graph (R²)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(tree_counts, train_r2, "o-", color="#d62728", label="train", linewidth=2, markersize=4)
    ax.plot(tree_counts, val_r2, "o-", color="#1f77b4", label="validation", linewidth=2, markersize=4)
    _style_axes(ax, f"{name} — Model Accuracy (R²)", "Accuracy (R² score)")
    lo = min(train_r2 + val_r2)
    ax.set_ylim(min(-0.05, lo - 0.05) if lo < 0 else max(-0.05, lo - 0.05), 1.05)
    ax.axhline(0.0, color="#999", linestyle=":", linewidth=1)
    ax.text(
        0.02,
        0.02,
        "RandomForest · R² score (1.0 = perfect fit)\n"
        "X-axis = trees in the ensemble",
        transform=ax.transAxes,
        fontsize=8,
        color="#555",
        va="bottom",
    )
    acc_path = _save(fig, f"{file_stem}_accuracy.png")

    # Companion error graph
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(tree_counts, train_mae, "o-", color="#d62728", label="train", linewidth=2, markersize=4)
    ax.plot(tree_counts, val_mae, "o-", color="#1f77b4", label="validation", linewidth=2, markersize=4)
    _style_axes(ax, f"{name} — Train vs Validation Error (MAE)", f"MAE ({unit})")
    ax.text(
        0.02,
        0.02,
        "Lower is better · companion MAE curve",
        transform=ax.transAxes,
        fontsize=8,
        color="#555",
        va="bottom",
    )
    err_path = _save(fig, f"{file_stem}_error.png")

    return {
        "trees": tree_counts,
        "train_r2": train_r2,
        "val_r2": val_r2,
        "train_mae": train_mae,
        "val_mae": val_mae,
        "files": [acc_path.name, err_path.name],
        "final_val_accuracy_r2": val_r2[-1],
        "final_val_mae": val_mae[-1],
    }


def plot_classifier_accuracy(
    name: str,
    file_stem: str,
    X_train,
    y_train,
    X_val,
    y_val,
    n_estimators: int = 100,
    max_depth: int | None = 12,
    stages: int = 20,
):
    step = max(1, n_estimators // stages)
    tree_counts = list(range(step, n_estimators + 1, step))
    if tree_counts[-1] != n_estimators:
        tree_counts.append(n_estimators)

    train_acc, val_acc, train_f1, val_f1 = [], [], [], []
    model = ExtraTreesClassifier(
        n_estimators=step,
        max_depth=max_depth,
        class_weight="balanced_subsample",
        random_state=99,
        n_jobs=1,
        warm_start=True,
    )

    for i, n in enumerate(tree_counts):
        model.set_params(n_estimators=n)
        model.fit(X_train, y_train)
        proba_tr = model.predict_proba(X_train)[:, 1]
        proba_va = model.predict_proba(X_val)[:, 1]
        thr = float(getattr(__import__("leak_detection_model", fromlist=["DECISION_THRESHOLD"]), "DECISION_THRESHOLD", 0.30))
        pred_tr = (proba_tr >= thr).astype(int)
        pred_va = (proba_va >= thr).astype(int)
        train_acc.append(float(accuracy_score(y_train, pred_tr)))
        val_acc.append(float(accuracy_score(y_val, pred_va)))
        train_f1.append(float(f1_score(y_train, pred_tr, zero_division=0)))
        val_f1.append(float(f1_score(y_val, pred_va, zero_division=0)))
        print(f"  [{name}] stage {i + 1}/{len(tree_counts)} trees={n}  val acc={val_acc[-1]:.4f}")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(tree_counts, train_acc, "o-", color="#d62728", label="train", linewidth=2, markersize=4)
    ax.plot(tree_counts, val_acc, "o-", color="#1f77b4", label="validation", linewidth=2, markersize=4)
    _style_axes(ax, f"{name} — Model Accuracy", "Accuracy")
    ax.set_ylim(0.5, 1.02)
    ax.text(
        0.02,
        0.02,
        "RandomForest / ExtraTrees · X-axis = trees in the ensemble",
        transform=ax.transAxes,
        fontsize=8,
        color="#555",
        va="bottom",
    )
    acc_path = _save(fig, f"{file_stem}_accuracy.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(tree_counts, train_f1, "o-", color="#d62728", label="train", linewidth=2, markersize=4)
    ax.plot(tree_counts, val_f1, "o-", color="#1f77b4", label="validation", linewidth=2, markersize=4)
    _style_axes(ax, f"{name} — F1 Score", "F1 score")
    ax.set_ylim(0.5, 1.02)
    f1_path = _save(fig, f"{file_stem}_f1.png")

    return {
        "trees": tree_counts,
        "train_accuracy": train_acc,
        "val_accuracy": val_acc,
        "train_f1": train_f1,
        "val_f1": val_f1,
        "files": [acc_path.name, f1_path.name],
        "final_val_accuracy": val_acc[-1],
        "final_val_f1": val_f1[-1],
    }


def main():
    print("=== AquaMind — regenerating model accuracy graphs ===\n")
    print("[0] Clearing older graphs in ai/training_curves …")
    clear_old_graphs()

    summary: dict = {
        "note": "Validation accuracy curves for AquaMind models (RandomForest ensembles)."
    }

    # 1) Reservoir shortage
    print("\n[1/4] Water shortage (reservoir) model")
    res = WaterShortageModel()
    rows = res._prepared_rows()
    unique_dates = sorted(rows["Date"].unique())
    train_end = unique_dates[max(1, int(len(unique_dates) * 0.70)) - 1]
    validation_end = unique_dates[max(1, int(len(unique_dates) * 0.85)) - 1]
    train = rows[rows["Date"] <= train_end]
    validation = rows[(rows["Date"] > train_end) & (rows["Date"] <= validation_end)]
    summary["water_shortage"] = plot_regressor_accuracy(
        name="Water Shortage Prediction",
        file_stem="water_shortage",
        X_train=train[RES_FEATURES],
        y_train=train["next_storage_pct"],
        X_val=validation[RES_FEATURES],
        y_val=validation["next_storage_pct"],
        n_estimators=150,
        max_depth=None,
        min_samples_leaf=3,
        unit="percentage points",
    )

    # 2) Groundwater
    print("\n[2/4] Groundwater forecast model")
    gw = GroundwaterModel()
    gw_rows, _ = gw._prepared_rows()
    train = gw_rows[gw_rows["Year"] <= 2019]
    validation = gw_rows[(gw_rows["Year"] >= 2020) & (gw_rows["Year"] <= 2022)]
    if len(train) > 40000:
        train = train.sample(n=40000, random_state=42)
    if len(validation) > 15000:
        validation = validation.sample(n=15000, random_state=42)
    summary["groundwater"] = plot_regressor_accuracy(
        name="Groundwater Forecast",
        file_stem="groundwater",
        X_train=train[GW_FEATURES],
        y_train=train["Water_Level"],
        X_val=validation[GW_FEATURES],
        y_val=validation["Water_Level"],
        n_estimators=220,
        max_depth=20,
        min_samples_leaf=2,
        unit="meters",
        stages=11,
    )

    # 3) Leak detection
    print("\n[3/4] Acoustic leak detection model")
    from leak_detection_model import SPLIT_SEED, _augment_no_leak, _stratified_group_split

    data = collect_all_recordings()
    train, validation, _test = _stratified_group_split(data, seed=SPLIT_SEED)
    train = _augment_no_leak(train)
    summary["leak_detection"] = plot_classifier_accuracy(
        name="Acoustic Leak Detection",
        file_stem="leak_detection",
        X_train=train[LEAK_FEATURES],
        y_train=train["label"],
        X_val=validation[LEAK_FEATURES],
        y_val=validation["label"],
        n_estimators=700,
        max_depth=None,
        stages=14,
    )

    # 4) Demand
    print("\n[4/4] Water demand model")
    from sklearn.model_selection import train_test_split as _tts

    demand = WaterDemandModel()
    drows = demand._prepared_rows()
    d_train, d_temp = _tts(drows, test_size=0.30, random_state=42)
    d_val, _d_test = _tts(d_temp, test_size=0.50, random_state=42)
    summary["water_demand"] = plot_regressor_accuracy(
        name="Water Demand Forecast",
        file_stem="water_demand",
        X_train=d_train[DEMAND_FEATURES],
        y_train=d_train["demand_mgd"],
        X_val=d_val[DEMAND_FEATURES],
        y_val=d_val["demand_mgd"],
        n_estimators=250,
        max_depth=14,
        min_samples_leaf=2,
        unit="MGD",
        stages=20,
    )

    # Summary accuracy bar chart — all models
    fig, ax = plt.subplots(figsize=(10, 5.5))
    labels = [
        "Water Shortage\n(R²)",
        "Groundwater\n(R²)",
        "Leak Detection\n(Accuracy)",
        "Water Demand\n(R²)",
    ]
    values = [
        summary["water_shortage"]["final_val_accuracy_r2"],
        summary["groundwater"]["final_val_accuracy_r2"],
        summary["leak_detection"]["final_val_accuracy"],
        summary["water_demand"]["final_val_accuracy_r2"],
    ]
    colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd"]
    bars = ax.bar(labels, values, color=colors, edgecolor="white", width=0.65)
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.03,
            f"{val:.3f}",
            ha="center",
            fontsize=10,
            fontweight="bold",
        )
    ymin = min(0.0, min(values) - 0.1)
    ax.set_ylim(ymin, 1.15)
    ax.axhline(0.0, color="#999", linestyle=":", linewidth=1)
    ax.set_ylabel("Validation accuracy score")
    ax.set_title("AquaMind — Model Accuracy (Validation)", fontsize=13, fontweight="bold")
    ax.grid(True, axis="y", alpha=0.3)
    ax.text(
        0.5,
        -0.16,
        "Regressors: R² · Leak detection: classification accuracy",
        transform=ax.transAxes,
        ha="center",
        fontsize=8,
        color="#555",
    )
    summary_path = _save(fig, "all_models_accuracy_summary.png")
    summary["summary_chart"] = summary_path.name

    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        if isinstance(obj, (np.floating, float)):
            return float(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        return obj

    meta_path = OUT_DIR / "curve_metrics.json"
    meta_path.write_text(json.dumps(_clean(summary), indent=2), encoding="utf-8")
    print(f"\nDone. Accuracy graphs are in: {OUT_DIR}")
    print(f"Metrics JSON: {meta_path}")
    print("\nPrimary accuracy files:")
    for name in [
        "water_shortage_accuracy.png",
        "groundwater_accuracy.png",
        "leak_detection_accuracy.png",
        "water_demand_accuracy.png",
        "all_models_accuracy_summary.png",
    ]:
        print(f"  - {OUT_DIR / name}")


if __name__ == "__main__":
    main()
