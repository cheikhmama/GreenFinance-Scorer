import uuid

import pytest
from sqlmodel import col, func, select

from app.company.models import Entreprise
from app.core.enums import CanalDepot, MethodeDonnee, Pilier, TypeRapport
from app.core.exceptions import ValidationError
from app.ingestion.models import IndicateurESG, PreuveDocumentaire, RapportESG
from app.scoring.engine import calculer_score, obtenir_configuration_reference
from app.scoring.models import ConfigurationPonderation


def _rapport(session) -> RapportESG:
    entreprise = Entreprise(nom=f"Cible {uuid.uuid4()}", secteur="Industrie", pays="France")
    session.add(entreprise)
    session.flush()
    rapport = RapportESG(
        entreprise_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        fichier_source="rapports/test/dummy.pdf",
    )
    session.add(rapport)
    session.flush()
    return rapport


def _preuve(session) -> PreuveDocumentaire:
    preuve = PreuveDocumentaire(
        nom_document="rapport-test.pdf",
        annee=2025,
        nombre_pages_total=1,
        page_debut=1,
        page_fin=1,
        pdf_extrait_genere="preuves/test/page_1.pdf",
    )
    session.add(preuve)
    session.flush()
    return preuve


def _ajouter_indicateur(session, rapport_id: uuid.UUID, preuve_id: uuid.UUID, pilier: Pilier, code: str, valeur: float) -> None:
    session.add(
        IndicateurESG(
            rapport_id=rapport_id,
            pilier=pilier,
            code=code,
            valeur=valeur,
            unite="x",
            methode=MethodeDonnee.RAPPORTEE,
            preuve_id=preuve_id,
        )
    )


# Valeurs synthétiques "Atlas Industries" (data_test/reference_e2e/atlas_industries) — mêmes
# chiffres que ceux régénérés dans le PDF de référence E2E (Phase 5 §9).
_INDICATEURS_ATLAS = {
    (Pilier.ENVIRONNEMENT, "intensite_scope_1_2_marketbased"): 22.0,
    (Pilier.ENVIRONNEMENT, "intensite_scope_1_2_3_hors_cat11"): 95.0,
    (Pilier.ENVIRONNEMENT, "intensite_scope_1_2_3_total"): 410.0,
    (Pilier.SOCIAL, "femmes_management_pourcentage"): 35.0,
    (Pilier.SOCIAL, "deces_professionnels"): 0.0,
    (Pilier.GOUVERNANCE, "femmes_conseil_pourcentage"): 40.0,
}


def test_calcul_complet_trois_piliers(session) -> None:
    rapport = _rapport(session)
    preuve = _preuve(session)
    for (pilier, code), valeur in _INDICATEURS_ATLAS.items():
        _ajouter_indicateur(session, rapport.id, preuve.id, pilier, code, valeur)
    session.commit()

    score = calculer_score(session, rapport.id)
    session.commit()

    assert score.score_environnement == pytest.approx(49.78, abs=0.05)
    assert score.score_social == pytest.approx(82.0, abs=0.01)
    assert score.score_gouvernance == pytest.approx(80.0, abs=0.01)
    assert score.valeur_globale == pytest.approx(65.39, abs=0.05)


def test_indicateur_manquant_repondere_le_pilier(session) -> None:
    """Retirer intensite_scope_1_2_marketbased ne doit pas compter comme 0 : le pilier
    ENVIRONNEMENT se recalcule sur les deux indicateurs restants, poids reponderes."""
    rapport = _rapport(session)
    preuve = _preuve(session)
    for (pilier, code), valeur in _INDICATEURS_ATLAS.items():
        if code == "intensite_scope_1_2_marketbased":
            continue
        _ajouter_indicateur(session, rapport.id, preuve.id, pilier, code, valeur)
    session.commit()

    score = calculer_score(session, rapport.id)
    session.commit()

    # intensite_scope_1_2_3_hors_cat11=95/200 -> sous-note 52.5 ; intensite_scope_1_2_3_total=
    # 410/500 -> sous-note 18. Poids 0.33/0.33 repondérés à parts égales -> moyenne simple.
    assert score.score_environnement == pytest.approx((52.5 + 18.0) / 2, abs=0.05)


def test_pilier_entierement_absent_reste_nul(session) -> None:
    rapport = _rapport(session)
    preuve = _preuve(session)
    for (pilier, code), valeur in _INDICATEURS_ATLAS.items():
        if pilier == Pilier.SOCIAL:
            continue
        _ajouter_indicateur(session, rapport.id, preuve.id, pilier, code, valeur)
    session.commit()

    score = calculer_score(session, rapport.id)
    session.commit()

    assert score.score_social is None
    assert score.score_environnement is not None
    assert score.score_gouvernance is not None
    # Score global recalculé sur ENVIRONNEMENT (poids 0.5) + GOUVERNANCE (poids 0.25) seuls,
    # repondérés : (49.78*0.5 + 80*0.25) / 0.75.
    attendu = (score.score_environnement * 0.5 + score.score_gouvernance * 0.25) / 0.75
    assert score.valeur_globale == pytest.approx(attendu, abs=0.01)


def test_aucun_indicateur_leve_score_incalculable(session) -> None:
    rapport = _rapport(session)
    session.commit()

    with pytest.raises(ValidationError) as exc_info:
        calculer_score(session, rapport.id)
    assert exc_info.value.code == "score_incalculable"


def test_obtenir_configuration_reference_est_idempotent(session) -> None:
    # Compte relatif, pas une unicité globale sur la table : la base de test partagée (aucune
    # isolation par test, voir tests/integration/conftest.py) peut déjà contenir une ligne de
    # référence créée par un run précédent -- seule la variation avant/après ce test compte.
    avant = session.exec(
        select(func.count())
        .select_from(ConfigurationPonderation)
        .where(col(ConfigurationPonderation.utilisateur_id).is_(None))
    ).one()

    premiere = obtenir_configuration_reference(session)
    deuxieme = obtenir_configuration_reference(session)

    assert premiere.id == deuxieme.id
    apres = session.exec(
        select(func.count())
        .select_from(ConfigurationPonderation)
        .where(col(ConfigurationPonderation.utilisateur_id).is_(None))
    ).one()
    assert apres - avant <= 1  # au plus une ligne créée par ce test, jamais deux
