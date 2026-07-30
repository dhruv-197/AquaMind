"""Framework schemas: universal prediction output and training config."""
from fastapi_app.prediction.framework.schemas.config import TrainingConfiguration
from fastapi_app.prediction.framework.schemas.output import UniversalPredictionOutput

__all__ = ["UniversalPredictionOutput", "TrainingConfiguration"]
