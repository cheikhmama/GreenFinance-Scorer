"""Routes HTTP de l'espace Administrateur.

Statut : Étape 10 partielle + Phase 3 §3.3 (cycle de vie du compte). Périmètre : file
d'attente/affectation/décision/publication des rapports (app/admin/review_queue.py,
app/audit/assignment.py pour l'affectation) et gestion des comptes utilisateurs — création avec
mot de passe temporaire, désactivation, changement de rôle contrôlé (app/admin/utilisateurs.py).
Ce router ne fait qu'appliquer le contrôle d'accès par rôle et appeler cette logique.
"""

import math
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.admin.dashboard import construire_tableau_de_bord
from app.admin.journal import lister_journal_audit
from app.admin.review_queue import (
    demander_correction,
    lister_avis,
    lister_entreprises_publiables,
    lister_rapports_a_affecter,
    lister_rapports_en_validation,
    lister_toutes_les_entreprises,
    lister_versions,
    publier_entreprise,
    reactiver_entreprise,
    rejeter_rapport,
    suspendre_entreprise,
    valider_rapport,
)
from app.admin.schemas import (
    AffecterAuditeurRequest,
    ChangerRoleRequest,
    CreerUtilisateurRequest,
    DecisionAdminRequest,
    EntrepriseAdmin,
    JournalAuditPublic,
    TableauDeBordAdmin,
    UtilisateurCree,
)
from app.admin.utilisateurs import (
    changer_role,
    creer_utilisateur,
    desactiver_utilisateur,
    lister_utilisateurs_par_role,
    reactiver_utilisateur,
)
from app.audit.assignment import affecter_auditeur
from app.audit.models import AvisAudit
from app.audit.schemas import AvisAuditAdmin
from app.auth.models import Utilisateur
from app.auth.permissions import require_role
from app.auth.schemas import UtilisateurPublic
from app.company.models import Entreprise
from app.company.rapports import lister_mes_rapports
from app.company.schemas import EntreprisePublic
from app.core import storage
from app.core.dependencies import get_session
from app.core.enums import Role
from app.core.exceptions import NotFoundError
from app.core.schemas import Page
from app.ingestion.models import RapportESG
from app.ingestion.schemas import RapportESGDetail, RapportESGPublic

router = APIRouter(tags=["admin"])


@router.get(
    "/admin/utilisateurs",
    response_model=Page[UtilisateurPublic],
    operation_id="listUsersByRole",
    summary="Lister les comptes actifs d'un rôle donné, avec recherche et pagination",
)
def lister_utilisateurs_route(
    role: Role,
    recherche: str | None = Query(None, description="Filtre sur l'e-mail"),
    inclure_inactifs: bool = Query(False, description="Inclure aussi les comptes désactivés"),
    doit_changer_mot_de_passe: bool | None = Query(
        None, description="Filtrer sur le mot de passe temporaire non changé"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(3, ge=1, le=50),
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> Page[UtilisateurPublic]:
    """Page de comptes existants pour un rôle donné — la seule source à partir de laquelle une
    relation acteur-à-acteur (ex. affectation d'un auditeur) doit être construite, jamais une
    saisie libre de nom/e-mail."""
    items, total = lister_utilisateurs_par_role(
        session,
        role,
        recherche=recherche,
        inclure_inactifs=inclure_inactifs,
        doit_changer_mot_de_passe=doit_changer_mot_de_passe,
        page=page,
        page_size=page_size,
    )
    return Page[UtilisateurPublic](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post(
    "/admin/utilisateurs",
    response_model=UtilisateurCree,
    status_code=201,
    operation_id="createUser",
    summary="Provisionner un compte avec un mot de passe temporaire à usage unique",
)
def creer_utilisateur_route(
    payload: CreerUtilisateurRequest,
    current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> UtilisateurCree:
    utilisateur, mot_de_passe_temporaire = creer_utilisateur(
        session,
        current_user.id,
        payload.email,
        payload.nom,
        payload.role,
        nom_entreprise=payload.nom_entreprise,
        secteur=payload.secteur,
        pays=payload.pays,
    )
    return UtilisateurCree(
        id=utilisateur.id,
        email=utilisateur.email,
        nom=utilisateur.nom,
        role=utilisateur.role,
        date_creation=utilisateur.date_creation,
        actif=utilisateur.actif,
        mot_de_passe_temporaire=mot_de_passe_temporaire,
    )


@router.post(
    "/admin/utilisateurs/{utilisateur_id}/desactiver",
    response_model=UtilisateurPublic,
    operation_id="deactivateUser",
    summary="Désactiver un compte utilisateur",
)
def desactiver_utilisateur_route(
    utilisateur_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> Utilisateur:
    return desactiver_utilisateur(session, current_user.id, utilisateur_id)


@router.post(
    "/admin/utilisateurs/{utilisateur_id}/reactiver",
    response_model=UtilisateurPublic,
    operation_id="reactivateUser",
    summary="Réactiver un compte utilisateur désactivé",
)
def reactiver_utilisateur_route(
    utilisateur_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> Utilisateur:
    return reactiver_utilisateur(session, current_user.id, utilisateur_id)


@router.post(
    "/admin/utilisateurs/{utilisateur_id}/role",
    response_model=UtilisateurPublic,
    operation_id="changeUserRole",
    summary="Changer le rôle d'un compte utilisateur",
)
def changer_role_route(
    utilisateur_id: uuid.UUID,
    payload: ChangerRoleRequest,
    current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> Utilisateur:
    return changer_role(session, current_user.id, utilisateur_id, payload.role)


@router.get(
    "/admin/rapports/a-affecter",
    response_model=list[RapportESGPublic],
    operation_id="listReportsToAssign",
    summary="Lister les rapports extraits en attente d'affectation",
)
def lister_rapports_a_affecter_route(
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> list[RapportESG]:
    return lister_rapports_a_affecter(session)


@router.post(
    "/admin/rapports/{rapport_id}/affecter",
    response_model=RapportESGPublic,
    operation_id="assignReportAuditor",
    summary="Affecter un rapport à un auditeur",
)
def affecter_route(
    rapport_id: uuid.UUID,
    payload: AffecterAuditeurRequest,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> RapportESG:
    return affecter_auditeur(session, rapport_id, payload.auditeur_id)


@router.get(
    "/admin/rapports/en-validation",
    response_model=list[RapportESGPublic],
    operation_id="listReportsInValidation",
    summary="Lister les rapports en attente de décision, avis d'audit déjà rendu",
)
def lister_rapports_en_validation_route(
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> list[RapportESG]:
    return lister_rapports_en_validation(session)


@router.get(
    "/admin/rapports/{rapport_id}",
    response_model=RapportESGDetail,
    operation_id="getAdminReport",
    summary="Consulter le détail complet d'un rapport, quel que soit son statut",
)
def consulter_rapport_route(
    rapport_id: uuid.UUID,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> RapportESG:
    rapport = session.get(RapportESG, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    return rapport


@router.get(
    "/admin/rapports/{rapport_id}/fichier",
    operation_id="getAdminReportFile",
    summary="Télécharger le PDF original déposé pour ce rapport",
)
def consulter_fichier_route(
    rapport_id: uuid.UUID,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> FileResponse:
    rapport = session.get(RapportESG, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    return FileResponse(storage.resolve_path(rapport.fichier_source))


@router.get(
    "/admin/rapports/{rapport_id}/versions",
    response_model=list[RapportESGPublic],
    operation_id="listReportVersions",
    summary="Lister toutes les versions d'un rapport (originale et corrections), dans l'ordre",
)
def lister_versions_route(
    rapport_id: uuid.UUID,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> list[RapportESG]:
    return lister_versions(session, rapport_id)


@router.get(
    "/admin/rapports/{rapport_id}/avis",
    response_model=list[AvisAuditAdmin],
    operation_id="listReportOpinions",
    summary="Lister les avis d'audit rendus sur un rapport",
)
def lister_avis_route(
    rapport_id: uuid.UUID,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> list[AvisAudit]:
    return lister_avis(session, rapport_id)


@router.post(
    "/admin/rapports/{rapport_id}/valider",
    response_model=RapportESGPublic,
    operation_id="validateReport",
    summary="Valider un rapport en attente de décision",
)
def valider_route(
    rapport_id: uuid.UUID,
    payload: DecisionAdminRequest,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> RapportESG:
    return valider_rapport(session, rapport_id, payload.commentaire)


@router.post(
    "/admin/rapports/{rapport_id}/rejeter",
    response_model=RapportESGPublic,
    operation_id="rejectReport",
    summary="Rejeter un rapport en attente de décision",
)
def rejeter_route(
    rapport_id: uuid.UUID,
    payload: DecisionAdminRequest,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> RapportESG:
    return rejeter_rapport(session, rapport_id, payload.commentaire)


@router.post(
    "/admin/rapports/{rapport_id}/demander-correction",
    response_model=RapportESGPublic,
    operation_id="requestReportCorrection",
    summary="Renvoyer un rapport en attente de décision vers l'entreprise pour correction",
)
def demander_correction_route(
    rapport_id: uuid.UUID,
    payload: DecisionAdminRequest,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> RapportESG:
    return demander_correction(session, rapport_id, payload.commentaire)


@router.get(
    "/admin/entreprises",
    response_model=Page[EntrepriseAdmin],
    operation_id="listAllCompanies",
    summary="Lister toutes les entreprises avec un résumé de statut (dépôts, dernier statut, compte lié)",
)
def lister_toutes_les_entreprises_route(
    recherche: str | None = Query(None, description="Filtre sur le nom, le secteur ou le pays"),
    page: int = Query(1, ge=1),
    page_size: int = Query(3, ge=1, le=50),
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> Page[EntrepriseAdmin]:
    items, total = lister_toutes_les_entreprises(
        session, recherche=recherche, page=page, page_size=page_size
    )
    return Page[EntrepriseAdmin](
        items=[
            EntrepriseAdmin(
                **EntreprisePublic.model_validate(entreprise).model_dump(),
                utilisateur_id=entreprise.utilisateur_id,
                nombre_rapports=nombre_rapports,
                dernier_statut_rapport=dernier_statut,
            )
            for entreprise, nombre_rapports, dernier_statut in items
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get(
    "/admin/entreprises/publiables",
    response_model=Page[EntreprisePublic],
    operation_id="listPublishableCompanies",
    summary="Lister les entreprises ayant au moins un rapport validé, pas encore publiées",
)
def lister_entreprises_publiables_route(
    recherche: str | None = Query(None, description="Filtre sur le nom, le secteur ou le pays"),
    page: int = Query(1, ge=1),
    page_size: int = Query(3, ge=1, le=50),
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> Page[EntreprisePublic]:
    items, total = lister_entreprises_publiables(
        session, recherche=recherche, page=page, page_size=page_size
    )
    return Page[EntreprisePublic](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post(
    "/admin/entreprises/{entreprise_id}/publier",
    response_model=EntreprisePublic,
    operation_id="publishCompany",
    summary="Publier une entreprise",
)
def publier_route(
    entreprise_id: uuid.UUID,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> Entreprise:
    return publier_entreprise(session, entreprise_id)


@router.post(
    "/admin/entreprises/{entreprise_id}/suspendre",
    response_model=EntreprisePublic,
    operation_id="suspendCompany",
    summary="Suspendre une entreprise (bloque tout nouveau dépôt de rapport)",
)
def suspendre_route(
    entreprise_id: uuid.UUID,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> Entreprise:
    return suspendre_entreprise(session, entreprise_id)


@router.post(
    "/admin/entreprises/{entreprise_id}/reactiver",
    response_model=EntreprisePublic,
    operation_id="reactivateCompany",
    summary="Réactiver une entreprise suspendue",
)
def reactiver_entreprise_route(
    entreprise_id: uuid.UUID,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> Entreprise:
    return reactiver_entreprise(session, entreprise_id)


@router.get(
    "/admin/entreprises/{entreprise_id}/rapports",
    response_model=list[RapportESGPublic],
    operation_id="listAdminCompanyReports",
    summary="Lister tous les rapports déposés par une entreprise",
)
def lister_rapports_entreprise_route(
    entreprise_id: uuid.UUID,
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> list[RapportESG]:
    return lister_mes_rapports(session, entreprise_id)


@router.get(
    "/admin/journal-audit",
    response_model=Page[JournalAuditPublic],
    operation_id="listAuditLog",
    summary="Consulter le journal d'audit (connexions, changements de rôle, désactivations...)",
)
def lister_journal_audit_route(
    acteur_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    type_ressource: str | None = Query(None),
    id_ressource: uuid.UUID | None = Query(None),
    concerne_id: uuid.UUID | None = Query(
        None, description="Historique complet d'un utilisateur précis, acteur ou cible"
    ),
    depuis: datetime | None = Query(None, description="Borne basse incluse"),
    jusqu_a: datetime | None = Query(None, description="Borne haute incluse"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> Page[JournalAuditPublic]:
    items, total = lister_journal_audit(
        session,
        acteur_id=acteur_id,
        action=action,
        type_ressource=type_ressource,
        id_ressource=id_ressource,
        concerne_id=concerne_id,
        depuis=depuis,
        jusqu_a=jusqu_a,
        page=page,
        page_size=page_size,
    )
    return Page[JournalAuditPublic](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get(
    "/admin/dashboard",
    response_model=TableauDeBordAdmin,
    operation_id="getAdminDashboard",
    summary="Indicateurs agrégés du tableau de bord Administrateur",
)
def tableau_de_bord_route(
    _current_user: Utilisateur = Depends(require_role(Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> TableauDeBordAdmin:
    return construire_tableau_de_bord(session)
