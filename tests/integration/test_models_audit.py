import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.audit.models import AuditOpinion
from app.auth.models import User
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import (
    AuditDecision,
    DataMethod,
    Pillar,
    ReportType,
    Role,
    SubmissionChannel,
)
from app.core.models import Notification
from app.ingestion.models import (
    DiscrepancyFlag,
    ESGMetric,
    ESGReport,
    Evidence,
)


def _utilisateur(session, role: Role) -> User:
    utilisateur = User(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        password_hash="hash",
        role=role,
    )
    session.add(utilisateur)
    session.flush()
    return utilisateur


def _rapport_avec_indicateur(session) -> tuple[ESGReport, ESGMetric]:
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
    preuve = Evidence(
        document_name="doc.pdf",
        year=2025,
        total_pages=10,
        page_start=1,
        page_end=2,
        excerpt_pdf_path="s3://bucket/extrait.pdf",
    )
    session.add(preuve)
    session.flush()
    indicateur = ESGMetric(
        report_id=rapport.id,
        pillar=Pillar.GOUVERNANCE,
        metric_code="GOV-01",
        value=1.0,
        unit="ratio",
        method=DataMethod.RAPPORTEE,
        proof_id=preuve.id,
    )
    session.add(indicateur)
    session.flush()
    return rapport, indicateur


def test_creation_avis_audit(session) -> None:
    rapport, _ = _rapport_avec_indicateur(session)
    auditeur = _utilisateur(session, Role.AUDITOR)

    avis = AuditOpinion(
        report_id=rapport.id,
        auditor_id=auditeur.id,
        decision=AuditDecision.FAVORABLE,
        comment="Données cohérentes avec le rapport annuel.",
    )
    session.add(avis)
    session.flush()

    assert avis.id is not None
    assert avis.report.id == rapport.id
    assert avis.auditor.id == auditeur.id
    assert avis in rapport.audit_opinions
    assert avis in auditeur.audit_opinions


def test_creation_signalement_ecart_ciblant_un_indicateur(session) -> None:
    rapport, indicateur = _rapport_avec_indicateur(session)

    signalement = DiscrepancyFlag(
        metric_id=indicateur.id,
        company_id=rapport.company_id,
        nature="Valeur incohérente avec l'année précédente",
    )
    session.add(signalement)
    session.flush()

    assert signalement.id is not None
    assert signalement.status == "OUVERT"
    assert signalement.metric_id == indicateur.id
    # La cible est bien l'indicateur, jamais uniquement le rapport entier.
    assert signalement.metric.report_id == rapport.id
    assert signalement in indicateur.discrepancy_flags


def test_indicateur_id_doit_referencer_un_indicateur_pas_un_rapport(session) -> None:
    rapport, _ = _rapport_avec_indicateur(session)

    # rapport.id n'est pas une clé valide de la table indicateur_esg : la
    # contrainte de clé étrangère rejette la confusion rapport/indicateur.
    signalement = DiscrepancyFlag(
        metric_id=rapport.id,
        company_id=rapport.company_id,
        nature="x",
    )
    session.add(signalement)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_creation_notification(session) -> None:
    utilisateur = _utilisateur(session, Role.ENTERPRISE)

    notification = Notification(
        user_id=utilisateur.id,
        message="Votre rapport a été validé.",
        type="RAPPORT_VALIDE",
    )
    session.add(notification)
    session.flush()

    assert notification.id is not None
    assert notification.read is False
    assert notification in utilisateur.notifications
