"""Climate Risk Intelligence — unit tests (offline) + API smoke."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from climate.glofas_risk import analyze_glofas_flood
from climate.heatwave import analyze_heatwave
from climate.spi_proxy import rainfall_deficit_pct, spi3_proxy
from climate.waterbalance_ponding import estimate_waterlogging


def test_spi3_proxy_classifies_dry():
    dates = []
    precip = []
    start = date(2018, 1, 1)
    for i in range(365 * 5):
        d = start + timedelta(days=i)
        dates.append(d.isoformat())
        precip.append(0.1 if i >= 365 * 5 - 90 else 3.0)

    out = spi3_proxy(dates, precip)
    assert out["spi3_proxy"] is not None
    assert out["spi3_proxy"] < 0
    assert "method" in out


def test_rainfall_deficit_positive_when_dry():
    dates, precip = [], []
    start = date(2015, 1, 1)
    for i in range(365 * 6):
        d = start + timedelta(days=i)
        dates.append(d.isoformat())
        precip.append(0.2 if i >= 365 * 6 - 90 else 4.0)
    out = rainfall_deficit_pct(dates, precip, season_days=90)
    assert out["deficit_pct"] is not None
    assert out["deficit_pct"] > 0


def test_heatwave_active():
    dates = [f"2026-05-{d:02d}" for d in range(1, 8)]
    tmax = [41.0, 42.0, 43.0, 41.5, 40.5, 41.0, 42.0]
    out = analyze_heatwave(dates, tmax)
    assert out["active"] is True
    assert out["leak_priority_multiplier"] >= 1.0


def test_waterlogging_excess():
    precip = [5.0] * 24
    sm = [0.40] * 24
    out = estimate_waterlogging(precip, sm, sm, land_class="urban")
    assert out["potential_depth_mm"] > 0
    assert out["duration_band"] != "none"
    assert out["exposure_radius_km"] == 5.0
    assert any("Not a hydrodynamic" in a for a in out["assumptions"])


def test_glofas_risk_percentile():
    history = list(range(1, 91))
    forecast = [95] * 30
    payload = {
        "daily": {
            "time": [f"d{i}" for i in range(120)],
            "river_discharge": history + forecast,
        },
        "latitude": 28.6,
        "longitude": 77.2,
    }
    out = analyze_glofas_flood(payload)
    assert out["risk_class"] in ("elevated", "high", "extreme", "watch", "low")
    assert out["peak_m3s"] == 95
    assert "not" in out["method"].lower()


def test_presets_endpoint(auth_client):
    res = auth_client.get("/climate-risk/presets")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert len(body["presets"]) >= 1
    assert "lat" in body["presets"][0]


def test_analyze_with_mocked_upstreams():
    from fastapi_app.services.climate_risk_service import analyze_location

    forecast = {
        "_from_cache": False,
        "daily": {
            "time": [f"2026-07-{d:02d}" for d in range(1, 15)],
            "precipitation_sum": [2.0] * 14,
            "temperature_2m_max": [39.0] * 14,
            "temperature_2m_min": [28.0] * 14,
            "et0_fao_evapotranspiration": [5.0] * 14,
        },
        "hourly": {
            "precipitation": [1.0] * 48,
            "soil_moisture_0_to_7cm": [0.25] * 48,
            "soil_moisture_7_to_28cm": [0.28] * 48,
        },
    }
    start = date(2014, 1, 1)
    a_dates, a_precip, a_tmax, a_et = [], [], [], []
    for i in range(365 * 11):
        d = start + timedelta(days=i)
        a_dates.append(d.isoformat())
        a_precip.append(3.0)
        a_tmax.append(35.0)
        a_et.append(4.5)
    archive = {
        "_from_cache": False,
        "daily": {
            "time": a_dates,
            "precipitation_sum": a_precip,
            "temperature_2m_max": a_tmax,
            "temperature_2m_min": [22.0] * len(a_dates),
            "et0_fao_evapotranspiration": a_et,
        },
    }
    flood = {
        "_from_cache": False,
        "latitude": 28.61,
        "longitude": 77.21,
        "daily": {
            "time": [f"d{i}" for i in range(120)],
            "river_discharge": list(range(1, 91)) + [40] * 30,
        },
    }

    with (
        patch(
            "fastapi_app.services.climate_risk_service.fetch_forecast",
            new_callable=AsyncMock,
            return_value=forecast,
        ),
        patch(
            "fastapi_app.services.climate_risk_service.fetch_archive",
            new_callable=AsyncMock,
            return_value=archive,
        ),
        patch(
            "fastapi_app.services.climate_risk_service.fetch_flood",
            new_callable=AsyncMock,
            return_value=flood,
        ),
    ):
        result = asyncio.run(
            analyze_location(28.6139, 77.2090, label="Delhi NCT", land_class="urban")
        )

    assert result["success"] is True
    assert result["provenance"]["sources"]
    assert "flood" in result
    assert "waterlogging" in result
    assert result["recommendations"]
    assert result["links"]["shortage"] == "/shortage"


if __name__ == "__main__":
    from fastapi.testclient import TestClient
    from fastapi_app.main import app

    test_spi3_proxy_classifies_dry()
    test_rainfall_deficit_positive_when_dry()
    test_heatwave_active()
    test_waterlogging_excess()
    test_glofas_risk_percentile()
    test_presets_endpoint(TestClient(app))
    test_analyze_with_mocked_upstreams()
    print("All climate risk tests passed.")
