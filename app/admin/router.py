"""Routes HTTP de l'espace Administrateur.

Statut : Étape 10 partielle + Phase 3 §3.3 (cycle de vie du compte). Périmètre : file
d'attente/affectation/décision/publication des rapports (app/admin/review_queue.py,
app/audit/assignment.py pour l'affectation) et gestion des comptes utilisateurs — création avec
lien d'activation par e-mail, désactivation/réactivation (app/admin/utilisateurs.py). Le rôle d'un
compte se fixe une seule fois, à sa création (jamais de changement de rôle après coup : chaque
rôle porte ses propres permissions et son propre espace, les mélanger après coup n'a pas de sens
métier — voir aussi app/auth/schemas.py::ModifierProfilRequest).
Ce router ne fait qu'appliquer le contrôle d'accès par rôle et appeler cette logique.
"""

import math
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.admin.apercu import (
    calculer_performance_esg,
    construire_apercu_acteurs,
    entreprises_perimetre_esg,
    lister_entreprises_avec_score,
)
from app.admin.dashboard import construire_tableau_de_bord
from app.admin.journal import lister_journal_audit
from app.admin.onboarding import decider_inscription
from app.admin.review_queue import (
    consulter_entreprise_admin,
    demander_correction,
    lister_avis,
    lister_entreprises_a_republier,
    lister_entreprises_publiables,
    lister_rapports_a_affecter,
    lister_rapports_echec_extraction,
    lister_rapports_en_retard,
    lister_rapports_en_validation,
    lister_rapports_extraction_bloquee,
    lister_rapports_orphelins_en_validation,
    lister_tous_les_rapports,
    lister_toutes_les_entreprises,
    lister_versions,
    modifier_donnees_financieres,
    modifier_entreprise_admin,
    modifier_identifiants,
    publier_entreprise,
    reactiver_entreprise,
    recalculer_score,
    rejeter_rapport,
    relancer_extraction,
    resume_rapports_entreprise,
    supprimer_logo_entreprise,
    suspendre_entreprise,
    televerser_logo_entreprise,
    valider_rapport,
)
from app.admin.schemas import (
    AffecterAuditeurRequest,
    AnalyseAdmin,
    ApercuActeursAdmin,
    ChargeAuditeurAdmin,
    CompanyFinancials,
    CompanyFinancialsRequest,
    CompanyIdentifiers,
    CompanyIdentifiersRequest,
    CompanyOnboardingRequest,
    CompanyOnboardingResult,
    CreerUtilisateurRequest,
    DecisionAdminRequest,
    EntrepriseAdmin,
    EntrepriseAvecScoreAdmin,
    JournalAuditPublic,
    ModifierEntrepriseAdminRequest,
    PerformanceESGAdmin,
    PortefeuilleAdmin,
    ProjetAdmin,
    ScoreVerificationAdmin,
    StatistiquesAuditeursAdmin,
    StatistiquesChercheursAdmin,
    StatistiquesInstitutionsAdmin,
    StatistiquesInvestisseursAdmin,
    TableauDeBordAdmin,
    TrancheScorePublic,
    UtilisateurCree,
)
from app.admin.utilisateurs import (
    creer_utilisateur,
    desactiver_utilisateur,
    lister_utilisateurs_en_attente,
    lister_utilisateurs_par_role,
    reactiver_utilisateur,
    renvoyer_lien_activation,
)
from app.audit.assignment import affecter_auditeur, lister_charge_auditeurs
from app.audit.models import AvisAudit
from app.audit.schemas import AvisAuditAdmin
from app.auth.activation import envoyer_lien_activation
from app.auth.models import User
from app.auth.permissions import require_role
from app.auth.schemas import UtilisateurPublic
from app.company.models import Company
from app.company.rapports import lister_mes_rapports
from app.company.schemas import EntreprisePublic
from app.core import storage
from app.core.dependencies import get_session
from app.core.enums import ReportStatus, Role, StatutAnalyse, StatutProjet
from app.core.exceptions import NotFoundError
from app.core.schemas import Page
from app.ingestion.extractor import run_extraction_pipeline
from app.ingestion.models import ESGReport
from app.ingestion.schemas import RapportESGDetail, RapportESGPublic
from app.institution.projets import lister_projets_admin
from app.investor.portfolio import lister_portefeuilles_admin
from app.researcher.analyses import lister_analyses_admin
from app.scoring.engine import score_calculable, score_public
from app.scoring.models import ScoreESG

router = APIRouter(tags=["admin"])


def _vers_entreprise_admin(session: Session, entreprise: Company) -> EntrepriseAdmin:
    """Vue EntrepriseAdmin d'une entreprise déjà chargée — utilisée par les routes qui agissent
    sur UNE entreprise (détail, modification, logo), contrairement à lister_toutes_les_entreprises_
    route ci-dessous qui batch cette même construction pour toute une page à la fois."""
    nombre_rapports, dernier_statut, dernier_rapport_id = resume_rapports_entreprise(
        session, entreprise.id
    )
    return EntrepriseAdmin(
        **EntreprisePublic.model_validate(entreprise).model_dump(),
        utilisateur_id=entreprise.owner_user_id,
        nombre_rapports=nombre_rapports,
        dernier_statut_rapport=dernier_statut,
        dernier_rapport_id=dernier_rapport_id,
    )


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
    en_attente_activation: bool | None = Query(
        None, description="Filtrer sur les comptes qui n'ont pas encore cliqué leur lien d'activation"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(3, ge=1, le=50),
    _current_user: User = Depends(require_role(Role.ADMIN)),
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
        en_attente_activation=en_attente_activation,
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


@router.get(
    "/admin/utilisateurs/en-attente",
    response_model=list[UtilisateurPublic],
    operation_id="listUsersAwaitingActivation",
    summary="Lister les comptes actifs, tous rôles confondus, qui n'ont pas encore cliqué leur lien d'activation",
)
def lister_utilisateurs_en_attente_route(
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> list[User]:
    return lister_utilisateurs_en_attente(session)


@router.post(
    "/admin/utilisateurs",
    response_model=UtilisateurCree,
    status_code=201,
    operation_id="createUser",
    summary="Provisionner un compte et lui envoyer un lien d'activation par e-mail",
)
def creer_utilisateur_route(
    payload: CreerUtilisateurRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> UtilisateurCree:
    utilisateur = creer_utilisateur(
        session,
        current_user.id,
        payload.email,
        payload.nom,
        payload.role,
        nom_entreprise=payload.nom_entreprise,
        secteur=payload.secteur,
        pays=payload.pays,
    )
    envoyer_lien_activation(session, utilisateur, background_tasks)
    session.commit()
    return UtilisateurCree(
        id=utilisateur.id,
        email=utilisateur.email,
        nom=utilisateur.name,
        role=utilisateur.role,
        date_creation=utilisateur.created_at,
        actif=utilisateur.active,
    )


@router.post(
    "/admin/utilisateurs/{utilisateur_id}/renvoyer-activation",
    status_code=204,
    operation_id="resendActivationLink",
    summary="Régénérer et renvoyer le lien d'activation d'un compte pas encore activé",
)
def renvoyer_activation_route(
    utilisateur_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> None:
    renvoyer_lien_activation(session, current_user.id, utilisateur_id, background_tasks)


@router.post(
    "/admin/utilisateurs/{utilisateur_id}/desactiver",
    response_model=UtilisateurPublic,
    operation_id="deactivateUser",
    summary="Désactiver un compte utilisateur",
)
def desactiver_utilisateur_route(
    utilisateur_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> User:
    return desactiver_utilisateur(session, current_user.id, utilisateur_id)


@router.post(
    "/admin/utilisateurs/{utilisateur_id}/reactiver",
    response_model=UtilisateurPublic,
    operation_id="reactivateUser",
    summary="Réactiver un compte utilisateur désactivé",
)
def reactiver_utilisateur_route(
    utilisateur_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> User:
    return reactiver_utilisateur(session, current_user.id, utilisateur_id)


@router.get(
    "/admin/rapports",
    response_model=Page[RapportESGPublic],
    operation_id="listAllReports",
    summary="Lister tous les rapports, tous statuts confondus, avec filtre optionnel sur le statut",
)
def lister_tous_les_rapports_route(
    statut: ReportStatus | None = Query(None, description="Filtre sur le statut du rapport"),
    page: int = Query(1, ge=1),
    page_size: int = Query(3, ge=1, le=50),
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> Page[RapportESGPublic]:
    items, total = lister_tous_les_rapports(session, statut=statut, page=page, page_size=page_size)
    return Page[RapportESGPublic](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get(
    "/admin/rapports/en-retard",
    response_model=list[RapportESGPublic],
    operation_id="listOverdueReports",
    summary="Lister les rapports affectés à un auditeur au-delà du délai attendu, sans décision rendue",
)
def lister_rapports_en_retard_route(
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> list[ESGReport]:
    return lister_rapports_en_retard(session)


@router.get(
    "/admin/rapports/a-affecter",
    response_model=list[RapportESGPublic],
    operation_id="listReportsToAssign",
    summary="Lister les rapports extraits en attente d'affectation",
)
def lister_rapports_a_affecter_route(
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> list[ESGReport]:
    return lister_rapports_a_affecter(session)


@router.get(
    "/admin/rapports/echec-extraction",
    response_model=list[RapportESGPublic],
    operation_id="listFailedExtractionReports",
    summary="Lister les rapports dont l'extraction automatique a échoué",
)
def lister_rapports_echec_extraction_route(
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> list[ESGReport]:
    return lister_rapports_echec_extraction(session)


@router.get(
    "/admin/rapports/extraction-bloquee",
    response_model=list[RapportESGPublic],
    operation_id="listStuckExtractionReports",
    summary="Lister les rapports dont l'extraction semble interrompue (aucune erreur, aucune fin)",
)
def lister_rapports_extraction_bloquee_route(
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> list[ESGReport]:
    return lister_rapports_extraction_bloquee(session)


@router.post(
    "/admin/rapports/{rapport_id}/relancer-extraction",
    response_model=RapportESGPublic,
    operation_id="retryExtraction",
    summary="Relancer l'extraction d'un rapport en échec ou bloqué",
)
def relancer_extraction_route(
    rapport_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> ESGReport:
    rapport = relancer_extraction(session, rapport_id)
    assert rapport.fiscal_year is not None  # garanti par relancer_extraction ci-dessus
    background_tasks.add_task(run_extraction_pipeline, rapport.id, rapport.fiscal_year)
    return rapport


@router.post(
    "/admin/rapports/{rapport_id}/affecter",
    response_model=RapportESGPublic,
    operation_id="assignReportAuditor",
    summary="Affecter un rapport à un auditeur",
)
def affecter_route(
    rapport_id: uuid.UUID,
    payload: AffecterAuditeurRequest,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> ESGReport:
    return affecter_auditeur(session, rapport_id, payload.auditeur_id)


@router.get(
    "/admin/auditeurs/charge",
    response_model=Page[ChargeAuditeurAdmin],
    operation_id="listAuditorWorkload",
    summary="Lister la charge de travail (dossiers affectés, en retard, avis rendus) par Auditeur actif",
)
def lister_charge_auditeurs_route(
    recherche: str | None = Query(None, description="Filtre sur l'e-mail"),
    page: int = Query(1, ge=1),
    page_size: int = Query(3, ge=1, le=50),
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> Page[ChargeAuditeurAdmin]:
    items, total = lister_charge_auditeurs(session, recherche=recherche, page=page, page_size=page_size)
    return Page[ChargeAuditeurAdmin](
        items=[
            ChargeAuditeurAdmin(
                auditeur_id=auditeur.id,
                email=auditeur.email,
                dossiers_affectes=affectes,
                dossiers_en_retard=en_retard,
                avis_rendus=avis,
            )
            for auditeur, affectes, en_retard, avis in items
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get(
    "/admin/rapports/en-validation",
    response_model=list[RapportESGPublic],
    operation_id="listReportsInValidation",
    summary="Lister les rapports en attente de décision, avis d'audit déjà rendu",
)
def lister_rapports_en_validation_route(
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> list[ESGReport]:
    return lister_rapports_en_validation(session)


@router.get(
    "/admin/rapports/orphelins",
    response_model=list[RapportESGPublic],
    operation_id="listOrphanReportsInValidation",
    summary="Lister les rapports en attente de décision mais sans aucun avis d'audit (état incohérent)",
)
def lister_rapports_orphelins_route(
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> list[ESGReport]:
    return lister_rapports_orphelins_en_validation(session)


@router.get(
    "/admin/rapports/{rapport_id}/score-verification",
    response_model=ScoreVerificationAdmin,
    operation_id="verifyReportScorability",
    summary="Vérifier, avant décision, si ce rapport pourra être scoré",
)
def verifier_score_calculable_route(
    rapport_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> ScoreVerificationAdmin:
    return ScoreVerificationAdmin(calculable=score_calculable(session, rapport_id))


@router.post(
    "/admin/rapports/{rapport_id}/recalculer-score",
    response_model=ScoreESG,
    operation_id="recalculateReportScore",
    summary="Recalculer le score d'un rapport validé qui en est dépourvu (état incohérent)",
)
def recalculer_score_route(
    rapport_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> ScoreESG:
    return recalculer_score(session, rapport_id)


@router.get(
    "/admin/rapports/{rapport_id}",
    response_model=RapportESGDetail,
    operation_id="getAdminReport",
    summary="Consulter le détail complet d'un rapport, quel que soit son statut",
)
def consulter_rapport_route(
    rapport_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> RapportESGDetail:
    rapport = session.get(ESGReport, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    detail = RapportESGDetail.model_validate(rapport)
    return detail.model_copy(update={"score_officiel": score_public(session, rapport_id)})


@router.get(
    "/admin/rapports/{rapport_id}/fichier",
    operation_id="getAdminReportFile",
    summary="Télécharger le PDF original déposé pour ce rapport",
)
def consulter_fichier_route(
    rapport_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> FileResponse:
    rapport = session.get(ESGReport, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    if rapport.source_file is None:
        raise NotFoundError("Ce rapport n'a pas encore de fichier.", code="fichier_absent")
    return FileResponse(storage.resolve_path(rapport.source_file))


@router.get(
    "/admin/rapports/{rapport_id}/versions",
    response_model=list[RapportESGPublic],
    operation_id="listReportVersions",
    summary="Lister toutes les versions d'un rapport (originale et corrections), dans l'ordre",
)
def lister_versions_route(
    rapport_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> list[ESGReport]:
    return lister_versions(session, rapport_id)


@router.get(
    "/admin/rapports/{rapport_id}/avis",
    response_model=list[AvisAuditAdmin],
    operation_id="listReportOpinions",
    summary="Lister les avis d'audit rendus sur un rapport",
)
def lister_avis_route(
    rapport_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
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
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> ESGReport:
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
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> ESGReport:
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
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> ESGReport:
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
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> Page[EntrepriseAdmin]:
    items, total = lister_toutes_les_entreprises(
        session, recherche=recherche, page=page, page_size=page_size
    )
    return Page[EntrepriseAdmin](
        items=[
            EntrepriseAdmin(
                **EntreprisePublic.model_validate(entreprise).model_dump(),
                utilisateur_id=entreprise.owner_user_id,
                nombre_rapports=nombre_rapports,
                dernier_statut_rapport=dernier_statut,
                dernier_rapport_id=dernier_rapport_id,
            )
            for entreprise, nombre_rapports, dernier_statut, dernier_rapport_id in items
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
    _current_user: User = Depends(require_role(Role.ADMIN)),
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


@router.get(
    "/admin/entreprises/a-republier",
    response_model=Page[EntreprisePublic],
    operation_id="listCompaniesToRepublish",
    summary="Lister les entreprises publiées dont un rapport a été validé après la dernière publication",
)
def lister_entreprises_a_republier_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(3, ge=1, le=50),
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> Page[EntreprisePublic]:
    items, total = lister_entreprises_a_republier(session, page=page, page_size=page_size)
    return Page[EntreprisePublic](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get(
    "/admin/entreprises/scores",
    response_model=Page[EntrepriseAvecScoreAdmin],
    operation_id="listCompaniesWithScore",
    summary="Lister les entreprises publiées avec leur score ESG admissible, filtrable par secteur/pays",
)
def lister_entreprises_avec_score_route(
    secteur: str | None = Query(None),
    pays: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(3, ge=1, le=50),
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> Page[EntrepriseAvecScoreAdmin]:
    items, total = lister_entreprises_avec_score(
        session, secteur=secteur, pays=pays, page=page, page_size=page_size
    )
    return Page[EntrepriseAvecScoreAdmin](
        items=[
            EntrepriseAvecScoreAdmin(
                id=entreprise.id,
                nom=entreprise.name,
                secteur=entreprise.sector,
                pays=entreprise.country,
                score_global=score.valeur_globale if score else None,
                score_environnement=score.score_environnement if score else None,
                score_social=score.score_social if score else None,
                score_gouvernance=score.score_gouvernance if score else None,
            )
            for entreprise, score in items
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.patch(
    "/admin/companies/{company_id}/identifiers",
    response_model=CompanyIdentifiers,
    operation_id="updateCompanyIdentifiers",
    summary="Renseigner l'ISIN, le LEI ou le ticker d'une entreprise",
)
def update_company_identifiers(
    company_id: uuid.UUID,
    payload: CompanyIdentifiersRequest,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> CompanyIdentifiers:
    entreprise = modifier_identifiants(
        session, company_id, payload.model_dump(include=payload.model_fields_set)
    )
    return CompanyIdentifiers(
        company_id=entreprise.id, isin=entreprise.isin, lei=entreprise.lei, ticker=entreprise.ticker
    )


@router.patch(
    "/admin/companies/{company_id}/onboard",
    response_model=CompanyOnboardingResult,
    operation_id="onboardCompany",
    summary="Valider ou refuser l'inscription d'une entreprise",
)
def onboard_company(
    company_id: uuid.UUID,
    payload: CompanyOnboardingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> CompanyOnboardingResult:
    return decider_inscription(
        session, current_user.id, company_id, payload.decision, payload.reason, background_tasks
    )


@router.post(
    "/admin/entreprises/{entreprise_id}/publier",
    response_model=EntreprisePublic,
    operation_id="publishCompany",
    summary="Publier une entreprise",
)
def publier_route(
    entreprise_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> Company:
    return publier_entreprise(session, entreprise_id)


@router.post(
    "/admin/entreprises/{entreprise_id}/suspendre",
    response_model=EntreprisePublic,
    operation_id="suspendCompany",
    summary="Suspendre une entreprise (bloque tout nouveau dépôt de rapport)",
)
def suspendre_route(
    entreprise_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> Company:
    return suspendre_entreprise(session, entreprise_id)


@router.post(
    "/admin/entreprises/{entreprise_id}/reactiver",
    response_model=EntreprisePublic,
    operation_id="reactivateCompany",
    summary="Réactiver une entreprise suspendue",
)
def reactiver_entreprise_route(
    entreprise_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> Company:
    return reactiver_entreprise(session, entreprise_id)


@router.get(
    "/admin/entreprises/{entreprise_id}",
    response_model=EntrepriseAdmin,
    operation_id="getCompanyAdmin",
    summary="Consulter le profil complet d'une entreprise, quel que soit son statut",
)
def consulter_entreprise_route(
    entreprise_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> EntrepriseAdmin:
    entreprise = consulter_entreprise_admin(session, entreprise_id)
    return _vers_entreprise_admin(session, entreprise)


@router.patch(
    "/admin/entreprises/{entreprise_id}",
    response_model=EntrepriseAdmin,
    operation_id="updateCompanyProfile",
    summary="Mettre à jour le profil d'une entreprise (identité, description, site officiel, montant minimum)",
)
def modifier_entreprise_route(
    entreprise_id: uuid.UUID,
    payload: ModifierEntrepriseAdminRequest,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> EntrepriseAdmin:
    entreprise = modifier_entreprise_admin(
        session,
        entreprise_id,
        nom=payload.nom,
        secteur=payload.secteur,
        pays=payload.pays,
        description=payload.description,
        site_officiel=payload.site_officiel,
        montant_minimum_investissement=payload.montant_minimum_investissement,
        devise_montant_minimum=payload.devise_montant_minimum,
    )
    return _vers_entreprise_admin(session, entreprise)


@router.post(
    "/admin/entreprises/{entreprise_id}/logo",
    response_model=EntrepriseAdmin,
    operation_id="uploadCompanyLogo",
    summary="Ajouter ou remplacer le logo d'une entreprise",
)
def televerser_logo_entreprise_route(
    entreprise_id: uuid.UUID,
    fichier: UploadFile,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> EntrepriseAdmin:
    contenu = fichier.file.read()
    entreprise = televerser_logo_entreprise(session, entreprise_id, contenu)
    return _vers_entreprise_admin(session, entreprise)


@router.delete(
    "/admin/entreprises/{entreprise_id}/logo",
    response_model=EntrepriseAdmin,
    operation_id="deleteCompanyLogo",
    summary="Retirer le logo d'une entreprise",
)
def supprimer_logo_entreprise_route(
    entreprise_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> EntrepriseAdmin:
    entreprise = supprimer_logo_entreprise(session, entreprise_id)
    return _vers_entreprise_admin(session, entreprise)


@router.get(
    "/admin/entreprises/{entreprise_id}/rapports",
    response_model=list[RapportESGPublic],
    operation_id="listAdminCompanyReports",
    summary="Lister tous les rapports déposés par une entreprise",
)
def lister_rapports_entreprise_route(
    entreprise_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> list[ESGReport]:
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
    _current_user: User = Depends(require_role(Role.ADMIN)),
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
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> TableauDeBordAdmin:
    return construire_tableau_de_bord(session)


@router.get(
    "/admin/apercu-acteurs",
    response_model=ApercuActeursAdmin,
    operation_id="getAdminActorsOverview",
    summary="Statistiques agrégées des espaces Auditeur, Investisseur, Chercheur et Institution",
)
def apercu_acteurs_route(
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> ApercuActeursAdmin:
    apercu = construire_apercu_acteurs(session)
    return ApercuActeursAdmin(
        auditeurs=StatistiquesAuditeursAdmin(
            dossiers_affectes=apercu.auditeurs.dossiers_affectes,
            avis_rendus=apercu.auditeurs.avis_rendus,
        ),
        investisseurs=StatistiquesInvestisseursAdmin(
            portefeuilles_non_archives=apercu.investisseurs.portefeuilles_non_archives,
            positions_declarees=apercu.investisseurs.positions_declarees,
            entreprises_distinctes=apercu.investisseurs.entreprises_distinctes,
        ),
        chercheurs=StatistiquesChercheursAdmin(
            chercheurs_affectes_projets_ouverts=apercu.chercheurs.chercheurs_affectes_projets_ouverts,
            analyses_brouillon=apercu.chercheurs.analyses_brouillon,
            analyses_soumises=apercu.chercheurs.analyses_soumises,
            analyses_validees=apercu.chercheurs.analyses_validees,
            analyses_correction_demandee=apercu.chercheurs.analyses_correction_demandee,
        ),
        institutions=StatistiquesInstitutionsAdmin(
            projets_ouverts=apercu.institutions.projets_ouverts,
            projets_clotures=apercu.institutions.projets_clotures,
            invitations_en_attente=apercu.institutions.invitations_en_attente,
            analyses_a_examiner=apercu.institutions.analyses_a_examiner,
        ),
    )


@router.get(
    "/admin/performance-esg",
    response_model=PerformanceESGAdmin,
    operation_id="getAdminESGPerformance",
    summary="Score ESG global/E/S/G moyen et couverture, sur le périmètre des entreprises publiées",
)
def performance_esg_route(
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> PerformanceESGAdmin:
    performance = calculer_performance_esg(session, entreprises_perimetre_esg(session))
    return PerformanceESGAdmin(
        score_global_moyen=performance.score_global_moyen,
        score_environnement_moyen=performance.score_environnement_moyen,
        score_social_moyen=performance.score_social_moyen,
        score_gouvernance_moyen=performance.score_gouvernance_moyen,
        entreprises_avec_score=performance.entreprises_avec_score,
        entreprises_perimetre=performance.entreprises_perimetre,
        distribution=[
            TrancheScorePublic(
                borne_min=tranche.borne_min,
                borne_max=tranche.borne_max,
                nombre_entreprises=tranche.nombre_entreprises,
            )
            for tranche in performance.distribution
        ],
    )


@router.get(
    "/admin/portefeuilles",
    response_model=Page[PortefeuilleAdmin],
    operation_id="listPortfoliosAdmin",
    summary="Lister tous les portefeuilles non archivés, tous Investisseurs confondus",
)
def lister_portefeuilles_admin_route(
    recherche: str | None = Query(None, description="Filtre sur le nom du portefeuille ou l'e-mail"),
    page: int = Query(1, ge=1),
    page_size: int = Query(3, ge=1, le=50),
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> Page[PortefeuilleAdmin]:
    items, total = lister_portefeuilles_admin(session, recherche=recherche, page=page, page_size=page_size)
    return Page[PortefeuilleAdmin](
        items=[
            PortefeuilleAdmin(
                id=portefeuille.id,
                nom=portefeuille.name,
                investisseur_email=investisseur.email,
                devise_reference=portefeuille.reference_currency,
                nombre_positions=nombre_positions,
                montant_total=montant_total,
                date_creation=portefeuille.created_at,
            )
            for portefeuille, investisseur, nombre_positions, montant_total in items
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get(
    "/admin/analyses",
    response_model=Page[AnalyseAdmin],
    operation_id="listAnalysesAdmin",
    summary="Lister toutes les analyses Chercheur, filtrable par statut",
)
def lister_analyses_admin_route(
    statut: StatutAnalyse | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(3, ge=1, le=50),
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> Page[AnalyseAdmin]:
    items, total = lister_analyses_admin(session, statut=statut, page=page, page_size=page_size)
    return Page[AnalyseAdmin](
        items=[
            AnalyseAdmin(
                id=analyse.id,
                titre=analyse.titre,
                statut=analyse.statut,
                version=analyse.version,
                chercheur_email=chercheur_email,
                projet_nom=projet_nom,
                date_creation=analyse.date_creation,
                date_soumission=analyse.date_soumission,
                date_decision=analyse.date_decision,
            )
            for analyse, chercheur_email, projet_nom in items
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get(
    "/admin/projets",
    response_model=Page[ProjetAdmin],
    operation_id="listProjectsAdmin",
    summary="Lister tous les projets Institution, filtrable par statut",
)
def lister_projets_admin_route(
    statut: StatutProjet | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(3, ge=1, le=50),
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> Page[ProjetAdmin]:
    items, total = lister_projets_admin(session, statut=statut, page=page, page_size=page_size)
    return Page[ProjetAdmin](
        items=[
            ProjetAdmin(
                id=projet.id,
                nom=projet.nom,
                statut=projet.statut,
                institution_email=institution_email,
                nombre_chercheurs=nombre_chercheurs,
                date_creation=projet.date_creation,
                date_limite=projet.date_limite,
                date_cloture=projet.date_cloture,
            )
            for projet, institution_email, nombre_chercheurs in items
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


def _donnees_financieres(entreprise: Company) -> CompanyFinancials:
    return CompanyFinancials(
        company_id=entreprise.id,
        revenue=entreprise.revenue,
        revenue_currency=entreprise.revenue_currency,
        enterprise_value=entreprise.enterprise_value,
        enterprise_value_currency=entreprise.enterprise_value_currency,
        enterprise_value_as_of=entreprise.enterprise_value_as_of,
    )


@router.get(
    "/admin/companies/{company_id}/financials",
    response_model=CompanyFinancials,
    operation_id="getCompanyFinancials",
    summary="Données financières PCAF d'une entreprise (chiffre d'affaires, EVIC)",
)
def get_company_financials(
    company_id: uuid.UUID,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> CompanyFinancials:
    return _donnees_financieres(consulter_entreprise_admin(session, company_id))


@router.put(
    "/admin/companies/{company_id}/financials",
    response_model=CompanyFinancials,
    operation_id="updateCompanyFinancials",
    summary="Renseigner le chiffre d'affaires et l'EVIC d'une entreprise (PCAF)",
)
def update_company_financials(
    company_id: uuid.UUID,
    payload: CompanyFinancialsRequest,
    _current_user: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> CompanyFinancials:
    entreprise = modifier_donnees_financieres(session, company_id, payload.model_dump())
    return _donnees_financieres(entreprise)

