import random

"""Prompt 3.9 — scénario de bout en bout sur le schéma complet (Étape 3).

Construit un graphe couvrant les 14 entités du diagramme de classes plus les
deux clarifications ajoutées à la révision (configuration de pondération
ouverte à un Chercheur, position en devise étrangère convertie), et vérifie
que chaque relation se résout dans les deux sens — la preuve que le schéma
appliqué par la migration Alembic consolidée (b5f953dddf56) est fidèle aux
modèles SQLModel, pas seulement que chaque table existe isolément.
"""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from app.audit.models import AvisAudit
from app.auth.models import User
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import (
    CanalDepot,
    DecisionAudit,
    DevisePosition,
    MethodeDonnee,
    Pilier,
    Role,
    TypeDureeInvestissement,
    TypeRapport,
)
from app.core.models import Notification
from app.ingestion.models import (
    DonneeCarbone,
    ESGMetric,
    ESGReport,
    PreuveDocumentaire,
)
from app.investor.models import Portefeuille, PositionPortefeuille
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


def test_scenario_complet_schema_pivot_relations_bidirectionnelles(session) -> None:
    # --- Entreprise avec montant minimum d'investissement renseigné -------
    entreprise = Company(
        name="Acme Verte",
        sector="Industrie",
        country="MR",
        minimum_investment_amount=500.0,
    )
    session.add(entreprise)
    session.flush()

    # --- ESGReport -------------------------------------------------------
    rapport = ESGReport(
        company_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.AUTOMATIQUE,
        source_file="s3://bucket/rapport.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.flush()

    assert rapport in entreprise.reports
    assert rapport.company.id == entreprise.id

    # --- PreuveDocumentaire + ESGMetric + DonneeCarbone ---------------
    preuve = PreuveDocumentaire(
        nom_document="rapport-annuel-2025.pdf",
        annee=2025,
        nombre_pages_total=120,
        page_debut=42,
        page_fin=44,
        pdf_extrait_genere="s3://bucket/extraits/42-44.pdf",
    )
    session.add(preuve)
    session.flush()

    indicateur = ESGMetric(
        report_id=rapport.id,
        pillar=Pilier.ENVIRONNEMENT,
        metric_code="GHG-SCOPE1",
        value=123.4,
        unit="tCO2e",
        method=MethodeDonnee.RAPPORTEE,
        proof_id=preuve.id,
    )
    donnee_carbone = DonneeCarbone(
        rapport_id=rapport.id,
        scope=1,
        valeur_tonnes_co2e=123.4,
        annee=2025,
        methode=MethodeDonnee.RAPPORTEE,
        score_qualite_pcaf=3,
        preuve_id=preuve.id,
    )
    session.add(indicateur)
    session.add(donnee_carbone)
    session.flush()

    assert indicateur.report.id == rapport.id
    assert indicateur in rapport.metrics
    assert donnee_carbone.rapport.id == rapport.id
    assert donnee_carbone in rapport.carbon_data
    assert indicateur.proof.id == preuve.id
    assert indicateur in preuve.indicateurs
    assert donnee_carbone.preuve.id == preuve.id
    assert donnee_carbone in preuve.donnees_carbone

    # --- ConfigurationPonderation de référence ET personnalisée (Chercheur)
    chercheur = _utilisateur(session, Role.RESEARCHER)
    # Version tirée au hasard : une seule référence par version, base de test partagée.
    config_reference = ConfigurationPonderation(
        nom="reference", version=random.randint(10_000, 10_000_000), fichier_yaml="scoring/reference.yaml"
    )
    config_chercheur = ConfigurationPonderation(
        nom="config-chercheur",
        version=1,
        fichier_yaml="scoring/chercheur.yaml",
        utilisateur_id=chercheur.id,
    )
    session.add(config_reference)
    session.add(config_chercheur)
    session.flush()

    assert config_chercheur.utilisateur is not None
    assert config_chercheur.utilisateur.id == chercheur.id
    assert config_chercheur in chercheur.scoring_configs

    # --- ScoreESG (un par configuration, sur le même ESGReport) ----------
    score_reference = ScoreESG(
        rapport_id=rapport.id,
        configuration_id=config_reference.id,
        valeur_globale=72.0,
        score_environnement=70.0,
        score_social=75.0,
        score_gouvernance=71.0,
    )
    score_chercheur = ScoreESG(
        rapport_id=rapport.id,
        configuration_id=config_chercheur.id,
        valeur_globale=68.0,
        score_environnement=65.0,
        score_social=70.0,
        score_gouvernance=69.0,
    )
    session.add(score_reference)
    session.add(score_chercheur)
    session.flush()

    assert {s.id for s in rapport.scores} == {score_reference.id, score_chercheur.id}
    assert score_reference.rapport.id == rapport.id
    assert score_reference.configuration.id == config_reference.id
    assert score_reference in config_reference.scores
    assert score_chercheur.configuration.id == config_chercheur.id
    assert score_chercheur in config_chercheur.scores

    # --- Portefeuille + positions (USD converti, FIXE, OUVERTE) -----------
    investisseur = _utilisateur(session, Role.INVESTOR)
    portefeuille = Portefeuille(
        investisseur_id=investisseur.id, nom="Portefeuille vert", devise_reference=DevisePosition.USD
    )
    session.add(portefeuille)
    session.flush()

    assert portefeuille.investisseur.id == investisseur.id
    assert portefeuille in investisseur.portfolios

    debut_fixe = utcnow() + timedelta(days=1)
    position_usd = PositionPortefeuille.model_validate(
        {
            "portefeuille_id": portefeuille.id,
            "entreprise_id": entreprise.id,
            "montant_investi": 1000.0,
            "devise": DevisePosition.USD,
            "taux_change_utilise": 0.92,
            "montant_converti": 920.0,
            "type_duree": TypeDureeInvestissement.OUVERTE,
            "date_debut": utcnow(),
        }
    )
    position_fixe = PositionPortefeuille.model_validate(
        {
            "portefeuille_id": portefeuille.id,
            "entreprise_id": entreprise.id,
            "montant_investi": 2000.0,
            "devise": DevisePosition.MRU,
            "montant_converti": 52.0,
            "type_duree": TypeDureeInvestissement.FIXE,
            "date_debut": debut_fixe,
            "date_fin": debut_fixe + timedelta(days=180),
        }
    )
    position_ouverte = PositionPortefeuille.model_validate(
        {
            "portefeuille_id": portefeuille.id,
            "entreprise_id": entreprise.id,
            "montant_investi": 750.0,
            "devise": DevisePosition.EUR,
            "montant_converti": 750.0,
            "type_duree": TypeDureeInvestissement.OUVERTE,
            "date_debut": utcnow(),
        }
    )
    session.add(position_usd)
    session.add(position_fixe)
    session.add(position_ouverte)
    session.flush()

    assert position_usd.taux_change_utilise == 0.92
    assert position_usd.montant_converti == 920.0
    assert position_fixe.date_fin is not None
    assert position_ouverte.date_fin is None
    assert {position_usd.id, position_fixe.id, position_ouverte.id} == {
        p.id for p in portefeuille.positions
    }
    for position in (position_usd, position_fixe, position_ouverte):
        assert position.portefeuille.id == portefeuille.id
        assert position.entreprise.id == entreprise.id
        assert position in entreprise.positions

    # --- AvisAudit ----------------------------------------------------
    auditeur = _utilisateur(session, Role.AUDITOR)
    avis = AvisAudit(
        rapport_id=rapport.id,
        auditeur_id=auditeur.id,
        decision=DecisionAudit.RECOMMANDE_VALIDATION,
        commentaire="Données cohérentes avec le rapport annuel.",
    )
    session.add(avis)
    session.flush()

    assert avis.rapport.id == rapport.id
    assert avis in rapport.audit_opinions
    assert avis.auditeur.id == auditeur.id
    assert avis in auditeur.audit_opinions

    # --- Notification (entité transverse, hors diagramme de classes) ------
    notification = Notification(
        utilisateur_id=investisseur.id,
        message="Un nouveau rapport est disponible pour une entreprise de votre portefeuille.",
        type="RAPPORT_DISPONIBLE",
    )
    session.add(notification)
    session.flush()

    assert notification in investisseur.notifications
    assert notification.utilisateur.id == investisseur.id


def _rapport_avec_indicateur(session) -> tuple[Company, ESGReport, ESGMetric]:
    entreprise = Company(name="Acme Verte", sector="Industrie", country="MR")
    session.add(entreprise)
    session.flush()
    rapport = ESGReport(
        company_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.AUTOMATIQUE,
        source_file="s3://bucket/rapport.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.flush()
    preuve = PreuveDocumentaire(
        nom_document="rapport.pdf",
        annee=2025,
        nombre_pages_total=10,
        page_debut=1,
        page_fin=1,
        pdf_extrait_genere="s3://bucket/extraits/1.pdf",
    )
    session.add(preuve)
    session.flush()
    indicateur = ESGMetric(
        report_id=rapport.id,
        pillar=Pilier.SOCIAL,
        metric_code="effectif_total",
        value=1200.0,
        unit="",
        method=MethodeDonnee.RAPPORTEE,
        proof_id=preuve.id,
    )
    session.add(indicateur)
    session.flush()
    return entreprise, rapport, indicateur


def test_un_seul_indicateur_par_code_et_par_rapport(session) -> None:
    _entreprise, rapport, indicateur = _rapport_avec_indicateur(session)
    session.add(
        ESGMetric(
            report_id=rapport.id,
            pillar=Pilier.SOCIAL,
            metric_code=indicateur.metric_code,
            value=1300.0,
            unit="",
            method=MethodeDonnee.RAPPORTEE,
            proof_id=indicateur.proof_id,
        )
    )
    with pytest.raises(IntegrityError, match="uq_esg_metrics_report_metric_code"):
        session.flush()
    session.rollback()


def test_suppression_en_base_applique_les_regles_on_delete(session) -> None:
    """DELETE SQL direct (jamais la cascade ORM) : ce sont bien les règles ON DELETE de la base
    qui s'appliquent (docs/RENAME_PLAN.md §2.5)."""
    entreprise, rapport, indicateur = _rapport_avec_indicateur(session)
    auditeur = _utilisateur(session, Role.AUDITOR)
    rapport.auditor_id = auditeur.id
    session.add(rapport)
    session.flush()
    rapport_id, indicateur_id = rapport.id, indicateur.id

    # SET NULL : supprimer l'auditeur ne supprime jamais le rapport.
    session.execute(delete(User).where(col(User.id) == auditeur.id))
    session.expire_all()
    rapport_apres = session.get(ESGReport, rapport_id)
    assert rapport_apres is not None
    assert rapport_apres.auditor_id is None

    # CASCADE : supprimer l'entreprise emporte ses rapports et leurs indicateurs.
    session.execute(delete(Company).where(col(Company.id) == entreprise.id))
    session.expire_all()
    assert session.get(ESGReport, rapport_id) is None
    assert session.exec(select(ESGMetric).where(ESGMetric.id == indicateur_id)).first() is None
