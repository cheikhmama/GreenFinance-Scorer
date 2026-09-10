"""Logique métier de l'espace Entreprise sur les rapports — liste, dépôt, nouvelle version.

app/company/router.py ne fait qu'appliquer le contrôle d'accès par rôle et appeler cette
logique (même convention que app/admin/review_queue.py).
"""

import uuid

import structlog
from fastapi import BackgroundTasks
from sqlmodel import Session, col, select

from app.company.models import Entreprise
from app.company.upload_validation import calculer_checksum, valider_pdf
from app.core.enums import CanalDepot, StatutRapport, TypeRapport
from app.core.exceptions import NotFoundError, ValidationError
from app.core.storage import resolve_path, save_bytes
from app.ingestion.extractor import run_extraction_pipeline
from app.ingestion.models import RapportESG

logger = structlog.get_logger(__name__)


def lister_mes_rapports(session: Session, entreprise_id: uuid.UUID) -> list[RapportESG]:
    return list(
        session.exec(
            select(RapportESG)
            .where(RapportESG.entreprise_id == entreprise_id)
            .order_by(col(RapportESG.date_depot).desc())
        ).all()
    )


def _verifier_doublon(session: Session, entreprise_id: uuid.UUID, checksum: str) -> None:
    existant = session.exec(
        select(RapportESG.id).where(
            RapportESG.entreprise_id == entreprise_id,
            RapportESG.checksum_sha256 == checksum,
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
) -> RapportESG:
    entreprise = session.get(Entreprise, entreprise_id)
    if entreprise is not None and not entreprise.actif:
        raise ValidationError("Cette entreprise est suspendue.", code="entreprise_suspendue")

    valider_pdf(contenu)
    checksum = calculer_checksum(contenu)
    _verifier_doublon(session, entreprise_id, checksum)

    rapport_id = uuid.uuid4()
    chemin_relatif = _enregistrer_fichier(entreprise_id, rapport_id, contenu)

    rapport = RapportESG(
        id=rapport_id,
        entreprise_id=entreprise_id,
        type=type_rapport,
        canal=CanalDepot.ENTREPRISE,
        statut=StatutRapport.ENVOYE,
        fichier_source=chemin_relatif,
        annee_reporting=annee_reporting,
        checksum_sha256=checksum,
        version=version,
        rapport_precedent_id=rapport_precedent_id,
    )
    try:
        session.add(rapport)
        session.commit()
    except Exception:
        # Transaction compensatoire (Phase 4 §4.2) : le fichier est déjà sur disque, l'insertion
        # DB a échoué — pas de ligne orpheline en base, mais un fichier orphelin serait sans
        # conséquence fonctionnelle ; on nettoie quand même plutôt que de laisser trainer.
        session.rollback()
        resolve_path(chemin_relatif).unlink(missing_ok=True)
        raise
    session.refresh(rapport)

    # La transition ENVOYE -> EN_EXTRACTION se fait DANS run_extraction_pipeline, pas ici : le
    # statut doit refléter que l'extraction a réellement démarré, pas seulement été demandée.
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
) -> RapportESG:
    return _creer_rapport(
        session,
        background_tasks,
        entreprise_id=entreprise_id,
        type_rapport=type_rapport,
        annee_reporting=annee_reporting,
        contenu=contenu,
        version=1,
        rapport_precedent_id=None,
    )


def creer_correction(
    session: Session,
    background_tasks: BackgroundTasks,
    rapport_precedent_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    contenu: bytes,
    annee_reporting: int,
) -> RapportESG:
    """Dépose une nouvelle version en réponse à une demande de correction. Le rapport précédent
    n'est jamais modifié — il reste DEMANDE_CORRECTION indéfiniment, seule une nouvelle ligne
    liée est créée (voir app/ingestion/models.py::RapportESG, principe déjà acté en Phase 0)."""
    precedent = session.get(RapportESG, rapport_precedent_id)
    if precedent is None or precedent.entreprise_id != entreprise_id:
        # Même code que l'entreprise soit inconnue ou que le rapport appartienne à une autre —
        # jamais de 403 ici, pour ne pas confirmer l'existence d'un rapport_id d'autrui.
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    if precedent.statut != StatutRapport.DEMANDE_CORRECTION:
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
    )
