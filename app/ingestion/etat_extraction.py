"""État d'une extraction partagé par le pipeline et la supervision (tâches 4.1, 4.2).

Module volontairement léger : importé par le worker par défaut (tâche planifiée) et par l'API,
qui n'embarquent pas la pile d'extraction (Docling, torch, bge-m3) — seul
app/ingestion/extractor.py, exécuté par le worker d'extraction, en a besoin.
"""

import uuid

from sqlmodel import Session, col, select

from app.core.database import utcnow
from app.core.enums import ExtractionRunStatus, ReportStatus
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
    (app/worker/jobs.py::reprendre_extractions). Ne commite pas."""
    rapport.extraction_error = cause
    rapport.status = ReportStatus.EXTRACTION_FAILED
    rapport.extraction_attempts += 1
    session.add(rapport)
    cloturer_executions(session, rapport.id, ExtractionRunStatus.FAILED, cause)
    if rapport.company.owner_user_id is not None:
        notifier(
            session,
            rapport.company.owner_user_id,
            "RAPPORT_EXTRACTION_ECHOUEE",
            f"L'extraction de votre rapport {rapport.type.value} ({rapport.fiscal_year}) "
            "a échoué. Vous pouvez déposer une nouvelle version.",
            id_ressource=rapport.id,
        )
