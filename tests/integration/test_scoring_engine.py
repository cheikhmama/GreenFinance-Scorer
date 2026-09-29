import uuid

import pytest
from sqlmodel import col, func, select

from app.auth.hashing import hash_password
from app.auth.models import User
from app.company.models import Company
from app.core.enums import CanalDepot, MethodeDonnee, Pilier, Role, TypeRapport
from app.core.exceptions import ValidationError
from app.ingestion.models import ESGMetric, ESGReport, PreuveDocumentaire
from app.scoring.engine import (
    calculer_score,
    obtenir_configuration_reference,
    score_officiel,
)
from app.scoring.models import ConfigurationPonderation, ScoreESG


def _rapport(session) -> ESGReport:
    entreprise = Company(name=f"Cible {uuid.uuid4()}", sector="Industrie", country="France")
    session.add(entreprise)
    session.flush()
    rapport = ESGReport(
        company_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
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
        ESGMetric(
            report_id=rapport_id,
            pillar=pilier,
            metric_code=code,
            value=valeur,
            unit="x",
            method=MethodeDonnee.RAPPORTEE,
            proof_id=preuve_id,
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
    """_INDICATEURS_ATLAS ne fournit que les 6 codes v1 -- sous la méthodologie v2 (Phase 5 §9,
    élargie), les 3 nouveaux codes (part_renouvelable_pourcentage, dechets_valorises_pourcentage,
    femmes_effectif_pourcentage) sont donc absents et leurs piliers se repondèrent sur ce qui
    reste présent, exactement comme test_indicateur_manquant_repondere_le_pilier -- valeurs
    attendues recalculées en conséquence (voir config/weights/default.yaml pour les poids v2)."""
    rapport = _rapport(session)
    preuve = _preuve(session)
    for (pilier, code), valeur in _INDICATEURS_ATLAS.items():
        _ajouter_indicateur(session, rapport.id, preuve.id, pilier, code, valeur)
    session.commit()

    score = calculer_score(session, rapport.id)
    session.commit()

    assert score.score_environnement == pytest.approx(49.91, abs=0.01)
    assert score.score_social == pytest.approx(86.0, abs=0.01)
    assert score.score_gouvernance == pytest.approx(80.0, abs=0.01)
    assert score.valeur_globale == pytest.approx(66.45, abs=0.01)


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


def test_score_officiel_ignore_un_score_personnalise_du_meme_rapport(session) -> None:
    """Un rapport peut porter plusieurs ScoreESG (un par ConfigurationPonderation) — score_officiel
    ne doit jamais retomber sur un `.first()` non filtré : seul le score calculé sous la
    configuration de référence fait foi, jamais une pondération personnalisée d'un tiers."""
    rapport = _rapport(session)
    session.commit()

    reference = obtenir_configuration_reference(session)
    score_reference = ScoreESG(rapport_id=rapport.id, configuration_id=reference.id, valeur_globale=70.0)
    session.add(score_reference)
    session.commit()

    utilisateur = User(
        email=f"chercheur-{uuid.uuid4()}@example.com",
        password_hash=hash_password("s3cret-pass"),
        role=Role.RESEARCHER,
    )
    session.add(utilisateur)
    session.commit()
    configuration_perso = ConfigurationPonderation(
        nom="Pondération personnalisée", version=1, fichier_yaml="x", utilisateur_id=utilisateur.id
    )
    session.add(configuration_perso)
    session.commit()
    # Score personnalisé ajouté APRÈS le score de référence, pour vérifier qu'aucun tri implicite
    # par date/insertion ne le fait passer devant : seul configuration_id doit trancher.
    session.add(
        ScoreESG(rapport_id=rapport.id, configuration_id=configuration_perso.id, valeur_globale=12.0)
    )
    session.commit()

    officiel = score_officiel(session, rapport.id)
    assert officiel is not None
    assert officiel.id == score_reference.id
    assert officiel.valeur_globale == 70.0


def test_score_officiel_absent_si_rapport_non_score(session) -> None:
    rapport = _rapport(session)
    session.commit()

    assert score_officiel(session, rapport.id) is None


def test_changement_de_version_cree_une_nouvelle_configuration_et_invalide_lancien_score_officiel(
    session,
) -> None:
    """Comportement réel, pas juste théorique : passer default.yaml en v2 (Phase 5 §9) crée une
    nouvelle ligne ConfigurationPonderation distincte de toute ligne v1 déjà en base -- et
    score_officiel(), qui ne filtre que sur la configuration de référence COURANTE, redevient None
    pour un rapport scoré sous une ancienne version tant qu'il n'est pas recalculé (voir
    scripts/recalculer_scores_v2.py pour la reprise en masse après un tel changement)."""
    rapport = _rapport(session)
    preuve = _preuve(session)
    _ajouter_indicateur(
        session, rapport.id, preuve.id, Pilier.GOUVERNANCE, "femmes_conseil_pourcentage", 40.0
    )
    session.commit()

    # Une seule référence par version : réutilise la ligne v1 si la base partagée l'a déjà.
    configuration_v1_simulee = session.exec(
        select(ConfigurationPonderation).where(
            col(ConfigurationPonderation.utilisateur_id).is_(None),
            col(ConfigurationPonderation.version) == 1,
        )
    ).first() or ConfigurationPonderation(
        nom="Ancienne référence", version=1, fichier_yaml="config/weights/default.yaml"
    )
    session.add(configuration_v1_simulee)
    session.commit()
    score_sous_v1 = ScoreESG(
        rapport_id=rapport.id, configuration_id=configuration_v1_simulee.id, valeur_globale=70.0
    )
    session.add(score_sous_v1)
    session.commit()

    reference_courante = obtenir_configuration_reference(session)

    assert reference_courante.id != configuration_v1_simulee.id
    assert reference_courante.version == 2
    assert score_officiel(session, rapport.id) is None

    score_recalcule = calculer_score(session, rapport.id)
    session.commit()

    assert score_recalcule.configuration_id == reference_courante.id
    officiel = score_officiel(session, rapport.id)
    assert officiel is not None
    assert officiel.id == score_recalcule.id
