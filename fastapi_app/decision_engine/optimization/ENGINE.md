# AI Decision Optimization Engine

Central operational planning layer for AquaMind.

**Not** a prediction model. Consumes Demand, Reservoir, and Water Stress outputs.

Does not duplicate forecasting logic. Does not modify `prediction/framework/*`.

---

## Architecture

```
WaterDemandForecastService ──┐
ReservoirLevelForecastService ├──► DecisionOptimizationService
WaterStressIntelligenceService┘              │
                                             ▼
                               DecisionOptimizationEngine
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    ▼                        ▼                        ▼
            Ranked actions            Operational timeline     Strategy comparison
```

---

## Decision types

- Water Allocation
- Pump Scheduling
- Reservoir Release
- Conservation Advisory
- Emergency Response
- Infrastructure Priority
- Maintenance Priority

---

## Ranking criteria

| Factor | Weight |
|--------|--------|
| Impact | 0.28 |
| Risk reduction | 0.26 |
| Population benefit | 0.20 |
| Water saved | 0.16 |
| Cost efficiency | 0.10 |

---

## API

```http
GET  /api/v1/decision/status
POST /api/v1/decision/recommend
POST /api/v1/decision/compare
```

### Recommend

```json
{
  "region_id": "WARD-08",
  "horizon_days": 30,
  "max_actions": 12
}
```

### Compare

```json
{
  "region_id": "WARD-08",
  "horizon_days": 30,
  "aggressiveness": 1.0
}
```

Returns Current Strategy vs Optimized Strategy with water saved, risk reduction, population protected, and estimated cost.

---

## Dashboard

Route: `/decision-intelligence`

Sections: Top Recommendations, Priority Queue, Operational Timeline, Scenario Comparison, AI Reasoning, Expected Outcomes.
