"""Smoke-test inference for the four AquaMind sklearn models.

Run: py ai/predict.py
Requires trained .pkl files from `py ai/train.py`.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.append(os.path.dirname(__file__))

from water_shortage_model import WaterShortageModel
from groundwater_model import GroundwaterModel
from water_demand_model import WaterDemandModel
from leak_detection_model import LeakDetectionModel


def run_sample_predictions():
    print("=" * 70)
    print("  AquaMind AI - Inference Engine Execution Test")
    print("=" * 70)

    print("\n1. [MODEL: Water Shortage — RandomForest next-day storage]")
    shortage_model = WaterShortageModel()
    shortage_sample = {
        "reservoir_capacity_pct": 34.2,
        "rainfall_deficit_pct": -42.5,
        "temperature_c": 38.5,
        "daily_demand_mgd": 88.0,
    }
    shortage_pred = shortage_model.predict(shortage_sample)
    print("Input:", json.dumps(shortage_sample, indent=2))
    print("Output:", json.dumps(shortage_pred, indent=2))

    print("\n2. [MODEL: Groundwater — CGWB RandomForest well depth]")
    groundwater_model = GroundwaterModel()
    groundwater_sample = {
        "current_depth_m": 24.8,
        "prev2_depth_m": 24.2,
        "latitude": 28.6,
        "longitude": 77.2,
        "well_depth": 65.0,
        "observation_month": 5,
        "station_code": "DEMO",
    }
    groundwater_pred = groundwater_model.predict(groundwater_sample)
    print("Input:", json.dumps(groundwater_sample, indent=2))
    print("Output:", json.dumps(groundwater_pred, indent=2))

    print("\n3. [MODEL: Water Demand — RandomForest (synthetic labels)]")
    demand_model = WaterDemandModel()
    demand_sample = {
        "population_thousands": 1850.0,
        "temperature_c": 40.2,
        "industrial_activity_idx": 92.0,
        "is_weekend": 0,
        "is_heatwave": 1,
    }
    demand_pred = demand_model.predict(demand_sample)
    print("Input:", json.dumps(demand_sample, indent=2))
    print("Output:", json.dumps(demand_pred, indent=2))

    print("\n4. [MODEL: Leak Detection — ExtraTrees acoustic classifier]")
    leak_model = LeakDetectionModel()
    # Dict path is legacy; trained path expects CSV signal via predict_from_csv.
    leak_sample = {
        "pressure_bar": 1.6,
        "pressure_drop_bar": 2.8,
        "acoustic_vibration_db": 88.2,
        "flow_velocity_m_s": 4.1,
        "frequency_spike_hz": 2800.0,
    }
    leak_pred = leak_model.predict(leak_sample)
    print("Input (legacy dict — upload CSV for real ExtraTrees):", json.dumps(leak_sample, indent=2))
    print("Output:", json.dumps(leak_pred, indent=2))

    print("\n" + "=" * 70)
    print("  Inference smoke test finished")
    print("=" * 70)


if __name__ == "__main__":
    run_sample_predictions()
