"""Abstract model lifecycle — train / predict / evaluate / persist."""
from fastapi_app.prediction.framework.lifecycle.predictor import BaseModelPredictor

__all__ = ["BaseModelPredictor"]
