"""SPI-like 3-month precipitation z-score from Open-Meteo archive (not full WMO gamma SPI)."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean, pstdev
from typing import Any, Optional


def _parse_ym(d: str) -> tuple[int, int]:
    dt = datetime.strptime(d[:10], "%Y-%m-%d")
    return dt.year, dt.month


def monthly_precip(dates: list[str], precip: list[Optional[float]]) -> dict[tuple[int, int], float]:
    buckets: dict[tuple[int, int], float] = defaultdict(float)
    for d, p in zip(dates, precip):
        if p is None:
            continue
        buckets[_parse_ym(d)] += float(p)
    return dict(buckets)


def spi3_proxy(dates: list[str], precip: list[Optional[float]]) -> dict[str, Any]:
    """
    3-month rolling precip sum z-score vs all historical 3-month windows
    ending in the same calendar month (proxy SPI-3).
    """
    monthly = monthly_precip(dates, precip)
    if len(monthly) < 24:
        return {
            "spi3_proxy": None,
            "class": "insufficient_history",
            "method": "z-score of 3-month precip vs same-calendar-month windows; needs ≥24 months",
            "recent_3m_mm": None,
        }

    keys = sorted(monthly.keys())
    # Build 3-month sums keyed by end (year, month)
    rolling: list[tuple[tuple[int, int], float]] = []
    for i in range(2, len(keys)):
        y, m = keys[i]
        # ensure contiguous-ish: use last 3 available months in sorted list ending at i
        window_keys = keys[i - 2 : i + 1]
        s = sum(monthly[k] for k in window_keys)
        rolling.append(((y, m), s))

    if not rolling:
        return {
            "spi3_proxy": None,
            "class": "insufficient_history",
            "method": "z-score of 3-month precip",
            "recent_3m_mm": None,
        }

    end_ym, recent = rolling[-1]
    # Same calendar month peers
    peers = [val for (yy, mm), val in rolling if mm == end_ym[1]]
    if len(peers) < 5:
        peers = [val for _, val in rolling]

    mu = mean(peers)
    sigma = pstdev(peers) if len(peers) > 1 else 0.0
    z = 0.0 if sigma < 1e-6 else (recent - mu) / sigma

    if z <= -2.0:
        klass = "extremely_dry"
    elif z <= -1.5:
        klass = "severely_dry"
    elif z <= -1.0:
        klass = "moderately_dry"
    elif z < 1.0:
        klass = "near_normal"
    elif z < 1.5:
        klass = "moderately_wet"
    elif z < 2.0:
        klass = "severely_wet"
    else:
        klass = "extremely_wet"

    return {
        "spi3_proxy": round(z, 2),
        "class": klass,
        "recent_3m_mm": round(recent, 1),
        "climatology_mean_3m_mm": round(mu, 1),
        "end_year_month": f"{end_ym[0]:04d}-{end_ym[1]:02d}",
        "peer_windows": len(peers),
        "method": (
            "Proxy SPI-3: z-score of trailing 3-month precipitation vs historical "
            "windows ending in the same calendar month (Open-Meteo ERA5 archive). "
            "Not the full WMO gamma-distribution SPI."
        ),
    }


def rainfall_deficit_pct(dates: list[str], precip: list[Optional[float]], season_days: int = 90) -> dict[str, Any]:
    """Season-to-date precip vs mean of same DOY windows across years."""
    pairs = [(d[:10], float(p)) for d, p in zip(dates, precip) if p is not None]
    if len(pairs) < season_days + 365:
        # fallback: last N days vs mean of all N-day windows
        if len(pairs) < season_days * 2:
            return {
                "deficit_pct": None,
                "recent_mm": None,
                "normal_mm": None,
                "method": "insufficient archive for deficit",
            }

    # Group by year for last `season_days` of each year ending at latest date
    latest = pairs[-1][0]
    recent = pairs[-season_days:]
    recent_mm = sum(v for _, v in recent)

    # Historical: same length windows ending on same month-day across prior years
    md = latest[5:]  # MM-DD
    hist: list[float] = []
    by_year: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for d, v in pairs:
        by_year[d[:4]].append((d, v))

    for year, series in by_year.items():
        series = sorted(series)
        # find index of md in that year
        idx = next((i for i, (d, _) in enumerate(series) if d[5:] == md), None)
        if idx is None or idx + 1 < season_days:
            continue
        window = series[idx + 1 - season_days : idx + 1]
        if len(window) == season_days:
            hist.append(sum(v for _, v in window))

    if len(hist) < 3:
        # simpler: compare recent to mean of non-overlapping prior chunks
        chunk_means = []
        for i in range(0, len(pairs) - season_days, season_days):
            chunk_means.append(sum(v for _, v in pairs[i : i + season_days]))
        if not chunk_means:
            return {
                "deficit_pct": None,
                "recent_mm": round(recent_mm, 1),
                "normal_mm": None,
                "method": "insufficient history for deficit %",
            }
        normal = mean(chunk_means[:-1]) if len(chunk_means) > 1 else chunk_means[0]
    else:
        normal = mean(hist)

    if normal <= 1e-6:
        deficit = 0.0 if recent_mm <= 0 else 100.0
    else:
        deficit = ((normal - recent_mm) / normal) * 100.0

    return {
        "deficit_pct": round(deficit, 1),
        "recent_mm": round(recent_mm, 1),
        "normal_mm": round(normal, 1),
        "season_days": season_days,
        "method": (
            f"Rainfall deficit % = (climatology {season_days}-day precip − recent "
            f"{season_days}-day precip) / climatology × 100 from Open-Meteo archive."
        ),
    }
