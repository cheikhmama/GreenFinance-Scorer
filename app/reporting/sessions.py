"""Sessions de déclaration et périmètre d'accès multi-tenant (tâche 1.5, docs/WORKFLOWS.md §1.2).

Cycle : ouvrir (DRAFT, sans fichier) -> soumettre (dépôt du PDF : SUBMITTED, extraction en file)
ou abandonner (suppression du brouillon). La soumission passe par exactement le même chemin que
le dépôt en une étape (app/company/rapports.py::deposer_fichier).

Périmètre, appliqué à chaque lecture comme à chaque écriture — jamais laissé aux appelants :
- ENTERPRISE : les rapports de SA propre entreprise ;
- AUDITOR : les rapports qui lui sont affectés (lecture seule) ;
- ADMIN : tous.
Un rapport hors périmètre répond 404, jamais 403 : ne jamais confirmer l'existence d'un rapport
d'autrui (même règle que app/company/rapports.py::rapport_de_lentreprise).
"""

import uuid

import structlog
from fastapi import BackgroundTasks
from sqlalchemy import ColumnElement
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.auth.models import User
from app.company.models import Company
from app.company.rapports import deposer_fichier, verifier_entreprise_active
from app.core.enums import (
    ExtractionStatus,
    ReportStatus,
    ReportType,
    Role,
    SubmissionChannel,
)
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.ingestion.models import ESGReport
from app.reporting.schemas import ReportCreateRequest

logger = structlog.get_logger(__name__)

_INTROUVABLE = "Rapport introuvable."


def _entreprise_de(user: User) -> Company:
    if user.company is None:
        raise ValidationError(
            "Aucune entreprise n'est rattachée à ce compte.", code="entreprise_manquante"
        )
    return user.company


def perimetre(user: User) -> list[ColumnElement[bool]]:
    """Filtres SQL du périmètre de `user` — la seule définition, partagée par toutes les
    fonctions de ce module."""
    if user.role == Role.ADMIN:
        return []
    if user.role == Role.ENTERPRISE:
        return [col(ESGReport.company_id) == _entreprise_de(user).id]
    if user.role == Role.AUDITOR:
        return [col(ESGReport.auditor_id) == user.id]
    raise PermissionDeniedError(f"Rôle {user.role.value} non autorisé pour cette action.")


def rapport_visible(
    session: Session, user: User, rapport_id: uuid.UUID, *, verrouiller: bool = False
) -> ESGReport:
    requete = select(ESGReport).where(col(ESGReport.id) == rapport_id, *perimetre(user))
    if verrouiller:
        requete = requete.with_for_update()
    rapport = session.exec(requete).first()
    if rapport is None:
        raise NotFoundError(_INTROUVABLE, code="rapport_introuvable")
    return rapport


def _brouillon_modifiable(
    session: Session, user: User, rapport_id: uuid.UUID
) -> ESGReport:
    """Écriture sur un brouillon : Entreprise titulaire ou Administrateur seulement (l'Auditeur
    ne voit que des rapports déjà soumis), ligne verrouillée jusqu'au commit."""
    if user.role not in (Role.ENTERPRISE, Role.ADMIN):
        raise PermissionDeniedError(f"Rôle {user.role.value} non autorisé pour cette action.")
    rapport = rapport_visible(session, user, rapport_id, verrouiller=True)
    if rapport.status != ReportStatus.DRAFT:
        raise ValidationError("Ce rapport n'est plus un brouillon.", code="transition_invalide")
    return rapport


def ouvrir(session: Session, user: User, demande: ReportCreateRequest) -> ESGReport:
    if user.role == Role.ENTERPRISE:
        entreprise = _entreprise_de(user)
    elif user.role == Role.ADMIN:
        if demande.company_id is None:
            raise ValidationError(
                "company_id est requis pour un Administrateur.", code="entreprise_requise"
            )
        trouvee = session.get(Company, demande.company_id)
        if trouvee is None:
            raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
        entreprise = trouvee
    else:
        raise PermissionDeniedError(f"Rôle {user.role.value} non autorisé pour cette action.")
    verifier_entreprise_active(entreprise)

    brouillon = ESGReport(
        company_id=entreprise.id,
        type=demande.report_type,
        channel=SubmissionChannel.ENTREPRISE,
        fiscal_year=demande.fiscal_year,
        status=ReportStatus.DRAFT,
        extraction_status=ExtractionStatus.NOT_STARTED,
    )
    session.add(brouillon)
    try:
        session.commit()
    except IntegrityError as exc:
        # uq_esg_reports_one_draft_per_period — y compris sous deux ouvertures concurrentes.
        session.rollback()
        raise ValidationError(
            "Une déclaration est déjà ouverte pour cet exercice et ce type de rapport.",
            code="brouillon_existant",
        ) from exc
    session.refresh(brouillon)
    logger.info("reporting_session_opened", rapport_id=str(brouillon.id))
    return brouillon


def lister(
    session: Session,
    user: User,
    *,
    fiscal_year: int | None,
    status: ReportStatus | None,
    report_type: ReportType | None,
    company_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[ESGReport], int]:
    filtres = perimetre(user)
    if fiscal_year is not None:
        filtres.append(col(ESGReport.fiscal_year) == fiscal_year)
    if status is not None:
        filtres.append(col(ESGReport.status) == status)
    if report_type is not None:
        filtres.append(col(ESGReport.type) == report_type)
    if company_id is not None:
        # S'ajoute au périmètre, ne le remplace jamais : une Entreprise qui passe l'id d'une autre
        # obtient simplement une liste vide.
        filtres.append(col(ESGReport.company_id) == company_id)

    total = session.exec(select(func.count()).select_from(ESGReport).where(*filtres)).one()
    rapports = session.exec(
        select(ESGReport)
        .where(*filtres)
        .order_by(col(ESGReport.created_at).desc(), col(ESGReport.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(rapports), total


def consulter(session: Session, user: User, rapport_id: uuid.UUID) -> ESGReport:
    return rapport_visible(session, user, rapport_id)


def soumettre(
    session: Session,
    background_tasks: BackgroundTasks,
    user: User,
    rapport_id: uuid.UUID,
    contenu: bytes,
    nom_fichier: str | None,
) -> ESGReport:
    brouillon = _brouillon_modifiable(session, user, rapport_id)
    return deposer_fichier(session, background_tasks, brouillon, contenu, nom_fichier)


def abandonner(session: Session, user: User, rapport_id: uuid.UUID) -> None:
    brouillon = _brouillon_modifiable(session, user, rapport_id)
    session.delete(brouillon)
    session.commit()
    logger.info("reporting_session_discarded", rapport_id=str(rapport_id))
