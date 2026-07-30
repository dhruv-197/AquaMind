"""Dynamic recommendations from fused Water Stress outputs."""
from __future__ import annotations

from typing import Any

from fastapi_app.core.contracts import PredictionType, RiskLevel
from fastapi_app.decision_engine.rules import recommendation_from_prediction
from fastapi_app.prediction.base import PredictionOutput
from fastapi_app.prediction.models.water_stress.scenarios import delay_days_from_delta


def build_recommendations(
    *,
    fusion: dict[str, Any],
    region: dict[str, Any],
    baseline_wsi: float | None = None,
) -> dict[str, Any]:
    wsi = float(fusion["water_stress_index"])
    risk = RiskLevel(fusion["risk_level"])
    label = str(fusion.get("risk_label") or "MODERATE")
    name = str(region.get("name") or region.get("region_id") or "Region")
    industrial = float(region.get("industrial_share") or 0.25)
    pop_impact = int(fusion.get("population_impact") or 0)
    expected = fusion.get("expected_stress_date")

    actions: list[dict[str, Any]] = []

    if risk in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        release_bump = min(15, max(5, round((wsi - 60) * 0.35)))
        actions.append(
            {
                "id": "increase-pumping",
                "title": "Increase pumping capacity",
                "description": f"Raise emergency pumping for {name} while WSI remains {label}.",
                "priority": "immediate",
            }
        )
        cut = min(12, max(3, round(industrial * 20)))
        actions.append(
            {
                "id": "reduce-industrial",
                "title": "Reduce industrial allocation",
                "description": f"Cut industrial allocation by ~{cut}% to relieve network pressure.",
                "priority": "immediate",
            }
        )
        actions.append(
            {
                "id": "increase-release",
                "title": f"Increase reservoir release by {release_bump}%",
                "description": "Temporarily boost releases from primary storage to meet peak municipal demand.",
                "priority": "short_term",
            }
        )
        actions.append(
            {
                "id": "secondary-reservoir",
                "title": "Enable secondary reservoir",
                "description": "Bring standby storage online for the affected service area.",
                "priority": "short_term",
            }
        )
        actions.append(
            {
                "id": "conservation",
                "title": "Issue conservation advisory",
                "description": f"Public advisory for {name}; population at risk ≈ {pop_impact:,}.",
                "priority": "short_term",
            }
        )
        if risk == RiskLevel.CRITICAL:
            actions.append(
                {
                    "id": "emergency-supply",
                    "title": "Activate emergency supply plan",
                    "description": "Trigger contingency tankers / inter-basin transfer protocols.",
                    "priority": "immediate",
                }
            )
    elif risk == RiskLevel.MODERATE:
        actions.append(
            {
                "id": "tighten-releases",
                "title": "Tighten release scheduling",
                "description": "Align dam releases with forecast demand peaks for the next fortnight.",
                "priority": "short_term",
            }
        )
        actions.append(
            {
                "id": "draft-advisory",
                "title": "Prepare conservation advisory",
                "description": "Draft messaging for municipal stakeholders if WSI crosses High.",
                "priority": "monitor",
            }
        )
        if industrial >= 0.3:
            actions.append(
                {
                    "id": "industrial-watch",
                    "title": "Reduce industrial allocation",
                    "description": "Pre-negotiate a 5% industrial cut if stress escalates.",
                    "priority": "monitor",
                }
            )
    else:
        actions.append(
            {
                "id": "monitor",
                "title": "Continue monitoring",
                "description": f"{name} WSI is {label} ({wsi:.0f}). Maintain baseline telemetry review.",
                "priority": "monitor",
            }
        )

    insights: list[str] = []
    if expected:
        insights.append(f"{name} is expected to experience elevated stress by {expected}.")
    if pop_impact >= 50000:
        insights.append(f"Population at risk exceeds {pop_impact:,}.")
    if baseline_wsi is not None:
        delay = delay_days_from_delta(baseline_wsi, wsi)
        if delay > 0:
            insights.append(
                f"Scenario improves outlook — shortages delayed by roughly {delay} days vs baseline."
            )
        elif delay < 0:
            insights.append(
                f"Scenario worsens outlook — shortages advance by roughly {abs(delay)} days vs baseline."
            )
    if industrial >= 0.3 and risk in (RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.MODERATE):
        insights.append(
            f"Reducing industrial allocation by 5% could delay shortages by ~{max(5, int(12 * industrial))} days."
        )
    comps = fusion.get("components") or {}
    top = sorted(comps.items(), key=lambda kv: kv[1].get("contribution", 0), reverse=True)
    if top:
        key, _meta = top[0]
        # Deliberately no parenthetical debug detail here (e.g. "util=..., risk=...") —
        # the "Stress score fusion" panel already renders that per-component via
        # plainDetail(). Embedding it in this sentence produced garbled text on the
        # frontend: its parenthetical-stripping regex only removes up to the first
        # ")", so a nested-parens detail string like "(Demand≈68.9 MGD (share=45%),
        # util=89.59, risk=MEDIUM)" left ", util=89.59, risk=MEDIUM)." dangling after
        # the sentence. Keep this insight to a clean, complete sentence instead.
        insights.append(f"Primary stress driver: {key}.")

    # Decision Engine integration
    decision_po = PredictionOutput(
        prediction_type=PredictionType.WATER_STRESS,
        region_id=str(region.get("region_id") or "REG-1"),
        horizon_days=30,
        risk_level=risk,
        score=wsi,
        confidence=float(fusion.get("confidence") or 0.6),
        summary=insights[0] if insights else f"WSI={wsi:.1f} ({label}) for {name}",
        is_placeholder=False,
        metadata={
            "water_stress_index": wsi,
            "risk_label": label,
            "population_impact": pop_impact,
            "expected_stress_date": expected,
        },
    )
    engine_rec = recommendation_from_prediction(decision_po, risk)

    return {
        "recommended_actions": actions,
        "executive_insights": insights,
        "decision_engine": {
            "recommendation": engine_rec.model_dump(mode="json"),
            "prediction": decision_po.model_dump(mode="json"),
            "prediction_type": PredictionType.WATER_STRESS.value,
        },
    }
