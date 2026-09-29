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
from decimal import Decimal

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
    CarbonEmission,
    ESGMetric,
    ESGReport,
    Evidence,
)
from app.investor.models import Portfolio, PortfolioPosition
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

    # --- Evidence + ESGMetric + CarbonEmission ---------------
    preuve = Evidence(
        document_name="rapport-annuel-2025.pdf",
        year=2025,
        total_pages=120,
        page_start=42,
        page_end=44,
        excerpt_pdf_path="s3://bucket/extraits/42-44.pdf",
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
    donnee_carbone = CarbonEmission(
        report_id=rapport.id,
        scope=1,
        tonnes_co2e=123.4,
        year=2025,
        method=MethodeDonnee.RAPPORTEE,
        pcaf_data_quality=3,
        proof_id=preuve.id,
    )
    session.add(indicateur)
    session.add(donnee_carbone)
    session.flush()

    assert indicateur.report.id == rapport.id
    assert indicateur in rapport.metrics
    assert donnee_carbone.report.id == rapport.id
    assert donnee_carbone in rapport.carbon_data
    assert indicateur.proof.id == preuve.id
    assert indicateur in preuve.metrics
    assert donnee_carbone.proof.id == preuve.id
    assert donnee_carbone in preuve.carbon_emissions

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
    portefeuille = Portfolio(
        user_id=investisseur.id, name="Portefeuille vert", reference_currency=DevisePosition.USD
    )
    session.add(portefeuille)
    session.flush()

    assert portefeuille.user.id == investisseur.id
    assert portefeuille in investisseur.portfolios

    debut_fixe = utcnow() + timedelta(days=1)
    position_usd = PortfolioPosition.model_validate(
        {
            "portfolio_id": portefeuille.id,
            "company_id": entreprise.id,
            "outstanding_amount": Decimal(1000),
            "currency": DevisePosition.USD,
            "fx_rate_used": Decimal("0.92"),
            "converted_amount": Decimal(920),
            "duration_type": TypeDureeInvestissement.OUVERTE,
            "start_date": utcnow(),
        }
    )
    position_fixe = PortfolioPosition.model_validate(
        {
            "portfolio_id": portefeuille.id,
            "company_id": entreprise.id,
            "outstanding_amount": 2000.0,
            "currency": DevisePosition.MRU,
            "converted_amount": 52.0,
            "duration_type": TypeDureeInvestissement.FIXE,
            "start_date": debut_fixe,
            "end_date": debut_fixe + timedelta(days=180),
        }
    )
    position_ouverte = PortfolioPosition.model_validate(
        {
            "portfolio_id": portefeuille.id,
            "company_id": entreprise.id,
            "outstanding_amount": 750.0,
            "currency": DevisePosition.EUR,
            "converted_amount": 750.0,
            "duration_type": TypeDureeInvestissement.OUVERTE,
            "start_date": utcnow(),
        }
    )
    session.add(position_usd)
    session.add(position_fixe)
    session.add(position_ouverte)
    session.flush()

    assert position_usd.fx_rate_used == Decimal("0.92")
    assert position_usd.converted_amount == Decimal(920)
    assert position_fixe.end_date is not None
    assert position_ouverte.end_date is None
    assert {position_usd.id, position_fixe.id, position_ouverte.id} == {
        p.id for p in portefeuille.positions
    }
    for position in (position_usd, position_fixe, position_ouverte):
        assert position.portfolio.id == portefeuille.id
        assert position.company is not None and position.company.id == entreprise.id
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
    preuve = Evidence(
        document_name="rapport.pdf",
        year=2025,
        total_pages=10,
        page_start=1,
        page_end=1,
        excerpt_pdf_path="s3://bucket/extraits/1.pdf",
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
