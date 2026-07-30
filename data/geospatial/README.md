# National Water Assets (shared geospatial catalogue)

Single source of truth for AquaMind maps.

## File

`data/geospatial/water_assets.json`

## Asset types

- `reservoir`
- `dam`
- `groundwater_station`
- `demand_region`
- `water_stress_region`
- `leak_zone`

## Add a reservoir (no frontend code changes)

1. Append a record to `water_assets.json` (or edit `scripts/generate_water_assets.py` and re-run).
2. Restart FastAPI (repository loads on startup; call reload if hot-reloading misses file changes).

Required fields:

```json
{
  "id": "RSV-IND-999",
  "type": "reservoir",
  "name": "Example Reservoir",
  "state": "Maharashtra",
  "lat": 19.0,
  "lng": 73.0,
  "capacity_mcm": 500,
  "current_storage_pct": 55.0,
  "forecast_storage_pct": 52.0,
  "risk_level": "moderate",
  "confidence": 0.8,
  "last_updated": "2026-07-27T00:00:00Z",
  "meta": { "forecast_proxy_id": "RES-A", "country": "IN" }
}
```

`meta.forecast_proxy_id` links the national asset to the ML catalog (`RES-A` / `RES-B` / `RES-C`) so predictions keep working without expanding the training set.

## API

- `GET /api/v1/geospatial/assets?types=reservoir`
- `GET /api/v1/geospatial/reservoirs`
- `GET /api/v1/geospatial/assets/{id}`

## Frontend

- `src/services/geospatial.ts`
- `src/hooks/useWaterAssets.ts`
- `src/components/maps/SharedAssetMap.tsx` (marker clustering + lazy load)

All maps filter this catalogue — they do not hardcode markers.
