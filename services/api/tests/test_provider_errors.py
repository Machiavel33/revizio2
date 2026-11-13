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
