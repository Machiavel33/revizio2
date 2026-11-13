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
À partir de la transcription d'un cours, tu produis une fiche de révision PROPRE, structurée et pédagogique.

Principes de qualité (impératifs) :
- FIDÉLITÉ : n'invente rien. Tout doit venir de la transcription. Si une info manque, ne la fabrique pas.
- STRUCTURE : organise en sections logiques qui suivent le plan du cours. Chaque section a un titre clair.
- MISE EN AVANT : distingue les définitions, les formules, les exemples, les pièges et les astuces (champ `type`).
- CONCISION : des points courts et denses, pas de remplissage. Une idée par point.
- PÉDAGOGIE : objectifs d'apprentissage en tête, notions clés avec définitions précises, exemples concrets.
- RÉVISION ACTIVE : flashcards (question/réponse) et questions ouvertes pour s'auto-évaluer.

Règles de forme :
- Titres en français correct, sans jargon inutile.
- Les définitions sont des phrases complètes, pas des fragments.
- Les formules sont écrites en texte lisible (ex. "F = m × a").
- Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, conforme au schéma fourni."""

# Types de section (mise en avant visuelle côté front) :
#   "definition" (encadré notion), "formula" (formule), "example" (exemple),
#   "warning" (piège/attention), "tip" (astuce/mnémotechnique), "normal" (défaut).
SECTION_TYPES = ["normal", "definition", "formula", "example", "warning", "tip"]

SHEET_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "learning_objectives": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3 à 6 objectifs d'apprentissage concrets ('À la fin, savoir...').",
        },
        "key_concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "definition": {"type": "string"},
                    "importance": {"type": "string", "enum": ["high", "medium"]},
                    "example": {"type": "string"},
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
                    "type": {"type": "string", "enum": SECTION_TYPES},
                    "points": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["heading", "points"],
            },
        },
        "formulas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "expression": {"type": "string"},
                    "meaning": {"type": "string"},
                },
                "required": ["name", "expression"],
            },
        },
        "pitfalls": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Erreurs fréquentes / pièges à éviter.",
        },
        "mnemonics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Moyens mnémotechniques pour retenir.",
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
        "Produis une fiche de révision de haute qualité, conforme au schéma JSON. "
        "Renseigne si pertinent : learning_objectives, formulas, pitfalls, mnemonics. "
        "Pour chaque section, choisis un `type` (normal/definition/formula/example/warning/tip) "
        "afin de mettre en avant l'essentiel. Sois fidèle à la transcription, structuré et concis."
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


def normalize_sheet(content: dict) -> dict:
    """Normalise la sortie LLM : garantit une structure complète et cohérente.

    Tolère les champs manquants (anciens modèles, LLM partiel) en fournissant des
    valeurs par défaut sûres, et valide les types de section. Le front peut ainsi
    toujours rendre la fiche sans planter.
    """
    if not isinstance(content, dict):
        content = {}

    def _list(v) -> list:
        return v if isinstance(v, list) else []

    def _str(v, default="") -> str:
        return v if isinstance(v, str) else default

    # Notions clés : normalise importance + example.
    concepts = []
    for k in _list(content.get("key_concepts")):
        if not isinstance(k, dict):
            continue
        concepts.append(
            {
                "term": _str(k.get("term")),
                "definition": _str(k.get("definition")),
                "importance": k.get("importance") if k.get("importance") in ("high", "medium") else "medium",
                "example": _str(k.get("example")),
            }
        )

    # Sections : valide le type, garantit points = liste de strings.
    sections = []
    for s in _list(content.get("sections")):
        if not isinstance(s, dict):
            continue
        stype = s.get("type") if s.get("type") in SECTION_TYPES else "normal"
        points = [p for p in _list(s.get("points")) if isinstance(p, str)]
        sections.append(
            {"heading": _str(s.get("heading")), "type": stype, "points": points}
        )

    # Formules.
    formulas = []
    for f in _list(content.get("formulas")):
        if isinstance(f, dict) and f.get("expression"):
            formulas.append(
                {
                    "name": _str(f.get("name")),
                    "expression": _str(f.get("expression")),
                    "meaning": _str(f.get("meaning")),
                }
            )

    # Flashcards.
    flashcards = []
    for fc in _list(content.get("flashcards")):
        if isinstance(fc, dict) and fc.get("question"):
            flashcards.append(
                {"question": _str(fc.get("question")), "answer": _str(fc.get("answer"))}
            )

    return {
        "title": _str(content.get("title"), "Fiche de révision"),
        "summary": _str(content.get("summary")),
        "learning_objectives": [o for o in _list(content.get("learning_objectives")) if isinstance(o, str)],
        "key_concepts": concepts,
        "sections": sections,
        "formulas": formulas,
        "pitfalls": [p for p in _list(content.get("pitfalls")) if isinstance(p, str)],
        "mnemonics": [m for m in _list(content.get("mnemonics")) if isinstance(m, str)],
        "flashcards": flashcards,
        "review_questions": [q for q in _list(content.get("review_questions")) if isinstance(q, str)],
        "estimated_review_time_min": int(content.get("estimated_review_time_min") or 15),
    }


async def generate_sheet(
    transcript: str,
    provider: str,
    api_key: str,
    language: str = "fr",
) -> dict:
    if provider == "anthropic":
        result = await generate_sheet_anthropic(transcript, api_key, language=language)
    elif provider == "openai":
        result = await generate_sheet_openai(transcript, api_key, language=language)
    else:
        raise ValueError(f"Provider de génération non supporté: {provider}")
    result["content"] = normalize_sheet(result.get("content", {}))
    return result
