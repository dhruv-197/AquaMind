"""Unit tests for climate-linked groundwater outlook helpers."""
from __future__ import annotations

from datetime import date

from fastapi_app.services.groundwater_outlook import (
    build_depth_series,
    climate_adjusted_rate,
)


def test_climate_adjusted_rate_increases_with_deficit_and_heat():
    base = 2.0
    dry = climate_adjusted_rate(
        base,
        rainfall_deficit_pct=40.0,
        heatwave_active=True,
        gw_climate_stress_0_100=80.0,
    )
    wet = climate_adjusted_rate(
        base,
        rainfall_deficit_pct=-20.0,
        heatwave_active=False,
        gw_climate_stress_0_100=0.0,
    )
    assert dry > base
    assert wet < base
    assert dry > wet


def test_climate_adjusted_rate_clamps():
    huge = climate_adjusted_rate(
        50.0,
        rainfall_deficit_pct=80.0,
        heatwave_active=True,
        gw_climate_stress_0_100=100.0,
    )
    tiny = climate_adjusted_rate(
        -10.0,
        rainfall_deficit_pct=-50.0,
        heatwave_active=False,
        gw_climate_stress_0_100=0.0,
    )
    assert huge == 12.0
    assert tiny == -2.0


def test_build_depth_series_shape_and_join():
    series = build_depth_series(
        current_depth_m=25.0,
        historical_rate_m_year=1.2,
        forecast_rate_m_year=2.4,
        as_of=date(2026, 8, 1),
        past_months=30,
        future_months=18,
    )
    # past + join + future
    assert len(series) == 30 + 1 + 18

    hist = [p for p in series if p["historical"] is not None and p["forecast"] is None]
    join = [p for p in series if p["historical"] is not None and p["forecast"] is not None]
    fut = [p for p in series if p["historical"] is None and p["forecast"] is not None]

    assert len(hist) == 30
    assert len(join) == 1
    assert len(fut) == 18
    assert join[0]["historical"] == 25.0
    assert join[0]["forecast"] == 25.0
    assert join[0]["date"] == "2026-08"

    # Deeper over time under positive depletion (m bgl increases).
    assert fut[-1]["forecast"] > join[0]["forecast"]
    assert hist[0]["historical"] < join[0]["historical"]
