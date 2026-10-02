"""Vérification de l'adresse d'un demandeur d'inscription (tâche 5.11).

Une demande d'inscription n'est transmise à l'Administrateur qu'une fois l'adresse professionnelle
confirmée : un code à 6 chiffres part à cette adresse, le demandeur le saisit.

- Le code n'est jamais stocké en clair : empreinte HMAC-SHA256 (clé du serveur, liée à la
  demande) ; 30 minutes de validité ; 5 essais, après quoi il faut en redemander un.
- Une seule réponse pour tout échec (adresse inconnue, code faux, expiré, épuisé) : rien ne dit
  si une adresse a une demande en cours.
- Limites par adresse IP sur la vérification et le renvoi ; un renvoi au plus par minute.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

import redis
import structlog
from fastapi import BackgroundTasks
from sqlmodel import Session, col, select

from app.auth.models import User
from app.company.models import Company
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.email import EmailDeliveryError, envoyer_email_differe
from app.core.enums import RegistrationStatus
from app.core.exceptions import (
    ServiceUnavailableError,
    TooManyRequestsError,
    ValidationError,
)
from app.core.redis import get_redis_client, incrementer_fenetre

logger = structlog.get_logger(__name__)

VALIDITE = timedelta(minutes=30)
MAX_ESSAIS = 5
DELAI_ENTRE_ENVOIS = timedelta(seconds=60)
MAX_VERIFICATIONS_PAR_IP = 20
MAX_RENVOIS_PAR_IP = 5
FENETRE_SECONDES = 60 * 60

CODE_INVALIDE = "Code invalide ou expiré. Vérifiez-le, ou demandez-en un nouveau."


def _limiter(adresse_ip: str | None, prefixe: str, maximum: int) -> None:
    cle = f"{prefixe}:{hashlib.sha256((adresse_ip or 'inconnue').encode()).hexdigest()}"
    try:
        essais = incrementer_fenetre(get_redis_client(), cle, FENETRE_SECONDES)
    except redis.RedisError as exc:
        logger.error("registration_email_rate_limit_unavailable", error_type=type(exc).__name__)
        raise ServiceUnavailableError(
            "Le service d'inscription est temporairement indisponible. Réessayez plus tard."
        ) from exc
    if essais > maximum:
        raise TooManyRequestsError("Trop de tentatives. Réessayez dans une heure.")


def _empreinte(entreprise: Company, code: str) -> str:
    cle = get_settings().secret_key.encode()
    return hmac.new(cle, f"{entreprise.id}:{code}".encode(), hashlib.sha256).hexdigest()


def emettre_code(entreprise: Company) -> str:
    """Nouveau code pour cette demande (le précédent cesse de valoir) ; renvoyé en clair, à
    n'envoyer que par e-mail. Ne commite pas."""
    code = f"{secrets.randbelow(10**6):06d}"
    maintenant = utcnow()
    entreprise.email_verification_code_hash = _empreinte(entreprise, code)
    entreprise.email_verification_sent_at = maintenant
    entreprise.email_verification_expires_at = maintenant + VALIDITE
    entreprise.email_verification_attempts = 0
    return code


def envoyer_code(email: str, nom_entreprise: str, code: str) -> None:
    try:
        envoyer_email_differe(
            recipient=email,
            subject=f"Votre code de vérification : {code} — GreenFinance-Scorer",
            body=(
                f"Pour confirmer la demande d'inscription de {nom_entreprise}, saisissez ce code "
                "sur la page d'inscription :\n\n"
                f"    {code}\n\n"
                f"Il est valable {int(VALIDITE.total_seconds() // 60)} minutes. Si vous n'êtes pas à "
                "l'origine de cette demande, ignorez ce message.\n"
            ),
        )
    except EmailDeliveryError as exc:
        # Jamais l'adresse ni le code dans les journaux.
        logger.error("registration_code_email_failed", error_type=type(exc.__cause__ or exc).__name__)


def _demande_a_verifier(session: Session, email: str) -> Company | None:
    titulaire = session.exec(select(User).where(col(User.email) == email)).first()
    if titulaire is None:
        return None
    return session.exec(
        select(Company)
        .where(
            col(Company.owner_user_id) == titulaire.id,
            col(Company.status) == RegistrationStatus.EMAIL_VERIFICATION_PENDING,
        )
        .with_for_update()
    ).first()


def verifier_code(session: Session, email: str, code: str, adresse_ip: str | None) -> Company:
    """La demande dont l'adresse vient d'être confirmée (verrouillée, pas encore commitée), ou
    ValidationError `code_invalide` — un seul message pour tout échec."""
    _limiter(adresse_ip, "registration_email_verifications", MAX_VERIFICATIONS_PAR_IP)
    entreprise = _demande_a_verifier(session, email)
    if (
        entreprise is None
        or entreprise.email_verification_code_hash is None
        or entreprise.email_verification_expires_at is None
        or entreprise.email_verification_expires_at < utcnow()
    ):
        raise ValidationError(CODE_INVALIDE, code="code_invalide")
    if not hmac.compare_digest(entreprise.email_verification_code_hash, _empreinte(entreprise, code)):
        entreprise.email_verification_attempts += 1
        if entreprise.email_verification_attempts >= MAX_ESSAIS:
            # Code épuisé : il faut en redemander un.
            entreprise.email_verification_code_hash = None
        session.add(entreprise)
        session.commit()
        raise ValidationError(CODE_INVALIDE, code="code_invalide")
    entreprise.email_verification_code_hash = None
    entreprise.email_verification_expires_at = None
    entreprise.email_verified_at = utcnow()
    return entreprise


def renvoyer_code(
    session: Session, email: str, adresse_ip: str | None, background_tasks: BackgroundTasks
) -> None:
    """Nouveau code si une demande attend la confirmation de cette adresse et que le dernier
    envoi date d'au moins une minute ; sinon rien — même réponse dans tous les cas."""
    _limiter(adresse_ip, "registration_email_resends", MAX_RENVOIS_PAR_IP)
    entreprise = _demande_a_verifier(session, email)
    if entreprise is None:
        return
    dernier = entreprise.email_verification_sent_at
    if dernier is not None and utcnow() - dernier < DELAI_ENTRE_ENVOIS:
        return
    code = emettre_code(entreprise)
    session.add(entreprise)
    session.commit()
    background_tasks.add_task(envoyer_code, email, entreprise.name, code)
