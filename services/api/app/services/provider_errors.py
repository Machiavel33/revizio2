"""Traduction des erreurs des fournisseurs LLM en messages clairs et actionnables.

Un `raise_for_status()` brut remonte « 429 Too Many Requests » alors que la cause
réelle peut être « crédits épuisés » (permanent) ou « clé invalide ». On inspecte
le corps de la réponse pour produire un message exploitable par l'admin/étudiant.
"""

import httpx


class ProviderError(Exception):
    """Erreur d'un fournisseur LLM, avec un message clair et un code stable."""

    def __init__(self, provider: str, code: str, message: str) -> None:
        super().__init__(message)
        self.provider = provider
        self.code = code
        self.message = message


def _extract_error(body: dict) -> tuple[str, str]:
    """Retourne (code, message) depuis le corps d'erreur OpenAI/Anthropic."""
    err = body.get("error", body)
    if isinstance(err, dict):
        code = err.get("code") or err.get("type") or ""
        message = err.get("message") or ""
        return str(code), str(message)
    return "", str(err)


def raise_provider_error(provider: str, resp: httpx.Response) -> None:
    """Lève une ProviderError claire selon le statut et le corps de la réponse."""
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = {}
    code, message = _extract_error(body)
    low = (code + " " + message).lower()

    if "insufficient_quota" in low or "credit_balance_exhausted" in low or "no credits" in low:
        raise ProviderError(
            provider,
            "quota_exhausted",
            f"Crédits {provider} épuisés : ajoutez du crédit sur le compte du fournisseur "
            f"ou configurez une autre clé (BYOK).",
        )
    if resp.status_code == 401 or "invalid_api_key" in low or "authentication" in low:
        raise ProviderError(
            provider,
            "invalid_key",
            f"Clé {provider} invalide ou révoquée.",
        )
    if resp.status_code == 429:
        raise ProviderError(
            provider,
            "rate_limited",
            f"Limite de débit {provider} atteinte : réessayez dans un instant.",
        )
    if resp.status_code >= 500:
        raise ProviderError(
            provider,
            "provider_unavailable",
            f"Fournisseur {provider} indisponible (erreur {resp.status_code}).",
        )
    raise ProviderError(
        provider,
        "provider_error",
        f"Erreur {provider} ({resp.status_code}): {message[:200] or 'inconnue'}",
    )
