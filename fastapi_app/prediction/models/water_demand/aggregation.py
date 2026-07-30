"""Aggregate daily forecasts into week / month / year chart points."""
from __future__ import annotations

from typing import Any, Literal

import pandas as pd

from fastapi_app.prediction.models.water_demand.risk import demand_risk_level, risk_display_label

RELIABLE_DAY_LIMIT = 90

Granularity = Literal["days", "weeks", "months", "years"]

CHUNK_DAYS: dict[str, int] = {
    "days": 1,
    "weeks": 7,
    "months": 30,
    "years": 365,
}


def reliability_for_horizon(days: int, base_confidence: float) -> dict[str, Any]:
    """Confidence degradation + warning when horizon exceeds reliable range."""
    if days <= 30:
        tier = "high"
        factor = 1.0
        warning = None
    elif days <= RELIABLE_DAY_LIMIT:
        tier = "moderate"
        factor = 0.92
        warning = (
            "Forecast reliability is moderate beyond 30 days. "
            "Treat results as planning guidance, not operational set-points."
        )
    else:
        tier = "low"
        over = days - RELIABLE_DAY_LIMIT
        factor = max(0.35, 0.85 * (0.997 ** over))
        warning = (
            f"Requested horizon spans {days} days, which exceeds the model's "
            f"reliable recursive range (~{RELIABLE_DAY_LIMIT} days). "
            "Confidence is degraded; do not treat point estimates as precise."
        )
    return {
        "reliability_tier": tier,
        "confidence_factor": factor,
        "confidence": round(max(0.25, min(0.98, base_confidence * factor)), 4),
        "warning": warning,
        "reliable_day_limit": RELIABLE_DAY_LIMIT,
        "horizon_days": days,
    }


def _label_for_chunk(end_date: str, unit: Granularity, index: int) -> str:
    ts = pd.to_datetime(end_date)
    if unit == "days":
        return ts.strftime("%Y-%m-%d")
    if unit == "weeks":
        return f"Week {index} · W/E {ts.strftime('%d %b %Y')}"
    if unit == "months":
        return ts.strftime("%b %Y")
    return ts.strftime("%Y")


def _chunk_points(
    daily_points: list[dict[str, Any]],
    *,
    unit: Granularity,
    value: int,
    value_key: str,
) -> list[dict[str, Any]]:
    """Split consecutive daily points into exactly `value` fixed-size chunks."""
    chunk = CHUNK_DAYS[unit]
    need = value * chunk
    pts = daily_points[:need]
    if len(pts) < need:
        # Use whatever complete chunks exist
        value = len(pts) // chunk
        pts = pts[: value * chunk]
    out_chunks: list[dict[str, Any]] = []
    for i in range(value):
        block = pts[i * chunk : (i + 1) * chunk]
        if not block:
            break
        vals = [float(b[value_key]) for b in block if b.get(value_key) is not None]
        if not vals:
            continue
        end_date = block[-1]["date"]
        confs = [float(b["confidence"]) for b in block if b.get("confidence") is not None]
        out_chunks.append(
            {
                "index": i + 1,
                "date_raw": end_date,
                "date": _label_for_chunk(end_date, unit, i + 1),
                "value": sum(vals) / len(vals),
                "confidence": (sum(confs) / len(confs)) if confs else None,
                "days_in_period": len(block),
            }
        )
    return out_chunks


def aggregate_daily_forecast(
    daily_points: list[dict[str, Any]],
    *,
    unit: Granularity,
    value: int,
    capacity_mgd: float,
    rmse: float,
    confidence_factor: float = 1.0,
) -> list[dict[str, Any]]:
    """
    Return exactly `value` forecast points at the requested granularity.

    days   → value daily points
    weeks  → value weekly averages (7-day chunks)
    months → value monthly averages (30-day chunks)
    years  → value yearly averages (365-day chunks)
    """
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
        risk = demand_risk_level(pred, capacity_mgd)
        change = None if len(preds) < 2 else round(pred - preds[-2], 3)
        window = preds[-min(7 if unit == "days" else 4, len(preds)) :]
        out.append(
            {
                "date": c["date"],
                "period_label": c["date"],
                "period_index": step,
                "granularity": unit,
                "historical": None,
                "forecast": round(pred, 3),
                "lower": round(max(0.0, pred - band), 3),
                "upper": round(pred + band, 3),
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
    if not history_points:
        return []

    # Newest last
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

    chunks = _chunk_points(
        [{"date": p["date"], "forecast": p["historical"], "confidence": None} for p in history_points],
        unit=unit,
        value=max(lookback_periods, 1),
        value_key="forecast",
    )
    # _chunk_points takes from the start; for history we want the last N chunks
    # Rebuild from the end instead:
    chunk = CHUNK_DAYS[unit]
    need = lookback_periods * chunk
    tail = history_points[-need:] if len(history_points) >= need else history_points
    # Pad alignment from the end
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
    vals = []
    for i, c in enumerate(rebuilt):
        pred = float(c["value"])
        vals.append(pred)
        prev = vals[-2] if len(vals) >= 2 else None
        window = vals[-min(4, len(vals)) :]
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


def default_history_lookback(unit: Granularity, forecast_value: int) -> int:
    if unit == "days":
        return max(30, min(180, forecast_value * 2))
    if unit == "weeks":
        return max(12, min(52, forecast_value * 2))
    if unit == "months":
        return max(6, min(36, forecast_value * 2))
    return max(3, min(10, forecast_value * 2))
