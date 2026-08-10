# AquaMind AI

Water intelligence platform for **shortage prediction, acoustic leak detection, groundwater depletion forecasting, demand forecasting, climate risk, and reservoir imagery analysis** — fused into a single auditable Water Stress Index with an operations dashboard and AI-generated recommendations.

Built as a hackathon pilot on public and lab datasets. Every model's real held-out performance and every heuristic is disclosed rather than smoothed over — see [Model metrics](#model-metrics) and [Honest limits](#honest-limits).

---

## Modules

| Module | Backend | Entry point |
|--------|---------|-------------|
| **Water Stress Index** *(system-wide)* | Fusion over 4 models + climate | `/analytics/water-stress` · Operations Dashboard |
| **Regional Stress Intelligence** | Per-region fusion, own published weights | `/api/v1/predictions/stress/*` · `/water-stress` page |
| **Water shortage** | `water_shortage_model.pkl` (RandomForest) | `/predict-shortage` |
| **Leak detection** | `leak_detection_model.pkl` (ExtraTrees, acoustic) | `/detect-leak-signal` |
| **Groundwater** | `groundwater_model.pkl` (RandomForest, CGWB wells) | `/predict-groundwater-well` |
| **Demand forecast** | `water_demand_model.pkl` + framework model | `/predict-demand`, `/api/v1/predictions/demand/*` |
| **Reservoir forecast** | Framework model (joblib) | `/api/v1/predictions/reservoir/*` |
| **Decision optimization** | Rules engine over model outputs | `/api/v1/decision/*` |
| **Recommendation feedback** | Accept / defer / reject (intent only) | `/api/v1/recommendations/feedback` |
| **AquaLens** | Gemini Vision / Qwen2.5-VL + CLIPSeg | `/api/vision/analyze`, `/api/vision/history` |
| **Climate risk** | Open-Meteo + ERA5 + GloFAS | `/climate-risk/analyze` |
| **AI recommendations** | Local models + Gemini flash-lite (cached) | `/ai/recommendation-engine/live` |
| **AquaAI chat** | Gemini, grounded on live WSI | `/ai/copilot/chat` |

### Stack

- **Frontend** — React 19, Vite, Tailwind, Recharts, Leaflet, Framer Motion
- **App server** — Express (`server.ts`) on **:3000**, reverse-proxies `/api/*` to FastAPI
- **API** — FastAPI on **:8000**, SQLAlchemy, SQLite (`aquamind.db`); PostgreSQL via `DATABASE_URL`
- **ML** — scikit-learn / joblib under `ai/` and `fastapi_app/prediction/models/`
- **AI** — Google Gemini (vision + text), CLIPSeg for segmentation overlays

---

## Quick start

**Prerequisites:** Python 3.10+ (`py` on Windows), Node.js 18+, a [Google AI Studio](https://aistudio.google.com/) key for AquaLens/AquaAI, and the local `Aqua Dataset/` folder if you want to retrain or sync map layers.

### 1. Environment

```powershell
copy .env.example .env.local
```

Required in `.env.local`:

```env
GEMINI_API_KEY=your_google_ai_studio_key
JWT_SECRET_KEY=a-long-random-secret
DATABASE_URL=sqlite:///aquamind.db
```

> `JWT_SECRET_KEY` is mandatory outside development — the app **refuses to start** without it when `AQUAMIND_ENVIRONMENT` is not `development`/`test`, rather than silently falling back to a hardcoded secret.

Optional tuning:

```env
AQUAMIND_ENVIRONMENT=development     # gates demo seeding + JWT/CORS fail-closed
AQUAMIND_DEMO_MODE=false             # see "Demo resilience" below
AQUAMIND_REC_CACHE_TTL=3600          # recommendation cache TTL (s)
AQUAMIND_CLIMATE_CACHE_TTL=1800      # Open-Meteo cache TTL (s)
AQUAMIND_REC_MODEL=gemini-2.0-flash-lite
AQUAMIND_COPILOT_MODEL=gemini-2.0-flash-lite
ALLOWED_ORIGINS=https://your-frontend.example.com
VITE_API_BASE_URL=https://your-api.example.com   # build-time, non-localhost deploys only
```

Staging/production also run `fastapi_app/core/startup_checks.py` at boot: missing `JWT_SECRET_KEY`, wildcard CORS with credentials, or an unset `DATABASE_URL` **fail closed** instead of silently using development fallbacks.

### 2. Train models (required after clone)

`.pkl` weights are **not** in Git — regenerate locally:

```powershell
py -m pip install -r ai/requirements.txt
py -m pip install -r fastapi_app/requirements.txt
py ai\train.py
```

Writes four `.pkl` files plus matching `*.metadata.json` model cards (the metadata **is** tracked). Groundwater is the largest at ~145MB after hyperparameter tuning; GitHub's per-file limit is 100MB, hence the gitignore.

Optional — regenerate accuracy graphs into `ai/training_curves/`:

```powershell
py ai\plot_training_curves.py
```

### 3. Optional — populate map layers

```powershell
py ai\sync_map_from_datasets.py     # CWC reservoirs + sampled CGWB wells → SQLite
py ai\process_gwl_telemetry.py      # bounded sample of 6-hourly GWL telemetry
```

### 4. Run (two terminals)

```powershell
py -m uvicorn fastapi_app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
npm install
npm run dev
```

Open **http://localhost:3000** · API docs at **http://127.0.0.1:8000/docs**

First backend start creates and seeds `aquamind.db`.

---

## Authentication

**Every endpoint except health checks and the auth routes themselves requires a JWT bearer token.** Tokens are issued by `/auth/signup` and `/auth/login` and must be sent as `Authorization: Bearer <token>`. The frontend handles this automatically via `src/services/apiClient.ts`, which also clears the session and redirects to `/login` on any `401`.

### Access tiers

| Tier | Endpoints |
|------|-----------|
| **Public** | `/health`, `/`, `/auth/signup`, `/auth/login`, `/auth/request-password-reset`, `/auth/forgot-password` |
| **Any authenticated user** | All prediction, telemetry, analytics, vision, climate, decision, and recommendation routes |
| **Admin only** | `/auth/promote`, `/imports/reservoir`, `/api/v1/predictions/reservoir/train`, `/api/v1/predictions/demand/train` |

Roles: `user`, `government_officer`, `industry`, `admin`. **Public signup cannot self-assign `admin`** — an existing admin grants it via `POST /auth/promote`.

### Demo login (development only)

| Field | Value |
|-------|-------|
| Email | `admin@centralvalleywater.gov` |
| Password | `password123` |

Seeded automatically **only** when `AQUAMIND_ENVIRONMENT=development` (or `AQUAMIND_SEED_DEMO_DATA=true`). Any other environment skips seeding entirely, so this account does not exist in a production deploy.

### Password reset

Two-step, per-user, single-use tokens with a 30-minute expiry:

1. `POST /auth/request-password-reset` — issues a token. The response never reveals whether the email exists (no account enumeration).
2. `POST /auth/forgot-password` — completes the reset with that token.

> **Pilot limitation:** no mail provider is wired up, so the token is written to the **server console** instead of being emailed. Plug in a real provider before any production use.

### Rate limits

A global ceiling of **240 req/min per IP**, tightened on expensive routes:

| Limit | Routes |
|-------|--------|
| 5/min | `/auth/request-password-reset`, `/imports/reservoir`, both `/train` endpoints |
| 10/min | `/auth/signup`, `/auth/login`, `/auth/forgot-password`, `/api/vision/analyze` |
| 15/min | `/ai/copilot/chat` |
| 20/min | `/ai/recommendation-engine/live` |

---

## API reference

<details>
<summary><b>Full endpoint list</b></summary>

**Auth** — `POST /auth/signup` · `/auth/login` · `/auth/request-password-reset` · `/auth/forgot-password` · `/auth/promote` *(admin)*

**ML predictions** — `POST /predict-shortage` · `/predict-groundwater-well` · `/predict-groundwater` *(legacy calculator)* · `/predict-demand` · `/detect-leak-signal` · `/detect-leak` *(legacy)*

**Framework models** — `/api/v1/predictions/reservoir/{status,metrics,predict,train}` · `/api/v1/predictions/demand/{status,metrics,predict,train}` · `/api/v1/predictions/stress/{status,predict,simulate}`

> **Prediction stacks:** the Operations Dashboard and `/analytics/water-stress` use the legacy `ai/*.pkl` routes. Dedicated Demand / Reservoir / Water Stress / Decision pages use `/api/v1/...`. Prefer one stack per screen — the paths do not collide, but fused values can differ.

**Water intelligence** — `GET /analytics/water-stress` · `POST /predict/water-intelligence`

**Telemetry & analytics** — `/telemetry/sensors` · `/analytics/{leakages,groundwater,shortage-risks,consumption}` · `/regions` · `/weather`

**Decision optimization** — `/api/v1/decision/{status,recommend,compare}`

**Recommendation feedback** — `GET|POST /api/v1/recommendations/feedback` *(accept / defer / reject — operator intent only, not measured savings)*

**Geospatial** — `/api/v1/geospatial/assets` · `/assets/{asset_id}` · `/reservoirs`

**Vision (AquaLens)** — `POST /api/vision/analyze` · `GET /api/vision/history` *(user-scoped; near-duplicate scans collapsed)*

**Climate risk** — `/climate-risk/{presets,analyze,health}`

**Recommendations** — `GET /ai/recommendation-engine/live` · `POST /ai/recommendation-engine` · `GET|POST /recommendation`

**Reports & data** — `GET|POST /reports` · `/data-sources` · `/model-performance/{reservoir,groundwater,leak,demand}` · `POST /imports/reservoir` *(admin)*

**Chat** — `POST /ai/copilot/chat`

**System** — `GET /health` *(public, minimal)* · `GET /readiness` *(authenticated technical readiness, no secrets)* · `GET /ready` *(alias)*

</details>

---

## Water Stress Index

The gap this closes: the four models each answered a slice of shortage / leak / groundwater / demand, but nothing fused weather, consumption, reservoir, and sensor signals into one **water-stress tracking** score — which is what the problem statement actually asks for.

| Endpoint | Role |
|----------|------|
| `GET /analytics/water-stress` | Live WSI from DB telemetry + local models + Open-Meteo SPI |
| `POST /predict/water-intelligence` | Same fusion, with optional what-if overrides |

**Weights** (transparent, returned in every response): shortage 30% · groundwater 25% · leakage 20% · demand 15% · climate 10%.
**Stages:** `Low` · `Moderate` · `High` · `Critical`. Every response lists the top contributing **drivers** for auditability.

**UI:** dashboard hero card + component-breakdown chart, and a dedicated `/water-stress` page with drivers, fusion breakdown, scenario presets, baseline-vs-scenario comparison, and evidence export. Each component in that breakdown renders its **published weight** next to its contribution share, both read straight from the API response, so the on-screen breakdown can be checked against the endpoint instead of taken on trust.

### Two indices, two scopes

There are deliberately **two** stress fusions in this codebase. They answer different questions and therefore do not share a weight vector — a network-level index has to carry leakage, a regional one has to carry population. Both publish their weights in every response, so the difference is inspectable rather than hidden.

| | **System-wide WSI** | **Regional Stress Intelligence** |
|---|---|---|
| Endpoint | `GET /analytics/water-stress` · `POST /predict/water-intelligence` | `/api/v1/predictions/stress/{status,predict,simulate}` |
| Defined in | `services/water_stress_service.py` → `DEFAULT_WEIGHTS` | `prediction/models/water_stress/constants.py` → `FUSION_WEIGHTS` |
| Scope | Whole monitored network | One selected region at a time |
| Weights | shortage 30 · groundwater 25 · leakage 20 · demand 15 · climate 10 | demand 28 · reservoir 28 · rainfall 14 · groundwater 12 · population 10 · historical 8 |
| Surfaced on | Operations Dashboard hero KPI | `/water-stress` page, titled **Regional Water Stress** |

The `/water-stress` header names its module and version and states that it is scoped to one region and separate from the dashboard index, so the two numbers are never presented as the same measurement.

**What-if presets** (returned from `/api/v1/predictions/stress/status` as `what_if_presets`): `baseline`, `drought_rainfall_deficit`, `heatwave`, `increased_demand`, `leakage_increase` (mapped through the existing demand knob — no invented leak formula), and `conservation`. Custom slider overrides still go through `normalize_scenario()` clamps.

Supporting logic:

- **Orifice-style leak loss estimator** — acoustic training data has no volumetric labels, so litres/min is a disclosed heuristic, not a learned output
- **Groundwater depletion metrics** — rate, trend, days-to-critical, enriched onto GW predictions
- **Pilot consumption series** (`/analytics/consumption`) feeds shortage demand and WSI
- Seeded demo leak alerts are **muted from the WSI** so demo data can't fake a Critical reading
- Latest AquaLens scan attaches as read-only context (`context.aqualens_latest`) — evidence alongside the score, deliberately **not** a weighted input

```ts
import { fetchWaterStress, predictWaterIntelligence } from './services/telemetry';

const live = await fetchWaterStress();
console.log(live.water_stress.water_stress_index, live.water_stress.stage, live.water_stress.drivers);

const fused = await predictWaterIntelligence({
  reservoir_capacity_pct: 34.2,
  rainfall_deficit_pct: -20,
  spi3_proxy: -1.2,
});
```

---

## Internal data-quality contract

Reservoir storage, well depths, acoustic inference, weather, and consumption arrive on different clocks, in different units, and with different reliability. `fastapi_app/core/data_quality.py` is the single place that normalizes them, so every module reads the same vocabulary instead of each router inventing its own `source` string.

Both fused endpoints (`GET /analytics/water-stress`, `POST /predict/water-intelligence`) return a `metadata` block keyed by component — `water_stress`, `shortage`, `leak`, `groundwater`, `demand`, `climate`:

```jsonc
"metadata": {
  "demand": {
    "source": "water_demand_model + consumption_series",
    "method": "trained_model",        // trained_model · database_telemetry · weather_provider
                                      // engineering_estimate · rules_engine · vision_model · fallback
    "confidence": 0.93,               // always 0.0–1.0
    "data_quality": "high",           // high · medium · low · unknown
    "freshness": "fresh",             // fresh · recent · stale · unknown
    "availability": "available",      // available · stale · missing · unavailable
    "is_stale": false,
    "observed_at": "2026-07-26T00:00:00+00:00",
    "generated_at": "2026-07-26T06:08:11+00:00",
    "data_age_seconds": 21491.0,
    "model_version": "water_demand_model:RandomForestRegressor@2026-07-26",
    "unit": "million_gallons_per_day"
  }
}
```

Rules the contract enforces:

- **Units are fixed per field** — percentages 0–100 (rainfall anomaly −100–100), probabilities and confidence 0.0–1.0, demand in MGD, leak loss in L/min, groundwater depth in metres, temperature in °C. Out-of-range values are clamped; NaN, infinity, and impossible negatives are **rejected to `null`**, never rewritten as a plausible zero.
- **Quality is derived, not asserted** — the method sets a ceiling, an unverifiable `observed_at` caps it at `medium`, a stale observation drops it to `low`, and missing/failed upstreams force `unknown` with a null confidence.
- **`availability` keeps a valid zero distinct from no data**, so a partially-loaded dashboard still degrades honestly instead of showing a measured-looking 0.
- **The fused index inherits its stalest input's freshness**, and its confidence is the weight-averaged confidence of the contributing components.

Existing response fields (`predicted_risk_score`, `estimated_water_loss_lpm`, `forecasted_demand_mgd`, …) are unchanged — `metadata` is additive. It exists for quality control, freshness checks, auditing, and future model calibration; TypeScript types and helpers live in `src/types/apiContracts.ts` (re-exported from `src/services/telemetry.ts`) for Details, tooltip, and report panels rather than as badges on every card.

---

## Latency and caching

Dashboard and prediction hot paths use a process-local L1 TTL cache (`fastapi_app/core/ttl_cache.py`) with single-flight coalescing so concurrent identical requests share one computation:

| Surface | TTL | Key notes | Bypass |
|---------|-----|-----------|--------|
| Water Intelligence / WSI | ~45s | `wi:live` or hashed overrides | `force_refresh=true` |
| Weather (+ Open-Meteo) | ~120s | location + rounded lat/lon | `force_refresh=true` |
| Live recommendations | ~60s | process L1; Gemini still uses `ai/.rec_cache` (~1h) | `force_refresh=true` |
| Model status cards | ~60s | per model id | TTL expiry |
| Vision history | ~30s | asset_label + mode + limit | `force_refresh=true` |

Blocking sklearn / DB fusion / Open-Meteo work runs via `asyncio.to_thread` on the affected routes so one slow fusion does not stall unrelated dashboard endpoints. Responses expose `X-Process-Time-Ms`, `X-Request-Id`, and `X-Cache` (`HIT` / `MISS` / `BYPASS`) when a cache was consulted. Sklearn `.pkl` payloads are loaded once per model instance and reused.

Open-Meteo and Gemini already use explicit timeouts and bounded retries; rate-limit / non-model HTTP errors stop the Gemini model loop instead of burning the full budget.

---

## Shared API contracts

Typed envelopes live in `fastapi_app/schemas.py` (Pydantic) and `src/types/apiContracts.ts` (TypeScript). Prefer these for new UI and service code; legacy field names remain accepted.

| Surface | Backend schema | Frontend type | Notes |
|---------|----------------|---------------|-------|
| Water Stress / fusion | `WaterIntelligenceData` / `WaterIntelligenceResponse` | `WaterIntelligenceData` | Components typed; `extra=allow` keeps legacy keys |
| Shortage / leak / GW / demand (legacy predict) | `*PredictionRequest/Data/Response` | via fusion components | Client inputs rejected on range; responses use null for missing |
| Recommendations | `RecommendationData`, `AIRecommendationEngineData` | same names | Rules list vs AI string list both supported |
| Climate risk | `ClimateRiskAnalyzeBody`, `ClimateRiskResponse` | `ClimateRiskResult` in `climateRisk.ts` | Lat/lon validated −90…90 / −180…180 |
| Vision | `VisionAnalysisData` / `VisionAnalysisResponse` | `VisionAnalysisResult` | Prefer nested `data` when both flat and nested exist |
| Provenance | `DataQualityMetadata` | `DataQualityMetadata` | Built only via `build_metadata` / `normalize_component` |

**Envelope.** Most FastAPI routes return `{ success, message, timestamp, data }`. Climate risk keeps its existing top-level `provenance` / `climate` / `flood` shape for client compatibility.

**Prediction vs observation.** Model outputs (`predicted_*`, `forecasted_*`) are forecasts; DB telemetry fields and `observed_at` describe measurements. Multi-day shortage horizons: `day_1` is the trained task; `day_7` / `day_30` are extrapolated heuristics (see `multi_horizon.note`).

**Confidence.** Always 0.0–1.0 when present. It is a pilot reliability indicator (often from holdout error), **not** a calibrated probability. Null means unavailable — never treat as 0.

**Null vs zero.** Unavailable measurements use `null` (and `metadata.availability`), not `0`. Empty arrays mean a successful query with no rows. Failed provider/model calls use typed HTTP errors (or demo fixtures when demo mode is on).

**Horizons.** Demand/reservoir workspace `value` is 1–3650 in the chosen unit; legacy `horizon_days` is 1–365. Invalid client horizons are rejected.

Contract tests: `fastapi_app/tests/test_api_contracts.py`. Frontend helper: `displayMetric()` in `apiContracts.ts`.

---

## Dashboard loading

The operations dashboard loads in tiers rather than as one blocking batch, because the endpoints behind it are not equally fast. Measured against a local backend, reservoirs and leak alerts answer in 15–60 ms, while a **cold** `/analytics/water-stress` takes ~11 s (it reloads four models and may refetch the weather provider) and `/recommendation` ~4 s (it re-runs the fusion pipeline and calls Gemini). Warm, everything is ~300 ms.

`src/hooks/useDashboardData.ts` splits that into three tiers:

| Tier | Panels | When |
|------|--------|------|
| Essential | water stress, reservoirs, leak alerts | Requested immediately |
| Deferred | weather, groundwater, sensors | One tick after the shell paints |
| On demand | recommendations, AI executive briefing | Only when a panel or the user asks |

Water stress is requested in the first tier but is deliberately **not** part of the first-paint gate (`FIRST_PAINT_PANELS`); the command center renders as soon as reservoirs and leak alerts settle, and the fused index streams into its own KPI afterwards. There is no `/health` call on the critical path — each request reports its own success, and the full "unable to reach AquaMind services" screen appears only when *every* essential request fails with no cached value.

Each panel carries its own `{ status, data, error, updatedAt, stale }` state (`src/hooks/dashboardState.ts`), so the UI can tell loading, loaded-but-empty, failed, and stale-cached apart. A failed feed renders `-`/"Unavailable" rather than a zero that would read as a measurement, and a failed refresh keeps the previous value on screen marked stale instead of blanking the panel.

### Nothing on screen is decorative data

The same rule that governs a failed feed governs every trend, sparkline and secondary figure: **if it looks like a measurement, it came from one.** Concretely:

- **Sparklines are drawn from real series only.** `src/components/ui/sparkline.ts` pulls the `historical`, `forecast` or `confidence` channel out of the series a page already received, and returns `undefined` when fewer than two finite points exist or the line would be flat. `KpiCard` then omits the sparkline entirely. No card pads a single current value with leading points to manufacture a slope.
- **Trend chips are computed or absent.** `ExecutiveKpi.trend` is optional. The demand cards show the measured current → forecast move; groundwater, reservoir, alerts and weather derive theirs from their own readings; anything without a basis renders no chip rather than a plausible-sounding one.
- **"Predicted Demand" is a model output, not an extrapolation.** It reads the demand forecast the dashboard already fetches, and shows `-` with "Awaiting forecast feed" if that call fails.
- **Live Fusion Inputs** (dashboard header) counts how many of the five weighted WSI components the backend positively reports as `available` in its `metadata` block — `4 / 5 reporting`. It replaced a hardcoded confidence percentage, and doubles as a visible read-out of the data-quality contract.
- **Disclosed heuristics say so.** Where a figure is a planning heuristic rather than a measurement — the Population at Risk fallback, for instance — the card labels it and the tooltip spells out the derivation.

This is the same principle as the model metrics below: a number we cannot stand behind is not shown, or is shown clearly labelled as what it is.

Cancellation and deadlines live in `apiClient.ts`: `apiGet`/`apiPost` accept an `AbortSignal` and an optional `timeoutMs`, and reject with a typed `ApiError` (`network` · `http` · `timeout` · `aborted` · `unauthorized`). Dashboard requests use a 20 s budget (covers a cold water-stress fusion); vision analysis and copilot calls pass no `timeoutMs` and keep their existing unbounded behaviour. A refresh aborts the previous cycle, unmount aborts everything, aborts are never surfaced as failures, and a monotonic cycle counter stops a slow earlier response from overwriting a newer one. The full "unable to reach AquaMind services" screen appears only when both first-paint feeds (reservoirs and leak alerts) fail with no cache — a timed-out water-stress fusion alone does not blank the command center.

Successful payloads are kept in a module-level session cache (`src/services/dashboardCache.ts`), namespaced by signed-in account and never written to `localStorage`. Returning to the dashboard in the same session shows the cached view immediately while a refresh runs underneath.

---

## AquaLens

1. Upload a satellite or drone water-body image (`mode=reservoir` or `flood`).
2. Gemini Vision (Qwen2.5-VL fallback) returns structured hydrology metrics — health score, water spread, vegetation, sedimentation, dry shoreline, encroachment, water stress, **turbidity index, algae-bloom risk, shoreline-exposure %, and the model's self-reported confidence**.
3. CLIPSeg adds pixel-level class overlays (water, vegetation, shoreline). `mode=flood` switches to separating permanent water bodies from flood inundation over land, so operators don't mislabel a lake as a flood.
4. Every scan is **persisted** to the `vision_analyses` table, **scoped to the signed-in user**. The UI **Recent scan timeline** lists your recent scans for the active mode. History responses and the timeline **collapse near-identical rows** (same minute + health/risk/confidence) and the API **reuses** a prior row on double-submit within ~2 minutes so retries do not inflate the timeline.
5. Before/after comparison only runs when both scans share the **same asset label and mode** — cross-site diffs are refused with an explicit warning rather than inventing a trend.

```
POST /api/vision/analyze     multipart: file, mode=reservoir|flood, asset_label (optional)
GET  /api/vision/history     ?asset_label=&vision_mode=&limit=&force_refresh=
```

Requires `torch` + `transformers`. CLIPSeg weights download **lazily on the first upload**, never at startup, and the overlay is best-effort: if it fails or exceeds its deadline the VLM analysis is still returned with `segmentation.available = false`.

Every provider gets its own deadline and the chain shares a wall-clock budget, so an unreachable provider costs seconds rather than minutes. If no provider answers, the request returns **503 with a clear message** — not a fabricated analysis — unless demo mode is on (see below).

---

## Recommendation feedback & decision UX

Operators can mark a recommendation **accepted**, **deferred**, or **rejected** via `POST /api/v1/recommendations/feedback`. Records are per-user, upserted by `recommendation_id`, and returned by the matching `GET`. The API disclaimer is explicit: this stores **operator intent**, not measured water savings.

On the Decision / Recommended Actions screens, the **Current** strategy is the do-nothing baseline (often zeros for intervention knobs) — it is shown for comparison against optimized actions, not as a failed optimization. Scenario evidence on Water Stress can be exported from the UI for review packs.

---

## Demo resilience

A live demo runs on someone else's Wi-Fi. `AQUAMIND_DEMO_MODE=true` lets the app degrade to checked-in fixtures when an *optional* provider is unreachable, so a captive portal cannot take the walkthrough down.

```env
AQUAMIND_DEMO_MODE=true            # allow fixtures when a provider is unavailable
AQUAMIND_DEMO_FORCE_FIXTURES=true  # skip providers entirely (offline rehearsal)
```

Both default to **false**, so nothing changes if the settings are omitted. `AQUAMIND_DEMO_FORCE_FIXTURES` is ignored unless demo mode is also on. Every decision runs through one predicate, `should_use_fixture()` in `fastapi_app/core/demo_mode.py` — there are no ad-hoc demo checks elsewhere in the codebase.

Fallback order, per surface:

| Surface | Order | Demo mode off |
|---------|-------|---------------|
| Recommendations / briefing | Gemini → local rules engine → fixture | Gemini → local rules engine (always answers) |
| AquaLens | Gemini Vision → Qwen (OpenRouter) → Qwen (DashScope) → fixture | 503 with a retryable message |
| Water-stress fusion | Live fusion → fixture | 500 |

Fixtures live in `fastapi_app/demo_fixtures/` (`water_intelligence`, `recommendations`, `vision_reservoir`, `leak_detection`). They are validated against the required fields of the response they stand in for before being returned, they are never written to the recommendation cache, and they carry `source: "demo_fixture"`, `data_quality: "low"`, and their original capture timestamp — so a fixture is never mistaken for a current reading. There is deliberately no flood-mode vision fixture: with nothing captured for that mode, the provider error surfaces instead.

Provenance is consistent across all three paths. Every recommendation response reports `source` as exactly one of `remote_ai`, `rules_fallback`, or `demo_fixture`, with a `metadata` block describing the path that actually ran, so a rules result can never be labelled as remote AI.

`GET /readiness` (authenticated; `GET /ready` is an alias) reports dependency status for a pre-demo or deployment check — database latency, which trained artifacts are available/loaded, whether Gemini/Qwen/DashScope and weather are configured, CLIPSeg (`loaded` · `not_loaded` · `unavailable`), and demo mode. Overall status is `ready`, `degraded`, or `not_ready`. Keys are reduced to a configured/unavailable boolean and never echoed. The probe does not load CLIPSeg or call remote AI/weather providers. Public `GET /health` stays a lightweight liveness check.

---

## Climate Risk Intelligence

Live upstreams, no API key needed for standard Open-Meteo use:

| Source | Role |
|--------|------|
| Open-Meteo Forecast | Near-term precipitation, Tmax, ET₀, hourly soil moisture |
| Open-Meteo Archive (ERA5) | Multi-year climatology → rainfall deficit + SPI-3 proxy |
| Open-Meteo Flood (GloFAS) | River discharge → fluvial flood **risk class** |

Responses are cached to `climate/.om_cache/` (gitignored, TTL-bounded, with size-capped eviction).

---

## AI Recommendations & AquaAI

**Recommendations** are token-efficient by design: local sklearn outputs and DB telemetry are compressed into a **compact numeric** context, Gemini flash-lite turns that into ≤3 short actions with a capped `maxOutputTokens`, and results are cached (~1h) under `ai/.rec_cache/` and shared across Dashboard, Decision Intelligence, and Reports. Because only numbers are sent — never raw user text — the prompt has no injection surface.

If Gemini fails, a local rules fallback takes over with the same numeric context, so the actions still name the affected zone, storage level, and supply cut. Remote calls are bounded twice: each attempt has its own timeout, and all model attempts in one request share a total budget. A timeout ends the attempt chain immediately rather than re-trying the same unresponsive endpoint under a different model id — the case that used to cost `timeout × model count` before the fallback appeared. The executive briefing carries a client-side deadline as well, so the report modal always resolves to either a briefing or a local snapshot.

**AquaAI** (`POST /ai/copilot/chat`) is the in-app assistant, grounded on the live WSI and its drivers, with chat history for follow-ups and off-topic refusal. The floating widget is portaled to `document.body` above Leaflet map panes so it is not clipped inside map containers.

---

## Security hardening (pilot)

Outside `development` / `test`, boot fails closed when JWT, CORS, or database config is unsafe (`startup_checks.py`). Auth errors stay generic (no account enumeration). Vision history is filtered by `user_id`. Rate limits and security headers apply on the API; Docker images prefer non-root where configured. See `fastapi_app/tests/test_security_hardening.py`.

---

## Model metrics

Reported against the **held-out test set**, not the friendlier validation split. Exact numbers live in `ai/*.metadata.json` and are regenerated by `py ai/train.py` — this table does not invent values.

| Model | Held-out test | Validation | Baseline | Notes |
|-------|---------------|------------|----------|-------|
| Shortage | MAE 1.3125 pp · RMSE 4.2789 pp | MAE 1.1375 · RMSE 2.9524 | Persistence MAE **0.6687** (model does **not** beat it) | Seasonal-naive unsupported (single March 2024 month). No R² published in metadata. |
| Groundwater | MAE 3.1684 m · RMSE 9.783 · R² 0.5176 | MAE 2.488 · RMSE 4.9979 · R² 0.8251 | Persistence baseline written at retrain; cite test over validation | Temporal year split; validation≫test R² = distribution shift. |
| Leak | P 0.7582 · R 0.9583 · F1 0.8466 · Acc 0.7396 | F1 0.9302 | Majority-class F1 **0.8571** (from test CM; model F1 does not beat it) | Lab-trained; threshold 0.3; no learned volume. |
| Demand | MAE 3.101 MGD · R² 0.9519 | MAE 3.223 · R² 0.9521 | Mean baseline R² = 0 by definition | **Synthetic-label validation only** — measures generator recovery, not AMI accuracy. |

Every `/predict-shortage` response includes `technical_accuracy_note` and an `evaluation` block distinguishing the trained **one-day** output from **extrapolated** 7/30-day horizons. Status cards: `GET /api/v1/models/{id}/status` and sanitized `GET /model-performance/{reservoir,groundwater,leak,demand}`.

### Evaluation approach

- **Shortage / groundwater:** chronological splits (by unique date / by year). Tests assert future rows do not enter training.
- **Leak:** stratified **file-level** split so windows from the same recording stay in one partition.
- **Demand:** random i.i.d. split on synthetic rows (documented); chronological splits apply once real AMI series replace labels.
- Baselines: persistence (shortage, groundwater), mean R²=0 (demand), majority class from published confusion matrix (leak).
- `confidence` fields are holdout-error indicators, **not** calibrated probabilities.

Validation metrics guide training choices; **test** metrics (and baseline comparisons) are what we cite for technical review. Passing validation is not production readiness.

### Next data for field deployment

- Multi-season reservoir storage + station-matched rainfall/inflow/release
- Metered AMI / SCADA demand and holiday calendars
- Field DMA acoustic labels (not lab-only)
- Local aquifer calibration for groundwater wells

### Honest limits

- Shortage trains on a **single March 2024 CWC extract**; its test partition spans few unique calendar days across many reservoirs.
- 7- and 30-day shortage horizons are a **geometrically damped extrapolation** of the 1-day forecast.
- Acoustic model is **lab-trained**, not field DMA data. Volumetric loss is an orifice heuristic.
- SPI-3 is a **z-score proxy**, not full WMO gamma SPI. Waterlogging uses a disclosed water-balance assumption. GloFAS gives ~5 km cell discharge risk, **not** flooded-area polygons.
- The GWL processor samples telemetry files rather than loading the full multi-GB corpus.

---

## Testing

```powershell
py -m pytest fastapi_app/tests -q
```

~248 tests covering WSI weighting and stage boundaries, leak-loss caps, groundwater metrics, the data-quality contract, API envelopes (`test_api_contracts.py`), L1 TTL cache / single-flight (`test_perf_cache.py`), demo resilience (`test_demo_mode.py`), readiness (`test_readiness.py`), security hardening (`test_security_hardening.py` — JWT/CORS fail-closed, user-scoped vision history, generic 401s), reliability (`test_reliability_hardening.py`), model evaluation disclosures (`test_model_evaluation.py`), product surfaces (`test_product_improvements.py` — scenario presets, recommendation feedback, AquaLens comparison / dedupe), dataset validation, training/serialization round-trips, decision ranking, climate math with mocked upstreams, and HTTP-level auth (unauthenticated prediction rejection; signup cannot self-assign `admin`).

Frontend typecheck, dashboard-loading tests, and encoding check:

```powershell
npm run lint
npm run test:dashboard
npm run check:encoding
```

`test:dashboard` covers the loading contract (first-paint tiers, panel independence, abort/timeout classification, cache reuse). `check:encoding` (`scripts/check_encoding.py`) fails if user-facing sources contain classic mojibake markers (Latin-1 misreads of UTF-8 punctuation, or the Unicode replacement character).

---

## Deployment

| File | Role |
|------|------|
| `fastapi_app/Dockerfile` | API image. `ai/*.pkl` are **not** baked in — mount them as a volume (see the header comment) |
| `Dockerfile` | Frontend + Express proxy. A down FastAPI returns a real `502`, never mock data |
| `docker-compose.yml` | Wires both; requires `JWT_SECRET_KEY`, `DATABASE_URL`, and `ALLOWED_ORIGINS` |
| `.github/workflows/ci.yml` | Typechecks + builds frontend, runs backend pytest on every push/PR |

```powershell
copy .env.example .env
# set JWT_SECRET_KEY (≥32 chars), DATABASE_URL, ALLOWED_ORIGINS (no '*'), GEMINI_API_KEY
docker compose up --build
```

`AQUAMIND_ENVIRONMENT=production` (the compose default) disables demo seeding, rejects development JWT/CORS fallbacks, and refuses wildcard origins with credentials. API images run as a non-root user where configured. Schema creation still uses SQLAlchemy `create_all` — a proper migration tool (Alembic) remains a deployment follow-up before long-lived production schemas.

---

## Project structure

```text
aquamind-ai/
├── src/                       # React UI
│   ├── pages/                 # Route-level pages (lazy-loaded)
│   ├── components/            # dashboard/executive, stress, vision, maps, ui,
│   │                          #   copilot (AquaAI portal), decision…
│   ├── hooks/
│   │   ├── dashboardState.ts  # Pure per-panel state + load tiers
│   │   └── useDashboardData.ts# Tiered fetch, abort, deadline, cache
│   ├── types/
│   │   └── apiContracts.ts    # Shared TS envelopes + display helpers
│   ├── components/ui/
│   │   └── sparkline.ts       # Series → sparkline; undefined rather than invent
│   └── services/
│       ├── apiClient.ts       # Shared fetch: JWT, 401, AbortSignal, timeouts
│       ├── dashboardCache.ts  # In-memory session cache for dashboard payloads
│       ├── visionAnalysis.ts  # AquaLens analyze + history client
│       ├── readiness.ts       # Authenticated readiness probe client
│       └── jwt.ts             # Client-side expiry check
├── fastapi_app/
│   ├── main.py                # App factory, CORS, rate limiter, error handlers
│   ├── core/                  # config, security, rate_limit, safe_paths,
│   │                          #   data_quality, demo_mode, ai_fallback,
│   │                          #   ttl_cache, startup_checks
│   ├── demo_fixtures/         # Checked-in fallback payloads, demo mode only
│   ├── routers/               # HTTP layer (incl. recommendation_feedback)
│   ├── services/              # model, water_stress, vision_history, readiness…
│   ├── prediction/            # Framework + trained models (reservoir, demand, stress)
│   ├── decision_engine/       # Rules + optimization
│   ├── database/              # models.py (source of truth), schema.sql (PG reference)
│   └── tests/                 # pytest suite + conftest auth fixtures
├── climate/                   # Open-Meteo clients, SPI / heat / GloFAS / ponding
├── ai/                        # Training scripts + recommendation engine
│   ├── train.py               # Trains all four models
│   ├── evaluation.py          # Shared evaluation helpers
│   ├── *.metadata.json        # Model cards — tracked
│   ├── training_curves/       # Tracked graphs
│   └── *.pkl                  # Local only (gitignored)
├── scripts/                   # check_encoding.py and other repo checks
├── public/                    # Static assets served by Vite (logos, favicons, media)
├── data/                      # Sample + synthetic datasets
├── Aqua Dataset/              # Large local corpus (gitignored)
├── hackathon/                 # Pitch materials (*.pptx gitignored; markdown ok)
├── _archive/                  # Scratch/duplicates parked out of the root (gitignored,
│                              #   safe to delete — see _archive/README.md)
├── index.html                 # Vite entry
├── server.ts                  # Express + /api reverse proxy
├── aquamind.db                # Local SQLite (gitignored; DATABASE_URL default)
├── Dockerfile · docker-compose.yml · .github/workflows/ci.yml
└── .env.example
```

Everything else in the root is build or runtime configuration that its tooling resolves from the project root — `package.json`, `package-lock.json`, `bun.lock`, `tsconfig.json`, `vite.config.ts`, `.dockerignore`, `.gitignore` — plus `metadata.json` and `assets/.aistudio/`, which are AI Studio project markers unused by the Vite build.

---

## Git notes

| Tracked | Local only (gitignored) |
|---------|-------------------------|
| Source, `ai/*.metadata.json`, `training_curves/` | `ai/*.pkl`, `data/*/artifacts/` |
| `data/synthetic/`, `data/geospatial/` (small) | `Aqua Dataset/`, `data/imports/` |
| `.env.example`, `.github/workflows/` | `.env.local`, `aquamind.db`, `.rec_cache/`, `.om_cache/` |
| `fastapi_app/demo_fixtures/` | `.tmp-*` scratch files, `hackathon/*.pptx`, `.claude/`, `_archive/` |

Metadata files write **repo-relative** paths so committed model cards never leak absolute machine paths.

**After clone:** set `.env.local` → `py ai\train.py` → start FastAPI → `npm run dev`.

---

## Scope

Hackathon / pilot build on public and lab datasets with local SQLite and optional Gemini. The models are pilots with disclosed limitations — **retrain on real utility feeds and validate against field data before using any output for operational decisions.**

## License

Private / pilot project
