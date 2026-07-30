"""Model persistence interfaces — backend chosen later (joblib / MLflow / cloud)."""
from fastapi_app.prediction.framework.persistence.store import ModelPersistence

__all__ = ["ModelPersistence"]
