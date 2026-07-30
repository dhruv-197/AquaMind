"""Generate LEARNING CURVES (score vs training-set size) for AquaMind models.

Why this file exists in addition to plot_training_curves.py
-----------------------------------------------------------
plot_training_curves.py plots metrics against the NUMBER OF TREES. For a
RandomForest / ExtraTrees ensemble that curve is flat by construction: trees are
grown independently and the ensemble average converges after ~20-30 trees. A
flat line there is correct, but it carries no information about whether the
model is data-limited.

The standard learning curve for a non-iterative estimator plots the score
against the AMOUNT OF TRAINING DATA. That curve rises, and the train/validation
gap tells you something useful:
  * validation still climbing at 100%  -> more data would help
  * curves converged and close together -> model is data-saturated
  * large persistent gap               -> variance / overfitting

Run from project root:
  py ai\\plot_learning_curves.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score

AI_DIR = Path(__file__).resolve().parent
OUT_DIR = AI_DIR / "learning_curves"
sys.path.insert(0, str(AI_DIR))

from water_shortage_model import FEATURES as RES_FEATURES, WaterShortageModel
from groundwater_model import FEATURES as GW_FEATURES, GroundwaterModel
from leak_detection_model import FEATURES as LEAK_FEATURES, collect_all_recordings
from water_demand_model import FEATURES as DEMAND_FEATURES, WaterDemandModel

FRACTIONS = [0.1, 0.2, 0.3, 0.4, 0.55, 0.7, 0.85, 1.0]
TRAIN_COLOR = "#c0392b"
VAL_COLOR = "#1f6feb"


def _style(ax, title: str, ylabel: str):
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel("Training samples used")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.35)
    ax.legend(loc="best", frameon=True)


def _save(fig, name: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"    saved {path.name}")


def learning_curve_regressor(
    *, name, file_stem, X_train, y_train, X_val, y_val,
    n_estimators, max_depth, min_samples_leaf, unit,
):
    X_train = X_train.reset_index(drop=True)
    y_train = y_train.reset_index(drop=True)
    rng = np.random.RandomState(42)
    order = rng.permutation(len(X_train))

    sizes, tr_r2, va_r2, tr_mae, va_mae = [], [], [], [], []
    for frac in FRACTIONS:
        k = max(20, int(len(X_train) * frac))
        idx = order[:k]
        Xs, ys = X_train.iloc[idx], y_train.iloc[idx]
        model = RandomForestRegressor(
            n_estimators=n_estimators, max_depth=max_depth,
            min_samples_leaf=min_samples_leaf, random_state=42, n_jobs=-1,
        )
        model.fit(Xs, ys)
        p_tr, p_va = model.predict(Xs), model.predict(X_val)
        sizes.append(k)
        tr_r2.append(float(r2_score(ys, p_tr)))
        va_r2.append(float(r2_score(y_val, p_va)))
        tr_mae.append(float(mean_absolute_error(ys, p_tr)))
        va_mae.append(float(mean_absolute_error(y_val, p_va)))
        print(f"    n={k:>7,}  train R2={tr_r2[-1]:.4f}  val R2={va_r2[-1]:.4f}")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(sizes, tr_r2, "o-", color=TRAIN_COLOR, label="train")
    ax.plot(sizes, va_r2, "o-", color=VAL_COLOR, label="validation")
    _style(ax, f"{name} — Learning Curve (R²)", "R² score")
    ax.text(0.02, 0.03, "Rising validation curve = model benefits from more data",
            transform=ax.transAxes, fontsize=8, color="#555")
    _save(fig, f"{file_stem}_learning_r2.png")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(sizes, tr_mae, "o-", color=TRAIN_COLOR, label="train")
    ax.plot(sizes, va_mae, "o-", color=VAL_COLOR, label="validation")
    _style(ax, f"{name} — Learning Curve (Error)", f"MAE ({unit})")
    _save(fig, f"{file_stem}_learning_error.png")

    return {"sizes": sizes, "train_r2": tr_r2, "val_r2": va_r2,
            "train_mae": tr_mae, "val_mae": va_mae}


def learning_curve_classifier(
    *, name, file_stem, X_train, y_train, X_val, y_val, n_estimators, max_depth,
):
    X_train = X_train.reset_index(drop=True)
    y_train = y_train.reset_index(drop=True)
    rng = np.random.RandomState(42)
    order = rng.permutation(len(X_train))

    sizes, tr_acc, va_acc, tr_f1, va_f1 = [], [], [], [], []
    for frac in FRACTIONS:
        k = max(20, int(len(X_train) * frac))
        idx = order[:k]
        Xs, ys = X_train.iloc[idx], y_train.iloc[idx]
        if len(np.unique(ys)) < 2:
            continue
        model = ExtraTreesClassifier(
            n_estimators=n_estimators, max_depth=max_depth,
            random_state=42, n_jobs=-1,
        )
        model.fit(Xs, ys)
        p_tr, p_va = model.predict(Xs), model.predict(X_val)
        sizes.append(k)
        tr_acc.append(float(accuracy_score(ys, p_tr)))
        va_acc.append(float(accuracy_score(y_val, p_va)))
        tr_f1.append(float(f1_score(ys, p_tr, zero_division=0)))
        va_f1.append(float(f1_score(y_val, p_va, zero_division=0)))
        print(f"    n={k:>7,}  train acc={tr_acc[-1]:.4f}  val acc={va_acc[-1]:.4f}")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(sizes, tr_acc, "o-", color=TRAIN_COLOR, label="train")
    ax.plot(sizes, va_acc, "o-", color=VAL_COLOR, label="validation")
    _style(ax, f"{name} — Learning Curve (Accuracy)", "Accuracy")
    ax.text(0.02, 0.03,
            "ExtraTrees fit training data exactly by design; judge on the validation line",
            transform=ax.transAxes, fontsize=8, color="#555")
    _save(fig, f"{file_stem}_learning_accuracy.png")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(sizes, tr_f1, "o-", color=TRAIN_COLOR, label="train")
    ax.plot(sizes, va_f1, "o-", color=VAL_COLOR, label="validation")
    _style(ax, f"{name} — Learning Curve (F1)", "F1 score")
    _save(fig, f"{file_stem}_learning_f1.png")

    return {"sizes": sizes, "train_accuracy": tr_acc, "val_accuracy": va_acc,
            "train_f1": tr_f1, "val_f1": va_f1}


def main():
    print("=== AquaMind — learning curves (score vs training-set size) ===\n")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "note": (
            "Learning curves: score vs number of training samples. Unlike the "
            "tree-count curves, these show whether each model is data-limited."
        )
    }

    print("[1/4] Water shortage (reservoir)")
    res = WaterShortageModel()
    rows = res._prepared_rows()
    dates = sorted(rows["Date"].unique())
    tr_end = dates[max(1, int(len(dates) * 0.70)) - 1]
    va_end = dates[max(1, int(len(dates) * 0.85)) - 1]
    tr = rows[rows["Date"] <= tr_end]
    va = rows[(rows["Date"] > tr_end) & (rows["Date"] <= va_end)]
    summary["water_shortage"] = learning_curve_regressor(
        name="Water Shortage Prediction", file_stem="water_shortage",
        X_train=tr[RES_FEATURES], y_train=tr["next_storage_pct"],
        X_val=va[RES_FEATURES], y_val=va["next_storage_pct"],
        n_estimators=150, max_depth=None, min_samples_leaf=3,
        unit="percentage points",
    )

    print("\n[2/4] Groundwater")
    gw = GroundwaterModel()
    gw_rows, _ = gw._prepared_rows()
    tr = gw_rows[gw_rows["Year"] <= 2019]
    va = gw_rows[(gw_rows["Year"] >= 2020) & (gw_rows["Year"] <= 2022)]
    if len(tr) > 40000:
        tr = tr.sample(n=40000, random_state=42)
    if len(va) > 15000:
        va = va.sample(n=15000, random_state=42)
    summary["groundwater"] = learning_curve_regressor(
        name="Groundwater Forecast", file_stem="groundwater",
        X_train=tr[GW_FEATURES], y_train=tr["Water_Level"],
        X_val=va[GW_FEATURES], y_val=va["Water_Level"],
        n_estimators=120, max_depth=20, min_samples_leaf=2, unit="meters",
    )

    print("\n[3/4] Acoustic leak detection")
    from leak_detection_model import SPLIT_SEED, _augment_no_leak, _stratified_group_split

    data = collect_all_recordings()
    tr, va, _te = _stratified_group_split(data, seed=SPLIT_SEED)
    tr = _augment_no_leak(tr)
    summary["leak_detection"] = learning_curve_classifier(
        name="Acoustic Leak Detection", file_stem="leak_detection",
        X_train=tr[LEAK_FEATURES], y_train=tr["label"],
        X_val=va[LEAK_FEATURES], y_val=va["label"],
        n_estimators=400, max_depth=None,
    )

    print("\n[4/4] Water demand")
    from sklearn.model_selection import train_test_split as _tts

    demand = WaterDemandModel()
    drows = demand._prepared_rows()
    d_tr, d_tmp = _tts(drows, test_size=0.30, random_state=42)
    d_va, _d_te = _tts(d_tmp, test_size=0.50, random_state=42)
    summary["water_demand"] = learning_curve_regressor(
        name="Water Demand Forecast", file_stem="water_demand",
        X_train=d_tr[DEMAND_FEATURES], y_train=d_tr["demand_mgd"],
        X_val=d_va[DEMAND_FEATURES], y_val=d_va["demand_mgd"],
        n_estimators=250, max_depth=14, min_samples_leaf=2, unit="MGD",
    )

    # Combined 2x2 figure for slides
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    panels = [
        ("water_shortage", "Water Shortage", "val_r2", "train_r2", "R²"),
        ("groundwater", "Groundwater", "val_r2", "train_r2", "R²"),
        ("leak_detection", "Leak Detection", "val_accuracy", "train_accuracy", "Accuracy"),
        ("water_demand", "Water Demand", "val_r2", "train_r2", "R²"),
    ]
    for ax, (key, label, vkey, tkey, ylab) in zip(axes.ravel(), panels):
        d = summary.get(key) or {}
        if not d:
            continue
        ax.plot(d["sizes"], d[tkey], "o-", color=TRAIN_COLOR, label="train")
        ax.plot(d["sizes"], d[vkey], "o-", color=VAL_COLOR, label="validation")
        ax.set_title(label, fontsize=11, fontweight="bold")
        ax.set_xlabel("Training samples")
        ax.set_ylabel(ylab)
        ax.grid(True, alpha=0.35)
        ax.legend(loc="best", fontsize=8)
    fig.suptitle("AquaMind — Learning Curves (score vs training-set size)",
                 fontsize=14, fontweight="bold")
    _save(fig, "all_models_learning_curves.png")

    (OUT_DIR / "learning_curve_metrics.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nDone. Graphs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
