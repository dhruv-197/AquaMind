"""Validation stage — schema / range checks before feature engineering."""
from __future__ import annotations

from fastapi_app.core.contracts import DataSourceType
from fastapi_app.data_sources.base import DataRecordBatch
from fastapi_app.processing.base import ProcessingIssue, ProcessingStage


# Soft range rules keyed by source type → field → (min, max)
_RANGE_RULES: dict[DataSourceType, dict[str, tuple[float, float]]] = {
    DataSourceType.HISTORICAL_RESERVOIR: {
        "current_level_pct": (0.0, 100.0),
        "capacity_mcm": (0.0, 1_000_000.0),
    },
    DataSourceType.HISTORICAL_DEMAND: {
        "demand_mgd": (0.0, 10_000.0),
    },
    DataSourceType.WEATHER_API: {
        "temperature_c": (-20.0, 55.0),
        "humidity_pct": (0.0, 100.0),
        "precipitation_mm": (0.0, 1000.0),
    },
}


class ValidationStage(ProcessingStage):
    name = "validation"

    async def apply(
        self, batches: dict[DataSourceType, DataRecordBatch]
    ) -> dict[DataSourceType, DataRecordBatch]:
        validated: dict[DataSourceType, DataRecordBatch] = {}
        for source_type, batch in batches.items():
            issues: list[dict] = []
            rules = _RANGE_RULES.get(source_type, {})
            kept = []
            for record in batch.records:
                ok = True
                for field, (lo, hi) in rules.items():
                    if field not in record:
                        continue
                    try:
                        value = float(record[field])
                    except (TypeError, ValueError):
                        issues.append(
                            ProcessingIssue(
                                severity="warning",
                                code="non_numeric",
                                message=f"{field} is not numeric",
                                source_type=source_type,
                            ).model_dump()
                        )
                        ok = False
                        break
                    if value < lo or value > hi:
                        issues.append(
                            ProcessingIssue(
                                severity="warning",
                                code="out_of_range",
                                message=f"{field}={value} outside [{lo}, {hi}]",
                                source_type=source_type,
                            ).model_dump()
                        )
                        ok = False
                        break
                if ok:
                    kept.append(record)

            meta = dict(batch.metadata)
            meta["validation"] = {
                "input_rows": len(batch.records),
                "output_rows": len(kept),
                "issues": issues,
            }
            validated[source_type] = batch.model_copy(update={"records": kept, "metadata": meta})
        return validated
