"""Mise en file des travaux de fond (tâche 4.1, docs/ARCHITECTURE.md §6) — côté API.

L'API ne fait plus aucun travail lourd ni envoi SMTP elle-même : elle dépose un job ARQ dans Redis,
exécuté par un worker (app/worker/settings.py). Deux files :
- FILE_EXTRACTION : l'extraction Docling/LLM, un seul job à la fois par worker (mémoire, GPU) —
  remplace l'ancien threading.Lock ;
- FILE_DEFAUT : e-mails et PDF de synthèse, qui n'attendent jamais derrière une extraction.

Toujours APRÈS le commit de la transaction qui a créé l'état à traiter : via BackgroundTasks
(exécuté après l'envoi de la réponse) dans une requête, ou juste après session.commit() ailleurs.
Un worker ne lit donc jamais un état pas encore commité.

Identifiant de job déterministe quand un doublon serait nuisible (`extract:{rapport_id}`) : ARQ
refuse un second job du même identifiant tant que le premier existe — une double soumission ne
lance jamais deux extractions.
"""

import asyncio
from typing import Any

import structlog
from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

FILE_DEFAUT = "arq:queue"
FILE_EXTRACTION = "arq:extraction"


class FileIndisponible(Exception):
    """Redis injoignable : le job n'a pas pu être déposé."""


def parametres_redis() -> RedisSettings:
    parametres = RedisSettings.from_dsn(get_settings().redis_url)
    # Échouer vite plutôt que de bloquer une requête ou une tâche post-réponse : un job perdu
    # d'extraction est repris par la tâche planifiée (app/worker/jobs.py::reprendre_extractions).
    parametres.conn_retries = 1
    return parametres


async def _envoyer_a_redis(
    fonction: str, args: tuple[Any, ...], job_id: str | None, file: str
) -> bool:
    pool = await create_pool(parametres_redis())
    try:
        job = await pool.enqueue_job(fonction, *args, _job_id=job_id, _queue_name=file)
    finally:
        await pool.aclose()
    return job is not None


def enfiler(fonction: str, *args: Any, job_id: str | None = None, file: str = FILE_DEFAUT) -> bool:
    """Dépose un job (synchrone, pour le code synchrone de l'API). True si déposé, False si un job
    de même identifiant existe déjà (doublon ignoré). FileIndisponible si Redis ne répond pas."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:  # pragma: no cover — garde-fou de conception, aucune route asynchrone n'enfile
        raise RuntimeError("enfiler() est synchrone : utiliser _envoyer_a_redis depuis du code async.")
    try:
        depose = asyncio.run(_envoyer_a_redis(fonction, args, job_id, file))
    except (OSError, ConnectionError) as exc:
        raise FileIndisponible(fonction) from exc
    except Exception as exc:  # redis.exceptions.* n'héritent pas toutes d'OSError
        if type(exc).__module__.startswith("redis"):
            raise FileIndisponible(fonction) from exc
        raise
    if not depose:
        logger.info("job_deja_en_file", fonction=fonction, job_id=job_id)
    return depose


def enfiler_extraction(rapport_id: Any, annee_reporting: int) -> bool:
    return enfiler(
        "extract_report",
        rapport_id,
        annee_reporting,
        job_id=f"extract:{rapport_id}",
        file=FILE_EXTRACTION,
    )
