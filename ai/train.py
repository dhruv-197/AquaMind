"""Train AquaMind dataset-backed models.

Run from the project root with ``py ai\\train.py``.

Trains:
  1. Reservoir shortage model (CWC March 2024 daily data)
  2. Groundwater model (CGWB 2000–2024 wells dataset)
  3. Acoustic leak detection model (lab signal recordings)
  4. Water demand model (synthetic municipal labels, R² ≥ 0.80 gate)
"""
from __future__ import annotations

import json
from water_shortage_model import WaterShortageModel
from groundwater_model import GroundwaterModel
from leak_detection_model import LeakDetectionModel
from water_demand_model import WaterDemandModel
from inspect_datasets import main as inspect_datasets


def train_all_models() -> dict:
    inspect_datasets()
    results = {}

    print("\n=== [1/4] Training Reservoir Shortage Model ===")
    reservoir_meta = WaterShortageModel().train()
    results["reservoir"] = reservoir_meta["metrics"]
    print(json.dumps(reservoir_meta["metrics"], indent=2))

    print("\n=== [2/4] Training Groundwater Level Model ===")
    gw_meta = GroundwaterModel().train()
    results["groundwater"] = gw_meta["metrics"]
    print(json.dumps(gw_meta["metrics"], indent=2))

    print("\n=== [3/4] Training Acoustic Leak Detection Model ===")
    leak_meta = LeakDetectionModel().train()
    results["leak_detection"] = leak_meta["metrics"]
    print(json.dumps(leak_meta["metrics"], indent=2))

    print("\n=== [4/4] Training Water Demand Model (CWC drawdown + weather) ===")
    demand_meta = WaterDemandModel().train()
    results["demand"] = demand_meta["metrics"]
    print(json.dumps(demand_meta["metrics"], indent=2))

    print("\nAquaMind PILOT training complete (4 models).")
    return results


if __name__ == "__main__":
    train_all_models()
