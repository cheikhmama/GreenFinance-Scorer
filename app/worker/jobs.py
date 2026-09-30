"""Jobs exécutés par les workers ARQ (tâche 4.1, docs/ARCHITECTURE.md §6).

Le travail lui-même reste synchrone (Docling, SQLModel, smtplib) : chaque job l'exécute dans un
thread (asyncio.to_thread) pour ne pas bloquer la boucle du worker, et ouvre sa propre session.

Reprises :
- extract_report : un échec transitoire (quota ou erreur serveur du LLM, réseau) est retenté avec
  un délai croissant, jusqu'à MAX_TENTATIVES_EXTRACTION ; toute autre erreur marque le rapport
  FAILED avec une cause fixe dès la première fois (app/ingestion/extractor.py).
- send_email : SMTP indisponible -> retenté jusqu'à MAX_TENTATIVES_EMAIL ; configuration absente
  -> abandon journalisé, retenter n'y changerait rien.
"""

import asyncio
import uuid
from typing import Any

import structlog
from arq import Retry
from sqlmodel import Session

from app.core.database import engine
from app.core.email import EmailDeliveryError, ensure_email_configured, send_email
from app.ingestion import supervision, synthesis_report
from app.ingestion.etat_extraction import ExtractionTransitoire
from app.ingestion.models import ESGReport
from app.worker.queue import FILE_EXTRACTION

logger = structlog.get_logger(__name__)

MAX_TENTATIVES_EXTRACTION = 3
MAX_TENTATIVES_EMAIL = 5
DELAI_REPRISE_SECONDES = 60


def _delai(ctx: dict[str, Any]) -> int:
    return DELAI_REPRISE_SECONDES * int(ctx["job_try"])


def _executer_extraction(rapport_id: uuid.UUID, annee_reporting: int, derniere: bool) -> None:
    # Import au premier job : la pile d'extraction (Docling, torch, bge-m3) n'est chargée que par
    # le worker d'extraction, jamais par le worker par défaut ni par l'API (image légère, 4.2).
    from app.ingestion.extractor import run_extraction_pipeline

    run_extraction_pipeline(rapport_id, annee_reporting, derniere_tentative=derniere)


async def extract_report(ctx: dict[str, Any], rapport_id: uuid.UUID, annee_reporting: int) -> None:
    derniere = int(ctx["job_try"]) >= MAX_TENTATIVES_EXTRACTION
    try:
        await asyncio.to_thread(_executer_extraction, rapport_id, annee_reporting, derniere)
    except ExtractionTransitoire as exc:
        raise Retry(defer=_delai(ctx)) from exc


async def send_email_job(
    ctx: dict[str, Any], recipient: str, subject: str, body: str, reply_to: str | None = None
) -> None:
    try:
        ensure_email_configured()
    except EmailDeliveryError:
        logger.error("email_abandonne_configuration_absente")
        return
    try:
        await asyncio.to_thread(
            send_email, recipient=recipient, subject=subject, body=body, reply_to=reply_to
        )
    except EmailDeliveryError as exc:
        # Jamais l'adresse, le sujet ni le corps dans les journaux (liens et jetons).
        if int(ctx["job_try"]) < MAX_TENTATIVES_EMAIL:
            logger.warning("email_envoi_reporte", tentative=ctx["job_try"])
            raise Retry(defer=_delai(ctx)) from exc
        logger.error("email_abandonne", error_type=type(exc.__cause__ or exc).__name__)


def _regenerer_synthese(rapport_id: uuid.UUID) -> None:
    with Session(engine) as session:
        rapport = session.get(ESGReport, rapport_id)
        if rapport is None:
            return
        synthesis_report.regenerer_synthese(session, rapport)


async def generate_synthesis_pdf(ctx: dict[str, Any], rapport_id: uuid.UUID) -> None:
    await asyncio.to_thread(_regenerer_synthese, rapport_id)


def _superviser() -> tuple[list[uuid.UUID], list[tuple[uuid.UUID, int]]]:
    with Session(engine) as session:
        echouees = supervision.echouer_extractions_bloquees(session)
        session.commit()
        return echouees, supervision.extractions_en_file(session)


async def reprendre_extractions(ctx: dict[str, Any]) -> None:
    """Tâche planifiée : extractions bloquées -> FAILED, jobs d'extraction perdus -> redéposés."""
    echouees, en_file = await asyncio.to_thread(_superviser)
    for rapport_id in echouees:
        logger.warning("extraction_bloquee_marquee_en_echec", rapport_id=str(rapport_id))
    for rapport_id, annee in en_file:
        await ctx["redis"].enqueue_job(
            "extract_report",
            rapport_id,
            annee,
            _job_id=f"extract:{rapport_id}",
            _queue_name=FILE_EXTRACTION,
        )
