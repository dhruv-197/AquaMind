# Water Demand Forecast

Production XGBoost model plugged into the AquaMind Prediction Framework.

**Does not modify** `fastapi_app/prediction/framework/*`.

---

## Architecture flow

```
CSV / Parquet / DataFrame
        │
        ▼
DemandDatasetLoader (validate + clean)
        │
        ▼
DemandFeaturePipeline (extract → windows → missing → normalize → validate)
        │
        ▼
XGBoostDemandRegressor  ←── swappable DemandRegressorBackend
        │
        ▼
WaterDemandForecastModel (BaseModelPredictor)
        │
        ├── UniversalPredictionOutput
        └── ModelRegistry["water_demand"]
                │
                ▼
        /api/v1/predictions/demand/*
                │
                ▼
        Demand Forecast Dashboard (Recharts)
```

Dependency injection:

- Routers resolve the model only via `ModelRegistryDep` → `WaterDemandForecastService`
- Regressor, persistence, and logger are constructor-injected

---

## Training process

1. Load dataset (`use_sample=true` or `dataset_path`).
2. Validate dates, duplicates, missing demand, outliers.
3. Fit feature pipeline (lags, rolling means, climate, calendar flags).
4. Time-based train / validation split.
5. Fit `XGBRegressor`.
6. Compute MAE, RMSE, MAPE, R² on validation fold.
7. Persist artifact via joblib (`data/water_demand/artifacts/`).

### Train API

```http
POST /api/v1/predictions/demand/train
Content-Type: application/json

{
  "use_sample": true,
  "validation_split": 0.2,
  "random_seed": 42,
  "model_version": "1.0.0",
  "capacity_mgd": 160
}
```

---

## Dataset format

Required columns:

| Column | Type | Description |
|--------|------|-------------|
| `date` | ISO date | Daily timestamp |
| `demand_mgd` | float | Observed demand (MGD) |

Optional columns (ignored if absent):

`temperature_c`, `humidity_pct`, `rainfall_mm`, `day_of_week`, `month`,
`is_public_holiday`, `is_festival`, `population_thousands`, `season`,
`reservoir_storage_pct`, `groundwater_level_m`

Sample file: `data/water_demand/sample_demand.csv` (generated on first train).

Supports **CSV**, **Parquet**, and in-memory **DataFrame**.

---

## Feature list

Engineered candidates (only available columns are used):

- Climate: temperature, humidity, rainfall
- Calendar: day_of_week, month, public holiday, festival, season_code
- Drivers: population, reservoir storage %, groundwater level
- History: demand_lag_1, demand_lag_7, roll_mean_7/30, roll_std_7, consumption_trend_7

---

## Forecast horizons

- Tomorrow (1 day)
- 7 days
- 15 days
- 30 days

Recursive multi-step forecasting using lag features.

---

## Risk rules

| Utilization vs capacity | Risk |
|-------------------------|------|
| > 95% | HIGH |
| 80–95% | MEDIUM (`RiskLevel.MODERATE`) |
| < 80% | LOW |

---

## API usage

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/predictions/demand/train` | Train / retrain |
| POST | `/api/v1/predictions/demand/predict` | Forecast (+ Recharts series) |
| GET | `/api/v1/predictions/demand/status` | Trained? version? last trained? |
| GET | `/api/v1/predictions/demand/metrics` | MAE / RMSE / MAPE / R² |

### Predict (workspace)

```http
POST /api/v1/predictions/demand/predict

{
  "value": 30,
  "unit": "days"
}
```

Units: `days` | `weeks` | `months` | `years`  
Limits: 365 days · 52 weeks · 24 months · 5 years

Response includes `series` (historical + forecast + CI), `summary`, `insights`, and `model`.

---

## Replacing XGBoost later

Implement `DemandRegressorBackend` and inject into `WaterDemandForecastModel(regressor=...)`.
Do not change the framework or the HTTP contracts.
