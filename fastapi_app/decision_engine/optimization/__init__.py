"""AI Decision Optimization Engine package."""
from fastapi_app.decision_engine.optimization.engine import DecisionOptimizationEngine
from fastapi_app.decision_engine.optimization.service import DecisionOptimizationService

MODULE_KEY = "decision_optimization"
MODULE_VERSION = "1.0.0"

__all__ = [
    "DecisionOptimizationEngine",
    "DecisionOptimizationService",
    "MODULE_KEY",
    "MODULE_VERSION",
]
