"""Service de génération de fiche de révision via LLM (structured output).

Supporte Anthropic (Claude) et OpenAI (GPT). La clé API est déchiffrée à la volée.
La sortie est un JSON strict conforme au schéma StudySheetContent.
"""

# ruff: noqa: E501  (le prompt système contient des lignes longues volontaires)

import json

import httpx

from app.services.provider_errors import raise_provider_error

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = """Tu es un professeur agrégé expert en pédagogie et en création de fiches de révision.
À partir de la transcription d'un cours, tu produis une fiche de révision structurée, claire et complète.

Règles :
- Résume fidèlement le contenu, sans inventer d'informations absentes de la transcription.
- Extrais les notions clés avec des définitions précises.
- Organise le contenu en sections logiques.
- Génère des flashcards (question/réponse) pour la révision active.
- Propose des questions de révision ouvertes.
- Estime un temps de révision réaliste en minutes.
- Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, conforme au schéma fourni."""

SHEET_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "key_concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "definition": {"type": "string"},
                },
                "required": ["term", "definition"],
            },
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "points": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["heading", "points"],
            },
        },
        "flashcards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
            },
        },
        "review_questions": {"type": "array", "items": {"type": "string"}},
        "estimated_review_time_min": {"type": "integer"},
    },
    "required": [
        "title",
        "summary",
        "key_concepts",
        "sections",
        "flashcards",
        "review_questions",
        "estimated_review_time_min",
    ],
}


def _build_user_prompt(transcript: str, language: str) -> str:
    return (
        f"Langue du cours : {language}.\n"
        f"Voici la transcription du cours :\n\n---\n{transcript}\n---\n\n"
        f"Produis la fiche de révision au format JSON conforme au schéma."
    )


def _parse_json(text: str) -> dict:
    """Extrait et parse le JSON de la réponse LLM (tolère les fences markdown)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


async def generate_sheet_anthropic(
    transcript: str,
    api_key: str,
    language: str = "fr",
    model: str = "claude-3-5-sonnet-latest",
) -> dict:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": _build_user_prompt(transcript, language)}],
    }
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(ANTHROPIC_URL, headers=headers, json=body)
        if resp.status_code >= 400:
            raise_provider_error("anthropic", resp)
        payload = resp.json()
    text = "".join(
        block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text"
    )
    return {"content": _parse_json(text), "model": model}


async def generate_sheet_openai(
    transcript: str,
    api_key: str,
    language: str = "fr",
    model: str = "gpt-4o",
) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(transcript, language)},
        ],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(OPENAI_CHAT_URL, headers=headers, json=body)
        if resp.status_code >= 400:
            raise_provider_error("openai", resp)
        payload = resp.json()
    text = payload["choices"][0]["message"]["content"]
    return {"content": _parse_json(text), "model": model}


async def generate_sheet(
    transcript: str,
    provider: str,
    api_key: str,
    language: str = "fr",
) -> dict:
    if provider == "anthropic":
        return await generate_sheet_anthropic(transcript, api_key, language=language)
    if provider == "openai":
        return await generate_sheet_openai(transcript, api_key, language=language)
    raise ValueError(f"Provider de génération non supporté: {provider}")
