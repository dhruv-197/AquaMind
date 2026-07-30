"""Aggregate daily reservoir forecasts; reuse demand horizon reliability helpers."""
from __future__ import annotations

from typing import Any, Literal

from fastapi_app.prediction.models.water_demand.aggregation import (
    _chunk_points,
    _label_for_chunk,
    default_history_lookback,
    reliability_for_horizon,
)
from fastapi_app.prediction.models.reservoir.risk import reservoir_risk_level, risk_display_label

Granularity = Literal["days", "weeks", "months", "years"]

# Re-export for service convenience
__all__ = [
    "aggregate_daily_forecast",
    "aggregate_history",
    "default_history_lookback",
    "reliability_for_horizon",
]


def aggregate_daily_forecast(
    daily_points: list[dict[str, Any]],
    *,
    unit: Granularity,
    value: int,
    rmse: float,
    confidence_factor: float = 1.0,
) -> list[dict[str, Any]]:
    """Return exactly `value` forecast points at the requested granularity (storage %)."""
    if not daily_points or value < 1:
        return []

    if unit == "days":
        chunks = []
        for i, p in enumerate(daily_points[:value]):
            chunks.append(
                {
                    "index": i + 1,
                    "date_raw": p["date"],
                    "date": p["date"],
                    "value": float(p["forecast"]),
                    "confidence": p.get("confidence"),
                    "days_in_period": 1,
                }
            )
    else:
        chunks = _chunk_points(daily_points, unit=unit, value=value, value_key="forecast")

    grain_mult = {"days": 1.0, "weeks": 1.35, "months": 1.8, "years": 2.4}[unit]
    out: list[dict[str, Any]] = []
    preds: list[float] = []
    for c in chunks:
        pred = float(c["value"])
        preds.append(pred)
        step = int(c["index"])
        band = rmse * (1.0 + 0.085 * step) * 1.28 * grain_mult
        raw_conf = float(c["confidence"] or 0.7) * confidence_factor * (0.985 ** (step - 1))
        conf = max(0.25, min(0.98, raw_conf))
        risk = reservoir_risk_level(pred)
        change = None if len(preds) < 2 else round(pred - preds[-2], 3)
        window = preds[-min(7 if unit == "days" else 4, len(preds)) :]
        out.append(
            {
                "date": c["date"],
                "period_label": c["date"],
                "period_index": step,
                "granularity": unit,
                "historical": None,
                "forecast": round(max(0.0, min(100.0, pred)), 3),
                "lower": round(max(0.0, pred - band), 3),
                "upper": round(min(100.0, pred + band), 3),
                "confidence": round(conf, 4),
                "risk": risk_display_label(risk),
                "daily_change": change,
                "period_change": change,
                "rolling_avg": round(sum(window) / len(window), 3),
            }
        )
    return out


def aggregate_history(
    history_points: list[dict[str, Any]],
    *,
    unit: Granularity,
    lookback_periods: int,
) -> list[dict[str, Any]]:
    """Aggregate historical daily series to the same granularity as the forecast."""
    from fastapi_app.prediction.models.water_demand.aggregation import (
        CHUNK_DAYS,
    )

    if not history_points:
        return []

    if unit == "days":
        selected = history_points[-lookback_periods:]
        out = []
        vals: list[float] = []
        for i, p in enumerate(selected):
            d = float(p["historical"]) if p.get("historical") is not None else None
            if d is None:
                continue
            vals.append(d)
            prev = vals[-2] if len(vals) >= 2 else None
            window = vals[-min(7, len(vals)) :]
            out.append(
                {
                    "date": p["date"],
                    "period_label": p["date"],
                    "period_index": i + 1,
                    "granularity": "days",
                    "historical": round(d, 3),
                    "forecast": None,
                    "lower": None,
                    "upper": None,
                    "confidence": None,
                    "risk": None,
                    "daily_change": None if prev is None else round(d - prev, 3),
                    "period_change": None if prev is None else round(d - prev, 3),
                    "rolling_avg": round(sum(window) / len(window), 3),
                }
            )
        return out

    chunk = CHUNK_DAYS[unit]
    need = lookback_periods * chunk
    tail = history_points[-need:] if len(history_points) >= need else history_points
    usable = len(tail) - (len(tail) % chunk)
    tail = tail[-usable:] if usable else []
    rebuilt = []
    for i in range(0, len(tail), chunk):
        block = tail[i : i + chunk]
        vals = [float(b["historical"]) for b in block if b.get("historical") is not None]
        if not vals:
            continue
        end_date = block[-1]["date"]
        idx = len(rebuilt) + 1
        rebuilt.append(
            {
                "index": idx,
                "date": _label_for_chunk(end_date, unit, idx),
                "value": sum(vals) / len(vals),
            }
        )
    rebuilt = rebuilt[-lookback_periods:]
    out = []
    vals2: list[float] = []
    for i, c in enumerate(rebuilt):
        pred = float(c["value"])
        vals2.append(pred)
        prev = vals2[-2] if len(vals2) >= 2 else None
        window = vals2[-min(4, len(vals2)) :]
        out.append(
            {
                "date": c["date"],
                "period_label": c["date"],
                "period_index": i + 1,
                "granularity": unit,
                "historical": round(pred, 3),
                "forecast": None,
                "lower": None,
                "upper": None,
                "confidence": None,
                "risk": None,
                "daily_change": None if prev is None else round(pred - prev, 3),
                "period_change": None if prev is None else round(pred - prev, 3),
                "rolling_avg": round(sum(window) / len(window), 3),
            }
        )
    return out
