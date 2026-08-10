"""AquaAI — in-app water-intelligence chat.

User-facing brand is AquaAI. Model calls stay on the server.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import asyncio

MAX_MESSAGE_LENGTH = 700
# Compress anything longer than a tight briefing.
SUMMARIZE_CHAR_THRESHOLD = 320
# Prefer models that respond quickly on current AI Studio keys.
# gemini-flash-lite-latest / gemini-3.5-flash-lite often hang until timeout.
GEMINI_MODEL = os.getenv("AQUAMIND_COPILOT_MODEL", "gemini-3.1-flash-lite")
RESEARCH_MODEL = os.getenv("AQUAMIND_RESEARCH_MODEL", "gemini-3.1-flash-lite-preview")
FALLBACK_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-flash-latest",
    "gemini-3.6-flash",
]
# Keep chat snappy: one slow/hung model must not burn ~40s × N fallbacks.
GEMINI_TIMEOUT_SEC = float(os.getenv("AQUAMIND_COPILOT_TIMEOUT_SEC", "15"))
MAX_MODEL_ATTEMPTS = 3


OFF_TOPIC_MARKERS = (
    "pizza", "burger", "restaurant", "recipe", "cricket score", "football score",
    "military", "army ranking", "top 10 countr", "best movie", "netflix",
    "stock tip", "crypto", "bitcoin", "dating", "meme", "joke tell",
    "who will win election", "celebrity", "best phone", "iphone vs",
)

WATER_HINTS = (
    "water", "rain", "weather", "monsoon", "flood", "drought", "reservoir", "dam",
    "leak", "pipeline", "pipe", "groundwater", "aquifer", "well", "irrigation",
    "conservation", "waterlogging", "precipitation", "humidity", "temperature",
    "forecast", "shortage", "storage", "demand", "consumption", "overflow",
    "stress", "drawdown", "depletion", "recharge", "hydrolog", "canal",
    "borewell", "tank", "pond", "seepage", "inundation", "gujarat", "gujrat",
    "maharashtra", "maharastra", "delhi", "mumbai", "ahmedabad", "gandhinagar",
    "surat", "bengaluru", "chennai", "kolkata", "graph", "chart", "probability",
)

GREETINGS = {"hi", "hello", "hey", "good morning", "good evening", "good afternoon"}

SYSTEM_PROMPT = """You are AquaAI, the water-intelligence assistant for AquaMind (India).

Never say you are Gemini, ChatGPT, Google, or any other model. Always speak as AquaAI.

SCOPE: Only water, weather, rain, flood, drought, reservoirs, groundwater, leaks,
demand, conservation, water stress. Off-topic → one short polite refusal.

ANSWER STYLE (mandatory):
- Be ON THE POINT. Maximum 3 short bullet points (or 2–4 short lines). No essays.
- Always mix NUMBERS + text when possible, e.g.:
  "Bihar shortage risk today: ~25–35% (moderate). Tomorrow: similar unless >20 mm rain."
  "Patna groundwater stress: ~1.5–3 m/year drawdown in urban pockets."
- Include units: %, mm, m, MCM, L/min, °C, probability 0–100%.
- Lead with the direct answer (risk level + %). Then 1–2 supporting numbers.
- If LIVE TELEMETRY CONTEXT is provided below, ground numbers in it first.
- Prefer live WSI / component values over invented ranges when context is present.
- If exact live sensor data is unknown, give a reasoned numeric range and label it estimate.
- Do NOT invent AquaMind telemetry IDs. Do NOT write long background about rivers/history.
- No "Key metrics" sections, no portal recommendations unless asked.
- Graph requests: give 3 numeric points (label: value), nothing else.
"""


def _gemini_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")


class WaterCopilot:
    """Simple Gemini chat with optional summarization of long answers."""

    def __init__(self) -> None:
        self.api_key = _gemini_key()

    async def answer(
        self,
        message: str,
        db=None,
        context_tool: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        self.api_key = _gemini_key()
        question = (message or "").strip()
        if not question:
            raise ValueError("Please type a question.")
        if len(question) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Question must be at most {MAX_MESSAGE_LENGTH} characters.")

        lowered = question.lower().strip()

        if lowered in GREETINGS:
            return {
                "answer": (
                    "Hello! I'm AquaAI. Ask me about rainfall, shortages, leaks, "
                    "groundwater, demand, or water stress."
                ),
                "summarized": False,
                "source": "local",
                "suggestions": [
                    "Today's water shortage risk in Gujarat",
                    "Rain forecast for Ahmedabad",
                    "Groundwater depletion in Delhi",
                ],
            }

        if self._is_off_topic(lowered) and not self._looks_water_related(lowered):
            return self._refuse()

        if not self.api_key:
            return {
                "answer": (
                    "AquaAI is not configured yet. Add GEMINI_API_KEY to your .env.local file, "
                    "restart FastAPI, and try again."
                ),
                "summarized": False,
                "source": "config_error",
                "suggestions": [],
            }

        # Sync DB fusion + urllib Gemini must not block the event loop.
        live_context = await asyncio.to_thread(self._live_water_context_isolated)
        raw, err_kind = await asyncio.to_thread(
            self._ask_gemini, question, history or [], live_context
        )
        if raw is None:
            if err_kind == "rate_limit":
                msg = (
                    "AquaAI is busy right now (rate limit). Wait about a minute, then try again."
                )
            elif err_kind == "not_found":
                msg = (
                    "AquaAI could not reach a working model. "
                    "Set AQUAMIND_COPILOT_MODEL=gemini-3.1-flash-lite in .env.local and restart."
                )
            else:
                msg = "AquaAI could not answer right now. Please try again in a moment."
            # Still return live WSI snapshot if Gemini fails.
            if live_context:
                return {
                    "answer": f"{msg}\n\nLive snapshot: {live_context}",
                    "summarized": False,
                    "source": "gemini_unavailable_with_live_context",
                    "suggestions": ["What is the water stress index?", "Top stress drivers"],
                    "live_context": live_context,
                }
            return {
                "answer": msg,
                "summarized": False,
                "source": "gemini_unavailable",
                "suggestions": ["Try again in a minute", "Rain forecast for Delhi"],
            }

        # Prefer local trim if the reply is long — avoids a second API call under quota pressure.
        display, was_summarized = self._maybe_summarize(raw)
        return {
            "answer": display,
            "summarized": was_summarized,
            "full_answer": raw if was_summarized else None,
            "source": "gemini",
            "model": self._last_model or GEMINI_MODEL,
            "live_context": live_context,
            "suggestions": [
                "Explain that in simpler words",
                "What are the top WSI drivers?",
                "What about groundwater there?",
            ],
        }

    _last_model: str | None = None

    def _live_water_context_isolated(self) -> str | None:
        """Build live context off the request session (thread-safe).

        Prefers the short-lived WSI L1 cache so chat does not re-run fusion when
        the dashboard recently warmed ``wi:live``.
        """
        try:
            from fastapi_app.core.ttl_cache import WI_TTL_SEC, wi_cache
            from fastapi_app.database.connection import SessionLocal
            from fastapi_app.services.model_service import model_service

            cached = wi_cache.get("wi:live")
            if cached is not None:
                return self._format_live_context(cached)

            db = SessionLocal()
            try:
                payload = model_service.build_water_intelligence(db)
                wi_cache.set("wi:live", payload, WI_TTL_SEC)
                return self._format_live_context(payload)
            finally:
                db.close()
        except Exception as exc:
            print(f"[AquaAI] live context skipped: {exc}")
            return None

    def _format_live_context(self, payload: dict[str, Any]) -> str | None:
        wsi = payload.get("water_stress") or {}
        drivers = wsi.get("drivers") or []
        driver_txt = "; ".join(
            f"{d.get('component')}={d.get('contribution')}" for d in drivers[:3]
        )
        climate = payload.get("climate") or {}
        leak = payload.get("leak") or {}
        return (
            f"WSI={wsi.get('water_stress_index')} ({wsi.get('stage')}); "
            f"drivers=[{driver_txt}]; "
            f"SPI3={climate.get('spi3_proxy')}; "
            f"temp={climate.get('temperature_c')}C; "
            f"leak_source={leak.get('source')}; "
            f"shortage_score={(payload.get('shortage') or {}).get('predicted_risk_score')}; "
            f"demand_mgd={(payload.get('demand') or {}).get('forecasted_demand_mgd')}"
        )

    def _live_water_context(self, db) -> str | None:
        """Compact WSI + drivers string for grounding Gemini answers."""
        if db is None:
            return None
        try:
            from fastapi_app.services.model_service import model_service

            payload = model_service.build_water_intelligence(db)
            return self._format_live_context(payload)
        except Exception as exc:
            print(f"[AquaAI] live context skipped: {exc}")
            return None

    @staticmethod
    def _is_off_topic(text: str) -> bool:
        return any(marker in text for marker in OFF_TOPIC_MARKERS)

    @staticmethod
    def _looks_water_related(text: str) -> bool:
        return any(hint in text for hint in WATER_HINTS)

    @staticmethod
    def _refuse() -> dict[str, Any]:
        return {
            "answer": (
                "I’m AquaAI — I only help with water, weather, floods, "
                "groundwater, reservoirs, leaks, and conservation. "
                "I can’t answer unrelated topics like food or military rankings. "
                "Try asking about rainfall or water shortage instead."
            ),
            "summarized": False,
            "source": "scope_guard",
            "suggestions": [
                "Rain forecast for Delhi",
                "Water shortage risk in Gujarat",
                "Leak risks in Mumbai",
            ],
        }

    def _ask_gemini(
        self,
        question: str,
        history: list[dict[str, str]],
        live_context: str | None = None,
    ) -> tuple[str | None, str | None]:
        contents: list[dict[str, Any]] = []
        for turn in history[-8:]:
            role = turn.get("role")
            text = (turn.get("text") or "").strip()
            if not text or role not in {"user", "assistant"}:
                continue
            contents.append(
                {
                    "role": "user" if role == "user" else "model",
                    "parts": [{"text": text}],
                }
            )
        context_block = ""
        if live_context:
            context_block = f"\n\nLIVE TELEMETRY CONTEXT (prefer these numbers):\n{live_context}\n"
        # Reinforce brevity on every turn (models sometimes ignore system style alone).
        user_ask = (
            f"{question}{context_block}\n\n"
            "(Reply in ≤3 short bullets. Include numbers/%/mm/m where possible. No long background.)"
        )
        contents.append({"role": "user", "parts": [{"text": user_ask}]})

        # Plain generateContent first (reliable + fewer quota burns than search+retry).
        body_plain = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 512,
            },
        }

        models: list[str] = []
        for name in [GEMINI_MODEL, RESEARCH_MODEL, *FALLBACK_MODELS]:
            if name and name not in models:
                models.append(name)
        models = models[:MAX_MODEL_ATTEMPTS]

        saw_rate_limit = False
        saw_not_found = False
        for model in models:
            try:
                text = self._generate(model, body_plain)
                if text:
                    self._last_model = model
                    return text, None
            except urllib.error.HTTPError as err:
                detail = ""
                try:
                    detail = err.read().decode("utf-8", errors="ignore")[:200]
                except Exception:
                    pass
                print(f"[WaterCopilot] Gemini {model} failed: {err.code} {detail}")
                if err.code == 429:
                    saw_rate_limit = True
                    # Quota is shared across models — stop immediately.
                    return None, "rate_limit"
                if err.code == 404:
                    saw_not_found = True
                    continue
            except Exception as err:
                print(f"[WaterCopilot] Gemini {model} failed: {err}")

        if saw_rate_limit:
            return None, "rate_limit"
        if saw_not_found and not saw_rate_limit:
            return None, "not_found"
        return None, "unavailable"

    def _generate(self, model: str, body: dict[str, Any]) -> str:
        payload = json.dumps(body).encode()
        request = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=GEMINI_TIMEOUT_SEC) as response:
            data = json.loads(response.read().decode("utf-8"))
        parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        texts = [str(p.get("text") or "").strip() for p in parts if p.get("text")]
        joined = "\n".join(t for t in texts if t).strip()
        if not joined:
            raise RuntimeError("empty Gemini response")
        return joined

    def _maybe_summarize(self, answer: str) -> tuple[str, bool]:
        import re

        # Already short enough.
        if len(answer) <= SUMMARIZE_CHAR_THRESHOLD and answer.count("\n") <= 3:
            return answer.strip(), False

        lines = [ln.strip() for ln in answer.replace("**", "").splitlines() if ln.strip()]
        cleaned: list[str] = []
        for ln in lines:
            clean = re.sub(r"^[\s•\-\*#]+", "", ln).strip()
            if len(clean) < 12:
                continue
            if len(clean) > 160:
                clean = clean[:157] + "..."
            cleaned.append(clean)

        with_nums = [c for c in cleaned if re.search(r"\d", c)]
        without = [c for c in cleaned if c not in with_nums]
        picked = (with_nums + without)[:3]
        if picked:
            return "\n".join(f"• {text}" for text in picked), True
        return answer.strip(), False


water_copilot = WaterCopilot()
