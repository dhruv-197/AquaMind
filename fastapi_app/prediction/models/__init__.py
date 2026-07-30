"""Water Demand Forecast — first production model plugged into the ML framework."""
from fastapi_app.prediction.models.water_demand.factory import build_water_demand_model
from fastapi_app.prediction.models.water_demand.model import WaterDemandForecastModel

__all__ = ["WaterDemandForecastModel", "build_water_demand_model"]
