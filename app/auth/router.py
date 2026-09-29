"""Routes HTTP d'authentification (connexion, déconnexion, profil courant, changement de mot
de passe).

Statut : Phase 3 (durcissement de la session, voir app/auth/{tokens,revocation,csrf}.py) —
cookie __Host-, révocation Redis par génération de session, jeton CSRF signé. Le MFA reste hors
périmètre, réservé à une phase dédiée (app/core/config.py, mfa_issuer_name).
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, UploadFile
from sqlmodel import Session, select

from app.auth.activation import activer_compte
from app.auth.avatar import construire_avatar_data_uri
from app.auth.csrf import generate_csrf_token
from app.auth.email_change import confirmer_changement_email, demander_changement_email
from app.auth.hashing import hash_password, verify_password
from app.auth.models import User
from app.auth.password_reset import (
    demander_reinitialisation,
    reinitialiser_mot_de_passe,
)
from app.auth.rate_limit import (
    clear_login_attempts,
    enforce_login_rate_limit,
    register_failed_login_attempt,
)
from app.auth.revocation import current_generation, revoke_all_sessions
from app.auth.schemas import (
    ActiverCompteRequest,
    ChangerMotDePasseRequest,
    ConfirmerChangementEmailRequest,
    DemanderReinitialisationRequest,
    LoginRequest,
    ModifierProfilRequest,
    ReinitialiserMotDePasseRequest,
    UtilisateurPublic,
    VerifierMotDePasseRequest,
)
from app.auth.tokens import (
    ACCESS_TOKEN_TTL,
    COOKIE_NAME,
    CSRF_COOKIE_NAME,
    create_access_token,
)
from app.core.audit import auditer
from app.core.dependencies import get_current_user, get_session
from app.core.exceptions import UnauthorizedError

router = APIRouter(tags=["auth"])

_MAX_AGE = int(ACCESS_TOKEN_TTL.total_seconds())


def _ouvrir_session(response: Response, user: User, generation: int) -> None:
    """Pose les deux cookies de session (jeton d'accès + jeton CSRF), tous deux liés à la même
    génération de session (app/auth/revocation.py). __Host- exige Secure, Path=/ et aucun
    attribut Domain — Secure reste vrai même en développement local, où le navigateur traite
    localhost comme un contexte sécurisé (voir app/auth/tokens.py)."""
    token = create_access_token(user.id, user.role, generation=generation)
    csrf_token = generate_csrf_token(user.id, generation)

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=True,
        path="/",
        max_age=_MAX_AGE,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=True,
        path="/",
        max_age=_MAX_AGE,
    )


def _fermer_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.post(
    "/auth/login",
    response_model=UtilisateurPublic,
    operation_id="login",
    summary="Ouvrir une session par e-mail et mot de passe",
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> User:
    # IP fournie par le serveur ASGI, jamais lue dans un en-tête (voir app/auth/rate_limit.py).
    adresse_ip = request.client.host if request.client else None
    enforce_login_rate_limit(payload.email, adresse_ip)

    user = session.exec(select(User).where(User.email == payload.email)).first()
    if (
        user is None
        or not user.active
        or user.password_hash is None
        or not verify_password(payload.password, user.password_hash)
    ):
        register_failed_login_attempt(payload.email, adresse_ip)
        auditer(
            session,
            user.id if user else None,
            "connexion",
            "Utilisateur",
            user.id if user else None,
            "echec",
        )
        session.commit()
        raise UnauthorizedError("Identifiants invalides.", code="invalid_credentials")

    clear_login_attempts(payload.email)
    auditer(session, user.id, "connexion", "Utilisateur", user.id, "succes")
    session.commit()

    _ouvrir_session(response, user, current_generation(user.id))
    return user


@router.post(
    "/auth/mot-de-passe-oublie",
    status_code=204,
    operation_id="demanderReinitialisationMotDePasse",
    summary="Demander un lien de réinitialisation de mot de passe",
)
def mot_de_passe_oublie(
    payload: DemanderReinitialisationRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> None:
    demander_reinitialisation(session, payload.email, background_tasks)


@router.post(
    "/auth/reinitialiser-mot-de-passe",
    status_code=204,
    operation_id="reinitialiserMotDePasse",
    summary="Poser un nouveau mot de passe à partir d'un jeton de réinitialisation",
)
def reinitialiser_mot_de_passe_route(
    payload: ReinitialiserMotDePasseRequest,
    session: Session = Depends(get_session),
) -> None:
    reinitialiser_mot_de_passe(session, payload.token, payload.nouveau_mot_de_passe)


@router.post(
    "/auth/activer-compte",
    status_code=204,
    operation_id="activateAccount",
    summary="Poser son mot de passe et activer un compte à partir d'un jeton d'activation",
)
def activer_compte_route(
    payload: ActiverCompteRequest,
    session: Session = Depends(get_session),
) -> None:
    activer_compte(session, payload.token, payload.nouveau_mot_de_passe)


@router.post(
    "/auth/logout",
    status_code=204,
    operation_id="logout",
    summary="Fermer la session courante",
)
def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    revoke_all_sessions(current_user.id)
    auditer(session, current_user.id, "deconnexion", "Utilisateur", current_user.id, "succes")
    session.commit()
    _fermer_session(response)


@router.get(
    "/auth/me",
    response_model=UtilisateurPublic,
    operation_id="getCurrentUser",
    summary="Consulter le compte actuellement connecté",
)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch(
    "/auth/me",
    response_model=UtilisateurPublic,
    operation_id="updateMyProfile",
    summary="Modifier mon nom, et demander un changement d'e-mail",
)
def modifier_mon_profil(
    payload: ModifierProfilRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UtilisateurPublic:
    """Le nom change immédiatement. Un nouvel e-mail n'est qu'une DEMANDE (voir
    app/auth/email_change.py) : `email` reste l'ancienne adresse et `email_en_attente` indique où
    le lien de confirmation a été envoyé."""
    current_user.name = payload.nom
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    email_en_attente = None
    if payload.email != current_user.email:
        demander_changement_email(
            session, current_user, payload.email, payload.mot_de_passe_actuel, background_tasks
        )
        email_en_attente = payload.email

    return UtilisateurPublic.model_validate(current_user).model_copy(
        update={"email_en_attente": email_en_attente}
    )


@router.post(
    "/auth/confirmer-changement-email",
    response_model=UtilisateurPublic,
    operation_id="confirmEmailChange",
    summary="Confirmer un changement d'e-mail à partir du lien reçu à la nouvelle adresse",
)
def confirmer_changement_email_route(
    payload: ConfirmerChangementEmailRequest,
    session: Session = Depends(get_session),
) -> User:
    return confirmer_changement_email(session, payload.token)


@router.post(
    "/auth/me/avatar",
    response_model=UtilisateurPublic,
    operation_id="uploadMyAvatar",
    summary="Ajouter ou remplacer ma photo de profil",
)
def televerser_mon_avatar(
    fichier: UploadFile,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> User:
    contenu = fichier.file.read()
    current_user.avatar = construire_avatar_data_uri(contenu)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.delete(
    "/auth/me/avatar",
    response_model=UtilisateurPublic,
    operation_id="deleteMyAvatar",
    summary="Retirer ma photo de profil",
)
def supprimer_mon_avatar(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> User:
    current_user.avatar = None
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.post(
    "/auth/verifier-mot-de-passe",
    status_code=204,
    operation_id="verifyMyPassword",
    summary="Vérifier mon mot de passe actuel, sans rien modifier (étape 1 du changement)",
)
def verifier_mon_mot_de_passe(
    payload: VerifierMotDePasseRequest,
    current_user: User = Depends(get_current_user),
) -> None:
    # Même bac à sable de débit que la connexion : un attaquant en possession d'une session volée
    # ne connaît pas forcément le mot de passe, cette route ne doit pas devenir un oracle
    # illimité pour le deviner (voir app/auth/rate_limit.py).
    enforce_login_rate_limit(current_user.email)
    # Un compte authentifié a nécessairement déjà un mot de passe (login/activer-compte le
    # garantissent avant d'ouvrir une session) — jamais None ici.
    assert current_user.password_hash is not None
    if not verify_password(payload.mot_de_passe, current_user.password_hash):
        register_failed_login_attempt(current_user.email)
        raise UnauthorizedError("Mot de passe actuel invalide.", code="invalid_credentials")
    clear_login_attempts(current_user.email)


@router.post(
    "/auth/changer-mot-de-passe",
    response_model=UtilisateurPublic,
    operation_id="changePassword",
    summary="Changer son mot de passe et ouvrir une nouvelle session",
)
def changer_mot_de_passe(
    payload: ChangerMotDePasseRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> User:
    # Même limitation de débit que verifier_mon_mot_de_passe : sans elle, cette route vérifiant
    # elle aussi le mot de passe actuel en redevenait un oracle illimité.
    enforce_login_rate_limit(current_user.email)
    # Voir verifier_mon_mot_de_passe ci-dessus : jamais None pour un compte déjà authentifié.
    assert current_user.password_hash is not None
    if not verify_password(payload.mot_de_passe_actuel, current_user.password_hash):
        register_failed_login_attempt(current_user.email)
        raise UnauthorizedError("Mot de passe actuel invalide.", code="invalid_credentials")
    clear_login_attempts(current_user.email)

    current_user.password_hash = hash_password(payload.nouveau_mot_de_passe)
    session.add(current_user)
    auditer(
        session,
        current_user.id,
        "changement_mot_de_passe",
        "Utilisateur",
        current_user.id,
        "succes",
    )
    session.commit()
    session.refresh(current_user)

    # Révoque toute session existante (y compris celle qui vient de servir à cet appel), puis en
    # ouvre une nouvelle sur la génération résultante — jamais invalidée par sa propre
    # révocation, la comparaison portant sur une génération strictement inférieure.
    nouvelle_generation = revoke_all_sessions(current_user.id)
    _ouvrir_session(response, current_user, nouvelle_generation)
    return current_user
