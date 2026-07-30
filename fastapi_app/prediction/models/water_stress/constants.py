"""Constants for the Water Stress Intelligence fusion layer."""
from __future__ import annotations

from pathlib import Path

MODULE_KEY = "water_stress_intelligence"
MODULE_VERSION = "1.0.0"

# Fusion weights (must sum ≈ 1.0). Demand + reservoir dominate; placeholders fill the rest.
FUSION_WEIGHTS: dict[str, float] = {
    "demand": 0.28,
    "reservoir": 0.28,
    "rainfall": 0.14,
    "groundwater": 0.12,
    "population": 0.10,
    "historical": 0.08,
}

SAMPLE_REGIONS_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "water_stress" / "sample_regions.json"
)
