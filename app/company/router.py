"""Routes HTTP de l'espace Entreprise.

Statut : Étape 5/10 + Phase 4 §4.1/§4.2. Dépôt, liste, détail, nouvelle version (correction) —
la logique vit dans app/company/rapports.py (et app/company/upload_validation.py pour la
validation du fichier), ce router ne fait qu'appliquer le contrôle d'accès par rôle et l'appeler.

app/ingestion/ n'expose pas de router.py (voir ARCHITECTURE.md §2 : ingestion n'est pas une
surface API directe) — la logique appelée ici invoque directement app.ingestion.extractor.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, UploadFile
from sqlmodel import Session

from app.auth.models import Utilisateur
from app.auth.permissions import require_role
from app.company.rapports import creer_correction, deposer_rapport, lister_mes_rapports
from app.core.dependencies import get_session
from app.core.enums import Role, TypeRapport
from app.core.exceptions import NotFoundError, ValidationError
from app.ingestion.models import RapportESG
from app.ingestion.schemas import RapportESGDetail, RapportESGPublic

router = APIRouter(tags=["company"])


def _entreprise_id(current_user: Utilisateur) -> uuid.UUID:
    if current_user.entreprise is None:
        raise ValidationError(
            "Aucune entreprise n'est rattachée à ce compte.", code="entreprise_non_rattachee"
        )
    return current_user.entreprise.id


@router.get(
    "/company/rapports",
    response_model=list[RapportESGPublic],
    operation_id="listCompanyReports",
    summary="Lister les rapports déposés par l'entreprise",
)
def lister_rapports_route(
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE)),
    session: Session = Depends(get_session),
) -> list[RapportESG]:
    return lister_mes_rapports(session, _entreprise_id(current_user))


@router.post(
    "/company/rapports",
    response_model=RapportESGPublic,
    status_code=201,
    operation_id="submitCompanyReport",
    summary="Déposer un rapport ESG/climat",
)
def deposer_rapport_route(
    background_tasks: BackgroundTasks,
    fichier: UploadFile,
    type: TypeRapport = Form(...),
    annee_reporting: int = Form(...),
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE)),
    session: Session = Depends(get_session),
) -> RapportESG:
    contenu = fichier.file.read()
    return deposer_rapport(
        session, background_tasks, _entreprise_id(current_user), contenu, type, annee_reporting
    )


@router.post(
    "/company/rapports/{rapport_id}/corrections",
    response_model=RapportESGPublic,
    status_code=201,
    operation_id="submitCompanyReportCorrection",
    summary="Déposer une nouvelle version d'un rapport en attente de correction",
)
def creer_correction_route(
    rapport_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    fichier: UploadFile,
    annee_reporting: int = Form(...),
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE)),
    session: Session = Depends(get_session),
) -> RapportESG:
    contenu = fichier.file.read()
    return creer_correction(
        session,
        background_tasks,
        rapport_id,
        _entreprise_id(current_user),
        contenu,
        annee_reporting,
    )


@router.get(
    "/company/rapports/{rapport_id}",
    response_model=RapportESGDetail,
    operation_id="getCompanyReport",
    summary="Consulter le détail d'un rapport déposé par l'entreprise",
)
def consulter_rapport(
    rapport_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE)),
    session: Session = Depends(get_session),
) -> RapportESG:
    rapport = session.get(RapportESG, rapport_id)
    # Même code d'erreur, que le rapport n'existe pas ou appartienne à une autre entreprise —
    # jamais de 403 ici, pour ne pas confirmer l'existence d'un rapport_id d'autrui.
    if (
        rapport is None
        or current_user.entreprise is None
        or rapport.entreprise_id != current_user.entreprise.id
    ):
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    return rapport
