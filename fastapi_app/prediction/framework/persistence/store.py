"""
Model persistence interface.

Future implementations may use joblib, pickle, MLflow, or cloud object storage.
This module deliberately does not choose a backend.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, Field


class PersistenceManifest(BaseModel):
    """Descriptor returned after a successful save."""

    model_name: str
    model_version: str
    uri: str
    backend: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelPersistence(ABC):
    """Abstract artifact store injected into BaseModelPredictor."""

    backend_name: str = "abstract"

    @abstractmethod
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
        """
        Persist an artifact and return a URI / path string.

        Raises NotImplementedError until a concrete backend is provided.
        """

    @abstractmethod
    def load(
        self,
        *,
        model_name: str,
        model_version: str,
        path: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Load an artifact by name/version or explicit path."""

    @abstractmethod
    def exists(
        self,
        *,
        model_name: str,
        model_version: str,
        path: str | None = None,
    ) -> bool:
        """Return True if an artifact is available for the given identity."""

    def delete(
        self,
        *,
        model_name: str,
        model_version: str,
        path: str | None = None,
    ) -> None:
        """Optional delete — default raises until a backend supports it."""
        raise NotImplementedError(
            f"{type(self).__name__}.delete is not implemented"
        )


class UnconfiguredModelPersistence(ModelPersistence):
    """
    Placeholder backend used when no store is wired.

    Ensures callers get a clear NotImplementedError rather than a silent no-op.
    """

    backend_name = "unconfigured"

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
        raise NotImplementedError(
            "ModelPersistence backend not configured "
            "(choose joblib / pickle / MLflow / cloud later)."
        )

    def load(
        self,
        *,
        model_name: str,
        model_version: str,
        path: str | None = None,
        **kwargs: Any,
    ) -> Any:
        raise NotImplementedError(
            "ModelPersistence backend not configured "
            "(choose joblib / pickle / MLflow / cloud later)."
        )

    def exists(
        self,
        *,
        model_name: str,
        model_version: str,
        path: str | None = None,
    ) -> bool:
        return False
