"""Flux d'activation d'un compte provisionné par l'Administrateur.

Miroir de app/auth/password_reset.py, pour la première connexion plutôt qu'un mot de passe
oublié : aucun mot de passe n'est jamais généré ni transmis par l'Administrateur
(app/admin/utilisateurs.py::creer_utilisateur) — un lien d'activation à usage unique, envoyé par
SMTP, permet à la personne titulaire du compte de poser elle-même son mot de passe.

Le jeton en clair n'est jamais persisté (voir app/auth/models.py::ActivationCompte) : seule son
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
from app.auth.models import ActivationCompte, Utilisateur
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
    session: Session, utilisateur: Utilisateur, background_tasks: BackgroundTasks
) -> None:
    """Émet un nouveau lien d'activation — appelée à la fois à la création du compte
    (app/admin/utilisateurs.py::creer_utilisateur) et pour un renvoi (renvoyer_lien_activation).

    Un nouveau lien invalide les précédents, encore valides ou non — jamais plus d'un lien
    utilisable à la fois pour un même compte (même règle que password_reset.py)."""
    anciens = session.exec(
        select(ActivationCompte).where(
            col(ActivationCompte.utilisateur_id) == utilisateur.id,
            col(ActivationCompte.utilise_le).is_(None),
        )
    ).all()
    for ancien in anciens:
        session.delete(ancien)

    jeton_clair = secrets.token_urlsafe(32)
    session.add(
        ActivationCompte(
            utilisateur_id=utilisateur.id,
            jeton_hache=_hash_token(jeton_clair),
            date_expiration=utcnow() + ACTIVATION_TOKEN_TTL,
        )
    )
    session.commit()

    background_tasks.add_task(_envoyer_lien, utilisateur.email, jeton_clair)


def activer_compte(session: Session, jeton_clair: str, nouveau_mot_de_passe: str) -> Utilisateur:
    """Consomme le jeton, pose le mot de passe choisi et active le compte — aucune session n'est
    ouverte ici (même choix que password_reset.py::reinitialiser_mot_de_passe), l'utilisateur se
    connecte ensuite normalement."""
    jeton_hache = _hash_token(jeton_clair)
    entree = session.exec(
        select(ActivationCompte).where(col(ActivationCompte.jeton_hache) == jeton_hache)
    ).first()

    if entree is None or entree.utilise_le is not None or entree.date_expiration < utcnow():
        raise ValidationError("Ce lien d'activation est invalide ou a expiré.", code="jeton_invalide")

    user = session.get(Utilisateur, entree.utilisateur_id)
    if user is None or not user.actif or user.date_activation is not None:
        raise ValidationError("Ce lien d'activation est invalide ou a expiré.", code="jeton_invalide")

    entree.utilise_le = utcnow()
    user.mot_de_passe_hache = hash_password(nouveau_mot_de_passe)
    user.date_activation = utcnow()
    session.add(entree)
    session.add(user)
    auditer(session, user.id, "activation_compte", "Utilisateur", user.id, "succes")
    session.commit()
    session.refresh(user)
    return user
