"""Tests des profils d'encadrement par domaine (garde-fous IA)."""

from app.services.domain_profiles import (
    DROIT,
    EDUC_SPEC,
    EPS,
    GENERIC,
    POLICE,
    SANTE,
    build_domain_instructions,
    detect_profile,
)


def test_detect_droit():
    assert detect_profile("Droit constitutionnel") is DROIT
    assert detect_profile("Droit pénal") is DROIT
    assert detect_profile("Introduction au droit") is DROIT


def test_detect_eps():
    assert detect_profile("EPS") is EPS
    assert detect_profile("STAPS - motricité") is EPS
    assert detect_profile("Éducation physique et sportive") is EPS


def test_detect_educ_spec():
    assert detect_profile("Éducation spécialisée") is EDUC_SPEC
    assert detect_profile("Travail social et MDPH") is EDUC_SPEC
    assert detect_profile("AESH et ULIS") is EDUC_SPEC


def test_detect_police():
    assert detect_profile("Police judiciaire") is POLICE
    assert detect_profile("Procédure pénale") is POLICE
    assert detect_profile("Garde à vue") is POLICE


def test_detect_sante():
    assert detect_profile("Soins infirmiers") is SANTE
    assert detect_profile("Santé et protocoles") is SANTE


def test_detect_generic():
    assert detect_profile(None) is GENERIC
    assert detect_profile("") is GENERIC
    assert detect_profile("Mathématiques") is GENERIC
    assert detect_profile("Histoire") is GENERIC


def test_detect_accent_insensitive():
    # "Éducation spécialisée" avec accents -> détecté
    assert detect_profile("ÉDUCATION SPÉCIALISÉE") is EDUC_SPEC


def test_build_instructions_droit():
    block = build_domain_instructions(DROIT)
    assert "DOMAINE : Droit" in block
    assert "Ne cite JAMAIS un article de loi" in block
    assert "Pièges fréquents" in block


def test_build_instructions_generic_empty():
    assert build_domain_instructions(GENERIC) == ""


def test_each_profile_has_disclaimer():
    for p in (DROIT, EPS, EDUC_SPEC, POLICE, SANTE):
        assert p.disclaimer, f"{p.key} sans disclaimer"
        assert p.rules, f"{p.key} sans règles"
