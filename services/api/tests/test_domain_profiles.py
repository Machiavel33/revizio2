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
    assert detect_profile("Histoire") is GENERIC
    assert detect_profile("Philosophie") is GENERIC


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


def test_list_profiles():
    from app.services.domain_profiles import list_profiles

    profiles = list_profiles()
    keys = {p["key"] for p in profiles}
    assert "generic" in keys
    assert "droit" in keys
    assert "compta" in keys
    assert "informatique" in keys
    assert "sciences" in keys
    assert all("label" in p for p in profiles)


def test_explicit_domain_overrides_subject():
    from app.services.domain_profiles import COMPTA, detect_profile

    # subject dit "droit" mais domain_key explicite = compta -> compta gagne
    assert detect_profile("Droit pénal", domain_key="compta") is COMPTA


def test_get_profile_by_key():
    from app.services.domain_profiles import GENERIC, get_profile_by_key

    assert get_profile_by_key("generic") is GENERIC
    assert get_profile_by_key("droit") is DROIT
    assert get_profile_by_key("inexistant") is None
    assert get_profile_by_key(None) is None


def test_detect_new_domains():
    from app.services.domain_profiles import COMPTA, DROIT_TRAVAIL, INFORMATIQUE, SCIENCES

    assert detect_profile("Comptabilité générale") is COMPTA
    assert detect_profile("Droit du travail") is DROIT_TRAVAIL
    assert detect_profile("Programmation Python") is INFORMATIQUE
    assert detect_profile("Physique quantique") is SCIENCES
