"""Dataset abstractions supporting pandas DataFrames and future streaming sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Iterator, Optional, Sequence, Union

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


FrameLike = Union[pd.DataFrame, Sequence[dict[str, Any]]]


class DatasetMetadata(BaseModel):
    """Provenance and shape information for a dataset batch."""

    name: str = "unnamed"
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    row_count: int = 0
    column_names: list[str] = Field(default_factory=list)
    is_streaming: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class Dataset(ABC):
    """
    Base dataset contract.

    Concrete adapters may wrap in-memory DataFrames today and stream iterators later.
    """

    def __init__(
        self,
        data: FrameLike | None = None,
        *,
        name: str = "dataset",
        source: str | None = None,
        metadata: DatasetMetadata | None = None,
    ) -> None:
        self._frame: pd.DataFrame = self._coerce_frame(data)
        self.metadata = metadata or DatasetMetadata(
            name=name,
            source=source,
            row_count=len(self._frame),
            column_names=list(self._frame.columns),
            is_streaming=False,
        )

    @staticmethod
    def _coerce_frame(data: FrameLike | None) -> pd.DataFrame:
        if data is None:
            return pd.DataFrame()
        if isinstance(data, pd.DataFrame):
            return data.copy()
        return pd.DataFrame(list(data))

    @property
    def frame(self) -> pd.DataFrame:
        """In-memory tabular view. Streaming backends may materialize a window."""
        return self._frame

    def __len__(self) -> int:
        return len(self._frame)

    def empty(self) -> bool:
        return self._frame.empty

    def columns(self) -> list[str]:
        return list(self._frame.columns)

    def head(self, n: int = 5) -> pd.DataFrame:
        return self._frame.head(n)

    def to_records(self) -> list[dict[str, Any]]:
        return self._frame.to_dict(orient="records")

    def select(self, columns: Sequence[str]) -> pd.DataFrame:
        missing = [c for c in columns if c not in self._frame.columns]
        if missing:
            raise KeyError(f"Columns not found in dataset: {missing}")
        return self._frame.loc[:, list(columns)].copy()

    def iter_batches(self, batch_size: int = 1024) -> Iterator[pd.DataFrame]:
        """
        Batch iterator — enables future streaming without changing callers.

        Default implementation slices the in-memory frame. Streaming subclasses
        override this to yield remote/chunked batches.
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")
        total = len(self._frame)
        for start in range(0, total, batch_size):
            yield self._frame.iloc[start : start + batch_size].copy()

    @abstractmethod
    def validate(self) -> list[str]:
        """Return a list of validation issue messages (empty = valid)."""


class TrainingDataset(Dataset):
    """Labeled dataset used exclusively for model training / evaluation."""

    def __init__(
        self,
        data: FrameLike | None = None,
        *,
        feature_columns: Sequence[str] | None = None,
        target_column: str | None = None,
        name: str = "training_dataset",
        source: str | None = None,
        metadata: DatasetMetadata | None = None,
    ) -> None:
        super().__init__(data, name=name, source=source, metadata=metadata)
        self.feature_columns = list(feature_columns or [])
        self.target_column = target_column

    def features(self) -> pd.DataFrame:
        if not self.feature_columns:
            raise ValueError("feature_columns not configured on TrainingDataset")
        return self.select(self.feature_columns)

    def target(self) -> pd.Series:
        if not self.target_column:
            raise ValueError("target_column not configured on TrainingDataset")
        if self.target_column not in self._frame.columns:
            raise KeyError(f"Target column missing: {self.target_column}")
        return self._frame[self.target_column].copy()

    def split_xy(self) -> tuple[pd.DataFrame, pd.Series]:
        return self.features(), self.target()

    def validate(self) -> list[str]:
        issues: list[str] = []
        if self.empty():
            issues.append("TrainingDataset is empty")
        if not self.feature_columns:
            issues.append("feature_columns is empty")
        else:
            missing = [c for c in self.feature_columns if c not in self._frame.columns]
            if missing:
                issues.append(f"Missing feature columns: {missing}")
        if not self.target_column:
            issues.append("target_column is not set")
        elif self.target_column not in self._frame.columns:
            issues.append(f"Missing target column: {self.target_column}")
        return issues


class PredictionDataset(Dataset):
    """Unlabeled feature dataset for inference."""

    def __init__(
        self,
        data: FrameLike | None = None,
        *,
        feature_columns: Sequence[str] | None = None,
        name: str = "prediction_dataset",
        source: str | None = None,
        metadata: DatasetMetadata | None = None,
    ) -> None:
        super().__init__(data, name=name, source=source, metadata=metadata)
        self.feature_columns = list(feature_columns or [])

    def features(self) -> pd.DataFrame:
        if self.feature_columns:
            return self.select(self.feature_columns)
        return self._frame.copy()

    def validate(self) -> list[str]:
        issues: list[str] = []
        if self.empty():
            issues.append("PredictionDataset is empty")
        if self.feature_columns:
            missing = [c for c in self.feature_columns if c not in self._frame.columns]
            if missing:
                issues.append(f"Missing feature columns: {missing}")
        return issues
