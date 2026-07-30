"""Water Demand Forecast model package (XGBoost)."""
from fastapi_app.prediction.models.water_demand.factory import build_water_demand_model
from fastapi_app.prediction.models.water_demand.model import WaterDemandForecastModel

MODEL_KEY = "water_demand"
MODEL_VERSION = "1.0.0"

__all__ = ["WaterDemandForecastModel", "build_water_demand_model", "MODEL_KEY", "MODEL_VERSION"]
