"""Water Stress Intelligence package (fusion layer — not an ML model)."""
from fastapi_app.prediction.models.water_stress.service import WaterStressIntelligenceService

MODULE_KEY = "water_stress_intelligence"
MODULE_VERSION = "1.0.0"

__all__ = ["WaterStressIntelligenceService", "MODULE_KEY", "MODULE_VERSION"]
