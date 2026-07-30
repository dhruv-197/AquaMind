"""Slide-ready evaluation charts for AquaMind models.

Every chart here is computed from the project's own datasets and splits, so each
number can be reproduced by re-running this script.

Charts produced (ai/evaluation_charts/):
  1. feature_importance.png       - what each model actually learned from
  2. predicted_vs_actual.png      - regression fit against the ideal diagonal
  3. baseline_comparison.png      - model vs naive baseline (the honesty chart)
  4. leak_confusion_roc.png       - confusion matrix + ROC/AUC for the classifier
  5. error_distribution.png       - where prediction errors actually fall
  6. groundwater_coverage_map.png - national well coverage behind the GW model

Run from project root:
  py ai\\plot_evaluation_charts.py
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
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    r2_score,
    roc_auc_score,
    roc_curve,
)

AI_DIR = Path(__file__).resolve().parent

# "--slides" renders the same charts with presentation-sized type so they stay
# readable when dropped into a PowerPoint slide at half-page size.
SLIDE_MODE = "--slides" in sys.argv
OUT_DIR = AI_DIR / ("evaluation_charts_slides" if SLIDE_MODE else "evaluation_charts")

if SLIDE_MODE:
    matplotlib.rcParams.update({
        "font.size": 17,
        "axes.titlesize": 20,
        "axes.labelsize": 17,
        "xtick.labelsize": 15,
        "ytick.labelsize": 15,
        "legend.fontsize": 15,
        "figure.titlesize": 24,
        "lines.linewidth": 2.6,
        "lines.markersize": 9,
        "axes.linewidth": 1.4,
    })

sys.path.insert(0, str(AI_DIR))

from water_shortage_model import FEATURES as RES_FEATURES, WaterShortageModel
from groundwater_model import FEATURES as GW_FEATURES, GroundwaterModel
from leak_detection_model import FEATURES as LEAK_FEATURES, collect_all_recordings
from water_demand_model import FEATURES as DEMAND_FEATURES, WaterDemandModel

BLUE = "#1f6feb"
RED = "#c0392b"
GREEN = "#2f7d4f"
GREY = "#8b979b"


def _pt(n):
    """Scale a hard-coded font size up for slide mode."""
    return int(n * 1.7) if SLIDE_MODE else n


def _fs(w, h):
    """Figure size, enlarged in slide mode to fit presentation-sized type."""
    return (w * 1.25, h * 1.25) if SLIDE_MODE else (w, h)


def _save(fig, name):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT_DIR / name, dpi=140)
    plt.close(fig)
    print(f"    saved {name}")


def load_splits():
    """Return train/val frames for all four models, using project split rules."""
    print("[data] preparing splits ...")
    d = {}

    res = WaterShortageModel()
    rows = res._prepared_rows()
    dates = sorted(rows["Date"].unique())
    tr_end = dates[max(1, int(len(dates) * 0.70)) - 1]
    va_end = dates[max(1, int(len(dates) * 0.85)) - 1]
    d["shortage"] = (
        rows[rows["Date"] <= tr_end],
        rows[(rows["Date"] > tr_end) & (rows["Date"] <= va_end)],
    )

    gw = GroundwaterModel()
    gw_rows, _ = gw._prepared_rows()
    tr = gw_rows[gw_rows["Year"] <= 2019]
    va = gw_rows[(gw_rows["Year"] >= 2020) & (gw_rows["Year"] <= 2022)]
    d["gw_full"] = gw_rows
    if len(tr) > 40000:
        tr = tr.sample(n=40000, random_state=42)
    if len(va) > 15000:
        va = va.sample(n=15000, random_state=42)
    d["groundwater"] = (tr, va)

    from leak_detection_model import SPLIT_SEED, _augment_no_leak, _stratified_group_split

    data = collect_all_recordings()
    ltr, lva, _ = _stratified_group_split(data, seed=SPLIT_SEED)
    d["leak"] = (_augment_no_leak(ltr), lva)

    from sklearn.model_selection import train_test_split as _tts

    dem = WaterDemandModel()
    drows = dem._prepared_rows()
    d_tr, d_tmp = _tts(drows, test_size=0.30, random_state=42)
    d_va, _ = _tts(d_tmp, test_size=0.50, random_state=42)
    d["demand"] = (d_tr, d_va)
    return d


def fit_models(S):
    print("[fit] training evaluation models ...")
    m = {}
    tr, _ = S["shortage"]
    m["shortage"] = RandomForestRegressor(
        n_estimators=150, min_samples_leaf=3, random_state=42, n_jobs=-1
    ).fit(tr[RES_FEATURES], tr["next_storage_pct"])

    tr, _ = S["groundwater"]
    m["groundwater"] = RandomForestRegressor(
        n_estimators=120, max_depth=20, min_samples_leaf=2, random_state=42, n_jobs=-1
    ).fit(tr[GW_FEATURES], tr["Water_Level"])

    tr, _ = S["leak"]
    m["leak"] = ExtraTreesClassifier(
        n_estimators=400, random_state=42, n_jobs=-1
    ).fit(tr[LEAK_FEATURES], tr["label"])

    tr, _ = S["demand"]
    m["demand"] = RandomForestRegressor(
        n_estimators=250, max_depth=14, min_samples_leaf=2, random_state=42, n_jobs=-1
    ).fit(tr[DEMAND_FEATURES], tr["demand_mgd"])
    return m


# ----------------------------------------------------------------- 1. features
def chart_feature_importance(M):
    print("[1] feature importance")
    spec = [
        ("shortage", RES_FEATURES, "Water Shortage"),
        ("groundwater", GW_FEATURES, "Groundwater"),
        ("leak", LEAK_FEATURES, "Leak Detection"),
        ("demand", DEMAND_FEATURES, "Water Demand"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=_fs(13, 9))
    for ax, (key, feats, label) in zip(axes.ravel(), spec):
        imp = M[key].feature_importances_
        order = np.argsort(imp)[::-1][:8]
        names = [feats[i].replace("_", " ") for i in order][::-1]
        vals = imp[order][::-1]
        ax.barh(names, vals, color=BLUE)
        ax.set_title(f"{label} — what drives the prediction",
                     fontsize=_pt(11), fontweight="bold")
        ax.set_xlabel("Relative importance")
        ax.grid(True, axis="x", alpha=0.3)
        for y, v in enumerate(vals):
            ax.text(v, y, f" {v:.2f}", va="center", fontsize=8)
    fig.suptitle("AquaMind — Feature Importance (Explainable AI)",
                 fontsize=_pt(14), fontweight="bold")
    _save(fig, "feature_importance.png")


# --------------------------------------------------------- 2. predicted-actual
def chart_pred_vs_actual(S, M):
    print("[2] predicted vs actual")
    spec = [
        ("shortage", RES_FEATURES, "next_storage_pct", "Water Shortage", "storage %"),
        ("groundwater", GW_FEATURES, "Water_Level", "Groundwater", "depth (m)"),
        ("demand", DEMAND_FEATURES, "demand_mgd", "Water Demand", "MGD"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=_fs(15, 5))
    for ax, (key, feats, target, label, unit) in zip(axes, spec):
        _, va = S[key]
        y = va[target].to_numpy()
        p = M[key].predict(va[feats])
        if len(y) > 4000:
            idx = np.random.RandomState(42).choice(len(y), 4000, replace=False)
            y, p = y[idx], p[idx]
        ax.scatter(y, p, s=_pt(8), alpha=0.30, color=BLUE, edgecolors="none")
        lo, hi = float(min(y.min(), p.min())), float(max(y.max(), p.max()))
        ax.plot([lo, hi], [lo, hi], "--", color=RED, lw=1.6, label="perfect prediction")
        r2 = r2_score(va[target], M[key].predict(va[feats]))
        mae = mean_absolute_error(va[target], M[key].predict(va[feats]))
        ax.set_title(f"{label}\nR² = {r2:.3f} · MAE = {mae:.2f}",
                     fontsize=_pt(11), fontweight="bold")
        ax.set_xlabel(f"Actual {unit}")
        ax.set_ylabel(f"Predicted {unit}")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=_pt(8), loc="upper left")
    fig.suptitle("AquaMind — Predicted vs Actual on unseen validation data",
                 fontsize=_pt(14), fontweight="bold")
    _save(fig, "predicted_vs_actual.png")


# ------------------------------------------------------------- 3. vs baseline
def chart_baseline(S, M):
    print("[3] model vs naive baseline")
    _, va = S["shortage"]
    sh_m = r2_score(va["next_storage_pct"], M["shortage"].predict(va[RES_FEATURES]))
    sh_b = r2_score(va["next_storage_pct"], va["storage_pct"])

    _, va = S["groundwater"]
    gw_m = r2_score(va["Water_Level"], M["groundwater"].predict(va[GW_FEATURES]))
    gw_b = r2_score(va["Water_Level"], va["prev_observed_depth"])

    _, va = S["demand"]
    dm_m = r2_score(va["demand_mgd"], M["demand"].predict(va[DEMAND_FEATURES]))
    dm_b = 0.0  # predicting the mean gives R2 = 0 by definition

    labels = ["Water Shortage", "Groundwater", "Water Demand"]
    model_s = [sh_m, gw_m, dm_m]
    base_s = [sh_b, gw_b, dm_b]

    x = np.arange(len(labels))
    w = 0.36
    fig, ax = plt.subplots(figsize=_fs(10, 5.8))
    ax.bar(x - w / 2, base_s, w, label="Naive baseline", color=GREY)
    ax.bar(x + w / 2, model_s, w, label="AquaMind model", color=GREEN)
    for i, (b, m) in enumerate(zip(base_s, model_s)):
        ax.text(i - w / 2, b + 0.015, f"{b:.3f}", ha="center", fontsize=9)
        ax.text(i + w / 2, m + 0.015, f"{m:.3f}", ha="center", fontsize=_pt(9),
                fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("R² on unseen data")
    ax.set_ylim(0, 1.12)
    ax.set_title("Model vs Naive Baseline — benchmarked, not assumed",
                 fontsize=_pt(13), fontweight="bold")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    ax.text(0.5, -0.16,
            "Baseline = repeat last known value (shortage, groundwater) / predict the mean (demand).",
            transform=ax.transAxes, ha="center", fontsize=_pt(9), color="#555")
    _save(fig, "baseline_comparison.png")
    return {"shortage": [sh_b, sh_m], "groundwater": [gw_b, gw_m],
            "demand": [dm_b, dm_m]}


# --------------------------------------------------------- 4. leak: cm + roc
def chart_leak_cm_roc(S, M):
    print("[4] leak confusion matrix + ROC")
    _, va = S["leak"]
    y = va["label"].to_numpy()
    proba = M["leak"].predict_proba(va[LEAK_FEATURES])[:, 1]
    pred = (proba >= 0.30).astype(int)
    cm = confusion_matrix(y, pred)
    auc = roc_auc_score(y, proba)
    fpr, tpr, _ = roc_curve(y, proba)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=_fs(13, 5.4))
    im = a1.imshow(cm, cmap="Blues")
    a1.set_xticks([0, 1], ["Predicted\nNo-leak", "Predicted\nLeak"])
    a1.set_yticks([0, 1], ["Actual\nNo-leak", "Actual\nLeak"])
    total = cm.sum()
    for i in range(2):
        for j in range(2):
            a1.text(j, i, f"{cm[i, j]}\n({cm[i, j] / total * 100:.0f}%)",
                    ha="center", va="center", fontsize=_pt(13), fontweight="bold",
                    color="white" if cm[i, j] > cm.max() / 2 else "#12242b")
    a1.set_title(f"Confusion Matrix\naccuracy {accuracy_score(y, pred):.3f} · "
                 f"F1 {f1_score(y, pred, zero_division=0):.3f}",
                 fontsize=_pt(11), fontweight="bold")
    fig.colorbar(im, ax=a1, fraction=0.046)

    a2.plot(fpr, tpr, color=BLUE, lw=2, label=f"ExtraTrees (AUC = {auc:.3f})")
    a2.plot([0, 1], [0, 1], "--", color=GREY, lw=1.3, label="random guess (AUC = 0.5)")
    a2.set_xlabel("False positive rate")
    a2.set_ylabel("True positive rate")
    a2.set_title("ROC Curve — leak vs no-leak", fontsize=_pt(11), fontweight="bold")
    a2.grid(True, alpha=0.3)
    a2.legend(loc="lower right", fontsize=9)
    fig.suptitle("Acoustic Leak Detection — classification performance",
                 fontsize=_pt(14), fontweight="bold")
    _save(fig, "leak_confusion_roc.png")
    return float(auc)


# ------------------------------------------------------ 5. error distribution
def chart_error_distribution(S, M):
    print("[5] error distribution")
    spec = [
        ("shortage", RES_FEATURES, "next_storage_pct", "Water Shortage", "percentage points"),
        ("groundwater", GW_FEATURES, "Water_Level", "Groundwater", "metres"),
        ("demand", DEMAND_FEATURES, "demand_mgd", "Water Demand", "MGD"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=_fs(15, 4.8))
    for ax, (key, feats, target, label, unit) in zip(axes, spec):
        _, va = S[key]
        err = M[key].predict(va[feats]) - va[target].to_numpy()
        lim = float(np.percentile(np.abs(err), 99))
        ax.hist(err, bins=45, range=(-lim, lim), color=BLUE, alpha=0.85)
        ax.axvline(0, color=RED, ls="--", lw=1.5)
        within = float(np.mean(np.abs(err) <= np.percentile(np.abs(err), 90)))
        ax.set_title(f"{label}\n90% of errors within "
                     f"±{np.percentile(np.abs(err), 90):.2f} {unit}",
                     fontsize=_pt(11), fontweight="bold")
        ax.set_xlabel(f"Prediction error ({unit})")
        ax.set_ylabel("Count")
        ax.grid(True, alpha=0.3)
    fig.suptitle("AquaMind — Error Distribution (centred on zero = unbiased)",
                 fontsize=_pt(14), fontweight="bold")
    _save(fig, "error_distribution.png")


# --------------------------------------------------------------- 6. coverage
def chart_coverage_map(S):
    print("[6] groundwater coverage map")
    rows = S["gw_full"]
    lat, lon = rows["Latitude"].to_numpy(), rows["Longitude"].to_numpy()
    ok = (lat > 5) & (lat < 40) & (lon > 65) & (lon < 100)
    lat, lon = lat[ok], lon[ok]
    fig, ax = plt.subplots(figsize=_fs(8.5, 9))
    ax.scatter(lon, lat, s=2.5 if SLIDE_MODE else 1.5, alpha=0.18, color=BLUE, edgecolors="none")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(f"Groundwater Model — National Well Coverage\n"
                 f"{len(rows):,} observations across India",
                 fontsize=_pt(13), fontweight="bold")
    ax.grid(True, alpha=0.25)
    ax.set_aspect("equal", adjustable="box")
    _save(fig, "groundwater_coverage_map.png")


def main():
    print("=== AquaMind — evaluation charts ===\n")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    S = load_splits()
    M = fit_models(S)
    chart_feature_importance(M)
    chart_pred_vs_actual(S, M)
    base = chart_baseline(S, M)
    auc = chart_leak_cm_roc(S, M)
    chart_error_distribution(S, M)
    chart_coverage_map(S)
    (OUT_DIR / "evaluation_metrics.json").write_text(
        json.dumps({"baseline_vs_model_r2": base, "leak_roc_auc": auc}, indent=2),
        encoding="utf-8",
    )
    print(f"\nDone. Charts in {OUT_DIR}")


if __name__ == "__main__":
    main()
