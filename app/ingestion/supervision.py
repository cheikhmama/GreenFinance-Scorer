"""Supervision des extractions (tâche 4.1) — exécutée par la tâche planifiée du worker
(app/worker/jobs.py::reprendre_extractions), plus à la lecture d'une page Admin.

- Une extraction RUNNING depuis plus de settings.extraction_timeout_minutes a été interrompue
  (worker tué, délai du job dépassé) : elle passe FAILED avec la cause fixe `delai_depasse`, et
  apparaît dans la file des échecs où l'Admin peut la relancer.
- Une extraction QUEUED dont le job a été perdu (Redis indisponible au moment du dépôt) est
  simplement redéposée : l'identifiant déterministe `extract:{rapport_id}` rend l'opération sans
  effet quand le job existe encore.
"""

import uuid
from datetime import timedelta

from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import ExtractionStatus
from app.ingestion.extractor import marquer_echec
from app.ingestion.models import ESGReport

CAUSE_DELAI_DEPASSE = "delai_depasse"


def echouer_extractions_bloquees(session: Session) -> list[uuid.UUID]:
    """Ne commite pas."""
    seuil = utcnow() - timedelta(minutes=get_settings().extraction_timeout_minutes)
    bloques = session.exec(
        select(ESGReport)
        .where(
            col(ESGReport.extraction_status) == ExtractionStatus.RUNNING,
            col(ESGReport.extraction_started_at).is_not(None),
            col(ESGReport.extraction_started_at) < seuil,
        )
        .with_for_update(skip_locked=True)
    ).all()
    for rapport in bloques:
        marquer_echec(session, rapport, CAUSE_DELAI_DEPASSE)
    return [rapport.id for rapport in bloques]


def extractions_en_file(session: Session) -> list[tuple[uuid.UUID, int]]:
    return [
        (rapport_id, annee)
        for rapport_id, annee in session.exec(
            select(ESGReport.id, ESGReport.fiscal_year).where(
                col(ESGReport.extraction_status) == ExtractionStatus.QUEUED,
                col(ESGReport.source_file).is_not(None),
                col(ESGReport.fiscal_year).is_not(None),
            )
        ).all()
        if annee is not None
    ]
