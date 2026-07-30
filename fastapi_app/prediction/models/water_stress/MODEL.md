# Water Stress Intelligence

Central fusion layer for AquaMind — **not** an independent ML model.

**Does not modify** `fastapi_app/prediction/framework/*`.  
**Does not duplicate** Demand or Reservoir forecasting logic.

---

## Architecture

```
WaterDemandForecastService ──┐
                             ├──► WaterStressIntelligenceService ──► WSI (0–100)
ReservoirLevelForecastService┘              │
Weather / GW / Rainfall / Population        │
Historical stress (placeholders) ───────────┘
                                            │
                                            ▼
                              Decision Engine recommendations
                                            │
                                            ▼
                         Water Stress Intelligence Workspace
```

Registry usage:

- Resolves upstream models via `ModelRegistryDep` (`water_demand`, `reservoir_forecast`)
- Leaves framework placeholder key `water_stress` untrained (no lifecycle ML)

---

## Data flow

1. Load regional GIS sample (ward / district / zone / municipality).
2. Call Demand + Reservoir `predict()` for the horizon (cached by reservoir id).
3. Build placeholder weather, groundwater, rainfall, population, historical priors.
4. Apply optional scenario deltas (rainfall, population, demand, temperature, reservoir).
5. Weighted fusion → Water Stress Index + risk band + confidence.
6. Generate recommendations, executive insights, chart series, map payload.

### Fusion weights (default)

| Component | Weight |
|-----------|--------|
| Demand forecast | 0.28 |
| Reservoir forecast | 0.28 |
| Rainfall | 0.14 |
| Groundwater | 0.12 |
| Population | 0.10 |
| Historical stress | 0.08 |

---

## Risk bands

| WSI | Label | Map color |
|-----|-------|-----------|
| 0–20 | Healthy | Green |
| 21–40 | Low | Yellow |
| 41–60 | Moderate | Orange |
| 61–80 | High | Red |
| 81–100 | Critical | Dark red |

---

## Scenario engine

`POST /api/v1/predictions/stress/simulate`

Knobs:

- `rainfall_delta_pct`
- `population_delta_pct`
- `demand_delta_pct`
- `temperature_delta_c`
- `reservoir_delta_pct` / `reservoir_level_pct`

Presets (What-If panel):

- Rainfall drops 30%
- Demand increases 20%
- Reservoir A reaches 15%
- Population grows 10%
- Temperature rises 3°C

Scenarios **re-fuse** existing prediction outputs — they do not retrain models.

---

## Decision logic

Recommendations are generated dynamically from fused WSI + regional attributes (industrial share, population impact, expected stress date), then mapped into `RulesDecisionEngine` via `PredictionType.WATER_STRESS`.

Examples: increase pumping, reduce industrial allocation, increase reservoir release, enable secondary reservoir, conservation advisory, emergency supply plan.

---

## API

```http
GET  /api/v1/predictions/stress/status
POST /api/v1/predictions/stress/predict
POST /api/v1/predictions/stress/simulate
```

### Predict body

```json
{
  "region_id": "WARD-08",
  "horizon_days": 30,
  "include_all_regions": true
}
```

### Simulate body

```json
{
  "region_id": "WARD-08",
  "horizon_days": 30,
  "preset_id": "rainfall_drop_30",
  "scenario": { "demand_delta_pct": 10 }
}
```

---

## Dashboard

Route: `/water-stress`

- Interactive stress map (region click updates KPIs / charts / recommendations)
- Scenario + What-If controls
- Historical vs forecast WSI chart with confidence interval
- Regional comparison
- Executive insights + recommended actions

---

## Sample GIS

`data/water_stress/sample_regions.json` — wards, zones, district, municipality with population, linked `reservoir_id`, and polygon rings for map rendering.
