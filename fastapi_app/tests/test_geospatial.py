"""Tests for shared geospatial water assets catalogue."""
from __future__ import annotations

from fastapi_app.geospatial.schemas import AssetType
from fastapi_app.geospatial.service import GeospatialService


def test_national_reservoir_count_in_range():
    svc = GeospatialService()
    res = svc.list_assets(types=[AssetType.reservoir])
    assert 75 <= res.total <= 150
    assert res.assets[0].lat and res.assets[0].lng
    assert res.assets[0].name
    assert res.assets[0].state


def test_resolve_forecast_proxy():
    svc = GeospatialService()
    reservoirs = svc.reservoirs()
    asset, proxy = svc.resolve_forecast_proxy(reservoirs[0].id)
    assert asset is not None
    assert proxy in {"RES-A", "RES-B", "RES-C"}


def test_filter_by_type_and_state():
    svc = GeospatialService()
    mh = svc.list_assets(types=[AssetType.reservoir], state="Maharashtra")
    assert mh.total >= 1
    assert all(a.state == "Maharashtra" for a in mh.assets)
