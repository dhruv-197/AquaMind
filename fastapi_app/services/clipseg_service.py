"""Zero-shot CLIPSeg segmentation for AquaLens interpretability.

Modes
-----
reservoir — water, vegetation, dry shoreline, sedimentation, encroachment
flood     — permanent water bodies vs flood inundation (plus land context)

Flood mode deliberately separates standing water bodies (rivers/lakes/reservoirs)
from anomalous inundation over land so operators are not guided to \"flood\"
areas that are actually normal water.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("aquamind.clipseg")

CLIPSEG_CLASSES: List[Dict[str, str]] = [
    {"id": "water", "prompt": "river stream lake or reservoir open water surface", "color": "#06b6d4", "label": "Water body"},
    {"id": "vegetation", "prompt": "green grass meadow pasture trees and plants", "color": "#22c55e", "label": "Vegetation"},
    {"id": "dry_shoreline", "prompt": "exposed dry riverbank mudflat bare sand shoreline", "color": "#f59e0b", "label": "Dry bank / bare land"},
    {"id": "sedimentation", "prompt": "brown turbid muddy sediment in water", "color": "#a16207", "label": "Sedimentation"},
    {"id": "encroachment", "prompt": "buildings roads bridges and human structures", "color": "#ef4444", "label": "Encroachment"},
]

# Extra prompts aggregated into reservoir display classes
_RESERVOIR_EXTRA_PROMPTS: List[Dict[str, str]] = [
    {"id": "water_river", "prompt": "narrow winding river or creek water"},
    {"id": "veg_grass", "prompt": "lush green grassy fields and farmland"},
    {"id": "veg_trees", "prompt": "trees hedgerows and woody vegetation"},
    {"id": "bare_mud", "prompt": "bare brown mud and dry sediment bank"},
]

# Flood inundation mapping — display classes (aggregated heats computed internally)
FLOOD_CLIPSEG_CLASSES: List[Dict[str, str]] = [
    {
        "id": "permanent_water",
        "prompt": "clear deep blue river lake reservoir or canal",
        "color": "#0ea5e9",
        "label": "Permanent water body",
    },
    {
        "id": "flood_inundation",
        "prompt": "murky brown grey flood water covering land",
        "color": "#e11d48",
        "label": "Flood inundation",
    },
    {
        "id": "dry_land",
        "prompt": "dry land soil fields without standing water",
        "color": "#a8a29e",
        "label": "Dry / non-flooded land",
    },
    {
        "id": "vegetation",
        "prompt": "green tree canopy foliage coconut palms and plants",
        "color": "#22c55e",
        "label": "Vegetation",
    },
    {
        "id": "built_up",
        "prompt": "house building roof road vehicles and structures",
        "color": "#f59e0b",
        "label": "Built-up area",
    },
]

# Extra prompts used only for flood heat aggregation (not shown as separate legend rows)
_FLOOD_EXTRA_PROMPTS: List[Dict[str, str]] = [
    {"id": "standing_water", "prompt": "standing water surface flood or river"},
    {"id": "flood_houses", "prompt": "houses and trees standing in flood water"},
    {"id": "flood_road", "prompt": "submerged flooded road with standing water"},
    {"id": "flood_fields", "prompt": "inundated flooded fields and wetlands"},
]

_MODEL = None
_PROCESSOR = None
_LOAD_ERROR: Optional[str] = None


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _lazy_load():
    """Load CLIPSeg once; keep failure message if deps/model unavailable."""
    global _MODEL, _PROCESSOR, _LOAD_ERROR
    if _MODEL is not None and _PROCESSOR is not None:
        return True
    if _LOAD_ERROR:
        return False
    try:
        import torch  # noqa: F401
        from transformers import CLIPSegForImageSegmentation, CLIPSegProcessor

        model_id = "CIDAS/clipseg-rd64-refined"
        logger.info("Loading CLIPSeg model %s (first run may download weights)...", model_id)
        _PROCESSOR = CLIPSegProcessor.from_pretrained(model_id)
        _MODEL = CLIPSegForImageSegmentation.from_pretrained(model_id)
        _MODEL.eval()
        logger.info("CLIPSeg model ready.")
        return True
    except Exception as exc:
        _LOAD_ERROR = str(exc)
        logger.warning("CLIPSeg unavailable: %s", exc)
        return False


def _pil_from_bytes(file_bytes: bytes):
    from PIL import Image

    image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    max_side = 512
    w, h = image.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        image = image.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    return image


def _image_to_b64_png(image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _unavailable(error: Optional[str] = None) -> Dict[str, Any]:
    return {
        "available": False,
        "error": error or _LOAD_ERROR or "CLIPSeg dependencies not installed (torch + transformers).",
        "model": "CIDAS/clipseg-rd64-refined",
        "classes": [],
        "overlay_base64": None,
        "original_base64": None,
    }


def _run_clipseg_heats(image, classes: List[Dict[str, str]]):
    import numpy as np
    import torch
    from PIL import Image

    prompts = [c["prompt"] for c in classes]
    inputs = _PROCESSOR(
        text=prompts,
        images=[image] * len(prompts),
        padding=True,
        return_tensors="pt",
    )

    with torch.no_grad():
        outputs = _MODEL(**inputs)

    logits = outputs.logits
    if logits.ndim == 2:
        logits = logits.unsqueeze(0)
    probs = torch.sigmoid(logits).cpu().numpy()

    target_size = image.size
    heats: List[Any] = []
    for idx in range(len(classes)):
        heat = probs[idx]
        heat_img = Image.fromarray((heat * 255).astype(np.uint8), mode="L")
        heat_img = heat_img.resize(target_size, Image.BILINEAR)
        heats.append(np.array(heat_img).astype(np.float32) / 255.0)
    return heats


def _compose_overlay(
    image,
    classes: List[Dict[str, str]],
    heats: List[Any],
    masks: List[Any],
    threshold: float,
    legend_title: str,
    legend_subtitle: str,
) -> Dict[str, Any]:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    class_results: List[Dict[str, Any]] = []
    overlay = image.convert("RGBA")
    base_arr = np.array(overlay).astype(np.float32)

    for idx, cls in enumerate(classes):
        heat_arr = heats[idx]
        mask = masks[idx]
        coverage = float(mask.mean() * 100.0)
        score = float(heat_arr[mask].mean()) if mask.any() else float(heat_arr.mean())
        peak = float(heat_arr.max())

        r, g, b = _hex_to_rgb(cls["color"])
        alpha = np.zeros_like(heat_arr, dtype=np.float32)
        alpha[mask] = np.clip(0.25 + heat_arr[mask] * 0.55, 0.25, 0.8)

        tint = np.zeros_like(base_arr)
        tint[..., 0] = r
        tint[..., 1] = g
        tint[..., 2] = b
        tint[..., 3] = alpha * 255.0

        m3 = mask[..., None]
        base_arr = np.where(
            m3,
            base_arr * (1.0 - tint[..., 3:4] / 255.0) + tint * (tint[..., 3:4] / 255.0),
            base_arr,
        )

        class_results.append(
            {
                "id": cls["id"],
                "label": cls["label"],
                "prompt": cls["prompt"],
                "color": cls["color"],
                "score": round(score, 3),
                "peak_score": round(peak, 3),
                "coverage_pct": round(coverage, 2),
                "threshold": threshold,
            }
        )

    composed = Image.fromarray(np.clip(base_arr, 0, 255).astype(np.uint8), mode="RGBA")

    legend_w = 240
    canvas = Image.new("RGBA", (composed.width + legend_w, composed.height), (15, 23, 42, 255))
    canvas.paste(composed, (0, 0))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    draw.text((composed.width + 12, 16), legend_title, fill=(226, 232, 240, 255), font=font)
    draw.text((composed.width + 12, 34), legend_subtitle, fill=(148, 163, 184, 255), font=font)
    y = 60
    for item in class_results:
        r, g, b = _hex_to_rgb(item["color"])
        draw.rectangle([composed.width + 12, y, composed.width + 28, y + 16], fill=(r, g, b, 255))
        draw.text((composed.width + 36, y), f"{item['label']}", fill=(241, 245, 249, 255), font=font)
        draw.text(
            (composed.width + 36, y + 14),
            f"score {item['score']:.2f}  cov {item['coverage_pct']:.1f}%",
            fill=(148, 163, 184, 255),
            font=font,
        )
        y += 42

    return {
        "classes": class_results,
        "overlay_base64": _image_to_b64_png(canvas.convert("RGB")),
        "original_base64": _image_to_b64_png(image),
    }


def _rgb_water_prior(image) -> Any:
    """Cheap RGB prior for murky / open water (helps when CLIPSeg under-fires on grey floodwater)."""
    import numpy as np

    arr = np.array(image).astype(np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    brightness = (r + g + b) / 3.0
    sat = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
    # Lush canopy (exclude from water prior)
    green_dom = (g > r + 18) & (g > b + 12) & (g > 70)
    # Murky flood / grey-green water: mid brightness, low-ish saturation
    murky = (brightness > 35) & (brightness < 165) & (sat < 60) & ~green_dom
    bluish = (b >= r) & (b >= g - 8) & (brightness < 190) & (sat < 90)
    return murky | bluish


def _rgb_vegetation_prior(image) -> Any:
    """RGB prior for green grass / canopy — stops dry-shoreline from eating meadows."""
    import numpy as np

    arr = np.array(image).astype(np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    return (g > r + 12) & (g > b + 8) & (g > 55)


def _rgb_bare_soil_prior(image) -> Any:
    """RGB prior for tan/brown bare mud (not green pasture)."""
    import numpy as np

    arr = np.array(image).astype(np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    brightness = (r + g + b) / 3.0
    # Brown/tan: R and G elevated vs B, not green-dominant
    return (
        (r > b + 10)
        & (g > b + 5)
        & (g <= r + 25)
        & (brightness > 50)
        & (brightness < 200)
        & ~((g > r + 12) & (g > b + 8))
    )


def segment_reservoir_image(file_bytes: bytes, threshold: float = 0.45) -> Dict[str, Any]:
    """Reservoir / shoreline zero-shot CLIPSeg (backward compatible)."""
    return segment_image(file_bytes, mode="reservoir", threshold=threshold)


def segment_flood_image(file_bytes: bytes, threshold: float = 0.42) -> Dict[str, Any]:
    """Flood mode: permanent water vs inundation exclusive masks."""
    return segment_image(file_bytes, mode="flood", threshold=threshold)


def segment_image(
    file_bytes: bytes,
    mode: str = "reservoir",
    threshold: float = 0.45,
) -> Dict[str, Any]:
    """
    Run zero-shot CLIPSeg for ``reservoir`` or ``flood`` mode.

    Flood mode:
      1) Detect standing water (CLIPSeg multi-prompt max + RGB murky-water prior)
      2) Label as permanent only when clear-water score clearly beats flood prompts
      3) Remaining water defaults to flood inundation (fixes murky Kerala-style scenes
         where a generic \"water body\" prompt outscores a weak flood prompt)
    """
    if not _lazy_load():
        return _unavailable()

    import numpy as np

    mode = (mode or "reservoir").lower().strip()
    if mode not in {"reservoir", "flood"}:
        mode = "reservoir"

    try:
        image = _pil_from_bytes(file_bytes)

        if mode == "flood":
            infer_specs = list(FLOOD_CLIPSEG_CLASSES) + list(_FLOOD_EXTRA_PROMPTS)
            heats_all = _run_clipseg_heats(image, infer_specs)
            by_id = {spec["id"]: heats_all[i] for i, spec in enumerate(infer_specs)}

            pw = by_id["permanent_water"]
            flood_heat = np.maximum.reduce(
                [
                    by_id["flood_inundation"],
                    by_id["flood_houses"],
                    by_id["flood_road"],
                    by_id["flood_fields"],
                ]
            )
            standing = by_id["standing_water"]
            veg = by_id["vegetation"]
            built = by_id["built_up"]
            dry = by_id["dry_land"]

            rgb_water = _rgb_water_prior(image)

            # Standing water presence (CLIPSeg OR murky RGB prior)
            water = (
                (standing >= 0.30)
                | (flood_heat >= 0.26)
                | (pw >= 0.34)
                | (rgb_water & (veg < 0.55))
            )

            # Strong canopy stays vegetation (trees over flood still labelled veg on canopy)
            strong_veg = veg >= 0.52

            # Permanent only if clear-water cue clearly beats flood cues
            permanent_mask = (
                water
                & (pw >= 0.40)
                & (pw >= flood_heat + 0.08)
                & (pw >= standing * 0.95)
                & ~strong_veg
            )

            # Default: water that is not clearly permanent → flood inundation
            flood_mask = water & ~permanent_mask & ~(strong_veg & (standing < 0.28) & ~rgb_water)

            veg_mask = strong_veg & ~permanent_mask
            # Built-up: lower threshold; keep visible even near water edge
            built_mask = (built >= 0.22) & ~permanent_mask
            # Prefer built over flood on high built score (roofs/road)
            built_over_flood = built_mask & (built >= flood_heat + 0.05)
            flood_mask = flood_mask & ~built_over_flood
            dry_mask = (dry >= 0.30) & ~water & ~veg_mask & ~built_mask

            # Display heats: use aggregated flood heat for flood class scoring
            display_heats = [
                pw,
                flood_heat,
                dry,
                veg,
                built,
            ]
            masks = [
                permanent_mask,
                flood_mask,
                dry_mask,
                veg_mask & ~flood_mask,  # canopy; don't double-paint flood
                built_mask & ~flood_mask & ~permanent_mask,
            ]

            # Recompute class scores from exclusive masks for honest legend coverage
            composed = _compose_overlay(
                image,
                FLOOD_CLIPSEG_CLASSES,
                display_heats,
                masks,
                threshold=0.28,
                legend_title="Flood CLIPSeg",
                legend_subtitle="Permanent vs inundation",
            )

            pw_cov = float(permanent_mask.mean() * 100.0)
            fl_cov = float(flood_mask.mean() * 100.0)
            ambiguous = float(((pw >= 0.35) & (flood_heat >= 0.28)).mean() * 100.0)

            guidance = {
                "permanent_water_pct": round(pw_cov, 2),
                "flood_inundation_pct": round(fl_cov, 2),
                "ambiguous_overlap_pct": round(ambiguous, 2),
                "human_guidance": (
                    "Cyan/blue = likely existing water bodies (do not treat as flood). "
                    "Red/rose = likely flood inundation / murky water over land. "
                    "Green = tree canopy. Amber = built-up. "
                    "Prioritize rose zones for field verification."
                ),
                "method": (
                    "CLIPSeg multi-prompt flood heats + RGB murky-water prior; "
                    "permanent only when clear-water score beats flood by margin; "
                    "remaining standing water defaults to inundation. "
                    "Visual guidance only — not a hydrodynamic model."
                ),
            }

            return {
                "available": True,
                "mode": "flood",
                "model": "CIDAS/clipseg-rd64-refined",
                "method": "CLIPSeg flood multi-prompt + RGB prior",
                "threshold": 0.28,
                "guidance": guidance,
                "error": None,
                **composed,
            }

        # Reservoir mode — land-first exclusive masks (fixes water over-paint ~70%)
        infer_specs = list(CLIPSEG_CLASSES) + list(_RESERVOIR_EXTRA_PROMPTS)
        heats_all = _run_clipseg_heats(image, infer_specs)
        by_id = {spec["id"]: heats_all[i] for i, spec in enumerate(infer_specs)}

        water_h = np.maximum(by_id["water"], by_id["water_river"])
        veg_h = np.maximum.reduce([by_id["vegetation"], by_id["veg_grass"], by_id["veg_trees"]])
        shore_h = np.maximum(by_id["dry_shoreline"], by_id["bare_mud"])
        sed_h = by_id["sedimentation"]
        enc_h = by_id["encroachment"]

        rgb_veg = _rgb_vegetation_prior(image)
        rgb_bare = _rgb_bare_soil_prior(image)

        # Strict bluish open-water prior only (murky prior caused meadow→water bleed)
        arr = np.array(image).astype(np.float32)
        r_ch, g_ch, b_ch = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        bright = (r_ch + g_ch + b_ch) / 3.0
        sat = np.maximum(np.maximum(r_ch, g_ch), b_ch) - np.minimum(np.minimum(r_ch, g_ch), b_ch)
        bluish_water = (
            (b_ch > r_ch + 4)
            & (b_ch >= g_ch - 6)
            & (bright > 40)
            & (bright < 175)
            & (sat > 12)
            & ~rgb_veg
        )

        water_h = np.where(rgb_veg, water_h * 0.55, water_h)
        water_h = np.where(rgb_bare, water_h * 0.70, water_h)
        veg_h = np.where(rgb_veg, np.maximum(veg_h, 0.48), veg_h)
        shore_h = np.where(rgb_bare & ~rgb_veg, np.maximum(shore_h, 0.44), shore_h)
        shore_h = np.where(rgb_veg, shore_h * 0.40, shore_h)

        # 1) Green land / vegetation first
        veg_mask = rgb_veg | (
            (veg_h >= 0.36) & (veg_h + 0.04 >= water_h) & (veg_h + 0.02 >= shore_h)
        )

        # 2) Bare land / dry bank (tan floodplain) — not green
        shore_mask = (~veg_mask) & (
            (rgb_bare & (water_h < 0.50))
            | (
                (shore_h >= 0.36)
                & (shore_h + 0.05 >= water_h)
                & (shore_h + 0.02 >= veg_h)
            )
        )

        # 3) Water only when clearly strongest (or bluish + decent score)
        water_mask = (~veg_mask) & (~shore_mask) & (
            (
                (water_h >= 0.46)
                & (water_h >= veg_h + 0.08)
                & (water_h >= shore_h + 0.06)
            )
            | (bluish_water & (water_h >= 0.38) & (water_h >= veg_h + 0.05))
        )

        # 4) Sedimentation on muddy patches
        sed_mask = (
            (~veg_mask)
            & (sed_h >= 0.40)
            & (sed_h + 0.02 >= shore_h)
            & (sed_h >= water_h * 0.85)
            & ~((water_mask) & (water_h >= 0.55))
        )

        # 5) Encroachment
        enc_mask = (enc_h >= 0.30) & ~veg_mask & ~water_mask

        water_mask = water_mask & ~veg_mask & ~shore_mask
        shore_mask = shore_mask & ~veg_mask & ~water_mask
        sed_mask = sed_mask & ~veg_mask & ~water_mask & ~shore_mask
        enc_mask = enc_mask & ~veg_mask & ~water_mask & ~shore_mask & ~sed_mask

        display_heats = [water_h, veg_h, shore_h, sed_h, enc_h]
        masks = [water_mask, veg_mask, shore_mask, sed_mask, enc_mask]

        composed = _compose_overlay(
            image,
            CLIPSEG_CLASSES,
            display_heats,
            masks,
            threshold=0.36,
            legend_title="CLIPSeg legend",
            legend_subtitle="Land-first exclusive classes",
        )
        return {
            "available": True,
            "mode": "reservoir",
            "model": "CIDAS/clipseg-rd64-refined",
            "method": "CLIPSeg reservoir land-first + exclusive masks",
            "threshold": 0.46,
            "error": None,
            **composed,
        }
    except Exception as exc:
        logger.exception("CLIPSeg segmentation failed")
        return _unavailable(str(exc))
