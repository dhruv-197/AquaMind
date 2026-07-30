"""Load and query the shared water_assets.json catalogue."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from .schemas import AssetType, WaterAsset

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "geospatial" / "water_assets.json"


class WaterAssetsRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_PATH
        self._version = "0.0.0"
        self._updated_at: str | None = None
        self._counts: dict[str, int] = {}
        self._assets: list[WaterAsset] = []
        self.reload()

    def reload(self) -> None:
        if not self.path.exists():
            logger.warning("Water assets file missing: %s", self.path)
            self._assets = []
            self._counts = {}
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self._version = str(raw.get("version") or "1.0.0")
        self._updated_at = raw.get("updated_at")
        self._counts = dict(raw.get("counts") or {})
        assets: list[WaterAsset] = []
        for row in raw.get("assets") or []:
            try:
                assets.append(WaterAsset.model_validate(row))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Skipping invalid asset row: %s (%s)", row.get("id"), exc)
        self._assets = assets
        if not self._counts:
            self._counts = {"total": len(assets)}
            for t in AssetType:
                self._counts[t.value] = sum(1 for a in assets if a.type == t)

    @property
    def version(self) -> str:
        return self._version

    @property
    def updated_at(self) -> str | None:
        return self._updated_at

    @property
    def counts(self) -> dict[str, int]:
        return dict(self._counts)

    def all(self) -> list[WaterAsset]:
        return list(self._assets)

    def by_id(self, asset_id: str) -> WaterAsset | None:
        for a in self._assets:
            if a.id == asset_id:
                return a
        return None

    def filter(
        self,
        *,
        types: Iterable[AssetType] | None = None,
        state: str | None = None,
        risk_level: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[WaterAsset]:
        rows = self._assets
        if types:
            allowed = set(types)
            rows = [a for a in rows if a.type in allowed]
        if state:
            s = state.strip().lower()
            rows = [a for a in rows if (a.state or "").lower() == s]
        if risk_level:
            r = risk_level.strip().lower()
            rows = [a for a in rows if (a.risk_level or "").lower() == r]
        if bbox:
            min_lat, min_lng, max_lat, max_lng = bbox
            rows = [
                a
                for a in rows
                if min_lat <= a.lat <= max_lat and min_lng <= a.lng <= max_lng
            ]
        if q:
            needle = q.strip().lower()
            rows = [
                a
                for a in rows
                if needle in a.name.lower()
                or needle in a.id.lower()
                or needle in (a.state or "").lower()
            ]
        if offset:
            rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]
        return rows


@lru_cache(maxsize=1)
def get_repository() -> WaterAssetsRepository:
    return WaterAssetsRepository()
