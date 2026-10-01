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
from app.core.database import utcnow
from app.core.enums import (
    RegistrationStatus,
    ReportStatus,
    ReportType,
    SubmissionChannel,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier
from app.core.storage import resolve_path, save_bytes
from app.ingestion.models import ESGReport
from app.worker.queue import enfiler_extraction

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
            .order_by(col(ESGReport.created_at).desc())
        ).all()
    )


def _verifier_doublon(
    session: Session, entreprise_id: uuid.UUID, checksum: str, rapport_id: uuid.UUID
) -> None:
    # Le rapport lui-même est exclu : joindre de nouveau le même fichier à un brouillon (après un
    # échec d'analyse, tâche 5.8) n'est pas un doublon.
    existant = session.exec(
        select(ESGReport.id).where(
            ESGReport.company_id == entreprise_id,
            ESGReport.checksum_sha256 == checksum,
            col(ESGReport.id) != rapport_id,
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


def verifier_entreprise_active(entreprise: Company | None) -> None:
    """Seule une entreprise ACTIVE dépose ou ouvre une déclaration — une inscription en attente,
    en demande d'informations ou refusée (tâches 1.3, 5.2), ou une entreprise suspendue, ne le peut
    pas."""
    if entreprise is not None and entreprise.status in (
        RegistrationStatus.PENDING_ONBOARDING,
        RegistrationStatus.INFO_REQUESTED,
        RegistrationStatus.REJECTED,
    ):
        raise ValidationError(
            "L'inscription de cette entreprise n'est pas encore validée.",
            code="inscription_non_validee",
        )
    if entreprise is not None and entreprise.status != RegistrationStatus.ACTIVE:
        raise ValidationError("Cette entreprise est suspendue.", code="entreprise_suspendue")


# États qui ne retiennent plus l'entreprise (tâche 5.9) : décision rendue, ou extraction d'un dépôt
# direct en échec — l'Administrateur la relance, l'Entreprise peut déclarer à nouveau.
STATUTS_SANS_SESSION = (
    ReportStatus.VALIDATED,
    ReportStatus.REJECTED,
    ReportStatus.EXTRACTION_FAILED,
)


def verifier_regles_exercice(session: Session, entreprise_id: uuid.UUID, exercice: int) -> None:
    """Règles d'une nouvelle déclaration (tâche 5.9), communes à tous les chemins qui créent un
    rapport — ouverture d'un brouillon, dépôt en une étape, import par URL ; jamais une
    correction, qui poursuit la déclaration en cours :
    - une seule déclaration active à la fois (brouillon, examen, ou correction demandée et pas
      encore déposée) : la terminer avant d'ouvrir un autre exercice ;
    - un exercice déjà validé ne se déclare plus, quel que soit le type de rapport.
    La ligne de l'entreprise est verrouillée jusqu'au commit : deux ouvertures simultanées ne
    passent pas toutes les deux."""
    session.exec(select(Company).where(col(Company.id) == entreprise_id).with_for_update()).first()
    rapports = session.exec(
        select(ESGReport).where(col(ESGReport.company_id) == entreprise_id)
    ).all()
    remplaces = {r.previous_report_id for r in rapports if r.previous_report_id is not None}
    actif = next(
        (
            r
            for r in rapports
            if r.status not in STATUTS_SANS_SESSION and r.id not in remplaces
        ),
        None,
    )
    if actif is not None:
        raise ValidationError(
            f"Une déclaration est déjà en cours (exercice {actif.fiscal_year}) : terminez-la "
            "avant d'en ouvrir une autre.",
            code="declaration_en_cours",
        )
    if any(r.status == ReportStatus.VALIDATED and r.fiscal_year == exercice for r in rapports):
        raise ValidationError(
            f"L'exercice {exercice} a déjà été validé : il ne peut plus être déclaré.",
            code="exercice_deja_valide",
        )


def deposer_fichier(
    session: Session,
    background_tasks: BackgroundTasks,
    rapport: ESGReport,
    contenu: bytes,
    nom_fichier_origine: str | None,
    *,
    soumettre: bool = True,
) -> ESGReport:
    """Dépose le PDF d'un rapport — nouveau (dépôt en une étape) ou brouillon existant (tâche 5.8,
    POST /reports/{id}/file) — et le passe à l'extraction : validation du PDF, détection de
    doublon, stockage, statut EXTRACTING (job en file), un seul commit, puis extraction en tâche
    de fond. Point unique : les deux chemins de dépôt appliquent exactement les mêmes règles.

    `soumettre=False` (brouillon) : le rapport reste non soumis — l'extraction le ramène en DRAFT
    avec sa liste de complétude, et seule la soumission explicite le verrouille
    (app/reporting/sessions.py::soumettre)."""
    entreprise = session.get(Company, rapport.company_id)
    verifier_entreprise_active(entreprise)

    valider_pdf(contenu)
    checksum = calculer_checksum(contenu)
    _verifier_doublon(session, rapport.company_id, checksum, rapport.id)

    chemin_relatif = _enregistrer_fichier(rapport.company_id, rapport.id, contenu)
    rapport.source_file = chemin_relatif
    rapport.original_filename = nettoyer_nom_fichier(nom_fichier_origine)
    rapport.checksum_sha256 = checksum
    rapport.status = ReportStatus.EXTRACTING
    rapport.extraction_started_at = None
    rapport.extraction_finished_at = None
    rapport.extraction_error = None
    if soumettre:
        rapport.submitted_at = utcnow()
    try:
        session.add(rapport)
        if soumettre and entreprise is not None and entreprise.owner_user_id is not None:
            notifier(
                session,
                entreprise.owner_user_id,
                "RAPPORT_DEPOSE",
                f"Votre rapport {rapport.type.value} ({rapport.fiscal_year}) a bien été reçu et "
                "est en cours d'extraction.",
                id_ressource=rapport.id,
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
    assert rapport.fiscal_year is not None  # toujours fourni au dépôt comme à l'ouverture
    background_tasks.add_task(enfiler_extraction, rapport.id, rapport.fiscal_year)
    logger.info(
        "rapport_depose",
        rapport_id=str(rapport.id),
        version=rapport.version,
        entreprise_id=str(rapport.company_id),
    )
    return rapport


def _creer_rapport(
    session: Session,
    background_tasks: BackgroundTasks,
    *,
    entreprise_id: uuid.UUID,
    type_rapport: ReportType,
    annee_reporting: int,
    contenu: bytes,
    version: int,
    rapport_precedent_id: uuid.UUID | None,
    nom_fichier_origine: str | None,
    canal: SubmissionChannel = SubmissionChannel.ENTREPRISE,
) -> ESGReport:
    if rapport_precedent_id is None:
        # Nouvelle déclaration (pas une correction) : mêmes règles qu'une ouverture de brouillon.
        verifier_regles_exercice(session, entreprise_id, annee_reporting)
    rapport = ESGReport(
        company_id=entreprise_id,
        type=type_rapport,
        channel=canal,
        fiscal_year=annee_reporting,
        version=version,
        previous_report_id=rapport_precedent_id,
    )
    return deposer_fichier(session, background_tasks, rapport, contenu, nom_fichier_origine)


def deposer_rapport(
    session: Session,
    background_tasks: BackgroundTasks,
    entreprise_id: uuid.UUID,
    contenu: bytes,
    type_rapport: ReportType,
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
    type_rapport: ReportType,
    annee_reporting: int,
) -> ESGReport:
    """Canal d'import automatique (SubmissionChannel.AUTOMATIQUE) : le PDF est récupéré côté serveur
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
        canal=SubmissionChannel.AUTOMATIQUE,
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
