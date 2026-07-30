"""Constants for the AI Decision Optimization Engine."""
from __future__ import annotations

MODULE_KEY = "decision_optimization"
MODULE_VERSION = "1.0.0"

# Ranking weights (must sum ≈ 1.0)
RANK_WEIGHTS: dict[str, float] = {
    "impact": 0.28,
    "risk_reduction": 0.26,
    "population_benefit": 0.20,
    "water_saved": 0.16,
    "cost_efficiency": 0.10,  # higher score = lower relative cost
}

# Rough unit economics for benefit estimates (pilot planning, not accounting)
WATER_VALUE_INR_PER_MCM = 850_000.0
ELECTRICITY_INR_PER_MWH = 6_500.0
