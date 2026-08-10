import asyncio
import os
import json
import base64
import logging
import time
import httpx
from typing import Awaitable, Callable, Dict, Any, Optional

from fastapi_app.core.ai_fallback import vision_fixture_result
from fastapi_app.core.config import get_settings
from fastapi_app.core.data_quality import DataQuality, Method, isoformat, utc_now
from fastapi_app.core.demo_mode import ProviderUnavailableError, should_use_fixture
from fastapi_app.services.vlm_prompt import (
    FLOOD_VL_SYSTEM_PROMPT,
    FLOOD_VL_USER_PROMPT,
    GEMINI_FLOOD_VISION_PROMPT,
    QWEN_VL_SYSTEM_PROMPT,
    QWEN_VL_USER_PROMPT,
)

logger = logging.getLogger("aquamind.vision_service")

# Structured prompt for Gemini Vision (same analysis criteria as Qwen2.5-VL)
GEMINI_VISION_PROMPT = """You are AquaLens, an advanced Earth Observation and Hydrological Computer Vision intelligence system.

Analyze this image carefully. Determine if this is a satellite image, drone aerial photo, or ground-level photo of a water body (reservoir, lake, dam, river, pond, etc).

If the image does NOT show a water body or reservoir, you MUST reflect that honestly in your analysis. For example:
- If it shows a person, building, or unrelated scene, set reservoir_health to 0, overall_risk to "No Reservoir Detected", and explain in the summary what the image actually shows.
- If it shows a dry landscape with no water, reflect that with low health scores and high risk.

If the image DOES show a water body, evaluate it honestly based on what you actually see:

1. reservoir_health: Integer 0-100 based on what you genuinely observe (water level, clarity, surrounding condition)
2. water_spread: Actual water surface coverage you see ('None', 'Critical Shrinkage', 'Low', 'Moderate', 'High', 'Extensive')
3. vegetation: Surrounding flora density you actually observe ('None', 'Sparse', 'Low', 'Medium', 'Dense', 'Overgrown')
4. sedimentation: Visible silt/turbidity ('Not Visible', 'Minimal', 'Low', 'Medium', 'High', 'Critical')
5. dry_shoreline: Exposed bank/shore margins you see ('Not Applicable', 'None', 'Minimal', 'Visible', 'Extensive', 'Severe Exposure')
6. encroachment: Any human construction/settlement near shoreline ('Not Applicable', 'Not Detected', 'Low Risk', 'Moderate Risk', 'Detected')
7. water_stress: Based on observable evidence ('Not Applicable', 'Low', 'Medium', 'High', 'Critical')
8. overall_risk: Honest assessment ('No Reservoir Detected', 'Low', 'Moderate', 'High', 'Critical')
9. turbidity_index: Integer 0-100 estimate of water cloudiness/sediment load from visible color and clarity (0 = crystal clear, 100 = opaque/heavily silted). Use 0 if no water is visible.
10. algae_bloom_risk: Visible green/scum surface cover suggesting algal bloom ('Not Applicable', 'None', 'Low', 'Medium', 'High')
11. shoreline_exposure_pct: Integer 0-100 rough visual estimate of how much normally-submerged shoreline/bank is exposed (dry lakebed visible around the waterline). 0 if not applicable or not visible.
12. confidence: Float 0.0-1.0 — your own honest confidence in this assessment given image quality, angle, and resolution. Lower it for blurry, distant, or ambiguous images.
13. summary: A factual paragraph describing what you ACTUALLY see in this image. Be specific about colors, visible features, water presence/absence, surroundings.
14. recommendations: Array of 4-6 specific actionable recommendations based on your REAL observations.

CRITICAL: Your analysis must be HONEST and based on what is ACTUALLY visible in the image.
Do NOT fabricate data. If you see no water, say so. If the image is not a reservoir, say so.

Return ONLY valid JSON matching this exact structure (no markdown, no commentary):
{
  "reservoir_health": <integer>,
  "water_spread": "<string>",
  "vegetation": "<string>",
  "sedimentation": "<string>",
  "dry_shoreline": "<string>",
  "encroachment": "<string>",
  "water_stress": "<string>",
  "overall_risk": "<string>",
  "turbidity_index": <integer>,
  "algae_bloom_risk": "<string>",
  "shoreline_exposure_pct": <integer>,
  "confidence": <float>,
  "summary": "<string>",
  "recommendations": ["<string>", ...]
}"""


class VisionService:
    """
    Vision Intelligence Service powered by Qwen2.5-VL / Gemini Vision.
    Analyzes reservoir satellite/drone imagery to produce structured visual metrics.
    """

    def __init__(self):
        self.dashscope_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")

    def _get_base64_data_uri(self, file_bytes: bytes, filename: str) -> str:
        ext = filename.split(".")[-1].lower() if "." in filename else "jpeg"
        mime_type = "image/png" if ext == "png" else "image/webp" if ext == "webp" else "image/jpeg"
        b64_str = base64.b64encode(file_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{b64_str}"

    def _get_mime_type(self, filename: str) -> str:
        ext = filename.split(".")[-1].lower() if "." in filename else "jpeg"
        if ext == "png":
            return "image/png"
        elif ext == "webp":
            return "image/webp"
        elif ext in ("tiff", "tif"):
            return "image/tiff"
        elif ext == "bmp":
            return "image/bmp"
        return "image/jpeg"

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Robustly parse JSON from model response, stripping markdown fences if present."""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        return json.loads(content)

    def _prompts_for_mode(self, mode: str) -> Dict[str, str]:
        if mode == "flood":
            return {
                "gemini": GEMINI_FLOOD_VISION_PROMPT,
                "system": FLOOD_VL_SYSTEM_PROMPT,
                "user": FLOOD_VL_USER_PROMPT,
            }
        return {
            "gemini": GEMINI_VISION_PROMPT,
            "system": QWEN_VL_SYSTEM_PROMPT,
            "user": QWEN_VL_USER_PROMPT,
        }

    async def _analyze_with_gemini(
        self, file_bytes: bytes, filename: str, mode: str = "reservoir"
    ) -> Dict[str, Any]:
        """Use Google Gemini Vision API to analyze the image with real AI inference."""
        prompts = self._prompts_for_mode(mode)
        try:
            from google import genai

            client = genai.Client(api_key=self.gemini_key)
            mime_type = self._get_mime_type(filename)
            # Prefer current Flash; fall back if a key/region lacks a specific id
            model_candidates = (
                "gemini-3.5-flash",
                "gemini-2.5-flash-lite",
                "gemini-flash-latest",
            )

            def _call(model_name: str) -> Optional[str]:
                # The google-genai client is synchronous; run it off the event
                # loop so one slow vision call cannot stall every other request.
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "inline_data": {
                                        "mime_type": mime_type,
                                        "data": base64.b64encode(file_bytes).decode("utf-8"),
                                    }
                                },
                                {"text": prompts["gemini"]},
                            ],
                        }
                    ],
                    config={"response_mime_type": "application/json"},
                )
                return response.text

            last_err: Optional[Exception] = None
            for model_name in model_candidates:
                try:
                    text = await asyncio.to_thread(_call, model_name)
                    if text:
                        logger.info("Gemini Vision succeeded with model=%s mode=%s", model_name, mode)
                        return self._parse_json_response(text)
                    raise ValueError(f"Empty response from {model_name}")
                except asyncio.CancelledError:
                    # The per-provider deadline fired. Trying the next model id
                    # would only push the request further past its budget.
                    raise
                except Exception as model_err:
                    last_err = model_err
                    logger.warning("Gemini model %s failed: %s", model_name, model_err)
            raise last_err or ValueError("Gemini Vision failed for all model candidates")

        except Exception as e:
            logger.error(f"Gemini Vision analysis failed: {e}")
            raise

    async def _analyze_with_qwen_openrouter(
        self, file_bytes: bytes, filename: str, mode: str = "reservoir"
    ) -> Dict[str, Any]:
        """Use OpenRouter Qwen2.5-VL to analyze the image."""
        prompts = self._prompts_for_mode(mode)
        data_uri = self._get_base64_data_uri(file_bytes, filename)
        timeout = get_settings().vision_provider_timeout_seconds
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "qwen/qwen-2.5-vl-72b-instruct",
                    "messages": [
                        {"role": "system", "content": prompts["system"]},
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": data_uri}},
                                {"type": "text", "text": prompts["user"]},
                            ],
                        },
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            if response.status_code == 200:
                res_data = response.json()
                content = res_data["choices"][0]["message"]["content"]
                return self._parse_json_response(content)
            else:
                raise ValueError(f"OpenRouter returned status {response.status_code}: {response.text}")

    async def _analyze_with_qwen_dashscope(
        self, file_bytes: bytes, filename: str, mode: str = "reservoir"
    ) -> Dict[str, Any]:
        """Use Alibaba DashScope Qwen2.5-VL to analyze the image."""
        prompts = self._prompts_for_mode(mode)
        data_uri = self._get_base64_data_uri(file_bytes, filename)
        timeout = get_settings().vision_provider_timeout_seconds
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.dashscope_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "qwen2.5-vl-72b-instruct",
                    "messages": [
                        {"role": "system", "content": prompts["system"]},
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": data_uri}},
                                {"type": "text", "text": prompts["user"]},
                            ],
                        },
                    ],
                },
            )
            if response.status_code == 200:
                res_data = response.json()
                content = res_data["choices"][0]["message"]["content"]
                return self._parse_json_response(content)
            else:
                raise ValueError(f"DashScope returned status {response.status_code}: {response.text}")
    def _refresh_keys(self) -> None:
        """Re-read env each request so .env.local updates apply without stale import-time keys."""
        self.dashscope_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")

    async def _run_provider(
        self,
        label: str,
        call: Callable[[], Awaitable[Dict[str, Any]]],
        *,
        timeout: float,
    ) -> Dict[str, Any]:
        """Run one provider under a hard deadline.

        A hosted VLM that stops responding must not be allowed to hold the whole
        chain open — the caller needs enough budget left to try the next one.
        """
        try:
            return await asyncio.wait_for(call(), timeout=timeout)
        except asyncio.TimeoutError as err:
            raise TimeoutError(f"{label} exceeded its {timeout:.0f}s deadline") from err

    async def _attach_segmentation(self, result: Dict[str, Any], file_bytes: bytes, mode: str) -> None:
        """Best-effort CLIPSeg overlay. Never invalidates a successful analysis."""
        timeout = get_settings().clipseg_timeout_seconds
        try:
            from fastapi_app.services.clipseg_service import segment_image

            logger.info("Running CLIPSeg segmentation overlay (mode=%s)...", mode)
            # segment_image is synchronous torch work and may load weights on
            # first call; keep it off the event loop and under a deadline.
            segmentation = await asyncio.wait_for(
                asyncio.to_thread(segment_image, file_bytes, mode=mode),
                timeout=timeout,
            )
            result["segmentation"] = segmentation
            if segmentation.get("available"):
                result["provider"] = f"{result.get('provider', 'AquaLens')} + CLIPSeg"
                result["analysis_mode"] = "vlm+clipseg"
        except asyncio.TimeoutError:
            logger.warning("CLIPSeg overlay exceeded %.0fs — returning VLM analysis alone.", timeout)
            result["segmentation"] = {
                "available": False,
                "error": "CLIPSeg overlay is temporarily unavailable.",
                "classes": [],
                "overlay_base64": None,
            }
        except Exception as seg_err:
            logger.warning("CLIPSeg step skipped: %s", type(seg_err).__name__)
            result["segmentation"] = {
                "available": False,
                "error": "CLIPSeg overlay is temporarily unavailable.",
                "classes": [],
                "overlay_base64": None,
            }

    async def analyze_reservoir_image(
        self, file_bytes: bytes, filename: str, mode: str = "reservoir"
    ) -> Dict[str, Any]:
        """
        Multimodal VLM analysis + CLIPSeg zero-shot segmentation overlay.

        mode:
          - reservoir — reservoir health metrics + shoreline classes
          - flood — permanent water vs flood inundation guidance + exclusive masks

        Priority: Gemini Vision -> Qwen2.5-VL (OpenRouter) -> Qwen2.5-VL (DashScope)

        Each provider gets its own deadline and the chain as a whole gets a
        wall-clock budget, so an unreachable provider costs seconds rather than
        minutes. If every provider fails the request raises
        `ProviderUnavailableError` — unless demo mode authorizes the captured
        AquaLens fixture.
        """
        mode = (mode or "reservoir").lower().strip()
        if mode not in {"reservoir", "flood"}:
            mode = "reservoir"

        settings = get_settings()
        self._refresh_keys()
        errors: list[str] = []
        result: Optional[Dict[str, Any]] = None

        if should_use_fixture(provider_failed=False) and mode == "reservoir":
            logger.warning("AQUAMIND_DEMO_FORCE_FIXTURES is on — serving the AquaLens fixture.")
            return vision_fixture_result(mode)

        # Gemini first — this is the configured hackathon key path
        providers: list[tuple[str, str, Callable[[], Awaitable[Dict[str, Any]]]]] = []
        if self.gemini_key:
            providers.append(
                (
                    "Gemini Vision",
                    "Gemini Vision",
                    lambda: self._analyze_with_gemini(file_bytes, filename, mode=mode),
                )
            )
        if self.openrouter_key:
            providers.append(
                (
                    "OpenRouter Qwen2.5-VL",
                    "Qwen2.5-VL (OpenRouter)",
                    lambda: self._analyze_with_qwen_openrouter(file_bytes, filename, mode=mode),
                )
            )
        if self.dashscope_key:
            providers.append(
                (
                    "DashScope Qwen2.5-VL",
                    "Qwen2.5-VL (DashScope)",
                    lambda: self._analyze_with_qwen_dashscope(file_bytes, filename, mode=mode),
                )
            )

        deadline = time.monotonic() + settings.vision_total_budget_seconds
        for label, provider_name, call in providers:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                errors.append(f"{label}: skipped, vision budget exhausted")
                logger.warning("Vision budget exhausted before trying %s.", label)
                break
            try:
                logger.info("Analyzing with %s (mode=%s)...", label, mode)
                result = await self._run_provider(
                    label,
                    call,
                    timeout=min(settings.vision_provider_timeout_seconds, remaining),
                )
                result["provider"] = provider_name
                result["analysis_mode"] = "vlm"
                break
            except Exception as e:
                errors.append(f"{label}: {e}")
                logger.warning("%s failed: %s", label, e)
                result = None

        if result is None:
            if should_use_fixture(provider_failed=True) and mode == "reservoir":
                logger.warning(
                    "All vision providers unavailable (%s) — serving the AquaLens demo fixture.",
                    "; ".join(errors) or "no provider configured",
                )
                return vision_fixture_result(mode)
            if not providers:
                raise ProviderUnavailableError(
                    "AquaLens vision analysis is not configured. Set GEMINI_API_KEY "
                    "(or an OpenRouter/DashScope key) in .env.local to enable image analysis."
                )
            raise ProviderUnavailableError(
                "AquaLens could not reach any vision provider. Check network access "
                "and provider status, then retry the upload.",
                provider_errors=errors,
            )

        result["vision_mode"] = mode

        if mode == "reservoir":
            # Honest score: no water body => health must be 0
            risk = str(result.get("overall_risk") or "").lower()
            spread = str(result.get("water_spread") or "").lower()
            if "no reservoir" in risk or spread in {"none", "not applicable", "n/a"}:
                result["reservoir_health"] = 0

        # Interpretable pixel overlay via zero-shot CLIPSeg
        await self._attach_segmentation(result, file_bytes, mode)

        # Same metadata block the fixture carries, so a client can always tell a
        # live analysis from a captured one without inspecting field values.
        result["metadata"] = {
            "source": "vision_provider",
            "method": Method.VISION_MODEL.value,
            "data_quality": DataQuality.MEDIUM.value,
            "confidence": result.get("confidence"),
            "generated_at": isoformat(utc_now()),
            "model_version": result.get("provider"),
        }

        return result


vision_service = VisionService()
