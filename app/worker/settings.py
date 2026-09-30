"""Configuration des deux workers ARQ (tâche 4.1).

    arq app.worker.settings.WorkerSettings            # e-mails, PDF de synthèse, tâche planifiée
    arq app.worker.settings.ExtractionWorkerSettings  # extractions Docling/LLM, une à la fois

keep_result=0 : aucun résultat conservé dans Redis — un job terminé libère aussitôt son
identifiant (une relance d'extraction après échec redépose le même `extract:{rapport_id}`), et
les arguments d'un e-mail (lien et jeton compris) ne restent pas stockés après l'envoi.
"""

import logging
from typing import Any, ClassVar

from arq import cron
from arq.worker import func

import app.core.registre_modeles  # noqa: F401 — relations entre modules, voir ce module
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.worker import jobs
from app.worker.queue import FILE_DEFAUT, FILE_EXTRACTION, parametres_redis


async def _au_demarrage(_ctx: dict[str, Any]) -> None:
    configure_logging(get_settings().environment)
    # ARQ journalise en INFO les arguments de chaque job (tronqués à 80 caractères) : pour un
    # e-mail, adresse et lien d'activation ou de réinitialisation, jeton compris. Seuls les
    # avertissements et échecs d'ARQ restent ; nos propres journaux n'en contiennent jamais.
    logging.getLogger("arq.worker").setLevel(logging.WARNING)
    logging.getLogger("arq.jobs").setLevel(logging.WARNING)


class WorkerSettings:
    queue_name = FILE_DEFAUT
    redis_settings = parametres_redis()
    on_startup = _au_demarrage
    max_jobs = 10
    functions: ClassVar[list[Any]] = [
        func(jobs.send_email_job, name="send_email", keep_result=0, max_tries=jobs.MAX_TENTATIVES_EMAIL),
        func(jobs.generate_synthesis_pdf, keep_result=0, max_tries=3),
    ]
    # Toutes les 5 minutes ; unique : un seul worker l'exécute si plusieurs tournent.
    cron_jobs: ClassVar[list[Any]] = [
        cron(jobs.reprendre_extractions, minute=set(range(0, 60, 5)), unique=True, run_at_startup=True),
    ]


class ExtractionWorkerSettings:
    queue_name = FILE_EXTRACTION
    redis_settings = parametres_redis()
    on_startup = _au_demarrage
    # Une extraction à la fois par worker (mémoire des modèles Docling / bge-m3) : remplace
    # l'ancien threading.Lock ; plus de débit = plus de conteneurs worker, pas plus de threads.
    max_jobs = 1
    functions: ClassVar[list[Any]] = [
        func(
            jobs.extract_report,
            keep_result=0,
            max_tries=jobs.MAX_TENTATIVES_EXTRACTION,
            # Au-delà, le job est interrompu ; la tâche planifiée le marquera `delai_depasse`.
            timeout=get_settings().extraction_timeout_minutes * 60,
        ),
    ]
