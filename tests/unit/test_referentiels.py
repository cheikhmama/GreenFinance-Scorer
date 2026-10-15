"""Correspondance des codes extraits avec les référentiels ESG (GHG Protocol, GRI, ESRS)."""

import re

from app.ingestion.cibles import INDICATEURS_CIBLES
from app.ingestion.referentiels import charger_referentiels
from app.ingestion.vocabulaire import CODES_AUTO_DECLARES_PAR_PILIER

AUTO_DECLARES = set(CODES_AUTO_DECLARES_PAR_PILIER) | {"score_global_declare"}


def test_chaque_code_cible_a_exactement_une_correspondance() -> None:
    referentiels = charger_referentiels()

    assert set(referentiels) == {c.code for c in INDICATEURS_CIBLES}


def test_references_bien_formees_et_carbone_rattache_au_ghg_protocol() -> None:
    for code, ref in charger_referentiels().items():
        if ref.gri is not None:
            assert re.fullmatch(r"GRI \d{1,3}-\d{1,2}(-[a-z](-[ivx]+)?)?", ref.gri), code
        if ref.esrs is not None:
            assert re.fullmatch(r"ESRS (E[1-5]|S[1-4]|G1|2 [A-Z]+)-\d{1,2}", ref.esrs), code
    for cible in INDICATEURS_CIBLES:
        if cible.cible == "donnee_carbone":
            assert charger_referentiels()[cible.code].ghg_protocol, cible.code


def test_scores_auto_declares_sans_reference() -> None:
    """Un score que l'entreprise s'attribue n'est la publication d'aucun référentiel : lui en
    prêter un laisserait croire à une donnée normée."""
    referentiels = charger_referentiels()

    for code in AUTO_DECLARES:
        ref = referentiels[code]
        assert (ref.ghg_protocol, ref.gri, ref.esrs) == (None, None, None), code
