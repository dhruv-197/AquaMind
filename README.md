# AquaMind AI

Water intelligence platform for **shortage prediction, acoustic leak detection, groundwater depletion forecasting, demand forecasting, climate risk, and reservoir imagery analysis** — fused into a single auditable Water Stress Index with an operations dashboard and AI-generated recommendations.

Built as a hackathon pilot on public and lab datasets. Every model's real held-out performance and every heuristic is disclosed rather than smoothed over — see [Model metrics](#model-metrics) and [Honest limits](#honest-limits).

---

## Modules

| Module | Backend | Entry point |
|--------|---------|-------------|
| **Water Stress Index** | Fusion over 4 models + climate | `/analytics/water-stress`, `/water-stress` page |
| **Water shortage** | `water_shortage_model.pkl` (RandomForest) | `/predict-shortage` |
| **Leak detection** | `leak_detection_model.pkl` (ExtraTrees, acoustic) | `/detect-leak-signal` |
| **Groundwater** | `groundwater_model.pkl` (RandomForest, CGWB wells) | `/predict-groundwater-well` |
| **Demand forecast** | `water_demand_model.pkl` + framework model | `/predict-demand`, `/api/v1/predictions/demand/*` |
| **Reservoir forecast** | Framework model (joblib) | `/api/v1/predictions/reservoir/*` |
| **Decision optimization** | Rules engine over model outputs | `/api/v1/decision/*` |
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
AQUAMIND_ENVIRONMENT=development     # gates demo seeding + JWT fallback
AQUAMIND_REC_CACHE_TTL=3600          # recommendation cache TTL (s)
AQUAMIND_CLIMATE_CACHE_TTL=1800      # Open-Meteo cache TTL (s)
AQUAMIND_REC_MODEL=gemini-2.0-flash-lite
AQUAMIND_COPILOT_MODEL=gemini-2.0-flash-lite
ALLOWED_ORIGINS=https://your-frontend.example.com
VITE_API_BASE_URL=https://your-api.example.com   # build-time, non-localhost deploys only
```

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

**Water intelligence** — `GET /analytics/water-stress` · `POST /predict/water-intelligence`

**Telemetry & analytics** — `/telemetry/sensors` · `/analytics/{leakages,groundwater,shortage-risks,consumption}` · `/regions` · `/weather`

**Decision optimization** — `/api/v1/decision/{status,recommend,compare}`

**Geospatial** — `/api/v1/geospatial/assets` · `/assets/{asset_id}` · `/reservoirs`

**Vision (AquaLens)** — `POST /api/vision/analyze` · `GET /api/vision/history`

**Climate risk** — `/climate-risk/{presets,analyze,health}`

**Recommendations** — `GET /ai/recommendation-engine/live` · `POST /ai/recommendation-engine` · `GET|POST /recommendation`

**Reports & data** — `GET|POST /reports` · `/data-sources` · `/model-performance/{reservoir,groundwater,leak,demand}` · `POST /imports/reservoir` *(admin)*

**Chat** — `POST /ai/copilot/chat`

**System** — `GET /health`

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

**UI:** dashboard hero card + component-breakdown chart, and a dedicated `/water-stress` page with drivers, fusion breakdown, and what-if sliders.

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

## AquaLens

1. Upload a satellite or drone water-body image, optionally tagged with a **site name**.
2. Gemini Vision (Qwen2.5-VL fallback) returns structured hydrology metrics — health score, water spread, vegetation, sedimentation, dry shoreline, encroachment, water stress, **turbidity index, algae-bloom risk, shoreline-exposure %, and the model's self-reported confidence**.
3. CLIPSeg adds pixel-level class overlays (water, vegetation, shoreline). `mode=flood` switches to separating permanent water bodies from flood inundation over land, so operators don't mislabel a lake as a flood.
4. Every scan is **persisted** to the `vision_analyses` table. Re-uploading under the same site name yields a **before/after comparison** (health delta + improving/stable/degrading trend) and a **trend chart** across that site's history.

```
POST /api/vision/analyze     multipart: file, mode=reservoir|flood, asset_label (optional)
GET  /api/vision/history     ?asset_label=&mode=&limit=
```

Requires `torch` + `transformers`; the first run downloads CLIPSeg weights.

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

**Recommendations** are token-efficient by design: local sklearn outputs and DB telemetry are compressed into a **compact numeric** context, Gemini flash-lite turns that into ≤3 short actions with a capped `maxOutputTokens`, and results are cached (~1h) under `ai/.rec_cache/` and shared across Dashboard, Decision Intelligence, and Reports. If Gemini fails, a local rules fallback takes over. Because only numbers are sent — never raw user text — the prompt has no injection surface.

**AquaAI** (`POST /ai/copilot/chat`) is the in-app assistant, grounded on the live WSI and its drivers, with chat history for follow-ups and off-topic refusal.

---

## Model metrics

Reported against the **held-out test set**, not the friendlier validation split. Exact numbers regenerate per run into `ai/*.metadata.json`.

| Model | Metric | Test | Validation | Notes |
|-------|--------|------|-----------|-------|
| Shortage | R² / MAE (pp) | ~0.96 / ~1.3 | ~0.98 / ~1.1 | ⚠️ **Does not beat a naive "tomorrow = today" baseline** (baseline MAE ~0.67pp). Only 30 days of source data — a pilot, not evidence of learned weather/demand signal. |
| Groundwater | R² | ~0.52 | ~0.85 | Genuinely beats persistence (~0.21 R²) on 2023+ held-out wells — the most defensible of the four. |
| Leak detection | Accuracy / F1 | ~0.74 / ~0.85 | ~0.88 / ~0.93 | Small held-out population (96 windows); one misclassified file moves it noticeably. |
| Demand | R² | ~0.95 | ~0.95 | Trained on a **synthetic** label from a hand-written formula — measures formula recovery, not real-world accuracy. |

Every `/predict-shortage` response carries a live `technical_accuracy_note` stating whether the model beat its baseline, so this is disclosed in the API contract, not just in docs.

Methodology that **is** sound: temporal (not random) splits for both time-series models, file-grouped splits for the acoustic classifier, and trailing-only rolling windows — verified free of leakage.

### Honest limits

- Shortage model trains on a **single March 2024 CWC extract**; its test partition spans only a handful of unique calendar days across many reservoirs, so the row count overstates independent observations.
- 7- and 30-day shortage horizons are a **geometrically damped extrapolation** of the 1-day forecast, not independently trained horizons.
- Acoustic model is **lab-trained**, not field DMA data. Volumetric loss is an orifice heuristic.
- SPI-3 is a **z-score proxy**, not full WMO gamma SPI. Waterlogging uses a disclosed water-balance + infiltration assumption, not DEM flood-fill. GloFAS gives ~5 km cell discharge risk, **not** flooded-area polygons.
- `confidence` fields are error-derived indicators, **not** calibrated probabilities.
- The GWL processor samples telemetry files rather than loading the full multi-GB corpus.

---

## Testing

```powershell
py -m pytest fastapi_app/tests -q
```

77 tests across 10 files covering WSI weighting and stage boundaries, leak-loss caps, groundwater metrics, dataset validation (bad timestamps, missing columns, duplicates), training/serialization round-trips, decision ranking, climate math with mocked upstreams, and HTTP-level auth — including a regression test that unauthenticated prediction calls are rejected and that signup cannot self-assign `admin`.

Frontend typecheck:

```powershell
npm run lint
```

---

## Deployment

| File | Role |
|------|------|
| `fastapi_app/Dockerfile` | API image. `ai/*.pkl` are **not** baked in — mount them as a volume (see the header comment) |
| `Dockerfile` | Frontend + Express proxy. A down FastAPI returns a real `502`, never mock data |
| `docker-compose.yml` | Wires both; refuses to start without `JWT_SECRET_KEY` |
| `.github/workflows/ci.yml` | Typechecks + builds frontend, runs backend pytest on every push/PR |

```powershell
copy .env.example .env
# set JWT_SECRET_KEY, GEMINI_API_KEY, ALLOWED_ORIGINS
docker compose up --build
```

`AQUAMIND_ENVIRONMENT=production` (the compose default) disables demo seeding and enforces a real JWT secret.

---

## Project structure

```text
aquamind-ai/
├── src/                       # React UI
│   ├── pages/                 # Route-level pages (lazy-loaded)
│   ├── components/            # dashboard/executive, stress, vision, maps, ui…
│   └── services/
│       ├── apiClient.ts       # Shared fetch: attaches JWT, handles 401
│       └── jwt.ts             # Client-side expiry check
├── fastapi_app/
│   ├── main.py                # App factory, CORS, rate limiter, error handlers
│   ├── core/                  # config, security (auth deps), rate_limit, safe_paths
│   ├── routers/               # HTTP layer, one module per domain
│   ├── services/              # model_service, water_stress, vision, vision_history…
│   ├── prediction/            # Framework + trained models (reservoir, demand, stress)
│   ├── decision_engine/       # Rules + optimization
│   ├── database/              # models.py (source of truth), schema.sql (PG reference)
│   └── tests/                 # pytest suite + conftest auth fixtures
├── climate/                   # Open-Meteo clients, SPI / heat / GloFAS / ponding
├── ai/                        # Training scripts + recommendation engine
│   ├── train.py               # Trains all four models
│   ├── *.metadata.json        # Model cards — tracked
│   ├── training_curves/       # Tracked graphs
│   └── *.pkl                  # Local only (gitignored)
├── data/                      # Sample + synthetic datasets
├── Aqua Dataset/              # Large local corpus (gitignored)
├── server.ts                  # Express + /api reverse proxy
├── Dockerfile · docker-compose.yml · .github/workflows/ci.yml
└── .env.example
```

---

## Git notes

| Tracked | Local only (gitignored) |
|---------|-------------------------|
| Source, `ai/*.metadata.json`, `training_curves/` | `ai/*.pkl`, `data/*/artifacts/` |
| `data/synthetic/`, `data/geospatial/` (small) | `Aqua Dataset/`, `data/imports/` |
| `.env.example` | `.env.local`, `aquamind.db`, `.rec_cache/`, `.om_cache/` |

Metadata files write **repo-relative** paths so committed model cards never leak absolute machine paths.

**After clone:** set `.env.local` → `py ai\train.py` → start FastAPI → `npm run dev`.

---

## Scope

Hackathon / pilot build on public and lab datasets with local SQLite and optional Gemini. The models are pilots with disclosed limitations — **retrain on real utility feeds and validate against field data before using any output for operational decisions.**

## License

Private / pilot project
