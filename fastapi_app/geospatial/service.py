"""Geospatial query service over the shared water assets catalogue."""

from __future__ import annotations

from .repository import WaterAssetsRepository, get_repository
from .schemas import AssetType, WaterAsset, WaterAssetsResponse


class GeospatialService:
    def __init__(self, repo: WaterAssetsRepository | None = None) -> None:
        self.repo = repo or get_repository()

    def list_assets(
        self,
        *,
        types: list[AssetType] | None = None,
        state: str | None = None,
        risk_level: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> WaterAssetsResponse:
        assets = self.repo.filter(
            types=types,
            state=state,
            risk_level=risk_level,
            bbox=bbox,
            q=q,
            limit=limit,
            offset=offset,
        )
        return WaterAssetsResponse(
            success=True,
            version=self.repo.version,
            updated_at=self.repo.updated_at,
            counts=self.repo.counts,
            total=len(assets),
            assets=assets,
            message=f"{len(assets)} assets",
        )

    def get_asset(self, asset_id: str) -> WaterAsset | None:
        return self.repo.by_id(asset_id)

    def reservoirs(self) -> list[WaterAsset]:
        return self.repo.filter(types=[AssetType.reservoir])

    def resolve_forecast_proxy(self, asset_id: str) -> tuple[WaterAsset | None, str | None]:
        """Map a national asset id → ML catalog proxy (RES-A/B/C)."""
        asset = self.repo.by_id(asset_id)
        if asset is None:
            return None, None
        proxy = None
        if asset.meta:
            proxy = asset.meta.get("forecast_proxy_id") or asset.meta.get("parent_reservoir_id")
        if isinstance(proxy, str) and proxy:
            return asset, proxy
        # Stable fallback
        return asset, ("RES-A", "RES-B", "RES-C")[hash(asset.id) % 3]
