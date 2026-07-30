# AquaMind Prediction Framework

Shared ML infrastructure for every future AquaMind prediction model.

**This package is framework-only.** It does not train models, does not import
TensorFlow / PyTorch / XGBoost, and does not implement forecasting algorithms.

---

## Folder structure

```
fastapi_app/prediction/
├── framework/
│   ├── datasets/           # Dataset, TrainingDataset, PredictionDataset
│   ├── features/           # FeaturePipeline + stage interfaces
│   ├── lifecycle/          # BaseModelPredictor (train/predict/evaluate/save/load/…)
│   ├── registry/           # ModelRegistry (dynamic string-key registration)
│   ├── schemas/            # UniversalPredictionOutput, TrainingConfiguration
│   ├── evaluation/         # MAE / RMSE / MAPE / R² / CustomMetric interfaces
│   ├── persistence/        # ModelPersistence ABC (backend undecided)
│   ├── logging/            # Structured lifecycle hooks
│   ├── adapters.py         # Bridge → Decision Engine PredictionOutput
│   ├── placeholders.py     # Untrained reserved model keys
│   └── FRAMEWORK.md        # This document
├── base.py                 # Service-layer Predictor (dashboard stubs)
├── registry.py             # PredictionType-keyed service registry
└── <domain>_*.py           # Stub service predictors (no ML)
```

Two registries coexist on purpose:

| Registry | Key type | Purpose |
|----------|----------|---------|
| `ModelRegistry` | `"reservoir_forecast"` | ML lifecycle models (framework) |
| `PredictionRegistry` | `PredictionType` enum | Decision Intelligence service stubs |

The **dashboard must resolve ML models only through `ModelRegistry` (DI)**.

---

## How future models plug in

1. **Subclass** `BaseModelPredictor`.
2. **Implement** `_train`, `_predict`, and optionally `_evaluate`.
3. **Inject** `FeaturePipeline`, `ModelPersistence`, and `PredictionLogger` via the constructor.
4. **Return** only `UniversalPredictionOutput` from `_predict`.
5. **Register** the instance — never construct it inside a router:

```python
from fastapi_app.prediction.framework.lifecycle.predictor import BaseModelPredictor
from fastapi_app.prediction.framework.registry.model_registry import ModelRegistry

class ReservoirForecastModel(BaseModelPredictor):
    def _train(self, dataset, config):
        ...  # future algorithm

    def _predict(self, dataset, *, prediction_horizon, **kwargs):
        ...  # must return UniversalPredictionOutput

# At composition root / DI (e.g. core/dependencies.py):
registry = ModelRegistry()
registry.register("reservoir_forecast", ReservoirForecastModel(model_name="reservoir_forecast"))
```

6. **Map to Decision Engine** (if needed) with `framework.adapters.to_decision_output`.

Reserved product keys (pre-registered as untrained placeholders):

- `water_demand`
- `reservoir_forecast`
- `leakage_risk`
- `water_stress`
- `flood`
- `drought`

Replace a placeholder by calling `registry.register(name, trained_instance)` (override allowed by default).

---

## Lifecycle

```
                    ┌─────────────────────┐
                    │ TrainingConfiguration│
                    └──────────┬──────────┘
                               │
 TrainingDataset ──► train() ──┤
                               ▼
                     is_trained() == True
                               │
                               ├──► save() ──► ModelPersistence
                               │
 PredictionDataset ─► predict() ──► UniversalPredictionOutput
                               │
 TrainingDataset ──► evaluate() ──► metric dict (via EvaluationSuite)
                               │
                     load() ◄── ModelPersistence
                               │
                     metadata() / version()
```

Required methods on every model:

| Method | Role |
|--------|------|
| `train()` | Fit; wraps `_train` + logging |
| `predict()` | Infer; returns `UniversalPredictionOutput` |
| `evaluate()` | Score against labels |
| `save()` / `load()` | Delegate to injected `ModelPersistence` |
| `metadata()` | Audit / registry payload |
| `version()` | Current model version string |
| `is_trained()` | Whether a fit/load has succeeded |

Unimplemented hooks raise `NotImplementedError`.

---

## Dependency flow

```
Dashboard / API router
        │
        │  Depends(get_model_registry)   ← never `Model()` in the route
        ▼
   ModelRegistry.get("reservoir_forecast")
        │
        ▼
   BaseModelPredictor
        ├── FeaturePipeline  (extraction → missing → window → normalize → validate)
        ├── TrainingConfiguration
        ├── ModelPersistence (joblib | pickle | MLflow | cloud — chosen later)
        └── PredictionLogger
                │
                ▼
   UniversalPredictionOutput
                │
                │  adapters.to_decision_output()
                ▼
   Decision Engine  →  Recommendations / Risk / Actions
```

FastAPI injection alias:

```python
from fastapi_app.core.dependencies import ModelRegistryDep

@router.get("/models")
async def list_models(registry: ModelRegistryDep):
    return registry.metadata()
```

---

## Architecture diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Water Decision Intelligence                       │
│                                                                       │
│  Data Sources → Processing → [Prediction Framework] → Decision Engine │
│                                       │                               │
│                                       ▼                               │
│                          Dashboard API (/api/v1/dashboard)            │
└──────────────────────────────────────────────────────────────────────┘

                    Prediction Framework (detail)
┌─────────────────────────────────────────────────────────────────────┐
│  Datasets          FeaturePipeline         BaseModelPredictor       │
│  • Dataset         • extract               • train / predict        │
│  • TrainingDataset • missing values        • evaluate               │
│  • PredictionDataset • time windows        • save / load            │
│                    • normalize             • metadata / version     │
│                    • validate                                       │
│                                                                     │
│  TrainingConfiguration          UniversalPredictionOutput           │
│  EvaluationMetric (MAE/…)       ModelPersistence (abstract)         │
│  PredictionLogger               ModelRegistry.register(name, model) │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Universal prediction output

Every model returns:

| Field | Description |
|-------|-------------|
| `prediction_id` | UUID for the event |
| `model_name` | Registry key |
| `model_version` | Version stamp |
| `generated_at` | UTC timestamp |
| `prediction_horizon` | Horizon (typically days) |
| `confidence_score` | Optional `[0, 1]` |
| `prediction` | Scalar / list / dict payload |
| `risk_level` | `low \| moderate \| high \| critical \| unknown` |
| `metadata` | Extensible bag |

---

## Constraints (do not violate)

- Do **not** train models inside this framework package.
- Do **not** import TensorFlow, PyTorch, or XGBoost here.
- Do **not** put model-specific feature logic in shared feature stages.
- Do **not** instantiate models in routers — use `ModelRegistry` via DI.
- Persistence backend is **intentionally unset**; inject a concrete store later.
