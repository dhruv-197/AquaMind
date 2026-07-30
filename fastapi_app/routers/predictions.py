from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from fastapi_app.core.security import get_current_user
from fastapi_app.database.connection import get_db
from fastapi_app.schemas import (
    ShortagePredictionRequest, ShortagePredictionResponse, ShortagePredictionData,
    GroundwaterPredictionRequest, GroundwaterPredictionResponse, GroundwaterPredictionData,
    GroundwaterWellRequest, GroundwaterWellResponse, GroundwaterWellData,
    DemandPredictionRequest, DemandPredictionResponse, DemandPredictionData,
    LeakDetectionRequest, LeakDetectionResponse, LeakDetectionData,
    LeakSignalResponse, LeakSignalData,
)
from fastapi_app.services.model_service import model_service
from fastapi_app.services.prediction_store import persist_prediction
import io
import pandas as pd

router = APIRouter(tags=["Machine Learning Predictions & Diagnostics"], dependencies=[Depends(get_current_user)])

# 1. Predict Water Shortage Risk
@router.post(
    "/predict-shortage",
    response_model=ShortagePredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Pilot one-day reservoir storage risk forecast",
    description=(
        "Uses CWC March 2024 reservoir storage plus Delhi NASA POWER weather joined by date "
        "(temperature_c, rainfall anomaly as rainfall_deficit_pct) to forecast next-day storage. "
        "daily_demand_mgd applies a transparent post-model demand-stress adjustment. "
        "Optional day_of_month sets the calendar-day feature used by the trained model."
    ),
)
async def predict_shortage(payload: ShortagePredictionRequest, db: Session = Depends(get_db)):
    try:
        inputs = payload.model_dump()
        result = model_service.predict_shortage(
            reservoir_capacity_pct=payload.reservoir_capacity_pct,
            rainfall_deficit_pct=payload.rainfall_deficit_pct,
            temperature_c=payload.temperature_c,
            daily_demand_mgd=payload.daily_demand_mgd,
            day_of_month=payload.day_of_month,
        )
        persist_prediction(
            db,
            model_name="water_shortage",
            inputs=inputs,
            results=result,
            confidence=result.get("confidence"),
        )
        return ShortagePredictionResponse(
            data=ShortagePredictionData(**result)
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Shortage model inference failed: {str(e)}")


# 2. Predict Groundwater (legacy formula-based, kept for backward compat)
@router.post(
    "/predict-groundwater",
    response_model=GroundwaterPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="[Legacy] Groundwater scenario calculator (not a trained model)",
    description="Formula-based scenario calculator. Use /predict-groundwater-well for the dataset-backed CGWB model."
)
async def predict_groundwater(payload: GroundwaterPredictionRequest, db: Session = Depends(get_db)):
    try:
        inputs = payload.model_dump()
        result = model_service.predict_groundwater(
            initial_depth_m=payload.initial_depth_m,
            annual_rainfall_mm=payload.annual_rainfall_mm,
            pumping_extraction_mld=payload.pumping_extraction_mld,
            aquifer_recharge_factor=payload.aquifer_recharge_factor,
            soil_porosity_idx=payload.soil_porosity_idx
        )
        persist_prediction(db, model_name="groundwater_legacy", inputs=inputs, results=result)
        return GroundwaterPredictionResponse(
            message="Groundwater scenario calculator (not a trained model). Use /predict-groundwater-well for dataset-backed predictions.",
            data=GroundwaterPredictionData(**result)
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Groundwater scenario failed: {str(e)}")


# 2b. Predict Groundwater Well (CGWB dataset-backed model)
@router.post(
    "/predict-groundwater-well",
    response_model=GroundwaterWellResponse,
    status_code=status.HTTP_200_OK,
    summary="CGWB historical well data pilot — next observation depth forecast",
    description=(
        "Predicts the next observed water-table depth using a RandomForestRegressor "
        "trained on CGWB 2000–2024 well observations (22,399 wells, 1.1M samples). "
        "Temporal split: train ≤2019, validation 2020–2022, test ≥2023. "
        "Test MAE ~3.6 m, RMSE ~10.4 m. "
        "PILOT: historical data only. Not a municipal aquifer-control model."
    )
)
async def predict_groundwater_well(payload: GroundwaterWellRequest, db: Session = Depends(get_db)):
    try:
        inputs = payload.model_dump()
        result = model_service.predict_groundwater_well(inputs)
        persist_prediction(
            db,
            model_name="groundwater_well",
            inputs=inputs,
            results=result,
            confidence=result.get("confidence"),
        )
        return GroundwaterWellResponse(data=GroundwaterWellData(**result))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Groundwater well model failed: {str(e)}")


# 3. Predict Water Demand
@router.post(
    "/predict-demand",
    response_model=DemandPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Water demand forecast (synthetic-label pilot)",
    description=(
        "RandomForest demand forecast from climate and calendar features. "
        "Training labels are synthetic (see ai/water_demand_model.metadata.json) — "
        "R² reflects recovery of the generator, not AMI validation. "
        "Population and industrial index (0–100) scale the prediction."
    ),
)
async def predict_demand(payload: DemandPredictionRequest, db: Session = Depends(get_db)):
    try:
        inputs = payload.model_dump()
        result = model_service.predict_demand(
            population_thousands=payload.population_thousands,
            temperature_c=payload.temperature_c,
            industrial_activity_idx=payload.industrial_activity_idx,
            is_weekend=payload.is_weekend,
            is_heatwave=payload.is_heatwave
        )
        persist_prediction(
            db,
            model_name="water_demand",
            inputs=inputs,
            results=result,
            confidence=result.get("confidence"),
        )
        return DemandPredictionResponse(
            message="Demand forecast completed (synthetic-label pilot).",
            data=DemandPredictionData(**result)
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Water demand forecast failed: {str(e)}")


# 4. Detect Leak (legacy, redirects to signal upload)
@router.post(
    "/detect-leak",
    response_model=LeakDetectionResponse,
    status_code=status.HTTP_200_OK,
    summary="[Legacy] Manual-field leak endpoint — use /detect-leak-signal instead",
    description="This legacy endpoint does not use the trained acoustic classifier. Upload a raw signal CSV via /detect-leak-signal to use the trained model."
)
async def detect_leak(payload: LeakDetectionRequest):
    try:
        result = model_service.detect_leak(
            pressure_bar=payload.pressure_bar,
            pressure_drop_bar=payload.pressure_drop_bar,
            acoustic_vibration_db=payload.acoustic_vibration_db,
            flow_velocity_m_s=payload.flow_velocity_m_s,
            frequency_spike_hz=payload.frequency_spike_hz
        )
        return LeakDetectionResponse(data=LeakDetectionData(**result))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Leak detection failed: {str(e)}")


# 4b. Detect Leak from Signal CSV upload
@router.post(
    "/detect-leak-signal",
    response_model=LeakSignalResponse,
    status_code=status.HTTP_200_OK,
    summary="Acoustic signal classifier — upload a raw signal CSV (Sample, Value columns)",
    description=(
        "Accepts a CSV file with Sample and Value columns (raw acoustic signal). "
        "Extracts 13 statistical and spectral features and classifies as Leak/No-Leak "
        "using an ExtraTreesClassifier trained on lab acoustic recordings. "
        "Group-aware split; see ai/leak_detection_model.metadata.json for metrics. "
        "Lab-trained PILOT — field verification required. "
        "Volumetric loss is an orifice heuristic, not a learned label."
    )
)
async def detect_leak_signal(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted.")
    try:
        content = await file.read()
        # Match training: only the first 24k rows are used for windowed features.
        df = pd.read_csv(io.BytesIO(content), nrows=24000)
        if "Value" not in df.columns:
            raise HTTPException(status_code=422, detail="CSV must have a 'Value' column with raw signal samples.")
        signal_values = pd.to_numeric(df["Value"], errors="coerce").dropna().tolist()
        if len(signal_values) < 100:
            raise HTTPException(status_code=422, detail=f"Signal too short ({len(signal_values)} samples); need at least 100.")
        result = model_service.detect_leak_signal(signal_values)
        persist_prediction(
            db,
            model_name="leak_detection_signal",
            inputs={"filename": file.filename, "n_samples": len(signal_values)},
            results=result,
            confidence=float(result.get("leak_probability") or 0.0),
        )
        return LeakSignalResponse(data=LeakSignalData(**result))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal classification failed: {str(e)}")
