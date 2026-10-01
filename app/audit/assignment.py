"""Affectation des dossiers d'entreprise aux auditeurs.

Appelé depuis app/admin/router.py (c'est l'Administrateur qui déclenche l'affectation), mais la
mutation elle-même vit ici — app/audit/ possède l'attribution des dossiers, l'admin invoque cette
interface plutôt que de réimplémenter localement la transition (voir ARCHITECTURE.md §1).
"""

import uuid
from datetime import timedelta

import structlog
from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app.audit.models import AuditOpinion
from app.auth.models import User
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import ReportStatus, Role
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier
from app.core.recherche import contient
from app.ingestion.models import ESGReport

logger = structlog.get_logger(__name__)


def affecter_auditeur(session: Session, rapport_id: uuid.UUID, auditeur_id: uuid.UUID) -> ESGReport:
    rapport = session.get(ESGReport, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    if rapport.status in (ReportStatus.EXTRACTING, ReportStatus.EXTRACTION_FAILED):
        raise ValidationError(
            "L'extraction de ce rapport n'est pas terminée.", code="extraction_non_terminee"
        )
    if rapport.status != ReportStatus.AWAITING_ASSIGNMENT:
        raise ValidationError(
            "Ce rapport n'est pas en attente d'affectation.", code="rapport_deja_affecte"
        )

    auditeur = session.get(User, auditeur_id)
    if auditeur is None or auditeur.role != Role.AUDITOR or not auditeur.active:
        raise ValidationError("Auditeur invalide.", code="auditeur_invalide")

    rapport.auditor_id = auditeur.id
    rapport.status = ReportStatus.IN_AUDIT
    rapport.assigned_at = utcnow()
    session.add(rapport)

    notifier(
        session,
        auditeur.id,
        "RAPPORT_AFFECTE_AUDITEUR",
        f"Un rapport {rapport.type.value} ({rapport.fiscal_year}) de {rapport.company.name} "
        "vous a été affecté pour audit.",
        id_ressource=rapport.id,
    )
    if rapport.company.owner_user_id is not None:
        notifier(
            session,
            rapport.company.owner_user_id,
            "RAPPORT_AFFECTE_ENTREPRISE",
            f"Votre rapport {rapport.type.value} ({rapport.fiscal_year}) a été affecté à un "
            "auditeur.",
            id_ressource=rapport.id,
        )

    session.commit()
    session.refresh(rapport)
    logger.info(
        "rapport_affecte_auditeur", rapport_id=str(rapport_id), auditeur_id=str(auditeur_id)
    )
    return rapport


def statistiques_charge_globale(session: Session) -> tuple[int, int]:
    """(dossiers actuellement affectés, avis rendus au total) tous Auditeurs confondus — vue de
    synthèse pour l'Aperçu Administrateur (app/admin/apercu.py). Les comptes actifs et le retard
    global sont déjà calculés ailleurs (app/admin/dashboard.py, app/admin/review_queue.py::
    lister_rapports_en_retard), pas dupliqués ici."""
    dossiers_affectes = session.exec(
        select(func.count())
        .select_from(ESGReport)
        .where(col(ESGReport.status) == ReportStatus.IN_AUDIT)
    ).one()
    avis_rendus = session.exec(select(func.count()).select_from(AuditOpinion)).one()
    return dossiers_affectes, avis_rendus


def lister_charge_auditeurs(
    session: Session,
    *,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[tuple[User, int, int, int]], int]:
    """Charge de travail par Auditeur actif — dossiers actuellement affectés, dont ceux en retard
    (au-delà de settings.sla_audit_jours), et avis rendus au total : le détail derrière le chiffre
    "Dossiers affectés" de l'Aperçu Administrateur (indicateur → liste filtrée). Pagination par
    offset/limit, même principe que les autres listes Admin (voir app/admin/utilisateurs.py)."""
    filtres: list[ColumnElement[bool]] = [
        col(User.role) == Role.AUDITOR,
        col(User.active).is_(True),
    ]
    if recherche:
        filtres.append(contient(recherche, User.email))

    total = session.exec(select(func.count()).select_from(User).where(*filtres)).one()
    auditeurs = list(
        session.exec(
            select(User)
            .where(*filtres)
            .order_by(col(User.email))
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )

    seuil_retard = utcnow() - timedelta(days=get_settings().sla_audit_jours)
    resultats: list[tuple[User, int, int, int]] = []
    for auditeur in auditeurs:
        dossiers_affectes = session.exec(
            select(func.count())
            .select_from(ESGReport)
            .where(
                col(ESGReport.auditor_id) == auditeur.id,
                col(ESGReport.status) == ReportStatus.IN_AUDIT,
            )
        ).one()
        dossiers_en_retard = session.exec(
            select(func.count())
            .select_from(ESGReport)
            .where(
                col(ESGReport.auditor_id) == auditeur.id,
                col(ESGReport.status) == ReportStatus.IN_AUDIT,
                col(ESGReport.assigned_at).is_not(None),
                col(ESGReport.assigned_at) < seuil_retard,
            )
        ).one()
        avis_rendus = session.exec(
            select(func.count())
            .select_from(AuditOpinion)
            .where(col(AuditOpinion.auditor_id) == auditeur.id)
        ).one()
        resultats.append((auditeur, dossiers_affectes, dossiers_en_retard, avis_rendus))
    return resultats, total
