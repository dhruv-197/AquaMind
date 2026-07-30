"""Operational timeline bucketing for optimized actions."""
from __future__ import annotations

from typing import Any

BUCKETS = ("today", "next_7_days", "next_30_days", "next_6_months")

BUCKET_LABELS = {
    "today": "Today",
    "next_7_days": "Next 7 Days",
    "next_30_days": "Next 30 Days",
    "next_6_months": "Next 6 Months",
}


def build_timeline(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {b: [] for b in BUCKETS}
    for a in actions:
        bucket = str(a.get("timeline_bucket") or "next_30_days")
        if bucket not in grouped:
            bucket = "next_30_days"
        grouped[bucket].append(
            {
                "id": a.get("id"),
                "title": a.get("title"),
                "priority_level": a.get("priority_level"),
                "decision_type": a.get("decision_type"),
                "rank": a.get("rank"),
                "estimated_water_saved_mcm": a.get("estimated_water_saved_mcm"),
                "population_protected": a.get("population_protected"),
            }
        )
    return [
        {
            "bucket": b,
            "label": BUCKET_LABELS[b],
            "actions": grouped[b],
            "count": len(grouped[b]),
        }
        for b in BUCKETS
    ]
