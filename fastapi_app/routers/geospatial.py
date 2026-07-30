"""HTTP API for the shared national Water Assets geospatial layer."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from fastapi_app.core.security import get_current_user
from fastapi_app.geospatial.schemas import AssetType, WaterAssetsResponse
from fastapi_app.geospatial.service import GeospatialService

router = APIRouter(prefix="/api/v1/geospatial", tags=["Geospatial"], dependencies=[Depends(get_current_user)])
_service = GeospatialService()


@router.get("/assets", response_model=WaterAssetsResponse)
async def list_water_assets(
    types: str | None = Query(
        None,
        description="Comma-separated asset types: reservoir,dam,groundwater_station,demand_region,water_stress_region,leak_zone",
    ),
    state: str | None = None,
    risk_level: str | None = None,
    bbox: str | None = Query(
        None,
        description="min_lat,min_lng,max_lat,max_lng",
    ),
    q: str | None = Query(None, description="Search name/id/state"),
    limit: int | None = Query(None, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    parsed_types: list[AssetType] | None = None
    if types:
        parsed_types = []
        for part in types.split(","):
            key = part.strip()
            if not key:
                continue
            try:
                parsed_types.append(AssetType(key))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Unknown asset type: {key}") from exc

    parsed_bbox = None
    if bbox:
        try:
            parts = [float(x.strip()) for x in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("bbox needs 4 numbers")
            parsed_bbox = (parts[0], parts[1], parts[2], parts[3])
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="bbox must be min_lat,min_lng,max_lat,max_lng",
            ) from exc

    return _service.list_assets(
        types=parsed_types,
        state=state,
        risk_level=risk_level,
        bbox=parsed_bbox,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/assets/{asset_id}")
async def get_water_asset(asset_id: str):
    asset = _service.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    return {"success": True, "asset": asset}


@router.get("/reservoirs", response_model=WaterAssetsResponse)
async def list_reservoirs(
    state: str | None = None,
    risk_level: str | None = None,
    q: str | None = None,
    limit: int | None = Query(None, ge=1, le=5000),
):
    return _service.list_assets(
        types=[AssetType.reservoir],
        state=state,
        risk_level=risk_level,
        q=q,
        limit=limit,
    )
