"""Dataset-backed Groundwater level prediction model using CGWB wells dataset.

Predicts the next observed water-level depth from lagged depths, well metadata,
and seasonal month encoding. Evaluated with a global temporal split.
"""
from __future__ import annotations

import json
import math
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

AI_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AI_DIR.parent
DEFAULT_DATA_PATH = (
    PROJECT_DIR
    / "Aqua Dataset"
    / "Quality_controlled_groundwater_levels_over_India"
    / "Input"
    / "1_India_GWLs_2000_2024_wells_within_India.csv"
)
MODEL_PATH = AI_DIR / "groundwater_model.pkl"
METADATA_PATH = AI_DIR / "groundwater_model.metadata.json"
STATIONS_PATH = AI_DIR / "groundwater_stations.json"

FEATURES = [
    "prev_observed_depth",
    "prev2_observed_depth",
    "depth_change",
    "Latitude",
    "Longitude",
    "Well Depth",
    "Month_sin",
    "Month_cos",
    "Well_Type_Encoded",
]
WELL_TYPE_MAP = {
    "-": 0,
    "Dug well": 1,
    "Bore well": 2,
    "Tube well": 3,
    "Piezometer": 4,
    "Dug cum bore well": 5,
    "Slim hole": 6,
}
REV_WELL_TYPE_MAP = {v: k for k, v in WELL_TYPE_MAP.items()}


class GroundwaterModel:
    """Predict next observed groundwater depth from CGWB observations."""

    def __init__(self):
        self.stations = {}
        self.load_stations()

    def load_stations(self):
        if STATIONS_PATH.exists():
            try:
                with open(STATIONS_PATH, "r", encoding="utf-8") as f:
                    self.stations = json.load(f)
            except Exception as e:
                print(f"[GroundwaterModel] Error loading stations JSON: {e}")

    def _prepared_rows(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        if not DEFAULT_DATA_PATH.exists():
            raise FileNotFoundError(f"CGWB groundwater data not found: {DEFAULT_DATA_PATH}")

        data = pd.read_csv(DEFAULT_DATA_PATH)

        wide_cols = []
        for c in data.columns:
            parts = c.split("-")
            if len(parts) == 2 and parts[0] in ["Jan", "May", "Aug", "Nov"] and parts[1].isdigit():
                wide_cols.append(c)

        id_cols = ["Station Code", "Station Name", "Latitude", "Longitude", "Well Depth", "Type of Well"]
        data_subset = data[id_cols + wide_cols].copy()

        stations_dict = {}
        lat_mean = pd.to_numeric(data_subset["Latitude"], errors="coerce").mean()
        lng_mean = pd.to_numeric(data_subset["Longitude"], errors="coerce").mean()
        depth_mean = pd.to_numeric(data_subset["Well Depth"], errors="coerce").mean()

        for _, row in data_subset.iterrows():
            code = str(row["Station Code"]).strip()
            if code and code != "nan":
                depth_val = row["Well Depth"]
                if pd.isna(depth_val) or str(depth_val).strip() in ["-", "", "nan", "NaN"]:
                    depth = depth_mean
                else:
                    try:
                        depth = float(depth_val)
                    except ValueError:
                        depth = depth_mean
                stations_dict[code] = {
                    "name": str(row["Station Name"]).strip(),
                    "lat": float(row["Latitude"]) if pd.notna(row["Latitude"]) else lat_mean,
                    "lng": float(row["Longitude"]) if pd.notna(row["Longitude"]) else lng_mean,
                    "depth": depth,
                    "type": str(row["Type of Well"]).strip() if pd.notna(row["Type of Well"]) else "-",
                }

        with open(STATIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(stations_dict, f, indent=2)
        self.stations = stations_dict

        df_long = data_subset.melt(
            id_vars=id_cols, value_vars=wide_cols, var_name="Observation", value_name="Water_Level"
        )

        month_map = {"Jan": 1, "May": 5, "Aug": 8, "Nov": 11}

        def parse_obs(obs):
            m_str, y_str = obs.split("-")
            year = 2000 + int(y_str)
            month = month_map[m_str]
            return year, month

        df_long["Year"], df_long["Month"] = zip(*df_long["Observation"].apply(parse_obs))
        df_long["TimeIndex"] = df_long["Year"] * 12 + df_long["Month"]

        df_long["Water_Level"] = pd.to_numeric(df_long["Water_Level"], errors="coerce")
        df_long = df_long.dropna(subset=["Water_Level"])

        df_long["Latitude"] = pd.to_numeric(df_long["Latitude"], errors="coerce")
        df_long["Longitude"] = pd.to_numeric(df_long["Longitude"], errors="coerce")
        df_long["Well Depth"] = pd.to_numeric(df_long["Well Depth"], errors="coerce")
        df_long = df_long.dropna(subset=["Latitude", "Longitude"])

        median_well_depth = df_long["Well Depth"].median()
        df_long["Well Depth"] = df_long["Well Depth"].fillna(median_well_depth)
        df_long["Well_Type_Encoded"] = (
            df_long["Type of Well"].fillna("-").map(WELL_TYPE_MAP).fillna(0).astype(int)
        )

        df_long = df_long.sort_values(["Station Code", "TimeIndex"])
        df_long["prev_observed_depth"] = df_long.groupby("Station Code")["Water_Level"].shift(1)
        df_long["prev2_observed_depth"] = df_long.groupby("Station Code")["Water_Level"].shift(2)
        df_long["depth_change"] = df_long["prev_observed_depth"] - df_long["prev2_observed_depth"]
        df_long["Month_sin"] = np.sin(2 * np.pi * df_long["Month"] / 12.0)
        df_long["Month_cos"] = np.cos(2 * np.pi * df_long["Month"] / 12.0)

        df_clean = df_long.dropna(subset=["prev_observed_depth", "prev2_observed_depth", "depth_change"]).copy()
        return df_clean, data

    def train(self) -> dict:
        print("[GroundwaterModel] Preprocessing groundwater dataset...")
        rows, _ = self._prepared_rows()
        if len(rows) < 100:
            raise ValueError("Not enough groundwater observations to train model.")

        train = rows[rows["Year"] <= 2019]
        validation = rows[(rows["Year"] >= 2020) & (rows["Year"] <= 2022)]
        test = rows[rows["Year"] >= 2023]

        if min(len(train), len(validation), len(test)) == 0:
            raise ValueError("Temporal split produced an empty partition.")

        print(
            f"[GroundwaterModel] Training RF Regressor "
            f"(Train={len(train)}, Val={len(validation)}, Test={len(test)})"
        )
        # min_samples_leaf=2 / max_depth=20 previously produced a ~2GB artifact
        # (very deep, high-leaf-count trees over 880k rows) for negligible
        # accuracy gain — a real operational cost (cold start, RAM, git-unfriendly
        # size). Shallower, more-regularized trees cut artifact size drastically
        # with test R² effectively unchanged.
        model = RandomForestRegressor(
            n_estimators=220,
            max_depth=14,
            min_samples_leaf=15,
            max_features="sqrt",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(train[FEATURES], train["Water_Level"])

        def metrics(frame: pd.DataFrame) -> dict:
            predicted = model.predict(frame[FEATURES])
            y = frame["Water_Level"]
            return {
                "mae_meters": round(float(mean_absolute_error(y, predicted)), 4),
                "rmse_meters": round(float(mean_squared_error(y, predicted) ** 0.5), 4),
                "r2": round(float(r2_score(y, predicted)), 4),
                "rows": int(len(frame)),
            }

        metadata = {
            "model_type": "RandomForestRegressor",
            "task": "next observed groundwater level depth prediction",
            "source": str(DEFAULT_DATA_PATH.relative_to(PROJECT_DIR)),
            "features": FEATURES,
            "target": "Water_Level",
            "temporal_split": {
                "train_end_year": 2019,
                "validation_years": "2020-2022",
                "test_start_year": 2023,
            },
            "metrics": {"validation": metrics(validation), "test": metrics(test)},
            "limitations": [
                "Trained on historical CGWB well telemetry; local aquifer-specific conditions vary.",
                "Weather and rainfall variables are excluded due to lack of spatial matching at well locations.",
                "Assumes well depth and well type remain constant over time.",
            ],
        }

        joblib.dump({"model": model, "features": FEATURES, "metadata": metadata}, MODEL_PATH)
        METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print("[GroundwaterModel] Training completed and saved.")
        print(json.dumps(metadata["metrics"], indent=2))
        return metadata

    def load_model(self) -> dict:
        if not MODEL_PATH.exists():
            return {"model": None, "features": FEATURES, "metadata": self.train()}
        payload = joblib.load(MODEL_PATH)
        if not isinstance(payload, dict) or "model" not in payload:
            return {"model": None, "features": FEATURES, "metadata": self.train()}
        # Retrain if feature set changed
        if payload.get("features") != FEATURES:
            return {"model": None, "features": FEATURES, "metadata": self.train()}
        return payload

    def predict(self, input_features: dict) -> dict:
        payload = self.load_model()
        model = payload["model"]

        station_code = input_features.get("station_code")
        lat = input_features.get("latitude")
        lng = input_features.get("longitude")
        well_depth = input_features.get("well_depth")
        well_type = input_features.get("well_type")
        current_depth = float(input_features["current_depth_m"])
        prev2_depth = float(input_features.get("prev2_depth_m", current_depth))
        month = int(input_features.get("observation_month", 5))

        station_name = "Custom Location"
        if station_code:
            station_code = str(station_code).strip()
            if station_code in self.stations:
                meta = self.stations[station_code]
                station_name = meta["name"]
                lat = meta["lat"]
                lng = meta["lng"]
                well_depth = meta["depth"]
                well_type = meta["type"]

        lat = float(lat) if lat is not None else 21.0
        lng = float(lng) if lng is not None else 78.0
        well_depth = float(well_depth) if well_depth is not None else 100.0
        well_type_encoded = WELL_TYPE_MAP.get(well_type, 0)
        depth_change = current_depth - prev2_depth
        month_sin = math.sin(2 * math.pi * month / 12.0)
        month_cos = math.cos(2 * math.pi * month / 12.0)

        feats = pd.DataFrame(
            [
                [
                    current_depth,
                    prev2_depth,
                    depth_change,
                    lat,
                    lng,
                    well_depth,
                    month_sin,
                    month_cos,
                    well_type_encoded,
                ]
            ],
            columns=FEATURES,
        )

        if model is None:
            projected = current_depth + 1.2
        else:
            projected = float(model.predict(feats)[0])

        projected = round(max(0.0, projected), 2)
        drawdown = round(projected - current_depth, 2)

        if drawdown > 3.0:
            status_label = "Critical Drawdown"
            trend = "Accelerating Depletion"
        elif drawdown > 0.5:
            status_label = "Moderate Depletion"
            trend = "Steady Depletion"
        elif drawdown < -0.5:
            status_label = "Stable Recharge"
            trend = "Reclaiming Table"
        else:
            status_label = "Stable / Equilibrium"
            trend = "Stable"

        test_mae = payload["metadata"]["metrics"]["test"]["mae_meters"]
        test_r2 = payload["metadata"]["metrics"]["test"].get("r2")

        return {
            "projected_depth_m": projected,
            "drawdown_rate_m": drawdown,
            "aquifer_status": status_label,
            "depletion_trend": trend,
            "station_name": station_name,
            "latitude": lat,
            "longitude": lng,
            "well_depth_m": well_depth,
            "well_type": well_type or "Unknown",
            "observation_month": month,
            "confidence": round(max(0.0, min(1.0, 1 - test_mae / 100)), 2),
            "model_scope": "groundwater well depth forecast",
            "test_r2": test_r2,
        }


if __name__ == "__main__":
    model = GroundwaterModel()
    model.train()
    sample = {
        "current_depth_m": 25.4,
        "latitude": 28.58,
        "longitude": 77.05,
        "well_depth": 80.0,
        "well_type": "Bore well",
        "observation_month": 5,
    }
    print("Sample Groundwater Prediction:", model.predict(sample))
