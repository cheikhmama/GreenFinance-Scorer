"""État d'une extraction partagé par le pipeline et la supervision (tâches 4.1, 4.2).

Module volontairement léger : importé par le worker par défaut (tâche planifiée) et par l'API,
qui n'embarquent pas la pile d'extraction (Docling, torch, bge-m3) — seul
app/ingestion/extractor.py, exécuté par le worker d'extraction, en a besoin.
"""

import uuid

from sqlmodel import Session, col, select

from app.auth.models import User
from app.core.database import utcnow
from app.core.enums import ExtractionRunStatus, ReportStatus, Role
from app.core.notifications import notifier
from app.ingestion.models import ESGReport, ExtractionRun


class ExtractionTransitoire(Exception):
    """Échec probablement passager (quota ou erreur serveur du LLM, réseau) : le worker retentera
    plus tard (app/worker/jobs.py::extract_report) au lieu de marquer le rapport en échec."""


def cloturer_executions(
    session: Session, rapport_id: uuid.UUID, statut: ExtractionRunStatus, cause: str
) -> None:
    """Clôt les exécutions encore ouvertes (RUNNING) d'un rapport (tâche 5.5) — par le pipeline
    (échec, remise en file) ou par la supervision (exécution interrompue). Ne commite pas."""
    for execution in session.exec(
        select(ExtractionRun).where(
            col(ExtractionRun.report_id) == rapport_id,
            col(ExtractionRun.status) == ExtractionRunStatus.RUNNING,
        )
    ).all():
        execution.status = statut
        execution.error = cause
        execution.finished_at = utcnow()
        session.add(execution)


def marquer_echec(session: Session, rapport: ESGReport, cause: str) -> None:
    """Échec classifié d'une extraction : cause fixe (jamais str(exc)), tentative comptée,
    entreprise prévenue. Partagé par le pipeline et la reprise planifiée des extractions bloquées
    (app/worker/jobs.py::reprendre_extractions). Ne commite pas.

    Un brouillon dont le fichier était en analyse (pas encore soumis, tâche 5.8) revient en
    DRAFT avec sa cause : l'Entreprise joint à nouveau un fichier, rien n'arrive chez l'Admin."""
    brouillon = rapport.submitted_at is None
    rapport.extraction_error = cause
    rapport.status = ReportStatus.DRAFT if brouillon else ReportStatus.EXTRACTION_FAILED
    rapport.extraction_attempts += 1
    session.add(rapport)
    cloturer_executions(session, rapport.id, ExtractionRunStatus.FAILED, cause)
    if rapport.company.owner_user_id is not None:
        notifier(
            session,
            rapport.company.owner_user_id,
            "RAPPORT_EXTRACTION_ECHOUEE",
            f"Le fichier de votre déclaration {rapport.type.value} ({rapport.fiscal_year}) "
            "n'a pas pu être lu. Vous pouvez le joindre à nouveau."
            if brouillon
            else f"L'extraction de votre rapport {rapport.type.value} ({rapport.fiscal_year}) "
            "a échoué. Vous pouvez déposer une nouvelle version.",
            id_ressource=rapport.id,
        )


def notifier_pret_a_affecter(session: Session, rapport: ESGReport) -> None:
    """Prévient les Administrateurs qu'un rapport soumis attend un auditeur — à la fin de
    l'extraction d'un dépôt en une étape, ou à la soumission d'un brouillon déjà analysé
    (tâche 5.8). Ne commite pas."""
    for admin in session.exec(
        select(User).where(col(User.role) == Role.ADMIN, col(User.active).is_(True))
    ).all():
        notifier(
            session,
            admin.id,
            "RAPPORT_PRET_A_AFFECTER",
            f"Le rapport {rapport.type.value} ({rapport.fiscal_year}) de "
            f"{rapport.company.name} est prêt à être affecté à un auditeur.",
            id_ressource=rapport.id,
        )
