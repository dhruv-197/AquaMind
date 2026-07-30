import os
import json
import base64
import logging
import httpx
from typing import Dict, Any, Optional
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
            last_err: Optional[Exception] = None
            for model_name in model_candidates:
                try:
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
                    text = response.text
                    if text:
                        logger.info("Gemini Vision succeeded with model=%s mode=%s", model_name, mode)
                        return self._parse_json_response(text)
                    raise ValueError(f"Empty response from {model_name}")
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
        async with httpx.AsyncClient(timeout=60.0) as client:
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
        async with httpx.AsyncClient(timeout=60.0) as client:
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

    async def analyze_reservoir_image(
        self, file_bytes: bytes, filename: str, mode: str = "reservoir"
    ) -> Dict[str, Any]:
        """
        Multimodal VLM analysis + CLIPSeg zero-shot segmentation overlay.

        mode:
          - reservoir — reservoir health metrics + shoreline classes
          - flood — permanent water vs flood inundation guidance + exclusive masks

        Priority: Gemini Vision -> Qwen2.5-VL (OpenRouter) -> Qwen2.5-VL (DashScope)
        """
        mode = (mode or "reservoir").lower().strip()
        if mode not in {"reservoir", "flood"}:
            mode = "reservoir"

        self._refresh_keys()
        errors = []
        result: Optional[Dict[str, Any]] = None

        # Gemini first — this is the configured hackathon key path
        if self.gemini_key:
            try:
                logger.info("Analyzing with Gemini Vision API (mode=%s)...", mode)
                result = await self._analyze_with_gemini(file_bytes, filename, mode=mode)
                result["provider"] = "Gemini Vision"
                result["analysis_mode"] = "vlm"
            except Exception as e:
                errors.append(f"Gemini Vision: {e}")
                logger.warning(f"Gemini Vision failed: {e}")

        if result is None and self.openrouter_key:
            try:
                logger.info("Analyzing with Qwen2.5-VL via OpenRouter (mode=%s)...", mode)
                result = await self._analyze_with_qwen_openrouter(file_bytes, filename, mode=mode)
                result["provider"] = "Qwen2.5-VL (OpenRouter)"
                result["analysis_mode"] = "vlm"
            except Exception as e:
                errors.append(f"OpenRouter Qwen2.5-VL: {e}")
                logger.warning(f"OpenRouter Qwen2.5-VL failed: {e}")

        if result is None and self.dashscope_key:
            try:
                logger.info("Analyzing with Qwen2.5-VL via DashScope (mode=%s)...", mode)
                result = await self._analyze_with_qwen_dashscope(file_bytes, filename, mode=mode)
                result["provider"] = "Qwen2.5-VL (DashScope)"
                result["analysis_mode"] = "vlm"
            except Exception as e:
                errors.append(f"DashScope Qwen2.5-VL: {e}")
                logger.warning(f"DashScope Qwen2.5-VL failed: {e}")

        if result is None:
            if not errors:
                raise RuntimeError(
                    "No vision AI API key configured. Set GEMINI_API_KEY in .env.local "
                    "(Google AI Studio key usually starts with AIza...)."
                )
            raise RuntimeError(f"Vision AI failed: {'; '.join(errors)}")

        result["vision_mode"] = mode

        if mode == "reservoir":
            # Honest score: no water body => health must be 0
            risk = str(result.get("overall_risk") or "").lower()
            spread = str(result.get("water_spread") or "").lower()
            if "no reservoir" in risk or spread in {"none", "not applicable", "n/a"}:
                result["reservoir_health"] = 0

        # Interpretable pixel overlay via zero-shot CLIPSeg
        try:
            from fastapi_app.services.clipseg_service import segment_image

            logger.info("Running CLIPSeg segmentation overlay (mode=%s)...", mode)
            segmentation = segment_image(file_bytes, mode=mode)
            result["segmentation"] = segmentation
            if segmentation.get("available"):
                result["provider"] = f"{result.get('provider', 'AquaLens')} + CLIPSeg"
                result["analysis_mode"] = "vlm+clipseg"
        except Exception as seg_err:
            logger.warning("CLIPSeg step skipped: %s", seg_err)
            result["segmentation"] = {
                "available": False,
                "error": str(seg_err),
                "classes": [],
                "overlay_base64": None,
            }

        return result


vision_service = VisionService()
