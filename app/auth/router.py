"""Routes HTTP d'authentification (connexion, déconnexion, profil courant, changement de mot
de passe).

Statut : Phase 3 (durcissement de la session, voir app/auth/{tokens,revocation,csrf}.py) —
cookie __Host-, révocation Redis par génération de session, jeton CSRF signé, garde
doit_changer_mot_de_passe. Le MFA reste hors périmètre, réservé à une phase dédiée
(app/core/config.py, mfa_issuer_name).
"""

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, select

from app.auth.csrf import generate_csrf_token
from app.auth.hashing import hash_password, verify_password
from app.auth.models import Utilisateur
from app.auth.rate_limit import (
    clear_login_attempts,
    enforce_login_rate_limit,
    register_failed_login_attempt,
)
from app.auth.revocation import current_generation, revoke_all_sessions
from app.auth.schemas import ChangerMotDePasseRequest, LoginRequest, UtilisateurPublic
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


def _ouvrir_session(response: Response, user: Utilisateur, generation: int) -> None:
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
    response: Response,
    session: Session = Depends(get_session),
) -> Utilisateur:
    enforce_login_rate_limit(payload.email)

    user = session.exec(select(Utilisateur).where(Utilisateur.email == payload.email)).first()
    if user is None or not user.actif or not verify_password(payload.password, user.mot_de_passe_hache):
        register_failed_login_attempt(payload.email)
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
    "/auth/logout",
    status_code=204,
    operation_id="logout",
    summary="Fermer la session courante",
)
def logout(
    response: Response,
    current_user: Utilisateur = Depends(get_current_user),
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
def me(current_user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    return current_user


@router.post(
    "/auth/changer-mot-de-passe",
    response_model=UtilisateurPublic,
    operation_id="changePassword",
    summary="Changer son mot de passe et ouvrir une nouvelle session",
)
def changer_mot_de_passe(
    payload: ChangerMotDePasseRequest,
    response: Response,
    current_user: Utilisateur = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Utilisateur:
    if not verify_password(payload.mot_de_passe_actuel, current_user.mot_de_passe_hache):
        raise UnauthorizedError("Mot de passe actuel invalide.", code="invalid_credentials")

    current_user.mot_de_passe_hache = hash_password(payload.nouveau_mot_de_passe)
    current_user.doit_changer_mot_de_passe = False
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
