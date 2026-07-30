"""Acoustic leak detection model trained on signal CSV recordings.

Folder structure expected:
  Leak detection training data/
    Accelerometer/ Dynamic Pressure Sensor/ Hydrophone/
      Branched/ Looped/
        No-leak/        -> label 0
        Gasket Leak/    -> label 1
        Orifice Leak/   -> label 1
        etc.

Extracts statistical + spectral features from raw signals (with windowing for
more samples), then trains a class-balanced RandomForestClassifier.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

AI_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AI_DIR.parent
LEAK_DATA_ROOT = PROJECT_DIR / "Aqua Dataset" / "Leak detection training data"
MODEL_PATH = AI_DIR / "leak_detection_model.pkl"
METADATA_PATH = AI_DIR / "leak_detection_model.metadata.json"

NO_LEAK_FOLDER = "No-leak"
SENSOR_TYPES = ["Accelerometer"]  # best-performing sensor family for this dataset
TOPOLOGIES = ["Branched", "Looped"]
LEAK_TYPES = ["No-leak", "Gasket Leak", "Orifice Leak", "Circumferential Crack", "Longitudinal Crack"]
SPLIT_SEED = 42
DECISION_THRESHOLD = 0.30
AUGMENT_NO_LEAK_COPIES = 8

FEATURES = [
    "signal_mean",
    "signal_std",
    "signal_rms",
    "signal_min",
    "signal_max",
    "signal_peak_to_peak",
    "signal_skewness",
    "signal_kurtosis",
    "zero_crossing_rate",
    "crest_factor",
    "spectral_energy",
    "spectral_peak_freq",
    "spectral_centroid",
    "spectral_low_energy",
    "spectral_mid_energy",
    "spectral_high_energy",
]


def _features_from_signal(signal: np.ndarray) -> Optional[np.ndarray]:
    if len(signal) < 100:
        return None

    mean_val = float(np.mean(signal))
    std_val = float(np.std(signal))
    rms_val = float(np.sqrt(np.mean(signal**2)))
    min_val = float(np.min(signal))
    max_val = float(np.max(signal))
    p2p_val = max_val - min_val
    crest = float(max(abs(min_val), abs(max_val)) / rms_val) if rms_val > 1e-12 else 0.0

    if std_val > 0:
        skewness = float(np.mean(((signal - mean_val) / std_val) ** 3))
        kurtosis = float(np.mean(((signal - mean_val) / std_val) ** 4))
    else:
        skewness = 0.0
        kurtosis = 0.0

    zero_crossings = int(np.sum(np.diff(np.sign(signal)) != 0))
    zcr = zero_crossings / len(signal)

    fft_vals = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(len(signal))
    power = fft_vals**2
    spectral_energy = float(np.sum(power))
    if len(fft_vals) > 0:
        peak_idx = int(np.argmax(fft_vals))
        peak_freq = float(freqs[peak_idx]) if peak_idx < len(freqs) else 0.0
        denom = float(np.sum(fft_vals)) + 1e-12
        spectral_centroid = float(np.sum(freqs * fft_vals) / denom)
    else:
        peak_freq = 0.0
        spectral_centroid = 0.0

    low_energy = float(np.sum(power[freqs < 0.1])) if np.any(freqs < 0.1) else 0.0
    mid_mask = (freqs >= 0.1) & (freqs <= 0.3)
    mid_energy = float(np.sum(power[mid_mask])) if np.any(mid_mask) else 0.0
    high_energy = float(np.sum(power[freqs > 0.3])) if np.any(freqs > 0.3) else 0.0

    return np.array(
        [
            mean_val,
            std_val,
            rms_val,
            min_val,
            max_val,
            p2p_val,
            skewness,
            kurtosis,
            zcr,
            crest,
            spectral_energy,
            peak_freq,
            spectral_centroid,
            low_energy,
            mid_energy,
            high_energy,
        ]
    )


def extract_feature_windows_from_csv(
    csv_path: Path,
    max_rows: int = 24000,
    window: int = 2500,
    stride: int = 2000,
) -> list[np.ndarray]:
    """Extract one or more feature vectors via sliding windows over the signal."""
    try:
        df = pd.read_csv(csv_path, nrows=max_rows)
        if "Value" not in df.columns:
            return []
        signal = pd.to_numeric(df["Value"], errors="coerce").dropna().to_numpy()
        if len(signal) < 100:
            return []

        feats_list: list[np.ndarray] = []
        if len(signal) <= window:
            one = _features_from_signal(signal)
            return [one] if one is not None else []

        for start in range(0, len(signal) - window + 1, stride):
            chunk = signal[start : start + window]
            feats = _features_from_signal(chunk)
            if feats is not None:
                feats_list.append(feats)
            if len(feats_list) >= 8:  # cap windows per file
                break
        return feats_list
    except Exception as e:
        print(f"  [WARN] Could not extract features from {csv_path.name}: {e}")
        return []


def collect_all_recordings() -> pd.DataFrame:
    """Walk the dataset folder tree and extract windowed features + labels."""
    records = []

    def add_file(csv_path: Path, sensor: str, topology: str, leak_type: str, label: int, group_id: str):
        print(f"  Extracting: {group_id}/{csv_path.name}")
        for idx, feats in enumerate(extract_feature_windows_from_csv(csv_path)):
            row = {
                "file": str(csv_path.relative_to(PROJECT_DIR)),
                "sensor": sensor,
                "topology": topology,
                "leak_type": leak_type,
                "label": label,
                "group_id": group_id,
                "window_id": idx,
            }
            for feat_name, feat_val in zip(FEATURES, feats):
                row[feat_name] = feat_val
            records.append(row)

    for sensor in SENSOR_TYPES:
        sensor_path = LEAK_DATA_ROOT / sensor
        if not sensor_path.exists():
            continue
        for topology in TOPOLOGIES:
            topo_path = sensor_path / topology
            if not topo_path.exists():
                continue
            for leak_type in LEAK_TYPES:
                lt_path = topo_path / leak_type
                if not lt_path.exists():
                    continue
                label = 0 if leak_type == NO_LEAK_FOLDER else 1
                group_id = f"{sensor}_{topology}_{leak_type}"
                for csv_path in sorted(lt_path.glob("*.csv")):
                    add_file(csv_path, sensor, topology, leak_type, label, group_id)

    return pd.DataFrame(records)


def _stratified_group_split(data: pd.DataFrame, seed: int = SPLIT_SEED):
    """Split by source file with both classes in train/val/test."""
    files = (
        data.groupby("file")
        .agg(label=("label", "first"), group_id=("group_id", "first"))
        .reset_index()
    )
    train_files, temp_files = train_test_split(
        files,
        test_size=0.30,
        random_state=seed,
        stratify=files["label"],
    )
    val_files, test_files = train_test_split(
        temp_files,
        test_size=0.50,
        random_state=seed,
        stratify=temp_files["label"],
    )
    train = data[data["file"].isin(set(train_files["file"]))]
    validation = data[data["file"].isin(set(val_files["file"]))]
    test = data[data["file"].isin(set(test_files["file"]))]
    return train, validation, test


def _augment_no_leak(train: pd.DataFrame, copies: int = AUGMENT_NO_LEAK_COPIES, seed: int = SPLIT_SEED) -> pd.DataFrame:
    """Light Gaussian noise on no-leak windows to balance classes."""
    rng = np.random.default_rng(seed)
    no_leak = train[train["label"] == 0]
    if len(no_leak) == 0:
        return train
    parts = [train]
    for _ in range(copies):
        noisy = no_leak.copy()
        for feat in FEATURES:
            scale = float(noisy[feat].std() or 1.0)
            noisy[feat] = noisy[feat] + rng.normal(0.0, 0.045 * scale, len(noisy))
        parts.append(noisy)
    return pd.concat(parts, ignore_index=True)


class LeakDetectionModel:
    """Binary leak/no-leak classifier trained on acoustic sensor recordings."""

    def __init__(self):
        self.payload = None

    def train(self) -> dict:
        print("[LeakDetectionModel] Collecting and extracting features from all recordings...")
        data = collect_all_recordings()
        if len(data) < 20:
            raise ValueError("Not enough recordings found for training.")

        print(
            f"[LeakDetectionModel] Windows extracted: {len(data)} "
            f"(leak={int((data['label'] == 1).sum())}, no-leak={int((data['label'] == 0).sum())})"
        )

        train, validation, test = _stratified_group_split(data, seed=SPLIT_SEED)
        train_aug = _augment_no_leak(train)
        print(
            f"[LeakDetectionModel] Train: {len(train)} (+aug {len(train_aug)}), "
            f"Val: {len(validation)}, Test: {len(test)}"
        )

        model = ExtraTreesClassifier(
            n_estimators=700,
            min_samples_leaf=1,
            class_weight="balanced_subsample",
            random_state=SPLIT_SEED,
            n_jobs=-1,
        )
        model.fit(train_aug[FEATURES], train_aug["label"])

        def cls_metrics(frame: pd.DataFrame, threshold: float = DECISION_THRESHOLD) -> dict:
            if len(frame) == 0:
                return {
                    "precision": None,
                    "recall": None,
                    "f1": None,
                    "accuracy": None,
                    "confusion_matrix": None,
                    "rows": 0,
                }
            proba = model.predict_proba(frame[FEATURES])[:, 1]
            preds = (proba >= threshold).astype(int)
            cm = confusion_matrix(frame["label"], preds, labels=[0, 1]).tolist()
            return {
                "precision": round(float(precision_score(frame["label"], preds, zero_division=0)), 4),
                "recall": round(float(recall_score(frame["label"], preds, zero_division=0)), 4),
                "f1": round(float(f1_score(frame["label"], preds, zero_division=0)), 4),
                "accuracy": round(float(accuracy_score(frame["label"], preds)), 4),
                "confusion_matrix": cm,
                "rows": int(len(frame)),
            }

        metadata = {
            "model_type": "ExtraTreesClassifier",
            "task": "binary acoustic leak / no-leak detection",
            "source": "Aqua Dataset/Leak detection training data",
            "sensors": SENSOR_TYPES,
            "topologies": TOPOLOGIES,
            "leak_types": [lt for lt in LEAK_TYPES if lt != NO_LEAK_FOLDER],
            "features": FEATURES,
            "target": "label (0=No-leak, 1=Leak)",
            "decision_threshold": DECISION_THRESHOLD,
            "split_method": "stratified file-level split + no-leak noise augmentation",
            "split_seed": SPLIT_SEED,
            "metrics": {
                "validation": cls_metrics(validation),
                "test": cls_metrics(test),
            },
            "limitations": [
                "Trained on accelerometer lab recordings (branched and looped topologies).",
                "No water-loss volume in training labels; volumetric estimates are not supported.",
            ],
        }

        joblib.dump(
            {
                "model": model,
                "features": FEATURES,
                "metadata": metadata,
                "decision_threshold": DECISION_THRESHOLD,
            },
            MODEL_PATH,
        )
        METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print("[LeakDetectionModel] Training complete. Metrics:")
        print(json.dumps(metadata["metrics"], indent=2))
        return metadata

    def load_model(self) -> dict:
        if not MODEL_PATH.exists():
            return {"model": None, "features": FEATURES, "metadata": self.train()}
        payload = joblib.load(MODEL_PATH)
        if not isinstance(payload, dict) or "model" not in payload:
            return {"model": None, "features": FEATURES, "metadata": self.train()}
        if payload.get("features") != FEATURES:
            return {"model": None, "features": FEATURES, "metadata": self.train()}
        return payload

    def predict_from_features(self, feature_vector: np.ndarray) -> dict:
        payload = self.load_model()
        model = payload["model"]
        if model is None:
            return {"is_leak": False, "probability": 0.5, "label": "Model unavailable"}

        feats_df = pd.DataFrame([feature_vector], columns=FEATURES)
        prob = float(model.predict_proba(feats_df)[0][1])
        threshold = float(payload.get("decision_threshold", DECISION_THRESHOLD))
        is_leak = prob >= threshold

        if prob >= 0.8:
            severity = "High anomaly detected"
        elif prob >= threshold:
            severity = "Moderate anomaly detected"
        else:
            severity = "No anomaly detected"

        test_f1 = payload["metadata"]["metrics"]["test"]["f1"]
        test_acc = payload["metadata"]["metrics"]["test"].get("accuracy")
        return {
            "is_leak_detected": bool(is_leak),
            "leak_probability": round(prob, 4),
            "severity": severity,
            "model_scope": "acoustic leak signal classifier",
            "test_f1": round(test_f1, 4) if test_f1 is not None else None,
            "test_accuracy": test_acc,
            "note": "Classification only — no volumetric water-loss estimate from this model.",
        }

    def predict_from_csv(
        self,
        signal_values: list[float],
        max_rows: int = 24000,
        window: int = 2500,
        stride: int = 2000,
    ) -> dict:
        """Classify a raw signal using the same windowing as training.

        Full-file stats/FFT (e.g. 900k samples) do not match the 2500-sample
        windows the ExtraTrees model saw — that mismatch caused no-leak CSVs
        to score as leaks. Cap + window + average window probabilities.
        """
        signal = np.asarray(signal_values, dtype=float)
        if len(signal) > max_rows:
            signal = signal[:max_rows]
        if len(signal) < 100:
            raise ValueError("Signal too short; need at least 100 samples.")

        windows: list[np.ndarray] = []
        if len(signal) <= window:
            one = _features_from_signal(signal)
            if one is None:
                raise ValueError("Signal too short; need at least 100 samples.")
            windows = [one]
        else:
            for start in range(0, len(signal) - window + 1, stride):
                feats = _features_from_signal(signal[start : start + window])
                if feats is not None:
                    windows.append(feats)
                if len(windows) >= 8:
                    break

        if not windows:
            raise ValueError("Could not extract features from signal.")

        payload = self.load_model()
        model = payload["model"]
        if model is None:
            return {
                "is_leak_detected": False,
                "leak_probability": 0.5,
                "severity": "Model unavailable",
                "model_scope": "acoustic leak signal classifier",
                "test_f1": None,
                "note": "Model unavailable",
            }

        feats_df = pd.DataFrame(windows, columns=FEATURES)
        probs = model.predict_proba(feats_df)[:, 1]
        # Mean over windows (stable); median resists a single noisy chunk.
        prob = float(np.mean(probs))
        threshold = float(payload.get("decision_threshold", DECISION_THRESHOLD))
        is_leak = prob >= threshold

        if prob >= 0.8:
            severity = "High anomaly detected"
        elif prob >= threshold:
            severity = "Moderate anomaly detected"
        else:
            severity = "No anomaly detected"

        test_f1 = payload["metadata"]["metrics"]["test"]["f1"]
        test_acc = payload["metadata"]["metrics"]["test"].get("accuracy")
        return {
            "is_leak_detected": bool(is_leak),
            "leak_probability": round(prob, 4),
            "severity": severity,
            "model_scope": "acoustic leak signal classifier",
            "test_f1": round(test_f1, 4) if test_f1 is not None else None,
            "test_accuracy": test_acc,
            "windows_scored": int(len(windows)),
            "note": (
                "Classification only — no volumetric water-loss estimate from this model. "
                f"Scored {len(windows)} window(s) matching training (<={max_rows} samples)."
            ),
        }

    def predict(self, input_features: dict) -> dict:
        payload = self.load_model()
        model = payload["model"]
        if model is None:
            return {
                "is_leak_detected": False,
                "leak_probability": 0.5,
                "severity": "Model unavailable — run py ai/train.py",
                "note": "Model unavailable",
            }
        return {
            "is_leak_detected": False,
            "leak_probability": 0.0,
            "severity": "Use /detect-leak-signal with a raw signal CSV upload",
            "note": "Upload a signal CSV to /detect-leak-signal for classification.",
        }


if __name__ == "__main__":
    m = LeakDetectionModel()
    m.train()
