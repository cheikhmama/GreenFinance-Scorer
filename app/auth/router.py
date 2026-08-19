"""Routes HTTP d'authentification (connexion, déconnexion, profil courant).

Statut : Auth MVP — Étape 9 partielle. Périmètre de cette passe : login/logout
par mot de passe + JWT en cookie httpOnly, RBAC, limitation de débit. La MFA
(app/core/config.py, mfa_issuer_name), le CSRF et la révocation/rotation de
session restent délibérément hors périmètre ici pour débloquer le reste du
backend et le frontend sans attendre le flux complet — à compléter dans une
passe ultérieure, sans changer le contrat de get_current_user.
"""

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, select

from app.auth.hashing import verify_password
from app.auth.models import Utilisateur
from app.auth.rate_limit import (
    clear_login_attempts,
    enforce_login_rate_limit,
    register_failed_login_attempt,
)
from app.auth.schemas import LoginRequest, UtilisateurPublic
from app.auth.tokens import COOKIE_NAME, create_access_token
from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_session
from app.core.exceptions import UnauthorizedError

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=UtilisateurPublic)
def login(
    payload: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> Utilisateur:
    enforce_login_rate_limit(payload.email)

    user = session.exec(select(Utilisateur).where(Utilisateur.email == payload.email)).first()
    if user is None or not user.actif or not verify_password(payload.password, user.mot_de_passe_hache):
        register_failed_login_attempt(payload.email)
        raise UnauthorizedError("Identifiants invalides.", code="invalid_credentials")

    clear_login_attempts(payload.email)
    token = create_access_token(user.id, user.role)
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        max_age=12 * 60 * 60,
    )
    return user


@router.post("/auth/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


@router.get("/auth/me", response_model=UtilisateurPublic)
def me(current_user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    return current_user
