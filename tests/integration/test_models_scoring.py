import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.models import User
from app.company.models import Company
from app.core.enums import CanalDepot, Role, TypeRapport
from app.ingestion.models import ESGReport
from app.scoring.models import ConfigurationPonderation, ScoreESG


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
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.AUTOMATIQUE,
        source_file="s3://bucket/rapport.pdf",
    )
    session.add(rapport)
    session.flush()
    return rapport


@pytest.mark.parametrize("role", [Role.INVESTOR, Role.RESEARCHER, Role.INSTITUTION])
def test_configuration_personnalisee_par_role(session, role: Role) -> None:
    utilisateur = _utilisateur(session, role)
    configuration = ConfigurationPonderation(
        nom=f"config-{role.value}",
        version=1,
        fichier_yaml="scoring/custom.yaml",
        utilisateur_id=utilisateur.id,
    )
    session.add(configuration)
    session.flush()

    assert configuration.id is not None
    assert configuration.utilisateur_id == utilisateur.id


def test_rapport_accepte_plusieurs_scores_un_par_configuration(session) -> None:
    rapport = _rapport(session)

    config_reference = ConfigurationPonderation(
        nom="reference", version=1, fichier_yaml="scoring/reference.yaml"
    )
    utilisateur = _utilisateur(session, Role.INVESTOR)
    config_perso = ConfigurationPonderation(
        nom="perso",
        version=1,
        fichier_yaml="scoring/perso.yaml",
        utilisateur_id=utilisateur.id,
    )
    session.add(config_reference)
    session.add(config_perso)
    session.flush()

    score_reference = ScoreESG(
        rapport_id=rapport.id,
        configuration_id=config_reference.id,
        valeur_globale=72.0,
        score_environnement=70.0,
        score_social=75.0,
        score_gouvernance=71.0,
    )
    score_perso = ScoreESG(
        rapport_id=rapport.id,
        configuration_id=config_perso.id,
        valeur_globale=68.0,
        score_environnement=65.0,
        score_social=70.0,
        score_gouvernance=69.0,
    )
    session.add(score_reference)
    session.add(score_perso)
    session.flush()

    assert len(rapport.scores) == 2
    assert {s.configuration_id for s in rapport.scores} == {
        config_reference.id,
        config_perso.id,
    }


@pytest.mark.parametrize(
    "champ", ["valeur_globale", "score_environnement", "score_social", "score_gouvernance"]
)
@pytest.mark.parametrize("valeur_invalide", [-0.5, 100.5])
def test_score_hors_bornes_rejete_en_base(session, champ: str, valeur_invalide: float) -> None:
    """Construction directe ScoreESG(**kwargs) (comme le fera le futur moteur de calcul,
    Étape 12) : la validation Pydantic (Field ge/le) n'est jamais déclenchée sur ce chemin —
    seule la contrainte CHECK côté PostgreSQL (Phase 5 §6) protège les 4 scores."""
    rapport = _rapport(session)
    configuration = ConfigurationPonderation(
        nom="reference", version=1, fichier_yaml="scoring/reference.yaml"
    )
    session.add(configuration)
    session.flush()

    valeurs = {
        "valeur_globale": 50.0,
        "score_environnement": 50.0,
        "score_social": 50.0,
        "score_gouvernance": 50.0,
    }
    valeurs[champ] = valeur_invalide
    session.add(
        ScoreESG(rapport_id=rapport.id, configuration_id=configuration.id, **valeurs)
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_utilisateur_id_nul_reserve_a_la_reference(session) -> None:
    """utilisateur_id nul = configuration de référence. Au niveau du
    schéma, rien n'empêche aujourd'hui de créer plusieurs configurations
    avec utilisateur_id nul : « une seule référence à la fois » est une
    règle applicative (couche service, à appliquer quand le moteur de
    scoring sera implémenté à l'Étape 12), pas une contrainte de base de
    données à ce stade — ce test documente explicitement cet état, il ne
    doit pas être interprété comme une lacune non détectée."""
    reference_1 = ConfigurationPonderation(
        nom="reference-v1", version=1, fichier_yaml="scoring/reference-v1.yaml"
    )
    reference_2 = ConfigurationPonderation(
        nom="reference-v2", version=2, fichier_yaml="scoring/reference-v2.yaml"
    )
    session.add(reference_1)
    session.add(reference_2)
    session.flush()

    assert reference_1.utilisateur_id is None
    assert reference_2.utilisateur_id is None
