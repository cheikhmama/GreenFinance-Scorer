"""Routes HTTP de l'espace Entreprise.

Statut : Étape 5/10 + Phase 4 §4.1/§4.2. Dépôt, liste, détail, nouvelle version (correction) —
la logique vit dans app/company/rapports.py (et app/company/upload_validation.py pour la
validation du fichier), ce router ne fait qu'appliquer le contrôle d'accès par rôle et l'appeler.

app/ingestion/ n'expose pas de router.py (voir ARCHITECTURE.md §2 : ingestion n'est pas une
surface API directe) — la logique appelée ici invoque directement app.ingestion.extractor.
"""

import uuid

import pydantic
from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.admin.kyc import controles_gleif
from app.auth.models import User
from app.auth.permissions import require_role
from app.company.import_rate_limit import enforce_url_import_rate_limit
from app.company.models import Company
from app.company.rapports import (
    creer_correction,
    deposer_rapport,
    importer_rapport_par_url,
    lister_mes_rapports,
    rapport_de_lentreprise,
)
from app.company.registration import (
    consulter_suivi,
    enregistrer_demande,
    repondre_demande_infos,
)
from app.company.schemas import (
    CompanyRegistrationRequest,
    EntreprisePublic,
    ImporterRapportParURLRequest,
    RegistrationStatusRequest,
    RegistrationStatusView,
    VerificationLei,
)
from app.company.upload_validation import TAILLE_MAX_MANDAT_OCTETS
from app.core import storage
from app.core.dependencies import get_session
from app.core.enums import KycCheckResult, ReportStatus, ReportType, Role
from app.core.exceptions import NotFoundError, ValidationError
from app.ingestion.models import ESGReport
from app.ingestion.schemas import RapportESGDetail, RapportESGPublic
from app.scoring.engine import score_public

router = APIRouter(tags=["company"])


def _demande_inscription(
    company_name: str = Form(),
    sector: str = Form(),
    country: str = Form(),
    contact_name: str = Form(),
    contact_email: str = Form(),
    isin: str | None = Form(default=None),
    lei: str | None = Form(default=None),
    website: str | None = Form(default=None),
    company_fax: str | None = Form(default=None),
) -> CompanyRegistrationRequest:
    """Champs à plat à côté de la lettre de mandat (tâche 5.2) ; CompanyRegistrationRequest reste
    la seule validation, ses erreurs une 422 par champ comme toute validation de requête."""
    try:
        return CompanyRegistrationRequest(
            company_name=company_name,
            sector=sector,
            country=country,
            contact_name=contact_name,
            contact_email=contact_email,
            isin=isin,
            lei=lei,
            website=website,
            company_fax=company_fax,
        )
    except pydantic.ValidationError as exc:
        raise RequestValidationError(exc.errors(include_url=False)) from exc


@router.post(
    "/companies/register",
    status_code=202,
    operation_id="registerCompany",
    summary="Demander l'inscription d'une entreprise (validation par l'Administrateur)",
    responses={
        202: {"description": "Demande reçue. Réponse identique que la demande aboutisse ou non."},
        429: {"description": "Limite de demandes par adresse IP atteinte."},
        503: {"description": "Envoi d'e-mails indisponible."},
    },
)
def register_company(
    request: Request,
    background_tasks: BackgroundTasks,
    mandate_letter: UploadFile,
    payload: CompanyRegistrationRequest = Depends(_demande_inscription),
    session: Session = Depends(get_session),
) -> None:
    # Lecture bornée : un fichier plus gros que la limite est refusé sans être lu en entier.
    contenu = mandate_letter.file.read(TAILLE_MAX_MANDAT_OCTETS + 1)
    enregistrer_demande(
        session, payload, contenu, request.client.host if request.client else None, background_tasks
    )


@router.post(
    "/companies/registration-status",
    response_model=RegistrationStatusView,
    operation_id="getRegistrationStatus",
    summary="Suivre une demande d'inscription (jeton reçu par e-mail)",
    responses={404: {"description": "Jeton inconnu ou remplacé par un plus récent."}},
)
def registration_status(
    payload: RegistrationStatusRequest, session: Session = Depends(get_session)
) -> RegistrationStatusView:
    return consulter_suivi(session, payload.token)


@router.post(
    "/companies/registration-status/reply",
    response_model=RegistrationStatusView,
    operation_id="replyToRegistrationInfoRequest",
    summary="Répondre à une demande d'informations : nouvelle lettre de mandat",
    responses={
        404: {"description": "Jeton inconnu ou remplacé par un plus récent."},
        429: {"description": "Limite d'envois par adresse IP atteinte."},
    },
)
def reply_to_registration_info_request(
    request: Request,
    mandate_letter: UploadFile,
    token: str = Form(min_length=20, max_length=200),
    message: str | None = Form(default=None, max_length=2000),
    session: Session = Depends(get_session),
) -> RegistrationStatusView:
    contenu = mandate_letter.file.read(TAILLE_MAX_MANDAT_OCTETS + 1)
    return repondre_demande_infos(
        session,
        token,
        contenu,
        (message or "").strip() or None,
        request.client.host if request.client else None,
    )


def _entreprise_id(current_user: User) -> uuid.UUID:
    if current_user.company is None:
        raise ValidationError(
            "Aucune entreprise n'est rattachée à ce compte.", code="entreprise_non_rattachee"
        )
    return current_user.company.id


@router.get(
    "/company/profil",
    response_model=EntreprisePublic,
    operation_id="getMyCompanyProfile",
    summary="Consulter la fiche de mon entreprise, telle que vue par les investisseurs",
)
def consulter_mon_profil_route(
    current_user: User = Depends(require_role(Role.ENTERPRISE)),
) -> Company:
    _entreprise_id(current_user)  # lève si aucune entreprise n'est rattachée
    assert current_user.company is not None
    return current_user.company


@router.get(
    "/company/lei-verification",
    response_model=VerificationLei,
    operation_id="getMyLeiVerification",
    summary="Vérifier en direct le LEI de mon entreprise auprès de la GLEIF",
)
def verifier_mon_lei_route(
    current_user: User = Depends(require_role(Role.ENTERPRISE)),
) -> VerificationLei:
    """Badge « GLEIF Validé » de l'en-tête Entreprise (tâche 5.9) : même contrôle que la fenêtre
    KYC de l'Administrateur (app/admin/kyc.py), refait à chaque appel, jamais stocké."""
    _entreprise_id(current_user)
    entreprise = current_user.company
    assert entreprise is not None
    controles = controles_gleif(entreprise)
    resultats = {controle.result for controle in controles}
    if resultats == {KycCheckResult.PASSED}:
        resultat = KycCheckResult.PASSED
    else:
        # Le plus parlant d'abord : un refus, puis une GLEIF muette, puis l'absence de LEI.
        resultat = next(
            r
            for r in (
                KycCheckResult.FAILED,
                KycCheckResult.NOT_VERIFIABLE,
                KycCheckResult.NOT_APPLICABLE,
            )
            if r in resultats
        )
    detail = " ".join(controle.detail for controle in controles if controle.result == resultat)
    return VerificationLei(lei=entreprise.lei, result=resultat, detail=detail)


@router.get(
    "/company/rapports",
    response_model=list[RapportESGPublic],
    operation_id="listCompanyReports",
    summary="Lister les rapports déposés par l'entreprise",
)
def lister_rapports_route(
    current_user: User = Depends(require_role(Role.ENTERPRISE)),
    session: Session = Depends(get_session),
) -> list[ESGReport]:
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
    type: ReportType = Form(...),
    annee_reporting: int = Form(...),
    current_user: User = Depends(require_role(Role.ENTERPRISE)),
    session: Session = Depends(get_session),
) -> ESGReport:
    contenu = fichier.file.read()
    return deposer_rapport(
        session,
        background_tasks,
        _entreprise_id(current_user),
        contenu,
        type,
        annee_reporting,
        fichier.filename,
    )


@router.post(
    "/company/rapports/import-url",
    response_model=RapportESGPublic,
    status_code=201,
    operation_id="importCompanyReportFromURL",
    summary="Importer un rapport ESG/climat depuis une URL (canal automatique)",
)
def importer_rapport_par_url_route(
    background_tasks: BackgroundTasks,
    payload: ImporterRapportParURLRequest,
    current_user: User = Depends(require_role(Role.ENTERPRISE, Role.ADMIN)),
    session: Session = Depends(get_session),
) -> ESGReport:
    if current_user.role == Role.ENTERPRISE:
        # Un entreprise_id fourni par un appelant Entreprise est toujours ignoré -- jamais fait
        # confiance à un client pour désigner une entreprise autre que la sienne.
        entreprise_id = _entreprise_id(current_user)
    else:
        if payload.company_id is None:
            raise ValidationError(
                "entreprise_id est requis pour un import déclenché par un administrateur.",
                code="entreprise_id_requis",
            )
        if session.get(Company, payload.company_id) is None:
            raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
        entreprise_id = payload.company_id

    enforce_url_import_rate_limit(entreprise_id)
    return importer_rapport_par_url(
        session,
        background_tasks,
        entreprise_id,
        payload.url,
        payload.type,
        payload.fiscal_year,
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
    current_user: User = Depends(require_role(Role.ENTERPRISE)),
    session: Session = Depends(get_session),
) -> ESGReport:
    contenu = fichier.file.read()
    return creer_correction(
        session,
        background_tasks,
        rapport_id,
        _entreprise_id(current_user),
        contenu,
        annee_reporting,
        fichier.filename,
    )


@router.get(
    "/company/rapports/{rapport_id}",
    response_model=RapportESGDetail,
    operation_id="getCompanyReport",
    summary="Consulter le détail d'un rapport déposé par l'entreprise",
)
def consulter_rapport(
    rapport_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.ENTERPRISE)),
    session: Session = Depends(get_session),
) -> RapportESGDetail:
    rapport = rapport_de_lentreprise(session, rapport_id, _entreprise_id(current_user))
    detail = RapportESGDetail.model_validate(rapport)
    if rapport.submitted_at is None:
        # Brouillon analysé (tâche 5.8) : la liste de complétude donne des comptes, jamais les
        # valeurs extraites ni le score auto-déclaré relu — rien qui invite à ajuster le fichier
        # à un résultat avant de soumettre.
        return detail.model_copy(
            update={
                "metrics": [],
                "carbon_data": [],
                "declared_global_score": None,
                "declared_global_score_proof": None,
            }
        )
    if rapport.status != ReportStatus.VALIDATED:
        # Pendant l'examen, l'Entreprise ne voit pas l'avancement de la revue (tâches 5.1, 5.6).
        sans_revue = {"review_status": None, "audited_value": None}
        detail = detail.model_copy(
            update={
                "metrics": [m.model_copy(update=sans_revue) for m in detail.metrics],
                "carbon_data": [d.model_copy(update=sans_revue) for d in detail.carbon_data],
            }
        )
    return detail.model_copy(update={"official_score": score_public(session, rapport_id)})


@router.get(
    "/company/rapports/{rapport_id}/fichier",
    operation_id="getCompanyReportOriginalFile",
    summary="Télécharger le PDF original tel que déposé (non le rapport de synthèse)",
)
def telecharger_rapport_original_route(
    rapport_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.ENTERPRISE)),
    session: Session = Depends(get_session),
) -> FileResponse:
    rapport = rapport_de_lentreprise(session, rapport_id, _entreprise_id(current_user))
    if rapport.source_file is None:
        raise NotFoundError("Ce rapport n'a pas encore de fichier.", code="fichier_absent")
    return FileResponse(storage.resolve_path(rapport.source_file), media_type="application/pdf")


@router.get(
    "/company/rapports/{rapport_id}/synthese/fichier",
    operation_id="getCompanyReportSynthesisFile",
    summary="Télécharger le rapport de synthèse généré par la plateforme",
)
def telecharger_rapport_synthese_route(
    rapport_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.ENTERPRISE)),
    session: Session = Depends(get_session),
) -> FileResponse:
    rapport = rapport_de_lentreprise(session, rapport_id, _entreprise_id(current_user))
    if rapport.synthesis_report_path is None:
        # Code distinct de "rapport introuvable" -- sûr à distinguer ici, la propriété est déjà
        # établie par rapport_de_lentreprise ci-dessus, donc cela ne confirme rien à un tiers.
        raise NotFoundError(
            "Le rapport de synthèse n'a pas encore été généré pour ce rapport.",
            code="synthese_non_generee",
        )
    return FileResponse(
        storage.resolve_path(rapport.synthesis_report_path), media_type="application/pdf"
    )
