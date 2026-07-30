"""Pilot data import and model transparency endpoints."""
from __future__ import annotations

import json
from pathlib import Path

import anyio
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from ai.water_shortage_model import METADATA_PATH as RESERVOIR_METADATA_PATH, WaterShortageModel
from fastapi_app.core.rate_limit import limiter
from fastapi_app.core.security import get_current_user, require_role
from pathlib import Path as _Path

_AI_DIR = _Path(__file__).resolve().parents[2] / "ai"
GW_METADATA_PATH = _AI_DIR / "groundwater_model.metadata.json"
LEAK_METADATA_PATH = _AI_DIR / "leak_detection_model.metadata.json"
DEMAND_METADATA_PATH = _AI_DIR / "water_demand_model.metadata.json"

# Reads (model transparency / metadata) only need a logged-in user; the
# mutating import-and-retrain endpoint below requires admin specifically.
router = APIRouter(tags=["Pilot Data Management"], dependencies=[Depends(get_current_user)])
PROJECT_DIR = Path(__file__).resolve().parents[2]
IMPORT_DIR = PROJECT_DIR / "data" / "imports"
REQUIRED_RESERVOIR_COLUMNS = {"Reservoir_name", "Date", "Live_capacity_FRL", "Storage"}


@router.get("/data-sources")
async def data_sources():
    """Return local, documented pilot source status; no source is presented as live."""
    inventory_path = PROJECT_DIR / "ai" / "dataset_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8")) if inventory_path.exists() else {}
    return {
        "success": True,
        "mode": "pilot",
        "sources": [
            {"name": "CWC reservoir extract", "status": "local historical file", "used_by": "one-day reservoir storage model (/predict-shortage)"},
            {"name": "NASA POWER Delhi weather", "status": "local historical file joined by date", "used_by": "shortage model temperature + rainfall deficit features (Delhi climate proxy)"},
            {"name": "CGWB groundwater wells 2000-2024", "status": "local historical file", "used_by": "groundwater well pilot model (/predict-groundwater-well)"},
            {"name": "Acoustic/pressure recordings (lab)", "status": "local labelled recordings", "used_by": "acoustic leak classifier (/detect-leak-signal)"},
            {"name": "Municipal demand training set", "status": "available", "used_by": "demand forecast model (/predict-demand)"},
            {"name": "Metered consumption feeds", "status": "optional upgrade path", "used_by": "future demand model enhancement"},
        ],
        "inventory": inventory,
    }


@router.get("/model-performance/reservoir")
async def reservoir_model_performance():
    if not RESERVOIR_METADATA_PATH.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservoir model metadata is unavailable. Run `py ai\\train.py` first.")
    return {"success": True, "model": json.loads(RESERVOIR_METADATA_PATH.read_text(encoding="utf-8"))}


@router.get("/model-performance/groundwater")
async def groundwater_model_performance():
    if not GW_METADATA_PATH.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Groundwater model metadata is unavailable. Run `py ai\\train.py` first.")
    return {"success": True, "model": json.loads(GW_METADATA_PATH.read_text(encoding="utf-8"))}


@router.get("/model-performance/leak")
async def leak_model_performance():
    if not LEAK_METADATA_PATH.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leak detection model metadata is unavailable. Run `py ai\\train.py` first.")
    return {"success": True, "model": json.loads(LEAK_METADATA_PATH.read_text(encoding="utf-8"))}


@router.get("/model-performance/demand")
async def demand_model_performance():
    if not DEMAND_METADATA_PATH.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand model metadata is unavailable. Run `py ai\\train.py` first.")
    return {"success": True, "model": json.loads(DEMAND_METADATA_PATH.read_text(encoding="utf-8"))}


@router.post("/imports/reservoir", dependencies=[require_role(["admin"])])
@limiter.limit("5/minute")
async def import_reservoir_csv(request: Request, file: UploadFile = File(...)):
    """[Admin only] Validate an admin-owned reservoir CSV, retain it locally, then retrain the pilot model.

    Previously unauthenticated: any caller could overwrite the shortage
    model's training data and trigger a synchronous retrain — a model-
    poisoning and denial-of-service vector. Now admin-gated, and the
    retrain itself runs in a worker thread so it no longer blocks the
    event loop for every other request while it fits.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a CSV file.")
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="CSV exceeds the 25 MB pilot import limit.")
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = IMPORT_DIR / "reservoir_latest.csv"
    target.write_bytes(content)
    try:
        sample = pd.read_csv(target, nrows=25)
        missing = sorted(REQUIRED_RESERVOIR_COLUMNS - set(sample.columns))
        if missing:
            target.unlink(missing_ok=True)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Missing required columns: {', '.join(missing)}")
        metadata = await anyio.to_thread.run_sync(WaterShortageModel().train)
    except HTTPException:
        raise
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Import could not train a pilot reservoir model: {exc}") from exc
    return {"success": True, "message": "Reservoir CSV imported and pilot model retrained.", "rows_checked": len(sample), "model": metadata}
