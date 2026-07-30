"""Generate candidate operational decisions from upstream prediction payloads."""
from __future__ import annotations

from typing import Any

from fastapi_app.decision_engine.optimization.constants import (
    ELECTRICITY_INR_PER_MWH,
    WATER_VALUE_INR_PER_MCM,
)


def _action(
    *,
    id: str,
    title: str,
    description: str,
    decision_type: str,
    priority: str,
    timeline: str,
    why: str,
    models: list[str],
    impact: float,
    risk_reduction: float,
    water_mcm: float,
    population: int,
    cost_inr: float,
    confidence: float,
    expected_benefits: list[str],
    benefit_inr: float | None = None,
) -> dict[str, Any]:
    benefit = benefit_inr
    if benefit is None:
        benefit = round(water_mcm * WATER_VALUE_INR_PER_MCM, 0)
    return {
        "id": id,
        "title": title,
        "description": description,
        "decision_type": decision_type,
        "priority_level": priority,
        "implementation_priority": priority,
        "timeline_bucket": timeline,
        "why": why,
        "contributing_models": models,
        "expected_impact": why,
        "expected_benefits": expected_benefits,
        "estimated_water_saved_mcm": round(water_mcm, 3),
        "population_protected": int(population),
        "estimated_cost_inr": round(cost_inr, 0),
        "estimated_benefit_inr": round(float(benefit), 0),
        "impact_score": round(impact, 1),
        "risk_reduction_score": round(risk_reduction, 1),
        "confidence": round(max(0.3, min(0.98, confidence)), 4),
        "ai_reasoning": {
            "why": why,
            "contributing_models": models,
            "expected_impact": expected_benefits,
            "confidence": round(max(0.3, min(0.98, confidence)), 4),
        },
    }


def generate_from_reservoir(reservoir: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not reservoir or not reservoir.get("trained"):
        return []
    actions: list[dict[str, Any]] = []
    summary = reservoir.get("summary") or {}
    pct = float(
        reservoir.get("forecasted_storage_pct")
        or summary.get("forecasted_storage_pct")
        or 50.0
    )
    days = summary.get("days_to_critical") or summary.get("remaining_days")
    capacity = float(reservoir.get("capacity_mcm") or summary.get("capacity_mcm") or 250.0)
    name = reservoir.get("reservoir_name") or reservoir.get("reservoir_id") or "Primary reservoir"
    conf = float(reservoir.get("confidence_score") or 0.7)
    models = ["reservoir_forecast"]

    if days and int(days) <= 60 and pct < 45:
        cut = min(18, max(8, round((40 - pct) * 0.45)))
        water = capacity * (cut / 100.0) * 0.35
        actions.append(
            _action(
                id="res-reduce-release",
                title=f"Reduce release by {cut}%",
                description=(
                    f"{name} expected below 20% in {int(days)} days "
                    f"(forecast storage {pct:.1f}%). Reduce releases to conserve storage."
                ),
                decision_type="reservoir_release",
                priority="immediate" if int(days) <= 21 or pct < 25 else "short_term",
                timeline="today" if int(days) <= 14 else "next_7_days",
                why=f"{name} projected critical in {int(days)} days at {pct:.1f}% storage.",
                models=models,
                impact=78 if pct < 30 else 65,
                risk_reduction=72 if int(days) <= 35 else 55,
                water_mcm=water,
                population=int(min(400_000, max(50_000, (60 - pct) * 8_000))),
                cost_inr=120_000,
                confidence=conf,
                expected_benefits=[
                    f"Conserve ~{water:.1f} MCM over the planning horizon",
                    "Delay critical storage breach",
                ],
            )
        )
        actions.append(
            _action(
                id="res-activate-secondary",
                title="Activate secondary reservoir",
                description=f"Bring standby storage online to buffer {name} drawdown.",
                decision_type="water_allocation",
                priority="short_term",
                timeline="next_7_days",
                why=f"Primary storage {name} under stress; secondary source reduces outage risk.",
                models=models + ["water_stress"],
                impact=70,
                risk_reduction=68,
                water_mcm=capacity * 0.06,
                population=180_000,
                cost_inr=850_000,
                confidence=conf * 0.92,
                expected_benefits=["Diversify supply", "Protect municipal peak demand"],
            )
        )
        actions.append(
            _action(
                id="res-delay-irrigation",
                title="Delay irrigation allocation",
                description="Postpone non-critical irrigation releases until storage recovers above 40%.",
                decision_type="water_allocation",
                priority="short_term",
                timeline="next_30_days",
                why="Irrigation deferral preserves municipal and industrial buffer.",
                models=models,
                impact=58,
                risk_reduction=50,
                water_mcm=capacity * 0.04,
                population=90_000,
                cost_inr=60_000,
                confidence=conf * 0.88,
                expected_benefits=[f"Reallocate ~{capacity * 0.04:.1f} MCM to urban supply"],
            )
        )
    elif pct < 55:
        actions.append(
            _action(
                id="res-tighten-curve",
                title="Tighten reservoir rule-curve releases",
                description=f"Align {name} releases with forecast demand peaks only.",
                decision_type="reservoir_release",
                priority="medium_term",
                timeline="next_30_days",
                why=f"Storage at {pct:.1f}% — proactive release discipline.",
                models=models,
                impact=45,
                risk_reduction=40,
                water_mcm=capacity * 0.02,
                population=40_000,
                cost_inr=40_000,
                confidence=conf,
                expected_benefits=["Reduce unnecessary drawdown"],
            )
        )
    return actions


def generate_from_demand(demand: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not demand or not demand.get("trained"):
        return []
    actions: list[dict[str, Any]] = []
    summary = demand.get("summary") or {}
    growth = float(summary.get("growth_pct") or 0.0)
    peak = float(summary.get("predicted_peak_demand_mgd") or demand.get("today_predicted_demand_mgd") or 0)
    util = float(summary.get("capacity_utilization_pct") or 0)
    conf = float(demand.get("confidence_score") or 0.7)
    models = ["water_demand"]
    risk = str(summary.get("expected_shortage_risk") or demand.get("risk_label") or "").upper()

    if growth >= 8 or util >= 85 or risk in {"HIGH", "CRITICAL", "MEDIUM", "MODERATE"}:
        actions.append(
            _action(
                id="dem-pump-capacity",
                title="Increase Pump Station 3 capacity",
                description=(
                    f"Demand expected to increase {growth:.1f}% "
                    f"(peak {peak:.1f} MGD, util {util:.0f}%). Boost PS-3 throughput."
                ),
                decision_type="infrastructure_priority",
                priority="immediate" if util >= 92 or risk in {"HIGH", "CRITICAL"} else "short_term",
                timeline="next_7_days" if util >= 90 else "next_30_days",
                why=f"Demand growth {growth:.1f}% with capacity utilisation {util:.0f}%.",
                models=models,
                impact=74 if util >= 90 else 60,
                risk_reduction=66,
                water_mcm=max(2.0, peak * 0.04),
                population=int(min(350_000, peak * 2_200)),
                cost_inr=2_400_000,
                confidence=conf,
                expected_benefits=[
                    "Avoid peak-hour shortfall",
                    "Stabilize pressure in high-demand DMAs",
                ],
            )
        )
        elec_mwh = max(8.0, peak * 0.12)
        elec_save = elec_mwh * ELECTRICITY_INR_PER_MWH * 0.18
        actions.append(
            _action(
                id="dem-offpeak-pumps",
                title="Run pumps during off-peak electricity hours",
                description="Shift non-critical pumping to off-peak tariff windows to cut operating cost.",
                decision_type="pump_scheduling",
                priority="short_term",
                timeline="today",
                why="Demand surge raises pumping load; off-peak scheduling reduces ₹ electricity cost.",
                models=models,
                impact=52,
                risk_reduction=28,
                water_mcm=0.4,
                population=25_000,
                cost_inr=75_000,
                confidence=conf * 0.9,
                expected_benefits=[
                    f"Estimated electricity cost reduction ≈ ₹{elec_save:,.0f}",
                    "Lower peak grid load",
                ],
                benefit_inr=elec_save,
            )
        )
    if util >= 80 or risk in {"HIGH", "CRITICAL"}:
        actions.append(
            _action(
                id="dem-conservation",
                title="Issue conservation advisory",
                description="Trigger municipal conservation messaging ahead of forecast peak demand.",
                decision_type="conservation_advisory",
                priority="short_term",
                timeline="next_7_days",
                why=f"Capacity utilisation {util:.0f}% with elevated shortage risk ({risk or 'n/a'}).",
                models=models + ["water_stress"],
                impact=55,
                risk_reduction=48,
                water_mcm=max(1.5, peak * 0.03),
                population=int(min(500_000, peak * 3_000)),
                cost_inr=180_000,
                confidence=conf * 0.85,
                expected_benefits=["Demand-side reduction of 3–5%", "Public preparedness"],
            )
        )
    return actions


def generate_from_stress(stress: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not stress or stress.get("water_stress_index") is None:
        return []
    actions: list[dict[str, Any]] = []
    wsi = float(stress["water_stress_index"])
    label = str(stress.get("risk_label") or "").upper()
    pop = int(stress.get("population_impact") or (stress.get("summary") or {}).get("population_affected") or 0)
    conf = float(stress.get("confidence") or 0.65)
    region = (stress.get("region") or {}).get("name") or "Selected region"
    models = ["water_stress", "water_demand", "reservoir_forecast"]
    expected = stress.get("expected_stress_date")

    # Prefer stress recommended_actions when present — enrich with optimization metrics
    for raw in stress.get("recommended_actions") or []:
        title = str(raw.get("title") or "Operational action")
        rid = str(raw.get("id") or title.lower().replace(" ", "-"))
        priority = str(raw.get("priority") or "short_term")
        dtype = _map_stress_title_to_type(title)
        severity = max(0.0, wsi - 40.0)
        actions.append(
            _action(
                id=f"stress-{rid}",
                title=title,
                description=str(raw.get("description") or title),
                decision_type=dtype,
                priority=priority if priority in {"immediate", "short_term", "medium_term", "monitor"} else "short_term",
                timeline=_timeline_from_priority(priority, wsi),
                why=(
                    f"{region} WSI={wsi:.1f} ({label})"
                    + (f"; elevated stress by {expected}" if expected else "")
                ),
                models=models,
                impact=min(95, 40 + severity),
                risk_reduction=min(90, 35 + severity * 0.9),
                water_mcm=max(1.0, severity * 0.25),
                population=max(pop, 20_000),
                cost_inr=200_000 + severity * 15_000,
                confidence=conf,
                expected_benefits=list(stress.get("executive_insights") or [])[:2]
                or [f"Reduce regional WSI pressure in {region}"],
            )
        )

    if wsi >= 61 and not any(a["id"] == "stress-emergency-supply" for a in actions):
        actions.append(
            _action(
                id="stress-emergency-supply",
                title="Activate emergency supply plan",
                description=f"Trigger contingency supply for {region} while WSI remains {label}.",
                decision_type="emergency_response",
                priority="immediate",
                timeline="today",
                why=f"WSI {wsi:.1f} indicates high/critical regional stress.",
                models=models,
                impact=88,
                risk_reduction=80,
                water_mcm=8.0,
                population=max(pop, 100_000),
                cost_inr=3_500_000,
                confidence=conf,
                expected_benefits=["Protect critical facilities", "Reduce outage duration"],
            )
        )

    if wsi >= 50:
        actions.append(
            _action(
                id="stress-maint-priority",
                title="Prioritize DMA maintenance in high-stress wards",
                description="Front-load leak / valve maintenance where WSI and population impact overlap.",
                decision_type="maintenance_priority",
                priority="medium_term",
                timeline="next_30_days",
                why="Maintenance in stressed DMAs multiplies water-saved benefit.",
                models=models,
                impact=48,
                risk_reduction=42,
                water_mcm=2.2,
                population=max(30_000, pop // 3),
                cost_inr=950_000,
                confidence=conf * 0.8,
                expected_benefits=["Reduce non-revenue water", "Improve network resilience"],
            )
        )
    return actions


def generate_infrastructure_baseline() -> list[dict[str, Any]]:
    """Always-available planning actions from infrastructure constraints (placeholders)."""
    return [
        _action(
            id="infra-telemetry",
            title="Increase telemetry refresh for priority assets",
            description="Raise SCADA / IoT polling cadence on pumps and reservoirs feeding stressed zones.",
            decision_type="infrastructure_priority",
            priority="monitor",
            timeline="next_6_months",
            why="Higher observability improves decision confidence across all models.",
            models=["water_stress"],
            impact=30,
            risk_reduction=22,
            water_mcm=0.3,
            population=10_000,
            cost_inr=220_000,
            confidence=0.7,
            expected_benefits=["Faster anomaly detection"],
        )
    ]


def _map_stress_title_to_type(title: str) -> str:
    t = title.lower()
    if "pump" in t:
        return "pump_scheduling"
    if "release" in t or "reservoir" in t:
        return "reservoir_release"
    if "industrial" in t or "allocation" in t:
        return "water_allocation"
    if "conservation" in t or "advisory" in t:
        return "conservation_advisory"
    if "emergency" in t:
        return "emergency_response"
    if "maintenance" in t:
        return "maintenance_priority"
    return "infrastructure_priority"


def _timeline_from_priority(priority: str, wsi: float) -> str:
    if priority == "immediate" or wsi >= 75:
        return "today"
    if priority == "short_term":
        return "next_7_days"
    if priority == "medium_term":
        return "next_30_days"
    return "next_6_months"
