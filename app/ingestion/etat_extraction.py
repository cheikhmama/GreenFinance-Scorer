"""État d'une extraction partagé par le pipeline et la supervision (tâches 4.1, 4.2).

Module volontairement léger : importé par le worker par défaut (tâche planifiée) et par l'API,
qui n'embarquent pas la pile d'extraction (Docling, torch, bge-m3) — seul
app/ingestion/extractor.py, exécuté par le worker d'extraction, en a besoin.
"""

from sqlmodel import Session

from app.core.enums import ReportStatus
from app.core.notifications import notifier
from app.ingestion.models import ESGReport


class ExtractionTransitoire(Exception):
    """Échec probablement passager (quota ou erreur serveur du LLM, réseau) : le worker retentera
    plus tard (app/worker/jobs.py::extract_report) au lieu de marquer le rapport en échec."""


def marquer_echec(session: Session, rapport: ESGReport, cause: str) -> None:
    """Échec classifié d'une extraction : cause fixe (jamais str(exc)), tentative comptée,
    entreprise prévenue. Partagé par le pipeline et la reprise planifiée des extractions bloquées
    (app/worker/jobs.py::reprendre_extractions). Ne commite pas."""
    rapport.extraction_error = cause
    rapport.status = ReportStatus.EXTRACTION_FAILED
    rapport.extraction_attempts += 1
    session.add(rapport)
    if rapport.company.owner_user_id is not None:
        notifier(
            session,
            rapport.company.owner_user_id,
            "RAPPORT_EXTRACTION_ECHOUEE",
            f"L'extraction de votre rapport {rapport.type.value} ({rapport.fiscal_year}) "
            "a échoué. Vous pouvez déposer une nouvelle version.",
            id_ressource=rapport.id,
        )
