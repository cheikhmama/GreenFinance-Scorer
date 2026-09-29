"""Avis d'audit rendus sur les dossiers d'entreprise.

Structure et persiste les avis d'audit (validation, réserves) — la décision finale (valider,
rejeter, demander correction) reste une action Administrateur (app/admin/review_queue.py), l'avis
ici n'est qu'une recommandation.
"""

import uuid

import structlog
from sqlmodel import Session, col, select

from app.audit.models import AvisAudit
from app.auth.models import Utilisateur
from app.core.enums import DecisionAudit, ReportStatus, Role
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier
from app.ingestion.models import ESGReport

logger = structlog.get_logger(__name__)

_LIBELLES_DECISION = {
    DecisionAudit.RECOMMANDE_VALIDATION: "recommande la validation",
    DecisionAudit.RECOMMANDE_REJET: "recommande le rejet",
    DecisionAudit.DEMANDE_CLARIFICATION: "demande une clarification",
}


def soumettre_avis(
    session: Session,
    rapport_id: uuid.UUID,
    auditeur_id: uuid.UUID,
    decision: DecisionAudit,
    commentaire: str | None,
) -> AvisAudit:
    rapport = session.get(ESGReport, rapport_id)
    # Même règle de non-divulgation que company/router.py::consulter_rapport : un rapport
    # inexistant et un rapport affecté à un autre auditeur rendent la même erreur, jamais un 403
    # qui confirmerait l'existence du rapport_id à quelqu'un à qui il n'est pas affecté.
    if rapport is None or rapport.auditor_id != auditeur_id:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    if rapport.status != ReportStatus.PENDING_AUDIT:
        raise ValidationError(
            "Un avis a déjà été soumis pour ce rapport.", code="avis_deja_soumis"
        )

    avis = AvisAudit(
        rapport_id=rapport_id,
        auditeur_id=auditeur_id,
        decision=decision,
        commentaire=commentaire,
    )
    session.add(avis)

    rapport.status = ReportStatus.PENDING_DECISION
    session.add(rapport)

    if rapport.company.owner_user_id is not None:
        notifier(
            session,
            rapport.company.owner_user_id,
            "RAPPORT_AVIS_RENDU_ENTREPRISE",
            f"L'examen de votre rapport {rapport.type.value} ({rapport.fiscal_year}) est "
            "terminé, en attente de décision finale.",
            id_ressource=rapport_id,
        )

    admins = session.exec(
        select(Utilisateur).where(
            col(Utilisateur.role) == Role.ADMINISTRATEUR, col(Utilisateur.actif).is_(True)
        )
    ).all()
    for admin in admins:
        notifier(
            session,
            admin.id,
            "RAPPORT_AVIS_RENDU_ADMIN",
            f"L'auditeur {_LIBELLES_DECISION[decision]} pour le rapport "
            f"{rapport.type.value} ({rapport.fiscal_year}) de {rapport.company.name}.",
            id_ressource=rapport_id,
        )

    session.commit()
    session.refresh(avis)
    logger.info("avis_audit_soumis", rapport_id=str(rapport_id), auditeur_id=str(auditeur_id))
    return avis
