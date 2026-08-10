"""One response envelope for every AI synthesis path.

Recommendations can be produced by a hosted LLM, by the local rules engine, or
by a checked-in fixture. AquaLens can be produced by a vision-language model or
by a fixture. Whichever path answers, callers see the same field set and a
metadata block that describes the path that *actually* ran — so a rules-engine
result can never be presented with remote-AI provenance, and a fixture can never
be mistaken for a live reading.
"""
from __future__ import annotations

from typing import Any

from fastapi_app.core.data_quality import DataQuality, Method, isoformat, utc_now
from fastapi_app.core.demo_mode import (
    SOURCE_DEMO_FIXTURE,
    SOURCE_REMOTE_AI,
    SOURCE_RULES_FALLBACK,
    FixtureValidationError,
    fixture_metadata,
    load_fixture,
)

#: Fields a recommendation payload must carry before it can be returned.
RECOMMENDATION_REQUIRED_FIELDS = ("recommendations", "expected_saving", "text_summary")

_METHOD_FOR_SOURCE = {
    SOURCE_REMOTE_AI: Method.REMOTE_AI,
    SOURCE_RULES_FALLBACK: Method.RULES_ENGINE,
    SOURCE_DEMO_FIXTURE: Method.FALLBACK,
}

_QUALITY_FOR_SOURCE = {
    SOURCE_REMOTE_AI: DataQuality.MEDIUM,
    SOURCE_RULES_FALLBACK: DataQuality.MEDIUM,
    SOURCE_DEMO_FIXTURE: DataQuality.LOW,
}


class SynthesisContractError(RuntimeError):
    """A synthesis result is missing fields the response contract guarantees."""


def _classify(raw_source: str, provider: str) -> tuple[str, bool]:
    """Map an engine's internal source label onto the public vocabulary.

    Returns `(source, cached)`. A cache hit keeps the provenance of whatever
    originally produced the entry rather than inventing a "cache" source.
    """
    raw_source = (raw_source or "").strip().lower()
    provider = (provider or "").strip().lower()

    if raw_source == "cache":
        cached = True
        raw_source = SOURCE_RULES_FALLBACK if provider in ("", "local-rules") else SOURCE_REMOTE_AI
    else:
        cached = False

    if raw_source in (SOURCE_REMOTE_AI, "gemini"):
        return SOURCE_REMOTE_AI, cached
    if raw_source == SOURCE_DEMO_FIXTURE:
        return SOURCE_DEMO_FIXTURE, cached
    return SOURCE_RULES_FALLBACK, cached


def normalize_recommendation_result(raw: Any) -> dict[str, Any]:
    """Validate a synthesis result and stamp it with consistent provenance.

    Raises `SynthesisContractError` when the payload could not satisfy the
    contract, so the caller degrades to the next path instead of returning a
    success response with holes in it.
    """
    if not isinstance(raw, dict):
        raise SynthesisContractError("Recommendation synthesis returned a non-object result.")

    recommendations = raw.get("recommendations")
    if isinstance(recommendations, str):
        recommendations = [recommendations]
    if not isinstance(recommendations, list):
        raise SynthesisContractError("Recommendation synthesis returned no recommendation list.")
    recommendations = [str(item).strip() for item in recommendations if str(item).strip()]
    if not recommendations:
        raise SynthesisContractError("Recommendation synthesis returned an empty recommendation list.")

    expected_saving = str(raw.get("expected_saving") or "").strip()
    if not expected_saving:
        raise SynthesisContractError("Recommendation synthesis returned no expected_saving.")

    text_summary = str(raw.get("text_summary") or "").strip() or " ".join(recommendations)

    provider = str(raw.get("provider") or "local-rules")
    source, cached = _classify(str(raw.get("source") or ""), provider)

    result = {
        **raw,
        "recommendations": recommendations,
        "expected_saving": expected_saving,
        "text_summary": text_summary,
        "source": source,
        "provider": provider,
        "metadata": {
            "source": source,
            "method": _METHOD_FOR_SOURCE[source].value,
            "data_quality": _QUALITY_FOR_SOURCE[source].value,
            "generated_at": isoformat(utc_now()),
            "model_version": provider,
            "cached": cached,
        },
    }
    return result


def recommendation_fixture_result() -> dict[str, Any]:
    """Materialize the recommendation fixture in the standard envelope.

    Callers must have cleared `should_use_fixture()` first; this function does
    not re-check demo mode, it only builds the payload.
    """
    fixture = load_fixture("recommendations")
    fixture.pop("_fixture", None)
    result = normalize_recommendation_result(
        {
            **fixture,
            "source": SOURCE_DEMO_FIXTURE,
            "provider": "demo-fixture",
        }
    )
    result["metadata"] = fixture_metadata(
        "recommendations",
        note="Captured recommendation set served because live synthesis was unavailable.",
    )
    return result


def water_intelligence_fixture() -> dict[str, Any]:
    """Materialize the dashboard fusion fixture with per-component provenance.

    Every component carries the same fixture metadata, so no card can imply it
    is showing a live reading while its neighbour shows a fixture.
    """
    fixture = load_fixture("water_intelligence")
    fixture.pop("_fixture", None)
    components = ("water_stress", "shortage", "leak", "groundwater", "demand", "climate")
    fixture["metadata"] = {
        component: fixture_metadata(
            "water_intelligence",
            observed_at=(fixture.get(component) or {}).get("observed_at"),
            model_version="demo_fixture:water_intelligence",
            note="Captured water-intelligence snapshot served because live fusion was unavailable.",
        )
        for component in components
    }
    return fixture


def vision_fixture_result(mode: str = "reservoir") -> dict[str, Any]:
    """Materialize the AquaLens fixture in the shape the vision route expects.

    Only reservoir mode has a fixture; flood mode has no captured reference, so
    the caller must surface the provider error rather than substitute one.
    """
    if (mode or "reservoir").lower().strip() != "reservoir":
        raise FixtureValidationError(f"No AquaLens demo fixture exists for mode {mode!r}.")

    fixture = load_fixture("vision_reservoir")
    fixture.pop("_fixture", None)
    fixture["provider"] = "AquaLens Reference Analysis"
    fixture["analysis_mode"] = "demo_fixture"
    fixture["vision_mode"] = "reservoir"
    fixture["metadata"] = fixture_metadata(
        "vision_reservoir",
        model_version="demo_fixture:vision_reservoir",
        note=(
            "Captured reference analysis served because no vision provider was reachable. "
            "It does not describe the uploaded image."
        ),
    )
    return fixture


def leak_fixture_result() -> dict[str, Any]:
    """Materialize the acoustic-leak fixture for `/detect-leak-signal`.

    Used only when the trained classifier artifact is missing (or deliberately
    forced) and demo mode authorizes the stand-in. The payload keeps the
    classifier's field names so the Alerts page and WSI fusion keep working.
    """
    fixture = load_fixture("leak_detection")
    fixture.pop("_fixture", None)
    fixture["source"] = SOURCE_DEMO_FIXTURE
    fixture["demo"] = True
    fixture["metadata"] = fixture_metadata(
        "leak_detection",
        observed_at=fixture.get("observed_at"),
        model_version="demo_fixture:leak_detection",
        note="Captured acoustic-leak result served because the classifier artifact was unavailable.",
    )
    return fixture
