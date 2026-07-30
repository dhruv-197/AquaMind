# Reservoir Level Forecast

Production XGBoost model plugged into the AquaMind Prediction Framework.

**Does not modify** `fastapi_app/prediction/framework/*`.

Sibling of [Water Demand Forecast](../water_demand/MODEL.md).

---

## Architecture flow

```
CSV / Parquet / DataFrame (multi-reservoir)
        │
        ▼
ReservoirDatasetLoader (validate + clean)
        │
        ▼
ReservoirFeaturePipeline (extract → windows → missing → normalize → validate)
        │
        ▼
XGBoostReservoirRegressor  ←── swappable ReservoirRegressorBackend
        │
        ▼
ReservoirLevelForecastModel (BaseModelPredictor)
        │
        ├── UniversalPredictionOutput
        └── ModelRegistry["reservoir_forecast"]
                │
                ▼
        /api/v1/predictions/reservoir/*
                │
                ├── Decision Engine recommendations
                ▼
        Reservoir Forecast Workspace (/reservoir-forecast)
```

Dependency injection:

- Routers resolve the model only via `ModelRegistryDep` → `ReservoirLevelForecastService`
- Regressor, persistence, and logger are constructor-injected
- Horizon conversion reuses `water_demand.horizon`

---

## Dataset format

Required columns:

| Column | Type | Description |
|--------|------|-------------|
| `date` | ISO date | Daily timestamp |
| `storage_pct` | float | Observed reservoir storage (%) |

Optional columns (ignored if absent):

| Column | Description |
|--------|-------------|
| `reservoir_id` / `reservoir_name` | Multi-reservoir identity |
| `inflow_mcm` / `outflow_mcm` | Hydrologic balance |
| `rainfall_mm` / `catchment_rainfall_mm` | Precipitation |
| `temperature_c` / `evaporation_mm` | Climate drivers |
| `capacity_mcm` | Reservoir capacity |
| `dam_release_mcm` | Release history |
| `groundwater_recharge_mcm` | Recharge contribution |
| `season` / `month` | Calendar seasonality |
| `location_lat` / `location_lng` | Map coordinates |

Sample data: `data/reservoir/sample_reservoir.csv` (Reservoir A / B / C).

---

## Training process

1. Load dataset (`use_sample=true` or `dataset_path`).
2. Validate dates, per-reservoir duplicates, missing storage, outliers.
3. Fit feature pipeline (lags, rolling means, net inflow, season, reservoir code).
4. Time-based train / validation split.
5. Fit `XGBRegressor`.
6. Compute MAE, RMSE, MAPE, R² on validation fold.
7. Persist artifact via joblib (`data/reservoir/artifacts/`).

### Train API

```http
POST /api/v1/predictions/reservoir/train
Content-Type: application/json

{
  "use_sample": true,
  "validation_split": 0.2,
  "random_seed": 42,
  "model_version": "1.0.0"
}
```

---

## Prediction

Supports the same forecast horizon component as Demand Forecast:

- Tomorrow / custom days / weeks / months / years
- Recursive daily forecast aggregated to exact period count
- Optional `reservoir_id` selects which reservoir history to recurse on

### Predict API

```http
POST /api/v1/predictions/reservoir/predict
Content-Type: application/json

{
  "value": 30,
  "unit": "days",
  "reservoir_id": "RES-A",
  "include_history_days": 365
}
```

### Output (`UniversalPredictionOutput`)

| Field | Description |
|-------|-------------|
| `forecasted_storage_pct` | Forecasted reservoir % |
| `forecasted_storage_mcm` | Forecasted storage (MCM) |
| `remaining_usable_storage_mcm` | Volume above critical (20%) |
| `confidence_score` | Model confidence |
| `risk_level` | Critical / High / Moderate / Healthy(low) |
| `prediction_horizon` | Horizon in days |
| `model_version` | Artifact version |
| `generated_at` | Timestamp |

---

## Risk levels

| Band | Storage % | RiskLevel |
|------|-----------|-----------|
| Critical | &lt; 20% | `critical` |
| High | 20–40% | `high` |
| Moderate | 40–60% | `moderate` |
| Healthy | &gt; 60% | `low` |

---

## Decision Engine

`recommendations.py` builds executive actions from prediction outputs and maps into `RulesDecisionEngine` templates (reduce release, increase groundwater, activate secondary reservoir, conservation advisory).

---

## Dashboard

Route: `/reservoir-forecast`

Includes:

- Interactive multi-reservoir map (selection updates forecast / KPIs / chart / insights)
- Horizon controls (shared Demand Forecast component)
- Large historical vs forecast chart with CI, capacity line, critical threshold, safe zone
- KPI cards, forecast summary, AI insights, model health, evaluation metrics
- CSV / PNG export

---

## Status & metrics

```http
GET /api/v1/predictions/reservoir/status
GET /api/v1/predictions/reservoir/metrics
```

Status includes the reservoir catalog (`reservoirs[]`) for map rendering.
