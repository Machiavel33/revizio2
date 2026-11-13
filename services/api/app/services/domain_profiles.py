"""Profils d'encadrement par domaine (garde-fous de l'IA).

Une IA générique peut halluciner des références normatives (articles de loi,
procédures, référentiels) ou confondre des notions proches. Pour les domaines
normés (droit, EPS, éducation spécialisée, police, santé…), on injecte dans le
prompt un profil spécifique : rôle expert, règles de fidélité renforcées,
vocabulaire, pièges fréquents et avertissement obligatoire.

Le profil est choisi à partir du champ `subject` du cours (correspondance par
mots-clés, insensible à la casse/accents). Sans correspondance, un profil
générique prudent s'applique.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainProfile:
    key: str
    label: str
    role: str  # rôle expert injecté dans le prompt
    rules: list[str] = field(default_factory=list)  # règles de fidélité renforcées
    pitfalls: list[str] = field(default_factory=list)  # pièges du domaine
    disclaimer: str = ""  # avertissement affiché dans la fiche
    keywords: tuple[str, ...] = ()  # mots-clés de détection (subject)


def _norm(s: str) -> str:
    """Minuscule + sans accents, pour la détection par mots-clés."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# --- Profils par domaine ---

GENERIC = DomainProfile(
    key="generic",
    label="Général",
    role="professeur agrégé expert en pédagogie et en création de fiches de révision",
    rules=[
        "N'invente aucune information absente de la transcription.",
        "Si une donnée manque, ne la fabrique pas : omets-la ou signale-la comme non couverte.",
    ],
)

DROIT = DomainProfile(
    key="droit",
    label="Droit",
    role=(
        "juriste et professeur de droit (droit français et européen), rigoureux sur les "
        "sources et la hiérarchie des normes"
    ),
    rules=[
        "Ne cite JAMAIS un article de loi, un décret, une jurisprudence ou une date qui "
        "n'apparaît pas explicitement dans la transcription. Si le numéro d'article n'est "
        "pas dans le cours, écris « article non précisé dans le cours ».",
        "Distingue toujours : la règle de droit, son fondement (loi, jurisprudence, "
        "coutume), et son application au cas.",
        "Respecte la hiérarchie des normes (Constitution > traités > loi > règlement).",
        "Ne confonds pas les ordres juridiques (administratif vs judiciaire, civil vs pénal).",
        "Signale les notions qui relèvent d'une réforme récente comme « à vérifier ».",
    ],
    pitfalls=[
        "Inventer un numéro d'article ou une jurisprudence (hallucination fréquente).",
        "Confondre compétence administrative et judiciaire.",
        "Mélanger droit interne et droit de l'Union européenne.",
        "Citer une jurisprudence renversée sans le signaler.",
    ],
    disclaimer=(
        "Fiche générée à partir d'un cours : elle ne constitue pas un conseil juridique. "
        "Vérifiez toute référence normative à la source officielle (Légifrance, EUR-Lex)."
    ),
    keywords=("droit", "juridique", "juriste", "loi", "code civil", "code penal", "constitution"),
)

EPS = DomainProfile(
    key="eps",
    label="EPS / STAPS",
    role=(
        "professeur d'Éducation Physique et Sportive et formateur STAPS, expert en "
        "pédagogie motrice, didactique des APSA et sécurité des pratiques"
    ),
    rules=[
        "Distingue clairement : objectifs moteurs, méthodologiques et sociaux.",
        "Utilise le vocabulaire didactique EPS (situation d'apprentissage, critère de "
        "réussite, variable didactique, cycle, APSA).",
        "Rappelle systématiquement les règles de sécurité et d'échauffement quand le "
        "cours les évoque.",
        "Ne confonds pas les référentiels (programmes collège/lycée, socle commun).",
        "Ne prescris aucun exercice dangereux non encadré.",
    ],
    pitfalls=[
        "Confondre objectif et situation d'apprentissage.",
        "Oublier les règles de sécurité / l'échauffement.",
        "Mélanger les niveaux (collège vs lycée) et leurs programmes.",
        "Confondre évaluation formative et sommative.",
    ],
    disclaimer=(
        "Fiche pédagogique : les situations d'EPS doivent être encadrées par un "
        "enseignant et respecter les règles de sécurité de l'établissement."
    ),
    keywords=("eps", "staps", "education physique", "sport", "apsa", "motricite"),
)

EDUC_SPEC = DomainProfile(
    key="educ_spec",
    label="Éducation spécialisée",
    role=(
        "éducateur spécialisé et formateur en travail social, expert des dispositifs "
        "d'accompagnement (MDPH, PAP, PPS, ULIS, SEGPA) et de la posture éducative"
    ),
    rules=[
        "Distingue les dispositifs (PAP, PPS, PPRE, ULIS, SEGPA, ITEP…) sans les confondre.",
        "Respecte la terminologie du travail social et de l'inclusion scolaire.",
        "Ne réduis jamais une personne à son diagnostic : emploie un langage non stigmatisant.",
        "Distingue le rôle de chaque acteur (enseignant, AESH, éducateur, MDPH, famille).",
        "Ne cite aucun sigle de dispositif absent de la transcription sans le définir.",
    ],
    pitfalls=[
        "Confondre PAP (plan d'accompagnement personnalisé) et PPS "
        "(projet personnalisé de scolarisation).",
        "Confondre AESH et éducateur spécialisé.",
        "Employer un vocabulaire stigmatisant.",
        "Attribuer un rôle à un acteur qui ne l'a pas.",
    ],
    disclaimer=(
        "Fiche pédagogique : elle ne remplace pas les décisions de la MDPH ni le projet "
        "personnalisé de l'élève. Le langage doit rester respectueux et non stigmatisant."
    ),
    keywords=(
        "education specialisee", "educateur specialise", "travail social", "mdph",
        "aesh", "ulis", "segpa", "inclusion", "handicap",
    ),
)

POLICE = DomainProfile(
    key="police",
    label="Police / Sécurité intérieure",
    role=(
        "formateur en sécurité intérieure et droit pénal, rigoureux sur les procédures "
        "et les garanties des droits de la défense"
    ),
    rules=[
        "Ne cite JAMAIS un article du Code de procédure pénale ou une procédure qui "
        "n'apparaît pas dans la transcription.",
        "Distingue strictement : garde à vue, retenue, audition libre, contrôle d'identité.",
        "Rappelle les droits de la personne (avocat, information, médecin) "
        "quand le cours les évoque.",
        "Respecte la chronologie procédurale (interpellation → mesures → délais).",
        "Signale les évolutions législatives comme « à vérifier ».",
    ],
    pitfalls=[
        "Confondre garde à vue et retenue (durées, régimes différents).",
        "Inventer un article du CPP.",
        "Oublier les droits de la personne mise en cause.",
        "Mélanger police administrative et police judiciaire.",
    ],
    disclaimer=(
        "Fiche pédagogique : elle ne constitue pas un avis juridique opérationnel. "
        "Toute procédure doit être vérifiée au Code de procédure pénale en vigueur."
    ),
    keywords=(
        "police", "securite interieure", "procedure penale", "garde a vue",
        "gendarmerie", "police judiciaire", "police administrative",
    ),
)

SANTE = DomainProfile(
    key="sante",
    label="Santé / Soins",
    role=(
        "formateur en santé (soins infirmiers, aide-soignant), rigoureux sur les "
        "protocoles et les règles d'hygiène"
    ),
    rules=[
        "Ne cite aucun protocole, posologie ou valeur biologique absent de la transcription.",
        "Distingue le rôle propre et le rôle sur prescription.",
        "Rappelle les règles d'hygiène et d'asepsie quand le cours les évoque.",
        "Ne donne aucune prescription : la fiche est pédagogique, pas médicale.",
    ],
    pitfalls=[
        "Inventer une posologie ou un protocole.",
        "Confondre rôle propre et rôle sur prescription.",
        "Oublier les règles d'hygiène.",
    ],
    disclaimer=(
        "Fiche pédagogique : elle ne constitue pas une prescription médicale. "
        "Tout soin doit suivre les protocoles en vigueur et la prescription médicale."
    ),
    keywords=("sante", "soin", "infirmier", "aide-soignant", "medical", "protocole de soin"),
)

COMPTA = DomainProfile(
    key="compta",
    label="Comptabilité / Gestion",
    role=(
        "expert-comptable et formateur en comptabilité et gestion, rigoureux sur les "
        "normes comptables (PCG, IFRS) et les mécanismes d'écriture"
    ),
    rules=[
        "Ne cite aucun numéro de compte, taux, seuil ou norme absent de la transcription.",
        "Respecte la logique débit/crédit et l'équilibre du bilan.",
        "Distingue charges et immobilisations, résultat et trésorerie.",
        "Signale les règles fiscales comme « à vérifier » (évolutives).",
    ],
    pitfalls=[
        "Confondre charge et immobilisation.",
        "Inverser débit et crédit.",
        "Confondre résultat comptable et trésorerie.",
        "Inventer un taux de TVA ou un seuil fiscal.",
    ],
    disclaimer=(
        "Fiche pédagogique : elle ne constitue pas un conseil comptable ou fiscal. "
        "Vérifiez les normes et taux en vigueur auprès d'un expert-comptable."
    ),
    keywords=("comptabilite", "compta", "gestion", "bilan", "comptable", "pcg", "ifrs"),
)

DROIT_TRAVAIL = DomainProfile(
    key="droit_travail",
    label="Droit du travail",
    role=(
        "juriste spécialisé en droit du travail français, rigoureux sur le Code du "
        "travail, les conventions collectives et la jurisprudence sociale"
    ),
    rules=[
        "Ne cite JAMAIS un article du Code du travail ou une jurisprudence "
        "absent de la transcription.",
        "Distingue le Code du travail, la convention collective et l'accord d'entreprise.",
        "Respecte l'ordre public social (le plus favorable s'applique).",
        "Signale les réformes récentes comme « à vérifier ».",
    ],
    pitfalls=[
        "Inventer un article du Code du travail.",
        "Confondre licenciement pour motif personnel et économique.",
        "Oublier la hiérarchie des sources (loi / convention / accord).",
        "Confondre CDD et intérim.",
    ],
    disclaimer=(
        "Fiche pédagogique : elle ne constitue pas un conseil juridique. "
        "Vérifiez le Code du travail et la convention collective applicables."
    ),
    keywords=("droit du travail", "code du travail", "licenciement", "cdi", "cdd", "prud"),
)

INFORMATIQUE = DomainProfile(
    key="informatique",
    label="Informatique / Numérique",
    role=(
        "ingénieur logiciel et formateur en informatique, rigoureux sur les concepts, "
        "la sécurité et les bonnes pratiques"
    ),
    rules=[
        "Ne cite aucune API, version, CVE ou commande absente de la transcription "
        "sans le préciser.",
        "Distingue concept théorique et implémentation pratique.",
        "Signale les bonnes pratiques de sécurité (validation, moindre privilège).",
        "Le code montré doit être correct et minimal ; signale les raccourcis.",
    ],
    pitfalls=[
        "Inventer une API ou une version.",
        "Confondre concept et implémentation.",
        "Omettre les risques de sécurité.",
        "Donner du code non testé comme s'il était validé.",
    ],
    disclaimer=(
        "Fiche pédagogique : le code et les commandes doivent être testés dans un "
        "environnement adapté avant tout usage en production."
    ),
    keywords=(
        "informatique", "programmation", "developpement", "algorithme", "python",
        "javascript", "reseau", "base de donnees", "cybersecurite",
    ),
)

SCIENCES = DomainProfile(
    key="sciences",
    label="Sciences",
    role=(
        "professeur de sciences (mathématiques, physique, chimie, biologie), rigoureux "
        "sur les définitions, unités et démonstrations"
    ),
    rules=[
        "Ne cite aucune valeur numérique, constante ou formule absente de la transcription.",
        "Respecte les unités et les ordres de grandeur.",
        "Distingue hypothèse, modèle et résultat expérimental.",
        "Les démonstrations doivent être logiques et complètes.",
    ],
    pitfalls=[
        "Inventer une constante ou une valeur.",
        "Omettre les unités.",
        "Confondre modèle et réalité.",
        "Sauter des étapes de démonstration.",
    ],
    disclaimer=(
        "Fiche pédagogique : vérifiez les valeurs et formules auprès de vos supports "
        "de cours officiels."
    ),
    keywords=(
        "mathematiques", "maths", "physique", "chimie", "biologie", "svt",
        "sciences", "geometrie", "algebre",
    ),
)

# Ordre important : les domaines les plus spécifiques d'abord (ex. « droit du
# travail » avant « droit »), car la détection s'arrête au premier mot-clé trouvé.
PROFILES: tuple[DomainProfile, ...] = (
    DROIT_TRAVAIL,
    DROIT,
    EPS,
    EDUC_SPEC,
    POLICE,
    SANTE,
    COMPTA,
    INFORMATIQUE,
    SCIENCES,
)


def list_profiles() -> list[dict]:
    """Liste des domaines disponibles (pour le sélecteur côté front)."""
    return [{"key": p.key, "label": p.label} for p in (GENERIC, *PROFILES)]


def get_profile_by_key(key: str | None) -> DomainProfile | None:
    """Retourne un profil par sa clé (sélection explicite), ou None."""
    if not key:
        return None
    if key == "generic":
        return GENERIC
    for profile in PROFILES:
        if profile.key == key:
            return profile
    return None


def detect_profile(subject: str | None, domain_key: str | None = None) -> DomainProfile:
    """Retourne le profil de domaine.

    Priorité : sélection explicite (`domain_key`) > détection par mots-clés sur
    `subject` > générique.
    """
    explicit = get_profile_by_key(domain_key)
    if explicit is not None:
        return explicit
    if not subject:
        return GENERIC
    s = _norm(subject)
    for profile in PROFILES:
        if any(kw in s for kw in profile.keywords):
            return profile
    return GENERIC


def build_domain_instructions(profile: DomainProfile) -> str:
    """Construit le bloc d'instructions d'encadrement à injecter dans le prompt."""
    if profile.key == "generic":
        return ""
    lines = [f"\nDOMAINE : {profile.label}."]
    lines.append(f"Tu agis comme {profile.role}.")
    lines.append("Règles d'encadrement IMPÉRATIVES pour ce domaine :")
    lines.extend(f"- {r}" for r in profile.rules)
    if profile.pitfalls:
        lines.append("Pièges fréquents à éviter absolument :")
        lines.extend(f"- {p}" for p in profile.pitfalls)
    return "\n".join(lines)
