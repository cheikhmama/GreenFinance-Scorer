"""Affectation des dossiers d'entreprise aux auditeurs.

Appelé depuis app/admin/router.py (c'est l'Administrateur qui déclenche l'affectation), mais la
mutation elle-même vit ici — app/audit/ possède l'attribution des dossiers, l'admin invoque cette
interface plutôt que de réimplémenter localement la transition (voir ARCHITECTURE.md §1).
"""

import uuid

import structlog
from sqlmodel import Session

from app.auth.models import Utilisateur
from app.core.database import utcnow
from app.core.enums import Role, StatutRapport
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier
from app.ingestion.models import RapportESG

logger = structlog.get_logger(__name__)


def affecter_auditeur(session: Session, rapport_id: uuid.UUID, auditeur_id: uuid.UUID) -> RapportESG:
    rapport = session.get(RapportESG, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    if rapport.statut != StatutRapport.EN_EXTRACTION:
        raise ValidationError(
            "Ce rapport n'est pas en attente d'affectation.", code="rapport_deja_affecte"
        )
    if rapport.extraction_terminee_le is None:
        raise ValidationError(
            "L'extraction de ce rapport n'est pas terminée.", code="extraction_non_terminee"
        )

    auditeur = session.get(Utilisateur, auditeur_id)
    if auditeur is None or auditeur.role != Role.AUDITEUR or not auditeur.actif:
        raise ValidationError("Auditeur invalide.", code="auditeur_invalide")

    rapport.auditeur_id = auditeur.id
    rapport.statut = StatutRapport.AFFECTE_AUDITEUR
    rapport.date_affectation = utcnow()
    session.add(rapport)

    notifier(
        session,
        auditeur.id,
        "RAPPORT_AFFECTE",
        f"Un dossier ({rapport.fichier_source}) vous a été affecté pour audit.",
    )
    if rapport.entreprise.utilisateur_id is not None:
        notifier(
            session,
            rapport.entreprise.utilisateur_id,
            "RAPPORT_AFFECTE",
            "Votre rapport a été affecté à un auditeur.",
        )

    session.commit()
    session.refresh(rapport)
    logger.info(
        "rapport_affecte_auditeur", rapport_id=str(rapport_id), auditeur_id=str(auditeur_id)
    )
    return rapport
