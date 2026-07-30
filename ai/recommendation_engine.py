"""Token-efficient AquaMind recommendation synthesis.

Uses local sklearn model outputs as numeric context, then a short Gemini
flash-lite call for natural-language actions. Results are disk-cached so
Dashboard / Recommendations / Reports share one call per cache window.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

AI_DIR = Path(__file__).resolve().parent
CACHE_DIR = AI_DIR / ".rec_cache"
CACHE_TTL_SEC = int(os.getenv("AQUAMIND_REC_CACHE_TTL", "3600"))  # 1 hour default
MAX_CACHE_FILES = int(os.getenv("AQUAMIND_REC_CACHE_MAX_FILES", "500"))
MAX_OUTPUT_TOKENS = 180
# Cheapest capable models first (vision stack is untouched elsewhere)
GEMINI_MODELS = [
    os.getenv("AQUAMIND_REC_MODEL", "").strip(),
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-2.0-flash",
]
GEMINI_MODELS = [m for m in GEMINI_MODELS if m]


def _round_num(value: Any, places: int = 1) -> float:
    try:
        return round(float(value), places)
    except (TypeError, ValueError):
        return 0.0


def _compact_stats(
    shortage: dict,
    leak: dict,
    groundwater: dict,
    demand: dict,
) -> dict[str, Any]:
    """Shrink model outputs to a few numbers — keeps prompt tiny."""
    return {
        "s_risk": _round_num(shortage.get("predicted_risk_score", shortage.get("risk_score", 50)), 0),
        "s_stage": int(_round_num(shortage.get("predicted_risk_stage", shortage.get("stage", 1)), 0)),
        "s_stor": _round_num(shortage.get("reservoir_capacity_pct", shortage.get("forecast_storage_pct", 50)), 0),
        "l_leak": 1 if leak.get("is_leak_detected") or leak.get("is_leak") else 0,
        "l_p": _round_num(leak.get("leak_probability", leak.get("probability", 0)), 2),
        "l_lpm": _round_num(leak.get("estimated_water_loss_lpm", 0), 0),
        "l_zone": str(leak.get("zone", "n/a"))[:24],
        "g_depth": _round_num(groundwater.get("projected_depth_m", groundwater.get("depth_m", 0)), 1),
        "g_draw": _round_num(groundwater.get("drawdown_rate_m", 0), 2),
        "d_mgd": _round_num(demand.get("forecasted_demand_mgd", demand.get("demand_mgd", 0)), 1),
        "d_surge": str(demand.get("peak_surge_risk", "Normal"))[:28],
    }


def _saving_display(leak: dict) -> str:
    loss_lpm = float(leak.get("estimated_water_loss_lpm", 0) or 0)
    daily = loss_lpm * 60 * 24
    if daily >= 1_000_000:
        return f"{round(daily / 1_000_000, 1)} Million Liters"
    if daily > 0:
        return f"{round(daily / 1000, 1)} Thousand Liters"
    # Conservation estimate from shortage stage when no active leak loss
    return "0.4 Million Liters"


def _cache_key(stats: dict) -> str:
    payload = json.dumps(stats, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _read_cache(key: str) -> Optional[dict]:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(data.get("cached_at", 0)) > CACHE_TTL_SEC:
            return None
        result = data.get("result")
        if isinstance(result, dict):
            result = {**result, "source": "cache", "provider": data.get("provider", "gemini")}
            return result
    except Exception:
        return None
    return None


def _evict_cache_if_needed() -> None:
    try:
        entries = list(CACHE_DIR.glob("*.json"))
        if len(entries) <= MAX_CACHE_FILES:
            return
        entries.sort(key=lambda e: e.stat().st_mtime)
        for entry in entries[: len(entries) - MAX_CACHE_FILES]:
            entry.unlink(missing_ok=True)
    except OSError:
        pass


def _write_cache(key: str, result: dict, provider: str) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = CACHE_DIR / f"{key}.json"
        path.write_text(
            json.dumps(
                {"cached_at": time.time(), "provider": provider, "result": result},
                indent=2,
            ),
            encoding="utf-8",
        )
        _evict_cache_if_needed()
    except Exception as err:
        print(f"[AIRecommendationEngine] cache write skipped: {err}")


def _rules_fallback(stats: dict, saving: str) -> dict:
    recs: list[str] = []
    days = max(1, int(stats["s_stor"] / 5) if stats["s_stor"] > 0 else 1)
    recs.append(f"Reservoir storage ~{int(stats['s_stor'])}% — plan contingency within ~{days} days.")
    if stats["s_risk"] >= 75:
        cut = "20%"
    elif stats["s_risk"] >= 55:
        cut = "15%"
    elif stats["s_risk"] >= 35:
        cut = "10%"
    else:
        cut = "5%"
    recs.append(f"Trim municipal supply by {cut} while Stage {stats['s_stage']} risk holds.")
    if stats["l_leak"]:
        recs.append(f"Prioritize repair in {stats['l_zone']} (p={stats['l_p']}, ~{int(stats['l_lpm'])} L/min).")
    else:
        recs.append("Run acoustic spot-checks on highest-loss DMA corridors.")
    if stats["g_draw"] > 2.0:
        recs.append("Cap aquifer pumping ~35% on fastest-drawdown wells.")
    if any(k in str(stats["d_surge"]).lower() for k in ("critical", "elevated", "surge")):
        recs.append("Shift irrigation / non-essential demand to off-peak night windows.")
    recs = recs[:4]
    summary = " ".join(recs) + f" Expected saving: {saving}."
    return {
        "recommendations": recs,
        "expected_saving": saving,
        "text_summary": summary,
        "source": "rules_fallback",
        "provider": "local-rules",
    }


class AIRecommendationEngine:
    def __init__(self):
        raw = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
        self.api_key = raw if raw and raw != "MY_GEMINI_API_KEY" else ""

    def generate_recommendations(
        self,
        water_shortage_prediction: dict,
        leak_detection: dict,
        groundwater_prediction: dict,
        water_demand: dict,
        force_refresh: bool = False,
    ) -> dict:
        stats = _compact_stats(
            water_shortage_prediction,
            leak_detection,
            groundwater_prediction,
            water_demand,
        )
        saving = _saving_display(leak_detection)
        key = _cache_key(stats)

        if not force_refresh:
            cached = _read_cache(key)
            if cached:
                return cached

        if self.api_key:
            try:
                gemini_result = self._call_gemini(stats, saving)
                if gemini_result:
                    gemini_result["source"] = "gemini"
                    _write_cache(key, gemini_result, gemini_result.get("provider", "gemini"))
                    return gemini_result
            except Exception as err:
                print(f"[AIRecommendationEngine] Gemini failed, using rules: {err}")

        fallback = _rules_fallback(stats, saving)
        # Cache rules too so repeated page loads stay free of API spend
        _write_cache(key, fallback, "local-rules")
        return fallback

    def _call_gemini(self, stats: dict, saving: str) -> Optional[dict]:
        # Ultra-short prompt (~120-180 tokens) to protect quota
        prompt = (
            "AquaMind water ops advisor. Compact stats:\n"
            f"shortage risk={stats['s_risk']} stage={stats['s_stage']} storage%={stats['s_stor']}\n"
            f"leak={stats['l_leak']} p={stats['l_p']} loss_lpm={stats['l_lpm']} zone={stats['l_zone']}\n"
            f"gw_depth_m={stats['g_depth']} drawdown_m={stats['g_draw']}\n"
            f"demand_mgd={stats['d_mgd']} surge={stats['d_surge']}\n"
            f"saving_hint={saving}\n"
            "Return JSON only:\n"
            '{"recommendations":["action1","action2","action3"],'
            f'"expected_saving":"{saving}",'
            '"text_summary":"one short paragraph"}\n'
            "Rules: max 3 short actions, concrete, no fluff."
        )

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
                "maxOutputTokens": MAX_OUTPUT_TOKENS,
            },
        }
        payload = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        last_err: Optional[Exception] = None

        for model in GEMINI_MODELS:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={self.api_key}"
            )
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=12) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                candidates = resp_data.get("candidates") or []
                if not candidates:
                    continue
                text_content = candidates[0]["content"]["parts"][0]["text"]
                parsed = json.loads(text_content.strip())
                recs = parsed.get("recommendations") or []
                if isinstance(recs, str):
                    recs = [recs]
                recs = [str(r).strip() for r in recs if str(r).strip()][:4]
                if not recs:
                    continue
                return {
                    "recommendations": recs,
                    "expected_saving": str(parsed.get("expected_saving") or saving),
                    "text_summary": str(parsed.get("text_summary") or " ".join(recs)),
                    "provider": model,
                }
            except Exception as err:
                last_err = err
                continue

        if last_err:
            raise last_err
        return None
