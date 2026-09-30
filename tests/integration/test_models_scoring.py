import random
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.models import User
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import ReportType, Role, SubmissionChannel
from app.ingestion.models import ESGReport
from app.scoring.models import Score, ScoringConfig


def _utilisateur(session, role: Role) -> User:
    utilisateur = User(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        password_hash="hash",
        role=role,
    )
    session.add(utilisateur)
    session.flush()
    return utilisateur


def _rapport(session) -> ESGReport:
    entreprise = Company(name="Acme", sector="Industrie", country="MR")
    session.add(entreprise)
    session.flush()
    rapport = ESGReport(
        company_id=entreprise.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.AUTOMATIQUE,
        source_file="s3://bucket/rapport.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.flush()
    return rapport


@pytest.mark.parametrize("role", [Role.INVESTOR, Role.RESEARCHER, Role.INSTITUTION])
def test_configuration_personnalisee_par_role(session, role: Role) -> None:
    utilisateur = _utilisateur(session, role)
    configuration = ScoringConfig(
        name=f"config-{role.value}",
        version=1,
        owner_user_id=utilisateur.id,
    )
    session.add(configuration)
    session.flush()

    assert configuration.id is not None
    assert configuration.owner_user_id == utilisateur.id


def test_rapport_accepte_plusieurs_scores_un_par_configuration(session) -> None:
    rapport = _rapport(session)

    # Version tirée au hasard : une seule référence par version, base de test partagée.
    config_reference = ScoringConfig(
        name="reference", version=random.randint(10_000, 10_000_000)
    )
    utilisateur = _utilisateur(session, Role.INVESTOR)
    config_perso = ScoringConfig(
        name="perso",
        version=1,
        owner_user_id=utilisateur.id,
    )
    session.add(config_reference)
    session.add(config_perso)
    session.flush()

    score_reference = Score(
        report_id=rapport.id,
        config_id=config_reference.id,
        global_score=72.0,
        environmental_score=70.0,
        social_score=75.0,
        governance_score=71.0,
    )
    score_perso = Score(
        report_id=rapport.id,
        config_id=config_perso.id,
        global_score=68.0,
        environmental_score=65.0,
        social_score=70.0,
        governance_score=69.0,
    )
    session.add(score_reference)
    session.add(score_perso)
    session.flush()

    assert len(rapport.scores) == 2
    assert {s.config_id for s in rapport.scores} == {
        config_reference.id,
        config_perso.id,
    }


@pytest.mark.parametrize(
    "champ", ["global_score", "environmental_score", "social_score", "governance_score"]
)
@pytest.mark.parametrize("valeur_invalide", [-0.5, 100.5])
def test_score_hors_bornes_rejete_en_base(session, champ: str, valeur_invalide: float) -> None:
    """Construction directe Score(**kwargs) (comme le fera le futur moteur de calcul,
    Étape 12) : la validation Pydantic (Field ge/le) n'est jamais déclenchée sur ce chemin —
    seule la contrainte CHECK côté PostgreSQL (Phase 5 §6) protège les 4 scores."""
    rapport = _rapport(session)
    configuration = ScoringConfig(
        name="reference", version=random.randint(10_000, 10_000_000)
    )
    session.add(configuration)
    session.flush()

    valeurs = {
        "global_score": 50.0,
        "environmental_score": 50.0,
        "social_score": 50.0,
        "governance_score": 50.0,
    }
    valeurs[champ] = valeur_invalide
    session.add(
        Score(report_id=rapport.id, config_id=configuration.id, **valeurs)
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_une_seule_reference_par_empreinte(session) -> None:
    """owner_user_id nul = configuration de référence : jamais deux lignes de référence pour une
    même méthodologie (uq_scoring_configs_reference_content_hash, tâche 3.1), mais la même
    méthodologie peut exister une fois par propriétaire. Empreinte tirée au hasard : la base de
    test est partagée entre exécutions."""
    empreinte = uuid.uuid4().hex * 2
    chercheur = _utilisateur(session, Role.RESEARCHER)
    session.add(ScoringConfig(name="reference", version=1, content_yaml="a: 1", content_hash=empreinte))
    session.add(
        ScoringConfig(
            name="perso", version=1, content_yaml="a: 1", content_hash=empreinte,
            owner_user_id=chercheur.id,
        )
    )
    session.flush()

    session.add(ScoringConfig(name="doublon", version=2, content_yaml="a: 1", content_hash=empreinte))
    with pytest.raises(IntegrityError, match="uq_scoring_configs_reference_content_hash"):
        session.flush()
    session.rollback()


def test_contenu_et_empreinte_vont_ensemble(session) -> None:
    session.add(ScoringConfig(name="incomplete", version=1, content_yaml="a: 1"))
    with pytest.raises(IntegrityError, match="ck_scoring_configs_content_with_hash"):
        session.flush()
    session.rollback()
