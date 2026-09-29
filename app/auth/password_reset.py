"""Flux « mot de passe oublié » en libre-service.

Les liens sont envoyés par SMTP après la réponse HTTP : la latence et les erreurs du relais
ne doivent pas révéler si une adresse correspond à un compte. La configuration est vérifiée
avant toute recherche de compte et produit la même erreur 503 pour toutes les adresses.
Le jeton n'apparaît jamais dans les journaux ni dans une réponse HTTP.

Le jeton en clair n'est jamais persisté (voir app/auth/models.py::PasswordResetToken) :
seule son empreinte SHA-256 l'est. Un hachage rapide suffit ici, contrairement au mot de passe
(bcrypt) — l'entropie du jeton (32 octets aléatoires) rend une attaque par force brute sur
l'empreinte impraticable, ce qui est le vrai facteur de sécurité, pas le coût du hachage.
"""

import hashlib
import secrets
from collections.abc import Callable
from datetime import timedelta
from typing import TypeVar

import redis
import structlog
from fastapi import BackgroundTasks
from sqlmodel import Session, col, select

from app.auth.hashing import hash_password
from app.auth.models import PasswordResetToken, User
from app.auth.revocation import revoke_all_sessions
from app.core.audit import auditer
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.email import EmailDeliveryError, ensure_email_configured, send_email
from app.core.exceptions import (
    ServiceUnavailableError,
    TooManyRequestsError,
    ValidationError,
)
from app.core.redis import get_redis_client, incrementer_fenetre

logger = structlog.get_logger(__name__)

TOKEN_TTL = timedelta(minutes=30)

# Même discipline anti-brute-force que app/auth/rate_limit.py, mais bornée à la demande d'un
# nouveau lien plutôt qu'à une tentative de connexion : au-delà, un compte cible verrait sa boîte
# inondée de liens sans qu'aucun ne soit jamais utilisé.
_RATE_LIMIT_MAX = 3
_RATE_LIMIT_WINDOW_SECONDS = 60 * 60

T = TypeVar("T")


def _rate_limit_key(email: str) -> str:
    return f"password_reset_requests:{email.strip().lower()}"


def _guarded(operation: str, call: Callable[[], T]) -> T:
    try:
        return call()
    except redis.RedisError as exc:
        logger.error(
            "password_reset_rate_limit_backend_unavailable",
            operation=operation,
            error_type=type(exc).__name__,
        )
        raise ServiceUnavailableError(
            "Service de réinitialisation temporairement indisponible. Réessayez plus tard."
        ) from exc


def _hash_token(jeton_clair: str) -> str:
    return hashlib.sha256(jeton_clair.encode()).hexdigest()


def _construire_lien(jeton_clair: str) -> str:
    base_url = get_settings().frontend_base_url.rstrip("/")
    return f"{base_url}/reinitialiser-mot-de-passe?token={jeton_clair}"


def _envoyer_lien(email: str, jeton_clair: str) -> None:
    try:
        send_email(
            recipient=email,
            subject="Réinitialisez votre mot de passe GreenFinance-Scorer",
            body=(
                "Vous avez demandé un nouveau mot de passe pour GreenFinance-Scorer.\n\n"
                f"{_construire_lien(jeton_clair)}\n\n"
                "Ce lien est valable 30 minutes et ne peut être utilisé qu'une fois.\n"
                "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail.\n"
            ),
        )
    except EmailDeliveryError as exc:
        # La réponse est déjà partie : aucun statut ou délai SMTP ne dépend du compte.
        # Ne jamais ajouter l'adresse, le message, le jeton ou la trace SMTP aux logs.
        logger.error("password_reset_delivery_failed", error_type=type(exc.__cause__ or exc).__name__)


def demander_reinitialisation(
    session: Session, email: str, background_tasks: BackgroundTasks
) -> None:
    """Étape 1 — ne révèle jamais si l'e-mail correspond à un compte existant : l'appelant reçoit
    le même 204, que le compte existe ou non (voir app/auth/router.py), si le service est
    configuré et la limite de demandes n'est pas atteinte. Un compte
    désactivé n'obtient pas de lien non plus (cohérent avec login, qui refuse aussi actif=False).

    Le compteur de débit s'incrémente pour toute adresse, y compris inconnue — sinon un 429
    n'apparaissant que pour une adresse existante deviendrait lui-même un moyen de deviner quels
    comptes existent, exactement le canal que le 204 uniforme ci-dessus cherche à fermer."""
    try:
        ensure_email_configured()
    except EmailDeliveryError as exc:
        raise ServiceUnavailableError(
            "Service de réinitialisation temporairement indisponible. Réessayez plus tard."
        ) from exc
    email_normalise = email.strip().lower()
    attempts = _guarded("get", lambda: get_redis_client().get(_rate_limit_key(email_normalise)))
    if attempts is not None and int(attempts) >= _RATE_LIMIT_MAX:
        raise TooManyRequestsError(
            "Trop de demandes de réinitialisation pour cette adresse. Réessayez plus tard."
        )

    _guarded(
        "incr",
        lambda: incrementer_fenetre(
            get_redis_client(), _rate_limit_key(email_normalise), _RATE_LIMIT_WINDOW_SECONDS
        ),
    )

    user = session.exec(
        select(User).where(col(User.email) == email_normalise)
    ).first()
    # Un compte jamais activé (app/auth/activation.py) n'a pas de mot de passe à réinitialiser —
    # doit passer par son lien d'activation, pas par ce flux ; même réponse uniforme que "compte
    # inconnu", pour ne rien révéler.
    if user is None or not user.active or user.password_hash is None:
        return

    # Un nouveau lien invalide les précédents, encore valides ou non — jamais plus d'un lien
    # utilisable à la fois pour un même compte.
    anciens = session.exec(
        select(PasswordResetToken).where(
            col(PasswordResetToken.user_id) == user.id,
            col(PasswordResetToken.used_at).is_(None),
        )
    ).all()
    for ancien in anciens:
        session.delete(ancien)

    jeton_clair = secrets.token_urlsafe(32)
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(jeton_clair),
            expires_at=utcnow() + TOKEN_TTL,
        )
    )
    auditer(session, user.id, "demande_reinitialisation_mot_de_passe", "Utilisateur", user.id, "succes")
    session.commit()

    background_tasks.add_task(_envoyer_lien, user.email, jeton_clair)


def reinitialiser_mot_de_passe(session: Session, jeton_clair: str, nouveau_mot_de_passe: str) -> None:
    """Étape 2 — consomme le jeton, pose le nouveau mot de passe et révoque toute session déjà
    ouverte (même geste que app/auth/router.py::changer_mot_de_passe, mais sans en rouvrir une :
    contrairement au changement authentifié, personne n'est encore identifié comme le titulaire
    légitime de la session côté navigateur ici)."""
    jeton_hache = _hash_token(jeton_clair)
    entree = session.exec(
        select(PasswordResetToken).where(
            col(PasswordResetToken.token_hash) == jeton_hache
        )
    ).first()

    if (
        entree is None
        or entree.used_at is not None
        or entree.expires_at < utcnow()
    ):
        raise ValidationError("Ce lien de réinitialisation est invalide ou a expiré.", code="jeton_invalide")

    user = session.get(User, entree.user_id)
    if user is None or not user.active or user.password_hash is None:
        raise ValidationError("Ce lien de réinitialisation est invalide ou a expiré.", code="jeton_invalide")

    entree.used_at = utcnow()
    user.password_hash = hash_password(nouveau_mot_de_passe)
    session.add(entree)
    session.add(user)
    auditer(
        session, user.id, "reinitialisation_mot_de_passe", "Utilisateur", user.id, "succes"
    )
    session.commit()

    revoke_all_sessions(user.id)
