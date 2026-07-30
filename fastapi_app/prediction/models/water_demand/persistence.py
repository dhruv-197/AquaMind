"""Joblib-backed ModelPersistence for the demand model (framework interface)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib

from fastapi_app.prediction.framework.persistence.store import ModelPersistence
from fastapi_app.prediction.models.water_demand.constants import ARTIFACTS_DIR


class JoblibModelPersistence(ModelPersistence):
    backend_name = "joblib"

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = Path(base_dir or ARTIFACTS_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _artifact_path(self, model_name: str, model_version: str, path: str | None = None) -> Path:
        if path:
            return Path(path)
        safe_name = model_name.replace("/", "_")
        safe_version = model_version.replace("/", "_")
        return self.base_dir / f"{safe_name}__{safe_version}.joblib"

    def _meta_path(self, artifact_path: Path) -> Path:
        return artifact_path.with_suffix(".meta.json")

    def save(
        self,
        *,
        model_name: str,
        model_version: str,
        artifact: Any,
        path: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        target = self._artifact_path(model_name, model_version, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(artifact, target)
        meta = {
            "model_name": model_name,
            "model_version": model_version,
            "backend": self.backend_name,
            "uri": str(target),
            "metadata": metadata or {},
        }
        self._meta_path(target).write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        return str(target)

    def load(
        self,
        *,
        model_name: str,
        model_version: str,
        path: str | None = None,
        **kwargs: Any,
    ) -> Any:
        target = self._artifact_path(model_name, model_version, path)
        if not target.exists():
            raise FileNotFoundError(f"Model artifact not found: {target}")
        return joblib.load(target)

    def exists(
        self,
        *,
        model_name: str,
        model_version: str,
        path: str | None = None,
    ) -> bool:
        return self._artifact_path(model_name, model_version, path).exists()
