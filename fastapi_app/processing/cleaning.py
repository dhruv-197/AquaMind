"""Cleaning stage — null handling, type coercion, duplicate drops."""
from __future__ import annotations

from typing import Any

from fastapi_app.core.contracts import DataSourceType
from fastapi_app.data_sources.base import DataRecordBatch
from fastapi_app.processing.base import ProcessingStage


class CleaningStage(ProcessingStage):
    name = "cleaning"

    async def apply(
        self, batches: dict[DataSourceType, DataRecordBatch]
    ) -> dict[DataSourceType, DataRecordBatch]:
        cleaned: dict[DataSourceType, DataRecordBatch] = {}
        for source_type, batch in batches.items():
            seen: set[str] = set()
            records: list[dict[str, Any]] = []
            dropped_duplicates = 0
            null_scrubbed = 0

            for record in batch.records:
                key = str(record.get("id") or record.get("observed_date") or id(record))
                if key in seen:
                    dropped_duplicates += 1
                    continue
                seen.add(key)

                scrubbed = {k: v for k, v in record.items() if v is not None}
                if len(scrubbed) < len(record):
                    null_scrubbed += 1
                records.append(scrubbed)

            meta = dict(batch.metadata)
            meta["cleaning"] = {
                "dropped_duplicates": dropped_duplicates,
                "null_scrubbed_rows": null_scrubbed,
                "output_rows": len(records),
            }
            cleaned[source_type] = batch.model_copy(update={"records": records, "metadata": meta})
        return cleaned
