"""
Structured logging hooks for model lifecycle events.

Uses the stdlib logging module only — no ML library imports.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class LifecycleLogEvent(BaseModel):
    """Machine-readable lifecycle event payload."""

    event: str
    model_name: str
    model_version: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class PredictionLogger:
    """
    Injectable logger for training / prediction / evaluation / errors.

    Hooks are intentionally thin so future sinks (JSON logs, OpenTelemetry)
    can wrap the same methods.
    """

    def __init__(
        self,
        model_name: str = "unknown",
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self.model_name = model_name
        self._logger = logger or logging.getLogger("aquamind.prediction")

    def _emit(self, event: LifecycleLogEvent, level: int = logging.INFO) -> None:
        payload = event.model_dump(mode="json")
        self._logger.log(level, "%s", payload)

    def training_started(
        self,
        *,
        model_name: str | None = None,
        model_version: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> LifecycleLogEvent:
        event = LifecycleLogEvent(
            event="training_started",
            model_name=model_name or self.model_name,
            model_version=model_version,
            details=details or {},
        )
        self._emit(event)
        return event

    def training_completed(
        self,
        *,
        model_name: str | None = None,
        model_version: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> LifecycleLogEvent:
        event = LifecycleLogEvent(
            event="training_completed",
            model_name=model_name or self.model_name,
            model_version=model_version,
            details=details or {},
        )
        self._emit(event)
        return event

    def prediction_completed(
        self,
        *,
        model_name: str | None = None,
        model_version: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> LifecycleLogEvent:
        event = LifecycleLogEvent(
            event="prediction_completed",
            model_name=model_name or self.model_name,
            model_version=model_version,
            details=details or {},
        )
        self._emit(event)
        return event

    def evaluation_completed(
        self,
        *,
        model_name: str | None = None,
        model_version: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> LifecycleLogEvent:
        event = LifecycleLogEvent(
            event="evaluation_completed",
            model_name=model_name or self.model_name,
            model_version=model_version,
            details=details or {},
        )
        self._emit(event)
        return event

    def error(
        self,
        *,
        operation: str,
        message: str,
        model_name: str | None = None,
        model_version: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> LifecycleLogEvent:
        event = LifecycleLogEvent(
            event="error",
            model_name=model_name or self.model_name,
            model_version=model_version,
            details={"operation": operation, **(details or {})},
            error=message,
        )
        self._emit(event, level=logging.ERROR)
        return event
