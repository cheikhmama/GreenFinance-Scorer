"""File de travaux ARQ (tâche 4.1) : jobs, reprises, tâche planifiée, dépôt après commit."""

import asyncio
import subprocess
import sys
import uuid
from datetime import timedelta

import pytest
from arq import Retry
from sqlmodel import select

from app.core.config import get_settings
from app.core.database import utcnow
from app.core.email import EmailDeliveryError, envoyer_email_differe
from app.core.enums import ExtractionStatus, ReportStatus, Role
from app.core.models import Notification
from app.ingestion import extractor
from app.ingestion.models import ESGReport
from app.worker import jobs, queue
from app.worker.settings import ExtractionWorkerSettings, WorkerSettings
from tests.integration.test_admin_router import (
    _create_entreprise_avec_utilisateur,
    _create_rapport,
    _create_rapport_en_validation,
    _create_utilisateur,
    _login,
)


def _executer(coroutine):
    return asyncio.run(coroutine)


def _relire(session, rapport_id: uuid.UUID) -> ESGReport:
    session.expire_all()
    rapport = session.get(ESGReport, rapport_id)
    assert rapport is not None
    return rapport


# --- pipeline : échec transitoire ou définitif -------------------------------------------------


def _pipeline_qui_echoue(monkeypatch, erreur: Exception) -> None:
    def _lever():
        raise erreur

    monkeypatch.setattr(extractor, "_get_embed_model", _lever)


def test_echec_transitoire_remis_en_file_puis_definitif_a_la_derniere_tentative(
    session, monkeypatch
) -> None:
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(
        session, entreprise.id, extraction_status=ExtractionStatus.QUEUED, fiscal_year=2024
    )
    _pipeline_qui_echoue(monkeypatch, ConnectionError("réseau"))

    with pytest.raises(extractor.ExtractionTransitoire):
        extractor.run_extraction_pipeline(rapport.id, 2024, derniere_tentative=False)
    remis_en_file = _relire(session, rapport.id)
    assert remis_en_file.extraction_status == ExtractionStatus.QUEUED
    assert remis_en_file.extraction_attempts == 0

    extractor.run_extraction_pipeline(rapport.id, 2024, derniere_tentative=True)
    echoue = _relire(session, rapport.id)
    assert echoue.extraction_status == ExtractionStatus.FAILED
    assert echoue.extraction_error == "chargement_modele_embedding_echoue"
    assert echoue.extraction_attempts == 1


def test_erreur_non_transitoire_jamais_retentee(session, monkeypatch) -> None:
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(
        session, entreprise.id, extraction_status=ExtractionStatus.QUEUED, fiscal_year=2024
    )
    _pipeline_qui_echoue(monkeypatch, ValueError("PDF corrompu"))

    extractor.run_extraction_pipeline(rapport.id, 2024, derniere_tentative=False)

    assert _relire(session, rapport.id).extraction_status == ExtractionStatus.FAILED


# --- jobs ---------------------------------------------------------------------------------------


def test_job_extraction_retente_avec_delai_croissant(monkeypatch) -> None:
    appels: list[bool] = []

    def _pipeline(_rapport_id, _annee, derniere_tentative: bool) -> None:
        appels.append(derniere_tentative)
        if not derniere_tentative:
            raise extractor.ExtractionTransitoire("appel_llm_echoue")

    monkeypatch.setattr(jobs, "_executer_extraction", _pipeline)
    rapport_id = uuid.uuid4()

    with pytest.raises(Retry) as premiere:
        _executer(jobs.extract_report({"job_try": 1}, rapport_id, 2024))
    with pytest.raises(Retry) as deuxieme:
        _executer(jobs.extract_report({"job_try": 2}, rapport_id, 2024))
    _executer(jobs.extract_report({"job_try": jobs.MAX_TENTATIVES_EXTRACTION}, rapport_id, 2024))

    assert (premiere.value.defer_score, deuxieme.value.defer_score) == (60_000, 120_000)
    assert appels == [False, False, True]  # la dernière tentative marque l'échec, jamais de Retry


def test_job_email_retente_puis_abandonne(monkeypatch) -> None:
    envois: list[str] = []

    def _smtp_en_panne(**kwargs) -> None:
        envois.append(kwargs["recipient"])
        raise EmailDeliveryError("SMTP")

    monkeypatch.setattr(jobs, "ensure_email_configured", lambda: None)
    monkeypatch.setattr(jobs, "send_email", _smtp_en_panne)

    with pytest.raises(Retry):
        _executer(jobs.send_email_job({"job_try": 1}, "a@example.com", "Sujet", "Corps"))
    _executer(jobs.send_email_job({"job_try": jobs.MAX_TENTATIVES_EMAIL}, "a@example.com", "S", "C"))

    assert envois == ["a@example.com", "a@example.com"]


def test_job_email_sans_configuration_abandonne_sans_retenter(monkeypatch) -> None:
    def _non_configure():
        raise EmailDeliveryError("Serveur SMTP non configuré.")

    envois: list[str] = []
    monkeypatch.setattr(jobs, "ensure_email_configured", _non_configure)
    monkeypatch.setattr(jobs, "send_email", lambda **kwargs: envois.append(kwargs["recipient"]))

    _executer(jobs.send_email_job({"job_try": 1}, "a@example.com", "Sujet", "Corps"))

    assert envois == []


def test_job_synthese_ecrit_le_pdf(session, monkeypatch) -> None:
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(session, entreprise.id)
    monkeypatch.setattr(
        "app.ingestion.synthesis_report.generer_rapport_synthese", lambda _s, _r: b"%PDF-1.4"
    )

    _executer(jobs.generate_synthesis_pdf({}, rapport.id))

    assert _relire(session, rapport.id).synthesis_report_path == f"synthese/{rapport.id}.pdf"


# --- tâche planifiée ------------------------------------------------------------------------------


class _RedisEnregistreur:
    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    async def enqueue_job(self, fonction, *args, _job_id=None, _queue_name=None):
        self.jobs.append((fonction, args, _job_id, _queue_name))


def test_tache_planifiee_echoue_les_bloquees_et_redepose_les_jobs_perdus(session) -> None:
    entreprise, proprietaire = _create_entreprise_avec_utilisateur(session)
    delai = timedelta(minutes=get_settings().extraction_timeout_minutes + 1)
    bloque = _create_rapport(
        session, entreprise.id, extraction_status=ExtractionStatus.RUNNING,
        extraction_started_at=utcnow() - delai, fiscal_year=2024,
    )
    en_cours = _create_rapport(
        session, entreprise.id, extraction_status=ExtractionStatus.RUNNING,
        extraction_started_at=utcnow(), fiscal_year=2023,
    )
    perdu = _create_rapport(
        session, entreprise.id, extraction_status=ExtractionStatus.QUEUED, fiscal_year=2022
    )
    redis = _RedisEnregistreur()

    _executer(jobs.reprendre_extractions({"redis": redis}))

    assert _relire(session, bloque.id).extraction_status == ExtractionStatus.FAILED
    assert _relire(session, bloque.id).extraction_error == "delai_depasse"
    assert _relire(session, en_cours.id).extraction_status == ExtractionStatus.RUNNING
    assert ("extract_report", (perdu.id, 2022), f"extract:{perdu.id}", "arq:extraction") in redis.jobs
    notifications = session.exec(
        select(Notification).where(Notification.utilisateur_id == proprietaire.id)
    ).all()
    assert any(n.type == "RAPPORT_EXTRACTION_ECHOUEE" for n in notifications)


# --- dépôt côté API ----------------------------------------------------------------------------


def test_redis_indisponible_devient_une_erreur_d_envoi(monkeypatch) -> None:
    async def _hors_ligne(*_args) -> bool:
        raise ConnectionError("redis")

    monkeypatch.setattr(queue, "_envoyer_a_redis", _hors_ligne)

    with pytest.raises(queue.FileIndisponible):
        queue.enfiler("send_email", "a@example.com")
    with pytest.raises(EmailDeliveryError):
        envoyer_email_differe(recipient="a@example.com", subject="S", body="C")


def test_adresse_invalide_jamais_mise_en_file(jobs_enfiles) -> None:
    with pytest.raises(EmailDeliveryError):
        envoyer_email_differe(recipient="pas-une-adresse", subject="S", body="C")

    envoyer_email_differe(recipient="ok@example.com", subject="S", body="C")

    assert [depot[0] for depot in jobs_enfiles] == ["send_email"]


def test_validation_programme_la_synthese_et_relance_programme_l_extraction(
    session, jobs_enfiles
) -> None:
    admin = _login(_create_utilisateur(session, Role.ADMIN).email, "s3cret-pass")
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    en_validation = _create_rapport_en_validation(session, entreprise.id, auditeur.id)
    en_echec = _create_rapport(
        session, entreprise.id, extraction_status=ExtractionStatus.FAILED, fiscal_year=2024,
        extraction_error="appel_llm_echoue",
    )
    en_cours = _create_rapport(
        session, entreprise.id, extraction_status=ExtractionStatus.RUNNING,
        extraction_started_at=utcnow() - timedelta(days=2), fiscal_year=2023,
    )

    valide = admin.post(f"/api/v1/admin/rapports/{en_validation.id}/valider", json={})
    relance = admin.post(f"/api/v1/admin/rapports/{en_echec.id}/relancer-extraction")
    refus = admin.post(f"/api/v1/admin/rapports/{en_cours.id}/relancer-extraction")

    assert valide.status_code == 200 and valide.json()["statut"] == ReportStatus.VALIDATED.value
    assert relance.status_code == 200
    # Une extraction encore RUNNING n'est plus relancée à la main : la tâche planifiée la passe
    # d'abord en échec (`delai_depasse`).
    assert refus.status_code == 422 and refus.json()["error"]["code"] == "relance_impossible"
    assert ("generate_synthesis_pdf", (en_validation.id,), None, "arq:queue") in jobs_enfiles
    assert (
        "extract_report", (en_echec.id, 2024), f"extract:{en_echec.id}", "arq:extraction"
    ) in jobs_enfiles


# --- configuration des workers ------------------------------------------------------------------


def test_workers_declarent_leurs_jobs_sur_des_files_separees() -> None:
    assert WorkerSettings.queue_name != ExtractionWorkerSettings.queue_name
    assert ExtractionWorkerSettings.max_jobs == 1
    assert {f.name for f in WorkerSettings.functions} == {"send_email", "generate_synthesis_pdf"}
    assert {f.name for f in ExtractionWorkerSettings.functions} == {"extract_report"}
    assert all(f.keep_result_s == 0 for f in [*WorkerSettings.functions, *ExtractionWorkerSettings.functions])


def test_ni_l_api_ni_le_worker_par_defaut_ne_chargent_la_pile_d_extraction() -> None:
    """Docling, torch et bge-m3 ne vivent que dans le worker d'extraction : l'API et le worker par
    défaut tournent sur l'image légère (tâche 4.2), sans ces dépendances."""
    code = (
        "import sys, app.main, app.worker.settings; "
        "print(sorted(m for m in ('torch', 'torchvision', 'docling', 'FlagEmbedding', 'faiss', "
        "'paddle', 'paddleocr', 'google.genai', 'app.ingestion.extractor') if m in sys.modules))"
    )
    sortie = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert sortie.stdout.strip() == "[]"


def test_le_worker_ne_journalise_pas_les_arguments_des_jobs() -> None:
    """Liens d'activation et de réinitialisation (jetons) : jamais dans les journaux du worker."""
    import logging

    from app.worker.settings import _au_demarrage

    _executer(_au_demarrage({}))

    # Niveau propre du logger (isEnabledFor dépend aussi d'un logging.disable global éventuel).
    for nom in ("arq.worker", "arq.jobs"):
        assert logging.getLogger(nom).getEffectiveLevel() == logging.WARNING
