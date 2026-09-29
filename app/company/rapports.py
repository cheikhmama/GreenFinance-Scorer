"""Logique métier de l'espace Entreprise sur les rapports — liste, dépôt, nouvelle version.

app/company/router.py ne fait qu'appliquer le contrôle d'accès par rôle et appeler cette
logique (même convention que app/admin/review_queue.py).
"""

import uuid

import structlog
from fastapi import BackgroundTasks
from sqlmodel import Session, col, select

from app.company.models import Company
from app.company.upload_validation import (
    calculer_checksum,
    nettoyer_nom_fichier,
    valider_pdf,
)
from app.company.url_fetch import telecharger_pdf_depuis_url
from app.core.enums import (
    CanalDepot,
    CompanyStatus,
    ExtractionStatus,
    ReportStatus,
    TypeRapport,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier
from app.core.storage import resolve_path, save_bytes
from app.ingestion.extractor import run_extraction_pipeline
from app.ingestion.models import ESGReport

logger = structlog.get_logger(__name__)


def rapport_de_lentreprise(
    session: Session, rapport_id: uuid.UUID, entreprise_id: uuid.UUID
) -> ESGReport:
    """Garde-fou de propriété partagé par toutes les routes de app/company/router.py qui lisent
    un rapport précis (détail, téléchargement du fichier original, téléchargement du PDF de
    synthèse) -- même 404 que le rapport n'existe pas ou appartienne à une autre entreprise,
    jamais de 403, pour ne pas confirmer l'existence d'un rapport_id d'autrui."""
    rapport = session.get(ESGReport, rapport_id)
    if rapport is None or rapport.company_id != entreprise_id:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    return rapport


def lister_mes_rapports(session: Session, entreprise_id: uuid.UUID) -> list[ESGReport]:
    return list(
        session.exec(
            select(ESGReport)
            .where(ESGReport.company_id == entreprise_id)
            .order_by(col(ESGReport.submitted_at).desc())
        ).all()
    )


def _verifier_doublon(session: Session, entreprise_id: uuid.UUID, checksum: str) -> None:
    existant = session.exec(
        select(ESGReport.id).where(
            ESGReport.company_id == entreprise_id,
            ESGReport.checksum_sha256 == checksum,
        )
    ).first()
    if existant is not None:
        raise ValidationError("Ce fichier a déjà été déposé.", code="doublon_detecte")


def _enregistrer_fichier(entreprise_id: uuid.UUID, rapport_id: uuid.UUID, contenu: bytes) -> str:
    # Nom de stockage entièrement déterminé par le serveur (Phase 4 §4.2) — jamais dérivé du nom
    # fourni par le client, même après assainissement : le répertoire et le nom de fichier ne
    # viennent que d'identifiants déjà connus côté serveur.
    chemin_relatif = f"rapports/{entreprise_id}/{rapport_id}.pdf"
    try:
        save_bytes(chemin_relatif, contenu)
    except OSError as exc:
        raise ValidationError(
            "Le fichier n'a pas pu être enregistré. Réessayez.", code="stockage_echoue"
        ) from exc
    return chemin_relatif


def _creer_rapport(
    session: Session,
    background_tasks: BackgroundTasks,
    *,
    entreprise_id: uuid.UUID,
    type_rapport: TypeRapport,
    annee_reporting: int,
    contenu: bytes,
    version: int,
    rapport_precedent_id: uuid.UUID | None,
    nom_fichier_origine: str | None,
    canal: CanalDepot = CanalDepot.ENTREPRISE,
) -> ESGReport:
    entreprise = session.get(Company, entreprise_id)
    if entreprise is not None and entreprise.status != CompanyStatus.ACTIVE:
        raise ValidationError("Cette entreprise est suspendue.", code="entreprise_suspendue")

    valider_pdf(contenu)
    checksum = calculer_checksum(contenu)
    _verifier_doublon(session, entreprise_id, checksum)

    rapport_id = uuid.uuid4()
    chemin_relatif = _enregistrer_fichier(entreprise_id, rapport_id, contenu)

    rapport = ESGReport(
        id=rapport_id,
        company_id=entreprise_id,
        type=type_rapport,
        channel=canal,
        status=ReportStatus.SUBMITTED,
        extraction_status=ExtractionStatus.QUEUED,
        source_file=chemin_relatif,
        original_filename=nettoyer_nom_fichier(nom_fichier_origine),
        fiscal_year=annee_reporting,
        checksum_sha256=checksum,
        version=version,
        previous_report_id=rapport_precedent_id,
    )
    try:
        session.add(rapport)
        if entreprise is not None and entreprise.owner_user_id is not None:
            notifier(
                session,
                entreprise.owner_user_id,
                "RAPPORT_DEPOSE",
                f"Votre rapport {type_rapport.value} ({annee_reporting}) a bien été reçu et est "
                "en cours d'extraction.",
                id_ressource=rapport_id,
            )
        session.commit()
    except Exception:
        # Transaction compensatoire (Phase 4 §4.2) : le fichier est déjà sur disque, l'insertion
        # DB a échoué — pas de ligne orpheline en base, mais un fichier orphelin serait sans
        # conséquence fonctionnelle ; on nettoie quand même plutôt que de laisser trainer.
        session.rollback()
        resolve_path(chemin_relatif).unlink(missing_ok=True)
        raise
    session.refresh(rapport)

    # Le passage QUEUED -> RUNNING se fait DANS run_extraction_pipeline, pas ici : le statut
    # d'extraction doit refléter que l'extraction a réellement démarré, pas seulement été demandée.
    background_tasks.add_task(run_extraction_pipeline, rapport_id, annee_reporting)
    logger.info(
        "rapport_depose", rapport_id=str(rapport_id), version=version, entreprise_id=str(entreprise_id)
    )
    return rapport


def deposer_rapport(
    session: Session,
    background_tasks: BackgroundTasks,
    entreprise_id: uuid.UUID,
    contenu: bytes,
    type_rapport: TypeRapport,
    annee_reporting: int,
    nom_fichier_origine: str | None,
) -> ESGReport:
    return _creer_rapport(
        session,
        background_tasks,
        entreprise_id=entreprise_id,
        type_rapport=type_rapport,
        annee_reporting=annee_reporting,
        contenu=contenu,
        version=1,
        rapport_precedent_id=None,
        nom_fichier_origine=nom_fichier_origine,
    )


def importer_rapport_par_url(
    session: Session,
    background_tasks: BackgroundTasks,
    entreprise_id: uuid.UUID,
    url: str,
    type_rapport: TypeRapport,
    annee_reporting: int,
) -> ESGReport:
    """Canal d'import automatique (CanalDepot.AUTOMATIQUE) : le PDF est récupéré côté serveur
    depuis une URL plutôt que reçu en multipart, mais rejoint ensuite exactement le même chemin
    que deposer_rapport (checksum, dédoublonnage, validation PDF, stockage, extraction en tâche
    de fond) -- seule la provenance du contenu change. La récupération elle-même (résolution DNS,
    garde-fous anti-SSRF, plafond de taille en flux) vit dans app/company/url_fetch.py, jamais
    ici : ce module orchestre, il ne refait pas la validation réseau."""
    contenu = telecharger_pdf_depuis_url(url)
    return _creer_rapport(
        session,
        background_tasks,
        entreprise_id=entreprise_id,
        type_rapport=type_rapport,
        annee_reporting=annee_reporting,
        contenu=contenu,
        version=1,
        rapport_precedent_id=None,
        nom_fichier_origine=None,
        canal=CanalDepot.AUTOMATIQUE,
    )


def creer_correction(
    session: Session,
    background_tasks: BackgroundTasks,
    rapport_precedent_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    contenu: bytes,
    annee_reporting: int,
    nom_fichier_origine: str | None,
) -> ESGReport:
    """Dépose une nouvelle version en réponse à une demande de correction. Le rapport précédent
    n'est jamais modifié — il reste REVISION_REQUESTED indéfiniment, seule une nouvelle ligne
    liée est créée (voir app/ingestion/models.py::ESGReport, principe déjà acté en Phase 0)."""
    precedent = session.get(ESGReport, rapport_precedent_id)
    if precedent is None or precedent.company_id != entreprise_id:
        # Même code que l'entreprise soit inconnue ou que le rapport appartienne à une autre —
        # jamais de 403 ici, pour ne pas confirmer l'existence d'un rapport_id d'autrui.
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    if precedent.status != ReportStatus.REVISION_REQUESTED:
        raise ValidationError(
            "Ce rapport n'est pas en attente de correction.", code="transition_invalide"
        )

    return _creer_rapport(
        session,
        background_tasks,
        entreprise_id=entreprise_id,
        type_rapport=precedent.type,
        annee_reporting=annee_reporting,
        contenu=contenu,
        version=precedent.version + 1,
        rapport_precedent_id=precedent.id,
        nom_fichier_origine=nom_fichier_origine,
    )
