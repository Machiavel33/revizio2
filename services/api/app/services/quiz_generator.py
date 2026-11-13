"""Génération de quiz par IA à partir de fiches de révision.

Produit des QCM (question + 4 choix + bonne réponse + explication) en JSON strict.
"""

import json

import httpx

from app.services.provider_errors import raise_provider_error

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = """Tu es un professeur qui crée des QCM de révision à partir de fiches de cours.
À partir du contenu fourni, génère des questions à choix multiples variées et pertinentes.

Règles :
- Chaque question a exactement 4 choix, une seule bonne réponse.
- Les questions couvrent différents points des fiches (pas de redondance).
- Mélange les niveaux (définitions, application, analyse).
- Fournis une explication courte pour la bonne réponse.
- Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour."""

QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "choices": {"type": "array", "items": {"type": "string"}},
                    "correct_index": {"type": "integer"},
                    "explanation": {"type": "string"},
                },
                "required": ["question", "choices", "correct_index", "explanation"],
            },
        },
    },
    "required": ["title", "questions"],
}


def _build_prompt(sheets_text: str, count: int, language: str) -> str:
    return (
        f"Langue : {language}.\n"
        f"Génère {count} questions à choix multiples à partir du contenu suivant :\n\n"
        f"---\n{sheets_text}\n---\n\n"
        f"Réponds en JSON conforme au schéma (title + questions[])."
    )


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


async def _anthropic(prompt: str, api_key: str, model: str) -> dict:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(ANTHROPIC_URL, headers=headers, json=body)
        if resp.status_code >= 400:
            raise_provider_error("anthropic", resp)
        payload = resp.json()
    text = "".join(b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
    return {"content": _parse_json(text), "model": model}


async def _openai(prompt: str, api_key: str, model: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(OPENAI_CHAT_URL, headers=headers, json=body)
        if resp.status_code >= 400:
            raise_provider_error("openai", resp)
        payload = resp.json()
    text = payload["choices"][0]["message"]["content"]
    return {"content": _parse_json(text), "model": model}


async def generate_quiz(
    sheets_text: str,
    provider: str,
    api_key: str,
    count: int = 10,
    language: str = "fr",
) -> dict:
    prompt = _build_prompt(sheets_text, count, language)
    if provider == "anthropic":
        return await _anthropic(prompt, api_key, "claude-3-5-sonnet-latest")
    if provider == "openai":
        return await _openai(prompt, api_key, "gpt-4o")
    raise ValueError(f"Provider non supporté: {provider}")
