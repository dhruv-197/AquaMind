"""Pilot data import and model transparency endpoints."""
from __future__ import annotations

import json
from pathlib import Path

import anyio
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from ai.water_shortage_model import WaterShortageModel
from fastapi_app.core.rate_limit import limiter
from fastapi_app.core.security import get_current_user, require_role
from fastapi_app.services.model_card_service import (
    PERFORMANCE_ALIASES,
    build_model_status,
    public_model_card,
)

# Reads (model transparency / metadata) only need a logged-in user; the
# mutating import-and-retrain endpoint below requires admin specifically.
router = APIRouter(tags=["Pilot Data Management"], dependencies=[Depends(get_current_user)])
PROJECT_DIR = Path(__file__).resolve().parents[2]
IMPORT_DIR = PROJECT_DIR / "data" / "imports"
REQUIRED_RESERVOIR_COLUMNS = {"Reservoir_name", "Date", "Live_capacity_FRL", "Storage"}


def _performance_payload(alias: str) -> dict:
    model_id = PERFORMANCE_ALIASES.get(alias)
    if not model_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown model.")
    card = public_model_card(model_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{alias} model metadata is unavailable. Run `py ai/train.py` first.",
        )
    return {"success": True, "model": card}


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
            {"name": "Municipal demand training set", "status": "synthetic labels (pilot)", "used_by": "demand forecast model (/predict-demand)"},
            {"name": "Metered consumption feeds", "status": "optional upgrade path", "used_by": "future demand model enhancement"},
        ],
        "inventory": inventory,
    }


@router.get("/model-performance/reservoir")
async def reservoir_model_performance():
    return _performance_payload("reservoir")


@router.get("/model-performance/groundwater")
async def groundwater_model_performance():
    return _performance_payload("groundwater")


@router.get("/model-performance/leak")
async def leak_model_performance():
    return _performance_payload("leak")


@router.get("/model-performance/demand")
async def demand_model_performance():
    return _performance_payload("demand")


@router.get(
    "/api/v1/models/{model_id}/status",
    summary="Path-free model status card for technical review",
)
async def model_status(model_id: str):
    """Consistent status: loaded, metrics, baselines, limitations — no filesystem paths."""
    resolved = PERFORMANCE_ALIASES.get(model_id, model_id)
    if resolved not in {
        "water_shortage",
        "groundwater",
        "water_demand",
        "leak_detection",
    }:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown model_id.")
    return {"success": True, "data": build_model_status(resolved)}


@router.post("/imports/reservoir", dependencies=[require_role(["admin"])])
@limiter.limit("5/minute")
async def import_reservoir_csv(request: Request, file: UploadFile = File(...)):
    """[Admin only] Validate an admin-owned reservoir CSV, retain it locally, then retrain the pilot model."""
    import io
    import tempfile

    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a CSV file.")
    # Never use the client filename as a filesystem path — fixed destination only.
    content = await file.read(25 * 1024 * 1024 + 1)
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="CSV exceeds the 25 MB pilot import limit.",
        )
    if not content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file is empty.")

    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = IMPORT_DIR / "reservoir_latest.csv"
    try:
        sample = pd.read_csv(io.BytesIO(content), nrows=25)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Malformed CSV. Ensure a valid comma-separated header row.",
        )
    missing = sorted(REQUIRED_RESERVOIR_COLUMNS - set(sample.columns))
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required columns: {', '.join(missing)}",
        )

    # Write via temp file then replace — avoid partial/corrupt retained uploads.
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=IMPORT_DIR,
            prefix=".reservoir_import_",
            suffix=".csv",
            delete=False,
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        tmp_path.replace(target)
        metadata = await anyio.to_thread.run_sync(WaterShortageModel().train)
    except HTTPException:
        raise
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Import could not train a pilot reservoir model.",
        ) from exc
    return {
        "success": True,
        "message": "Reservoir CSV imported and pilot model retrained.",
        "rows_checked": len(sample),
        "model": metadata,
    }
