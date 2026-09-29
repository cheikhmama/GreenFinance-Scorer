import uuid
from pathlib import Path

import pytest
import yaml
from sqlmodel import col, func, select

from app.auth.hashing import hash_password
from app.auth.models import User
from app.company.models import Company
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import CanalDepot, MethodeDonnee, Pillar, Role, TypeRapport
from app.core.exceptions import ValidationError
from app.ingestion.models import ESGMetric, ESGReport, Evidence
from app.scoring.engine import (
    apercu_score,
    calculer_score,
    enregistrer_configuration,
    obtenir_configuration_reference,
    schema_configuration,
    score_officiel,
    score_public,
)
from app.scoring.models import Score, ScoringConfig


def _rapport(session) -> ESGReport:
    entreprise = Company(name=f"Cible {uuid.uuid4()}", sector="Industrie", country="France")
    session.add(entreprise)
    session.flush()
    rapport = ESGReport(
        company_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.flush()
    return rapport


def _preuve(session) -> Evidence:
    preuve = Evidence(
        document_name="rapport-test.pdf",
        year=2025,
        total_pages=1,
        page_start=1,
        page_end=1,
        excerpt_pdf_path="preuves/test/page_1.pdf",
    )
    session.add(preuve)
    session.flush()
    return preuve


def _ajouter_indicateur(session, rapport_id: uuid.UUID, preuve_id: uuid.UUID, pilier: Pillar, code: str, valeur: float) -> None:
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
    (Pillar.ENVIRONNEMENT, "intensite_scope_1_2_marketbased"): 22.0,
    (Pillar.ENVIRONNEMENT, "intensite_scope_1_2_3_hors_cat11"): 95.0,
    (Pillar.ENVIRONNEMENT, "intensite_scope_1_2_3_total"): 410.0,
    (Pillar.SOCIAL, "femmes_management_pourcentage"): 35.0,
    (Pillar.SOCIAL, "deces_professionnels"): 0.0,
    (Pillar.GOUVERNANCE, "femmes_conseil_pourcentage"): 40.0,
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

    assert score.environmental_score == pytest.approx(49.91, abs=0.01)
    assert score.social_score == pytest.approx(86.0, abs=0.01)
    assert score.governance_score == pytest.approx(80.0, abs=0.01)
    assert score.global_score == pytest.approx(66.45, abs=0.01)


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
    assert score.environmental_score == pytest.approx((52.5 + 18.0) / 2, abs=0.05)


def test_pilier_entierement_absent_reste_nul(session) -> None:
    rapport = _rapport(session)
    preuve = _preuve(session)
    for (pilier, code), valeur in _INDICATEURS_ATLAS.items():
        if pilier == Pillar.SOCIAL:
            continue
        _ajouter_indicateur(session, rapport.id, preuve.id, pilier, code, valeur)
    session.commit()

    score = calculer_score(session, rapport.id)
    session.commit()

    assert score.social_score is None
    assert score.environmental_score is not None
    assert score.governance_score is not None
    # Score global recalculé sur ENVIRONNEMENT (poids 0.5) + GOUVERNANCE (poids 0.25) seuls,
    # repondérés : (49.78*0.5 + 80*0.25) / 0.75.
    attendu = (score.environmental_score * 0.5 + score.governance_score * 0.25) / 0.75
    assert score.global_score == pytest.approx(attendu, abs=0.01)


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
        .select_from(ScoringConfig)
        .where(col(ScoringConfig.owner_user_id).is_(None))
    ).one()

    premiere = obtenir_configuration_reference(session)
    deuxieme = obtenir_configuration_reference(session)

    assert premiere.id == deuxieme.id
    apres = session.exec(
        select(func.count())
        .select_from(ScoringConfig)
        .where(col(ScoringConfig.owner_user_id).is_(None))
    ).one()
    assert apres - avant <= 1  # au plus une ligne créée par ce test, jamais deux


def test_score_officiel_ignore_un_score_personnalise_du_meme_rapport(session) -> None:
    """Un rapport peut porter plusieurs Score (un par ScoringConfig) — score_officiel
    ne doit jamais retomber sur un `.first()` non filtré : seul le score calculé sous la
    configuration de référence fait foi, jamais une pondération personnalisée d'un tiers."""
    rapport = _rapport(session)
    session.commit()

    reference = obtenir_configuration_reference(session)
    score_reference = Score(report_id=rapport.id, config_id=reference.id, global_score=70.0)
    session.add(score_reference)
    session.commit()

    utilisateur = User(
        email=f"chercheur-{uuid.uuid4()}@example.com",
        password_hash=hash_password("s3cret-pass"),
        role=Role.RESEARCHER,
    )
    session.add(utilisateur)
    session.commit()
    configuration_perso = ScoringConfig(
        name="Pondération personnalisée", version=1, owner_user_id=utilisateur.id
    )
    session.add(configuration_perso)
    session.commit()
    # Score personnalisé ajouté APRÈS le score de référence, pour vérifier qu'aucun tri implicite
    # par date/insertion ne le fait passer devant : seule une configuration de référence compte.
    session.add(
        Score(report_id=rapport.id, config_id=configuration_perso.id, global_score=12.0)
    )
    session.commit()

    officiel = score_officiel(session, rapport.id)
    assert officiel is not None
    assert officiel.id == score_reference.id
    assert officiel.global_score == 70.0


def test_score_officiel_absent_si_rapport_non_score(session) -> None:
    rapport = _rapport(session)
    session.commit()

    assert score_officiel(session, rapport.id) is None


def _yaml_reference_modifie(tmp_path, **modifications) -> str:
    """Copie de la référence courante, modifiée : écrite sur disque, renvoie son chemin."""
    donnees = yaml.safe_load(Path(get_settings().default_scoring_config).read_text(encoding="utf-8"))
    donnees.update(modifications)
    chemin = tmp_path / "reference.yaml"
    chemin.write_text(yaml.safe_dump(donnees, allow_unicode=True), encoding="utf-8")
    return str(chemin)


def _rapport_gouvernance_seule(session) -> ESGReport:
    rapport = _rapport(session)
    preuve = _preuve(session)
    _ajouter_indicateur(
        session, rapport.id, preuve.id, Pillar.GOUVERNANCE, "femmes_conseil_pourcentage", 40.0
    )
    session.commit()
    return rapport


def test_calcul_relit_le_contenu_stocke_jamais_le_fichier(session, tmp_path, monkeypatch) -> None:
    """Configuration verrouillée (tâche 3.1) : modifier le fichier YAML — même sans changer son
    numéro de version — enregistre une NOUVELLE configuration ; l'ancienne garde son contenu, et
    le score officiel déjà publié d'un rapport reste le sien (il ne « disparaît » plus au premier
    changement de méthodologie)."""
    rapport = _rapport_gouvernance_seule(session)
    score_initial = calculer_score(session, rapport.id)
    session.commit()
    ancienne = obtenir_configuration_reference(session)
    contenu_ancien = ancienne.content_yaml

    reference = yaml.safe_load(contenu_ancien or "")
    reference["piliers"]["GOUVERNANCE"]["indicateurs"]["femmes_conseil_pourcentage"]["borne_max"] = 80
    chemin = tmp_path / "reference.yaml"
    chemin.write_text(yaml.safe_dump(reference, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(get_settings(), "default_scoring_config", str(chemin))

    nouvelle = obtenir_configuration_reference(session)
    session.commit()
    session.refresh(ancienne)

    assert nouvelle.id != ancienne.id
    assert nouvelle.version == ancienne.version  # même numéro, autre contenu : autre configuration
    assert nouvelle.content_hash != ancienne.content_hash
    assert ancienne.content_yaml == contenu_ancien
    assert schema_configuration(ancienne).piliers[Pillar.GOUVERNANCE].indicateurs[
        "femmes_conseil_pourcentage"
    ].borne_max != 80
    officiel = score_officiel(session, rapport.id)
    assert officiel is not None and officiel.id == score_initial.id


def test_couverture_stockee_sur_le_score_et_le_rapport(session) -> None:
    rapport = _rapport_gouvernance_seule(session)

    score = calculer_score(session, rapport.id)
    session.commit()
    session.refresh(rapport)

    configuration = obtenir_configuration_reference(session)
    schema = schema_configuration(configuration)
    gouvernance = schema.piliers[Pillar.GOUVERNANCE]
    attendue = gouvernance.poids * gouvernance.indicateurs["femmes_conseil_pourcentage"].poids
    assert score.coverage_rate == pytest.approx(attendue)
    assert rapport.coverage_rate == pytest.approx(attendue)
    assert rapport.config_hash == configuration.content_hash
    assert rapport.official_score == pytest.approx(score.global_score)
    public = score_public(session, rapport.id)
    assert public is not None and public.taux_couverture == pytest.approx(attendue)


def test_couverture_sous_le_minimum_bloque_le_score(session, tmp_path, monkeypatch) -> None:
    rapport = _rapport_gouvernance_seule(session)
    monkeypatch.setattr(
        get_settings(), "default_scoring_config", _yaml_reference_modifie(tmp_path, min_coverage=0.9)
    )

    apercu = apercu_score(session, rapport.id)
    with pytest.raises(ValidationError) as exc_info:
        calculer_score(session, rapport.id)

    assert exc_info.value.code == "couverture_insuffisante"
    assert apercu.calculable is False
    assert apercu.min_coverage == 0.9
    assert apercu.coverage_rate is not None and apercu.coverage_rate < 0.9


def test_enregistrer_configuration_par_empreinte_et_par_proprietaire(session) -> None:
    contenu = Path(get_settings().default_scoring_config).read_text(encoding="utf-8")
    chercheur = User(
        email=f"chercheur-{uuid.uuid4()}@example.com",
        password_hash=hash_password("s3cret-pass"),
        role=Role.RESEARCHER,
    )
    session.add(chercheur)
    session.flush()

    reference = enregistrer_configuration(session, contenu)
    # Un commentaire de plus ne change pas la méthodologie : même ligne.
    meme = enregistrer_configuration(session, "# relu\n" + contenu)
    perso = enregistrer_configuration(session, contenu, chercheur.id)
    perso_bis = enregistrer_configuration(session, contenu, chercheur.id)
    session.commit()

    assert meme.id == reference.id
    assert perso.id != reference.id and perso.content_hash == reference.content_hash
    assert perso_bis.id == perso.id
    assert perso.owner_user_id == chercheur.id
    with pytest.raises(ValidationError) as exc_info:
        enregistrer_configuration(session, "version: 1\nnom: x\npiliers: {}\n")
    assert exc_info.value.code == "configuration_invalide"


def test_configuration_sans_contenu_jamais_utilisee_pour_un_calcul() -> None:
    """Configuration antérieure à la tâche 3.1 dont le contenu n'a pas pu être repris."""
    with pytest.raises(ValidationError) as exc_info:
        schema_configuration(ScoringConfig(name="ancienne", version=1))
    assert exc_info.value.code == "configuration_sans_contenu"
