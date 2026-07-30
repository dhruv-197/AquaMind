"""Composable feature pipeline orchestrator (interfaces only)."""
from __future__ import annotations

from typing import Sequence

import pandas as pd

from fastapi_app.prediction.framework.datasets.base import Dataset
from fastapi_app.prediction.framework.features.stages import FeatureStage, FeatureStageResult


class FeaturePipeline:
    """
    Ordered chain of FeatureStage instances.

    Injectable into predictors. Contains no model-specific logic.
    Concrete stages are supplied by callers / DI.
    """

    def __init__(self, stages: Sequence[FeatureStage] | None = None) -> None:
        self._stages: list[FeatureStage] = list(stages or [])

    @property
    def stages(self) -> list[FeatureStage]:
        return list(self._stages)

    def add_stage(self, stage: FeatureStage) -> FeaturePipeline:
        self._stages.append(stage)
        return self

    def clear(self) -> None:
        self._stages.clear()

    def describe(self) -> list[dict]:
        return [stage.describe() for stage in self._stages]

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Run all stages sequentially. Raises NotImplementedError from stub stages."""
        current = frame.copy()
        for stage in self._stages:
            current = stage.transform(current)
        return current

    def transform_dataset(self, dataset: Dataset) -> pd.DataFrame:
        return self.transform(dataset.frame)

    def run_with_trace(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, list[FeatureStageResult]]:
        """Execute pipeline and collect per-stage observability envelopes."""
        current = frame.copy()
        trace: list[FeatureStageResult] = []
        for stage in self._stages:
            rows_in = len(current)
            current = stage.transform(current)
            trace.append(
                FeatureStageResult(
                    stage_name=stage.name,
                    rows_in=rows_in,
                    rows_out=len(current),
                    columns_out=list(current.columns),
                )
            )
        return current, trace
