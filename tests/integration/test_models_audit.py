import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.audit.models import AvisAudit
from app.auth.models import Utilisateur
from app.company.models import Company
from app.core.enums import (
    CanalDepot,
    DecisionAudit,
    MethodeDonnee,
    Pilier,
    Role,
    TypeRapport,
)
from app.core.models import Notification
from app.ingestion.models import (
    ESGMetric,
    ESGReport,
    PreuveDocumentaire,
    SignalementEcart,
)


def _utilisateur(session, role: Role) -> Utilisateur:
    utilisateur = Utilisateur(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        mot_de_passe_hache="hash",
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
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.AUTOMATIQUE,
        source_file="s3://bucket/rapport.pdf",
    )
    session.add(rapport)
    session.flush()
    preuve = PreuveDocumentaire(
        nom_document="doc.pdf",
        annee=2025,
        nombre_pages_total=10,
        page_debut=1,
        page_fin=2,
        pdf_extrait_genere="s3://bucket/extrait.pdf",
    )
    session.add(preuve)
    session.flush()
    indicateur = ESGMetric(
        report_id=rapport.id,
        pillar=Pilier.GOUVERNANCE,
        metric_code="GOV-01",
        value=1.0,
        unit="ratio",
        method=MethodeDonnee.RAPPORTEE,
        proof_id=preuve.id,
    )
    session.add(indicateur)
    session.flush()
    return rapport, indicateur


def test_creation_avis_audit(session) -> None:
    rapport, _ = _rapport_avec_indicateur(session)
    auditeur = _utilisateur(session, Role.AUDITEUR)

    avis = AvisAudit(
        rapport_id=rapport.id,
        auditeur_id=auditeur.id,
        decision=DecisionAudit.RECOMMANDE_VALIDATION,
        commentaire="Données cohérentes avec le rapport annuel.",
    )
    session.add(avis)
    session.flush()

    assert avis.id is not None
    assert avis.rapport.id == rapport.id
    assert avis.auditeur.id == auditeur.id
    assert avis in rapport.audit_opinions
    assert avis in auditeur.avis_rendus


def test_creation_signalement_ecart_ciblant_un_indicateur(session) -> None:
    rapport, indicateur = _rapport_avec_indicateur(session)

    signalement = SignalementEcart(
        indicateur_id=indicateur.id,
        entreprise_id=rapport.company_id,
        nature_ecart="Valeur incohérente avec l'année précédente",
    )
    session.add(signalement)
    session.flush()

    assert signalement.id is not None
    assert signalement.statut == "OUVERT"
    assert signalement.indicateur_id == indicateur.id
    # La cible est bien l'indicateur, jamais uniquement le rapport entier.
    assert signalement.indicateur.report_id == rapport.id
    assert signalement in indicateur.discrepancy_flags


def test_indicateur_id_doit_referencer_un_indicateur_pas_un_rapport(session) -> None:
    rapport, _ = _rapport_avec_indicateur(session)

    # rapport.id n'est pas une clé valide de la table indicateur_esg : la
    # contrainte de clé étrangère rejette la confusion rapport/indicateur.
    signalement = SignalementEcart(
        indicateur_id=rapport.id,
        entreprise_id=rapport.company_id,
        nature_ecart="x",
    )
    session.add(signalement)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_creation_notification(session) -> None:
    utilisateur = _utilisateur(session, Role.ENTREPRISE)

    notification = Notification(
        utilisateur_id=utilisateur.id,
        message="Votre rapport a été validé.",
        type="RAPPORT_VALIDE",
    )
    session.add(notification)
    session.flush()

    assert notification.id is not None
    assert notification.lu is False
    assert notification in utilisateur.notifications
