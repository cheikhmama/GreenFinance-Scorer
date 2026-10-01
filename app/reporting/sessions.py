"""Sessions de déclaration et périmètre d'accès multi-tenant (tâche 1.5, docs/WORKFLOWS.md §1.2).

Cycle (tâche 5.8) : ouvrir (DRAFT, sans fichier) -> joindre le PDF (EXTRACTING, non soumis ; le
pipeline ramène le brouillon en DRAFT avec sa liste de complétude, ou avec la cause d'un échec)
-> soumettre (AWAITING_ASSIGNMENT, `submitted_at` posé : le rapport est verrouillé) ; ou
abandonner (suppression du brouillon). Joindre passe par exactement le même chemin que le dépôt
en une étape (app/company/rapports.py::deposer_fichier).

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
from app.core.audit import auditer
from app.core.database import utcnow
from app.core.enums import (
    MetricCoverageStatus,
    Pillar,
    ReportStatus,
    ReportType,
    Role,
    SubmissionChannel,
)
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.notifications import notifier
from app.ingestion.cibles import INDICATEURS_CIBLES, CibleIndicateur
from app.ingestion.etat_extraction import notifier_pret_a_affecter
from app.ingestion.models import ESGReport, MetricCoverage
from app.ingestion.vocabulaire import CODES_AUTO_DECLARES_PAR_PILIER
from app.reporting.schemas import GROUPE_CARBONE, GroupeCompletude, ReportCreateRequest
from app.worker.queue import FileIndisponible, enfiler

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


def joindre_fichier(
    session: Session,
    background_tasks: BackgroundTasks,
    user: User,
    rapport_id: uuid.UUID,
    contenu: bytes,
    nom_fichier: str | None,
) -> ESGReport:
    """Joint (ou remplace) le PDF d'un brouillon et lance son analyse. Refusé pendant une analyse
    en cours : le brouillon n'est alors plus en DRAFT."""
    brouillon = _brouillon_modifiable(session, user, rapport_id)
    return deposer_fichier(
        session, background_tasks, brouillon, contenu, nom_fichier, soumettre=False
    )


def soumettre(
    session: Session, background_tasks: BackgroundTasks, user: User, rapport_id: uuid.UUID
) -> ESGReport:
    """Soumission explicite d'un brouillon analysé (tâche 5.8) : `submitted_at` posé, statut
    AWAITING_ASSIGNMENT, Administrateurs prévenus, le tout dans une transaction. Le reçu est le
    rapport lui-même : son empreinte SHA-256 et l'heure de soumission. Ensuite plus rien ne
    change le fichier ni la déclaration."""
    brouillon = _brouillon_modifiable(session, user, rapport_id)
    if brouillon.source_file is None:
        raise ValidationError(
            "Joignez le PDF du rapport avant de soumettre.", code="fichier_manquant"
        )
    if brouillon.extraction_finished_at is None or brouillon.extraction_error is not None:
        raise ValidationError(
            "L'analyse du fichier n'a pas abouti : joignez à nouveau le fichier.",
            code="analyse_non_terminee",
        )
    verifier_entreprise_active(brouillon.company)

    brouillon.submitted_at = utcnow()
    brouillon.status = ReportStatus.AWAITING_ASSIGNMENT
    session.add(brouillon)
    notifier_pret_a_affecter(session, brouillon)
    if brouillon.company.owner_user_id is not None:
        notifier(
            session,
            brouillon.company.owner_user_id,
            "RAPPORT_DEPOSE",
            f"Votre rapport {brouillon.type.value} ({brouillon.fiscal_year}) a été soumis ; "
            "il est verrouillé pendant son examen.",
            id_ressource=brouillon.id,
        )
    auditer(
        session,
        user.id,
        "report_submitted",
        "ESGReport",
        brouillon.id,
        "success",
        new_value=brouillon.checksum_sha256,
    )
    session.commit()
    session.refresh(brouillon)
    logger.info("reporting_session_submitted", rapport_id=str(brouillon.id))
    # PDF de synthèse : produit par le worker après le commit, comme après une validation.
    background_tasks.add_task(_programmer_synthese, brouillon.id)
    return brouillon


def _programmer_synthese(rapport_id: uuid.UUID) -> None:
    try:
        enfiler("generate_synthesis_pdf", rapport_id)
    except FileIndisponible:
        logger.error("synthese_pdf_non_programmee", rapport_id=str(rapport_id))


def _groupe(cible: CibleIndicateur) -> str | None:
    """Groupe d'un indicateur dans la liste de complétude ; None pour les scores auto-déclarés,
    qui ne sont pas des indicateurs à fournir."""
    if cible.cible == "donnee_carbone":
        return GROUPE_CARBONE
    if cible.code in CODES_AUTO_DECLARES_PAR_PILIER or cible.pilier is None:
        return None
    return cible.pilier.value


def liste_de_completude(
    session: Session, user: User, rapport_id: uuid.UUID
) -> list[GroupeCompletude]:
    """Indicateurs trouvés sur attendus par groupe (carbone, puis piliers) d'après la dernière
    analyse du fichier — des comptes, jamais une valeur ni un score (tâche 5.8). Vide tant
    qu'aucune analyse n'a abouti."""
    rapport = rapport_visible(session, user, rapport_id)
    if rapport.extraction_finished_at is None or rapport.extraction_error is not None:
        return []
    trouves = set(
        session.exec(
            select(MetricCoverage.metric_code).where(
                col(MetricCoverage.report_id) == rapport.id,
                col(MetricCoverage.status) == MetricCoverageStatus.TROUVE,
            )
        ).all()
    )
    groupes: dict[str, GroupeCompletude] = {}
    for cible in INDICATEURS_CIBLES:
        cle = _groupe(cible)
        if cle is None:
            continue
        groupe = groupes.setdefault(cle, GroupeCompletude(group=cle, expected=0, found=0))
        groupe.expected += 1
        if cible.code in trouves:
            groupe.found += 1
    ordre = [GROUPE_CARBONE, *(pilier.value for pilier in Pillar)]
    return [groupes[cle] for cle in ordre if cle in groupes]


def abandonner(session: Session, user: User, rapport_id: uuid.UUID) -> None:
    brouillon = _brouillon_modifiable(session, user, rapport_id)
    session.delete(brouillon)
    session.commit()
    logger.info("reporting_session_discarded", rapport_id=str(rapport_id))
