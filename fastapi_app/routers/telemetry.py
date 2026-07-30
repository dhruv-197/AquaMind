"""Hydrological GIS telemetry & analytics endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from fastapi_app.core.security import get_current_user
from fastapi_app.database.connection import get_db
from fastapi_app.database.models import (
    Alert,
    ConsumptionSeries,
    Groundwater,
    Reservoir,
    SensorData,
)

router = APIRouter(tags=["Hydrological GIS Telemetry & Analytics"], dependencies=[Depends(get_current_user)])


@router.get("/telemetry/sensors")
async def get_sensors(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Fetches telemetry sensors from the database (paginated).
    Note: sensor rows are demo-seeded unless replaced by a utility feed.
    """
    total = db.query(SensorData).count()
    sensors_list = (
        db.query(SensorData)
        .order_by(SensorData.last_updated.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "success": True,
        "demo": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "sensors": [
            {
                "id": s.id,
                "name": s.name,
                "type": s.type,
                "status": s.status,
                "value": s.value,
                "unit": s.unit,
                "batteryLevel": s.battery_level,
                "pipeId": s.pipe_id,
                "lastUpdated": s.last_updated.isoformat() if s.last_updated else None,
                "location": {
                    "lat": s.lat,
                    "lng": s.lng,
                    "address": s.address,
                    "zone": s.zone,
                },
            }
            for s in sensors_list
        ],
    }


@router.get("/analytics/leakages")
async def get_leakages(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Fetches leak anomalies / warnings (paginated).
    Seeded alerts are labeled demo=true. Acoustic model uploads write Prediction rows
    used by the Water Stress Index live leak component.
    """
    total = db.query(Alert).count()
    alerts_list = (
        db.query(Alert)
        .order_by(Alert.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "success": True,
        "demo": True,
        "source": "demo_seeded_alerts",
        "note": (
            "These rows are seeded for dashboard demos. For model-backed leak probability, "
            "upload an acoustic CSV on the Leak Detection page (/detect-leak-signal)."
        ),
        "total": total,
        "limit": limit,
        "offset": offset,
        "alerts": [
            {
                "id": a.id,
                "sensorId": a.sensor_id,
                "locationName": a.location_name,
                "lat": a.lat,
                "lng": a.lng,
                "zone": a.zone,
                "pipeMaterial": a.pipe_material,
                "pipeAgeYears": a.pipe_age_years,
                "detectedFlowDropPercent": a.detected_flow_drop_pct,
                "anomalyScore": a.anomaly_score,
                "estimatedWaterLossLpm": a.estimated_water_loss_lpm,
                "severity": a.severity,
                "status": a.status,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                "aiDiagnostics": a.ai_diagnostics,
                "demo": True,
            }
            for a in alerts_list
        ],
    }


@router.get("/analytics/groundwater")
async def get_groundwater(
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """CGWB well points with real lat/lng when synced from Aqua Dataset."""
    q = db.query(Groundwater).filter(
        Groundwater.location_lat.isnot(None),
        Groundwater.location_lng.isnot(None),
    )
    total = q.count()
    gw_list = q.offset(offset).limit(limit).all()
    return {
        "success": True,
        "source": (gw_list[0].data_source if gw_list and gw_list[0].data_source else "database"),
        "total": total,
        "limit": limit,
        "offset": offset,
        "aquifers": [
            {
                "id": g.id,
                "name": g.name,
                "depthToWaterM": g.depth_to_water_m,
                "depletionRateMYear": g.depletion_rate_m_year,
                "rechargeRateMYear": g.recharge_rate_m_year,
                "storageVolumeMcm": g.storage_volume_mcm,
                "safeYieldMcm": g.safe_yield_mcm,
                "projectedDepletionYear": g.projected_depletion_year,
                "soilMoistureIndex": g.soil_moisture_index,
                "lat": g.location_lat,
                "lng": g.location_lng,
                "state": g.state,
                "dataSource": g.data_source,
                "observedAt": g.observed_at,
            }
            for g in gw_list
        ],
    }


@router.get("/analytics/shortage-risks")
async def get_shortage_risks(
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Reservoir markers from CWC CSV sync (real coords + storage %)."""
    total = db.query(Reservoir).count()
    reservoirs_list = db.query(Reservoir).offset(offset).limit(limit).all()
    return {
        "success": True,
        "source": (
            reservoirs_list[0].data_source
            if reservoirs_list and reservoirs_list[0].data_source
            else "database"
        ),
        "total": total,
        "limit": limit,
        "offset": offset,
        "risks": [
            {
                "id": f"RSV-{r.id}",
                "name": r.name,
                "capacity": r.capacity_mcm,
                "currentLevel": r.current_level_pct,
                "coordinates": [r.location_lat, r.location_lng],
                # Pilot heuristic only — not a calibrated days-of-supply model.
                "estimatedDaysRemaining": int(r.current_level_pct * 1.5) + 7,
                "daysRemainingMethod": "heuristic_pilot_not_calibrated",
                "severity": (
                    "critical"
                    if r.current_level_pct < 35
                    else "warning"
                    if r.current_level_pct < 60
                    else "low"
                ),
                "dataSource": r.data_source,
                "observedAt": r.observed_at,
            }
            for r in reservoirs_list
        ],
    }


@router.get("/analytics/consumption")
async def get_consumption(
    db: Session = Depends(get_db),
    region_id: str = Query("REG-1"),
    limit: int = Query(30, ge=1, le=365),
):
    """Daily municipal consumption / demand proxy series (MGD)."""
    rows = (
        db.query(ConsumptionSeries)
        .filter(ConsumptionSeries.region_id == region_id)
        .order_by(ConsumptionSeries.observed_date.desc())
        .limit(limit)
        .all()
    )
    return {
        "success": True,
        "region_id": region_id,
        "source": rows[0].source if rows else "empty",
        "note": (
            "Pilot consumption series for WSI / shortage demand inputs. "
            "Replace with AMI or billed DMA metered data for production."
        ),
        "series": [
            {
                "date": r.observed_date.isoformat(),
                "demand_mgd": r.demand_mgd,
                "population_thousands": r.population_thousands,
                "source": r.source,
            }
            for r in reversed(rows)
        ],
    }


@router.get("/regions")
async def get_regions():
    """Registered municipal monitoring zones."""
    return {
        "success": True,
        "regions": [
            {"id": "REG-1", "name": "Delhi NCT Metro Division"},
            {"id": "REG-2", "name": "Mumbai H-West Ward Division"},
            {"id": "REG-3", "name": "Bengaluru East Tech Grid"},
            {"id": "REG-4", "name": "Thar Desert Hydro Basin"},
            {"id": "REG-5", "name": "Maharashtra Latur Division"},
        ],
    }
