"""Routes HTTP de l'espace Auditeur.

Statut : Étape 11 + Phase 4 §4.5 (historique). Consultation des dossiers assignés, soumission
d'un avis et historique des avis déjà rendus — la logique d'état vit dans
app/audit/opinion.py, ce router ne fait qu'appliquer le contrôle d'accès par rôle et
appeler cette logique.
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlmodel import Session, col, select

from app.audit.models import AvisAudit
from app.audit.opinion import soumettre_avis
from app.audit.preuves import fichier_preuve
from app.audit.schemas import AvisAuditAdmin, SoumettreAvisRequest
from app.auth.models import Utilisateur
from app.auth.permissions import require_role
from app.core import storage
from app.core.dependencies import get_session
from app.core.enums import Role, StatutRapport
from app.core.exceptions import NotFoundError
from app.ingestion.models import RapportESG
from app.ingestion.schemas import RapportESGDetail, RapportESGPublic
from app.scoring.engine import score_public

router = APIRouter(tags=["audit"])


@router.get(
    "/audit/rapports",
    response_model=list[RapportESGPublic],
    operation_id="listAssignedReports",
    summary="Lister les dossiers affectés à l'auditeur, en attente d'avis",
)
def lister_mes_dossiers(
    current_user: Utilisateur = Depends(require_role(Role.AUDITEUR)),
    session: Session = Depends(get_session),
) -> list[RapportESG]:
    return list(
        session.exec(
            select(RapportESG).where(
                RapportESG.auditeur_id == current_user.id,
                RapportESG.statut == StatutRapport.AFFECTE_AUDITEUR,
            )
        ).all()
    )


@router.get(
    "/audit/rapports/{rapport_id}",
    response_model=RapportESGDetail,
    operation_id="getAssignedReport",
    summary="Consulter le détail d'un dossier affecté à l'auditeur",
)
def consulter_dossier(
    rapport_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.AUDITEUR)),
    session: Session = Depends(get_session),
) -> RapportESGDetail:
    rapport = session.get(RapportESG, rapport_id)
    # Pas de restriction de statut ici (contrairement à la liste ci-dessus) : un auditeur peut
    # rouvrir un dossier sur lequel il a déjà rendu un avis.
    if rapport is None or rapport.auditeur_id != current_user.id:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    detail = RapportESGDetail.model_validate(rapport)
    return detail.model_copy(update={"score_officiel": score_public(session, rapport_id)})


@router.get(
    "/audit/rapports/{rapport_id}/preuves/{preuve_id}/fichier",
    operation_id="getEvidenceFileForAudit",
    summary="Consulter l'extrait PDF (une page) prouvant un indicateur ou une donnée carbone",
)
def consulter_preuve_route(
    rapport_id: uuid.UUID,
    preuve_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.AUDITEUR)),
    session: Session = Depends(get_session),
) -> FileResponse:
    chemin = fichier_preuve(session, rapport_id, preuve_id, current_user.id)
    return FileResponse(storage.resolve_path(chemin), media_type="application/pdf")


@router.get(
    "/audit/historique",
    response_model=list[AvisAuditAdmin],
    operation_id="listMyAuditOpinions",
    summary="Lister l'historique des avis déjà rendus par l'auditeur",
)
def lister_historique_route(
    current_user: Utilisateur = Depends(require_role(Role.AUDITEUR)),
    session: Session = Depends(get_session),
) -> list[AvisAudit]:
    return list(
        session.exec(
            select(AvisAudit)
            .where(AvisAudit.auditeur_id == current_user.id)
            .order_by(col(AvisAudit.date_avis).desc())
        ).all()
    )


@router.post(
    "/audit/rapports/{rapport_id}/avis",
    response_model=AvisAuditAdmin,
    status_code=201,
    operation_id="submitAuditOpinion",
    summary="Soumettre un avis d'audit sur un dossier affecté",
)
def soumettre_avis_route(
    rapport_id: uuid.UUID,
    payload: SoumettreAvisRequest,
    current_user: Utilisateur = Depends(require_role(Role.AUDITEUR)),
    session: Session = Depends(get_session),
) -> AvisAudit:
    return soumettre_avis(
        session, rapport_id, current_user.id, payload.decision, payload.commentaire
    )
