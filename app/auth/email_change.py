"""Changement d'e-mail confirmé par la nouvelle adresse (tâche 1.2, revue du 2026-09-28).

L'e-mail est l'identifiant de connexion : le changer sur la seule foi d'une session permettait à
qui détenait une session volée de mettre sa propre adresse, puis de prendre le compte via « mot de
passe oublié ». Désormais :

1. demander_changement_email exige le mot de passe actuel (même limitation de débit que la
   connexion, jamais un oracle illimité), enregistre la demande et envoie un lien à la NOUVELLE
   adresse — l'e-mail du compte ne change pas encore — et prévient l'ancienne adresse.
2. confirmer_changement_email applique le changement quand ce lien est ouvert.

Mêmes garanties que password_reset.py et activation.py : seule l'empreinte SHA-256 du jeton est
persistée, usage unique, expiration, une seule demande en cours par compte, et ni l'adresse ni le
jeton ne sont jamais journalisés.
"""

import hashlib
import secrets
from datetime import timedelta

import structlog
from fastapi import BackgroundTasks
from sqlmodel import Session, col, select

from app.auth.hashing import verify_password
from app.auth.models import EmailChangeRequest, User
from app.auth.rate_limit import (
    clear_login_attempts,
    enforce_login_rate_limit,
    register_failed_login_attempt,
)
from app.core.audit import auditer
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.email import EmailDeliveryError, ensure_email_configured, send_email
from app.core.exceptions import (
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)

logger = structlog.get_logger(__name__)

TOKEN_TTL = timedelta(hours=24)


def _hash_token(jeton_clair: str) -> str:
    return hashlib.sha256(jeton_clair.encode()).hexdigest()


def _construire_lien(jeton_clair: str) -> str:
    base_url = get_settings().frontend_base_url.rstrip("/")
    return f"{base_url}/confirmer-email?token={jeton_clair}"


def _envoyer_lien(nouvel_email: str, jeton_clair: str) -> None:
    try:
        send_email(
            recipient=nouvel_email,
            subject="Confirmez votre nouvelle adresse GreenFinance-Scorer",
            body=(
                "Vous avez demandé à utiliser cette adresse pour votre compte GreenFinance-Scorer."
                f"\n\n{_construire_lien(jeton_clair)}\n\n"
                f"Ce lien est valable {int(TOKEN_TTL.total_seconds() // 3600)} heures et ne peut "
                "être utilisé qu'une fois. Tant qu'il n'est pas ouvert, votre adresse actuelle "
                "reste celle du compte.\n"
            ),
        )
    except EmailDeliveryError as exc:
        # Jamais l'adresse, le message, le jeton ni la trace SMTP dans les logs.
        logger.error("email_change_delivery_failed", error_type=type(exc.__cause__ or exc).__name__)


def _prevenir_ancienne_adresse(ancien_email: str) -> None:
    try:
        send_email(
            recipient=ancien_email,
            subject="Changement d'adresse demandé sur votre compte GreenFinance-Scorer",
            body=(
                "Un changement de l'adresse e-mail de votre compte GreenFinance-Scorer vient "
                "d'être demandé. Il ne prendra effet que lorsque le lien envoyé à la nouvelle "
                "adresse sera ouvert.\n\nSi vous n'êtes pas à l'origine de cette demande, "
                "changez votre mot de passe sans attendre.\n"
            ),
        )
    except EmailDeliveryError as exc:
        logger.error("email_change_notice_failed", error_type=type(exc.__cause__ or exc).__name__)


def _email_pris(session: Session, email: str, sauf_user_id: object) -> bool:
    existant = session.exec(select(User).where(col(User.email) == email)).first()
    return existant is not None and existant.id != sauf_user_id


def demander_changement_email(
    session: Session,
    user: User,
    nouvel_email: str,
    mot_de_passe_actuel: str | None,
    background_tasks: BackgroundTasks,
) -> None:
    """`nouvel_email` est déjà normalisé (app/auth/schemas.py::EmailNormalise). Ne commite pas
    le changement d'adresse lui-même — seulement la demande."""
    if not mot_de_passe_actuel:
        raise ValidationError(
            "Le mot de passe actuel est requis pour changer d'adresse e-mail.",
            code="mot_de_passe_requis",
        )
    enforce_login_rate_limit(user.email)
    # Un compte authentifié a nécessairement déjà un mot de passe (login/activer-compte le
    # garantissent avant d'ouvrir une session).
    assert user.password_hash is not None
    if not verify_password(mot_de_passe_actuel, user.password_hash):
        register_failed_login_attempt(user.email)
        raise UnauthorizedError("Mot de passe actuel invalide.", code="invalid_credentials")
    clear_login_attempts(user.email)

    try:
        ensure_email_configured()
    except EmailDeliveryError as exc:
        raise ServiceUnavailableError(
            "Service d'envoi temporairement indisponible. Réessayez plus tard."
        ) from exc
    if _email_pris(session, nouvel_email, user.id):
        raise ValidationError("Un compte existe déjà avec cet e-mail.", code="email_deja_utilise")

    for ancienne in session.exec(
        select(EmailChangeRequest).where(
            col(EmailChangeRequest.user_id) == user.id,
            col(EmailChangeRequest.used_at).is_(None),
        )
    ).all():
        session.delete(ancienne)

    jeton_clair = secrets.token_urlsafe(32)
    session.add(
        EmailChangeRequest(
            user_id=user.id,
            new_email=nouvel_email,
            token_hash=_hash_token(jeton_clair),
            expires_at=utcnow() + TOKEN_TTL,
        )
    )
    auditer(session, user.id, "demande_changement_email", "Utilisateur", user.id, "succes")
    session.commit()

    background_tasks.add_task(_envoyer_lien, nouvel_email, jeton_clair)
    background_tasks.add_task(_prevenir_ancienne_adresse, user.email)


def confirmer_changement_email(session: Session, jeton_clair: str) -> User:
    """Applique le changement. L'unicité est revérifiée ici : l'adresse a pu être prise par un
    autre compte entre la demande et la confirmation."""
    entree = session.exec(
        select(EmailChangeRequest).where(
            col(EmailChangeRequest.token_hash) == _hash_token(jeton_clair)
        )
    ).first()
    if entree is None or entree.used_at is not None or entree.expires_at < utcnow():
        raise ValidationError("Ce lien de confirmation est invalide ou a expiré.", code="jeton_invalide")

    user = session.get(User, entree.user_id)
    if user is None or not user.active:
        raise ValidationError("Ce lien de confirmation est invalide ou a expiré.", code="jeton_invalide")
    if _email_pris(session, entree.new_email, user.id):
        raise ValidationError("Un compte existe déjà avec cet e-mail.", code="email_deja_utilise")

    ancien_email = user.email
    user.email = entree.new_email
    entree.used_at = utcnow()
    session.add(user)
    session.add(entree)
    auditer(
        session,
        user.id,
        "modification_email",
        "Utilisateur",
        user.id,
        "succes",
        ancienne_valeur=ancien_email,
        nouvelle_valeur=entree.new_email,
    )
    session.commit()
    session.refresh(user)
    return user
