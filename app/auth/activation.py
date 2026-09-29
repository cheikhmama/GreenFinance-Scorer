"""Flux d'activation d'un compte provisionné par l'Administrateur.

Miroir de app/auth/password_reset.py, pour la première connexion plutôt qu'un mot de passe
oublié : aucun mot de passe n'est jamais généré ni transmis par l'Administrateur
(app/admin/utilisateurs.py::creer_utilisateur) — un lien d'activation à usage unique, envoyé par
SMTP, permet à la personne titulaire du compte de poser elle-même son mot de passe.

Le jeton en clair n'est jamais persisté (voir app/auth/models.py::AccountActivationToken) : seule son
empreinte SHA-256 l'est, même raisonnement que password_reset.py (l'entropie du jeton rend une
attaque par force brute sur l'empreinte impraticable).
"""

import hashlib
import secrets
from datetime import timedelta

import structlog
from fastapi import BackgroundTasks
from sqlmodel import Session, col, select

from app.auth.hashing import hash_password
from app.auth.models import AccountActivationToken, User
from app.core.audit import auditer
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.email import EmailDeliveryError, send_email
from app.core.exceptions import ValidationError

logger = structlog.get_logger(__name__)

# Plus long que password_reset.py::TOKEN_TTL (30 minutes) : une invitation à activer un compte
# n'a pas l'urgence sécuritaire d'un mot de passe oublié, elle doit laisser le temps à la personne
# de la voir passer dans sa boîte de réception.
ACTIVATION_TOKEN_TTL = timedelta(days=7)


def _hash_token(jeton_clair: str) -> str:
    return hashlib.sha256(jeton_clair.encode()).hexdigest()


def _construire_lien(jeton_clair: str) -> str:
    base_url = get_settings().frontend_base_url.rstrip("/")
    return f"{base_url}/activer-compte?token={jeton_clair}"


def _envoyer_lien(email: str, jeton_clair: str) -> None:
    try:
        send_email(
            recipient=email,
            subject="Activez votre compte GreenFinance-Scorer",
            body=(
                "Un compte GreenFinance-Scorer a été créé pour vous.\n\n"
                f"{_construire_lien(jeton_clair)}\n\n"
                f"Ce lien est valable {ACTIVATION_TOKEN_TTL.days} jours et ne peut être utilisé "
                "qu'une fois. Il vous permettra de choisir votre mot de passe.\n"
            ),
        )
    except EmailDeliveryError as exc:
        # Ne jamais ajouter l'adresse, le message, le jeton ou la trace SMTP aux logs — même
        # politique que password_reset.py::_envoyer_lien.
        logger.error("activation_delivery_failed", error_type=type(exc.__cause__ or exc).__name__)


def envoyer_lien_activation(
    session: Session, utilisateur: User, background_tasks: BackgroundTasks
) -> None:
    """Émet un nouveau lien d'activation — appelée à la fois à la création du compte
    (app/admin/utilisateurs.py::creer_utilisateur) et pour un renvoi (renvoyer_lien_activation).

    Un nouveau lien invalide les précédents, encore valides ou non — jamais plus d'un lien
    utilisable à la fois pour un même compte (même règle que password_reset.py).

    Ne commite pas (tâche 1.4) : l'appelant commite le jeton avec le reste de son geste — création
    du compte, renvoi, ou validation d'une inscription — pour qu'un lien ne parte jamais pour un
    changement qui n'aurait pas été enregistré. L'envoi est une tâche de fond, exécutée après la
    réponse, donc après ce commit."""
    anciens = session.exec(
        select(AccountActivationToken).where(
            col(AccountActivationToken.user_id) == utilisateur.id,
            col(AccountActivationToken.used_at).is_(None),
        )
    ).all()
    for ancien in anciens:
        session.delete(ancien)

    jeton_clair = secrets.token_urlsafe(32)
    session.add(
        AccountActivationToken(
            user_id=utilisateur.id,
            token_hash=_hash_token(jeton_clair),
            expires_at=utcnow() + ACTIVATION_TOKEN_TTL,
        )
    )
    session.flush()

    background_tasks.add_task(_envoyer_lien, utilisateur.email, jeton_clair)


def activer_compte(session: Session, jeton_clair: str, nouveau_mot_de_passe: str) -> User:
    """Consomme le jeton, pose le mot de passe choisi et active le compte — aucune session n'est
    ouverte ici (même choix que password_reset.py::reinitialiser_mot_de_passe), l'utilisateur se
    connecte ensuite normalement."""
    jeton_hache = _hash_token(jeton_clair)
    entree = session.exec(
        select(AccountActivationToken).where(col(AccountActivationToken.token_hash) == jeton_hache)
    ).first()

    if entree is None or entree.used_at is not None or entree.expires_at < utcnow():
        raise ValidationError("Ce lien d'activation est invalide ou a expiré.", code="jeton_invalide")

    user = session.get(User, entree.user_id)
    if user is None or not user.active or user.activated_at is not None:
        raise ValidationError("Ce lien d'activation est invalide ou a expiré.", code="jeton_invalide")

    entree.used_at = utcnow()
    user.password_hash = hash_password(nouveau_mot_de_passe)
    user.activated_at = utcnow()
    session.add(entree)
    session.add(user)
    auditer(session, user.id, "activation_compte", "Utilisateur", user.id, "succes")
    session.commit()
    session.refresh(user)
    return user
