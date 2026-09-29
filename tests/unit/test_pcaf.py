"""Moteur PCAF pur (app/carbon/pcaf.py, tâche 2.3) — chiffres attendus calculés à la main."""

import uuid
from decimal import Decimal

import pytest

from app.carbon.pcaf import (
    CarbonExclusionReason,
    Emission,
    EmissionsEntreprise,
    LignePCAF,
    calculer_ligne,
    calculer_portefeuille,
    choisir_scope_2,
    qualite_donnee_pcaf,
)
from app.core.enums import MethodeDonnee

M = Decimal(1_000_000)


def _emissions(
    scope_1: float | None = None,
    scope_2: float | None = None,
    scope_3: float | None = None,
    *,
    q1: int | None = 2,
    q2: int | None = 2,
    q3: int | None = 2,
) -> EmissionsEntreprise:
    return EmissionsEntreprise(
        annee=2025,
        scope_1=Emission(scope_1, q1) if scope_1 is not None else None,
        scope_2=Emission(scope_2, q2) if scope_2 is not None else None,
        scope_2_base="market_based",
        scope_3=Emission(scope_3, q3) if scope_3 is not None else None,
    )


def _ligne(
    montant: Decimal,
    emissions: EmissionsEntreprise | None,
    *,
    evic: Decimal | None = None,
    ca: Decimal | None = None,
    rapprochee: bool = True,
) -> LignePCAF:
    return LignePCAF(uuid.uuid4(), montant, rapprochee, evic, ca, emissions)


def test_portefeuille_complet_calcule_a_la_main() -> None:
    a = _ligne(1 * M, _emissions(1000, 500, 5000), evic=10 * M, ca=50 * M)
    b = _ligne(3 * M, _emissions(200, 100, q2=4), evic=30 * M)
    c = _ligne(1 * M, None, rapprochee=False)

    r = calculer_portefeuille([a, b, c])

    assert r.valeur_totale == 5 * M
    # AF = 0,1 pour A et B : FE₁₊₂ = 0,1 × 1 500 + 0,1 × 300.
    assert r.emissions_financees_scope_1_2 == pytest.approx(180)
    # Scope 3 publié à part, jamais additionné : seul A en a un.
    assert r.emissions_financees_scope_3 == pytest.approx(500)
    # 180 tCO₂e sur 4 M€ couverts.
    assert r.empreinte_carbone_scope_1_2 == pytest.approx(45)
    # Seul A a un chiffre d'affaires : 1 500 t / 50 M.
    assert r.waci_scope_1_2 == pytest.approx(30)
    # Qualité pondérée : (1 M × 2 + 3 M × 4) / 4 M ; la moins bonne des deux scopes pour B.
    assert r.qualite_scope_1_2 == pytest.approx(3.5)
    assert r.qualite_scope_3 == pytest.approx(2)
    assert (r.couverture_scope_1_2, r.couverture_scope_3, r.couverture_waci) == pytest.approx(
        (0.8, 0.2, 0.2)
    )
    motifs = {ligne.position_id: ligne.motif_exclusion for ligne in r.lignes}
    assert motifs == {a.position_id: None, b.position_id: None, c.position_id: CarbonExclusionReason.UNMATCHED}


def test_donnee_manquante_exclue_jamais_comptee_zero() -> None:
    scope_1_seul = _ligne(1 * M, _emissions(1000), evic=10 * M, ca=10 * M)
    sans_evic = _ligne(1 * M, _emissions(100, 100, 400), ca=20 * M)
    sans_rapport = _ligne(1 * M, None)

    lignes = {ligne.position_id: calculer_ligne(ligne) for ligne in (scope_1_seul, sans_evic, sans_rapport)}

    assert lignes[scope_1_seul.position_id].motif_exclusion == CarbonExclusionReason.MISSING_EMISSIONS
    assert lignes[scope_1_seul.position_id].emissions_financees_scope_1_2 is None
    assert lignes[scope_1_seul.position_id].intensite_carbone is None
    assert lignes[sans_evic.position_id].motif_exclusion == CarbonExclusionReason.MISSING_EVIC
    # Sans EVIC, pas de facteur d'attribution… mais la WACI, elle, n'en a pas besoin.
    assert lignes[sans_evic.position_id].facteur_attribution is None
    assert lignes[sans_evic.position_id].emissions_financees_scope_3 is None
    assert lignes[sans_evic.position_id].intensite_carbone == pytest.approx(10)
    assert lignes[sans_rapport.position_id].motif_exclusion == CarbonExclusionReason.NO_VALIDATED_REPORT


def test_aucune_couverture_donne_des_agregats_nuls_pas_zero() -> None:
    r = calculer_portefeuille([_ligne(1 * M, None), _ligne(2 * M, None, rapprochee=False)])

    assert r.emissions_financees_scope_1_2 is None
    assert r.emissions_financees_scope_3 is None
    assert r.empreinte_carbone_scope_1_2 is None
    assert r.waci_scope_1_2 is None
    assert r.qualite_scope_1_2 is None
    assert (r.couverture_scope_1_2, r.couverture_scope_3, r.couverture_waci) == (0.0, 0.0, 0.0)


def test_portefeuille_vide() -> None:
    r = calculer_portefeuille([])

    assert r.valeur_totale == 0
    assert r.emissions_financees_scope_1_2 is None
    assert r.couverture_scope_1_2 == 0.0


def test_qualite_inconnue_sur_un_scope_rend_la_qualite_de_ligne_inconnue() -> None:
    ligne = calculer_ligne(_ligne(1 * M, _emissions(10, 10, q2=None), evic=10 * M))

    assert ligne.emissions_financees_scope_1_2 == pytest.approx(2)
    assert ligne.qualite is None


def test_scope_2_market_based_prefere() -> None:
    market, location, brut = Emission(1, 2), Emission(2, 2), Emission(3, 2)

    assert choisir_scope_2({"location_based": location, "market_based": market, None: brut}) == (
        market,
        "market_based",
    )
    assert choisir_scope_2({"location_based": location, None: brut}) == (brut, None)
    assert choisir_scope_2({"location_based": location}) == (location, "location_based")
    assert choisir_scope_2({}) == (None, None)


@pytest.mark.parametrize(
    ("methode", "attendu"),
    [(MethodeDonnee.RAPPORTEE, 2), (MethodeDonnee.CALCULEE, 3), (MethodeDonnee.ESTIMEE, 4)],
)
def test_qualite_derivee_de_la_methode(methode: MethodeDonnee, attendu: int) -> None:
    assert qualite_donnee_pcaf(methode) == attendu
