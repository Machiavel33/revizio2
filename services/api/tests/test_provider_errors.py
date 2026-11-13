"""Tests de la traduction des erreurs fournisseurs LLM."""

import httpx
import pytest

from app.services.provider_errors import ProviderError, raise_provider_error


def _resp(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("POST", "http://x"))


def test_quota_exhausted():
    r = _resp(429, {"error": {"code": "credit_balance_exhausted", "message": "no credits"}})
    with pytest.raises(ProviderError) as e:
        raise_provider_error("openai", r)
    assert e.value.code == "quota_exhausted"
    assert "Crédits openai épuisés" in e.value.message


def test_invalid_key():
    r = _resp(401, {"error": {"code": "invalid_api_key", "message": "bad key"}})
    with pytest.raises(ProviderError) as e:
        raise_provider_error("openai", r)
    assert e.value.code == "invalid_key"


def test_rate_limited():
    r = _resp(429, {"error": {"type": "rate_limit", "message": "slow down"}})
    with pytest.raises(ProviderError) as e:
        raise_provider_error("anthropic", r)
    assert e.value.code == "rate_limited"


def test_provider_unavailable():
    r = _resp(503, {})
    with pytest.raises(ProviderError) as e:
        raise_provider_error("openai", r)
    assert e.value.code == "provider_unavailable"


def test_generic_error():
    r = _resp(400, {"error": {"message": "bad request"}})
    with pytest.raises(ProviderError) as e:
        raise_provider_error("openai", r)
    assert e.value.code == "provider_error"


# --- Normalisation des fiches ---


def test_normalize_sheet_fills_defaults():
    from app.services.sheet_generator import normalize_sheet

    out = normalize_sheet({"title": "T", "summary": "S"})
    assert out["title"] == "T"
    assert out["learning_objectives"] == []
    assert out["key_concepts"] == []
    assert out["sections"] == []
    assert out["formulas"] == []
    assert out["pitfalls"] == []
    assert out["mnemonics"] == []
    assert out["estimated_review_time_min"] == 15


def test_normalize_sheet_validates_section_type():
    from app.services.sheet_generator import normalize_sheet

    out = normalize_sheet(
        {
            "sections": [
                {"heading": "A", "type": "warning", "points": ["p1", 123, "p2"]},
                {"heading": "B", "type": "invalid", "points": ["x"]},
            ]
        }
    )
    assert out["sections"][0]["type"] == "warning"
    assert out["sections"][0]["points"] == ["p1", "p2"]  # 123 filtré
    assert out["sections"][1]["type"] == "normal"  # type invalide -> normal


def test_normalize_sheet_concepts_importance():
    from app.services.sheet_generator import normalize_sheet

    out = normalize_sheet(
        {
            "key_concepts": [
                {"term": "A", "definition": "d", "importance": "high", "example": "e"},
                {"term": "B", "definition": "d", "importance": "bogus"},
            ]
        }
    )
    assert out["key_concepts"][0]["importance"] == "high"
    assert out["key_concepts"][0]["example"] == "e"
    assert out["key_concepts"][1]["importance"] == "medium"  # invalide -> medium


def test_normalize_sheet_handles_garbage():
    from app.services.sheet_generator import normalize_sheet

    out = normalize_sheet("not a dict")  # type: ignore[arg-type]
    assert out["title"] == "Fiche de révision"
    assert out["sections"] == []
