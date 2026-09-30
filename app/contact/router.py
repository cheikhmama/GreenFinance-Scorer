import hashlib

import redis
import structlog
from fastapi import APIRouter, Request

from app.contact.schemas import ContactMessageRequest
from app.core.config import get_settings
from app.core.email import EmailDeliveryError, envoyer_email_differe
from app.core.exceptions import ServiceUnavailableError, TooManyRequestsError
from app.core.redis import get_redis_client, incrementer_fenetre

router = APIRouter(tags=["contact"])
logger = structlog.get_logger(__name__)

_RATE_LIMIT_MAX = 3
_RATE_LIMIT_WINDOW_SECONDS = 3600


def _enforce_rate_limit(request: Request) -> None:
    # request.client vient du serveur ASGI. Ne jamais lire directement X-Forwarded-For :
    # seuls les proxys explicitement autorisés par le serveur peuvent réécrire cette IP.
    address = request.client.host if request.client else "unknown"
    key = f"contact_requests:{hashlib.sha256(address.encode()).hexdigest()}"
    try:
        attempts = incrementer_fenetre(get_redis_client(), key, _RATE_LIMIT_WINDOW_SECONDS)
    except redis.RedisError as exc:
        logger.error("contact_rate_limit_unavailable", error_type=type(exc).__name__)
        raise ServiceUnavailableError(
            "Le service de contact est temporairement indisponible. Réessayez plus tard."
        ) from exc
    if attempts > _RATE_LIMIT_MAX:
        raise TooManyRequestsError(
            "Trop de messages envoyés. Réessayez dans une heure."
        )


@router.post(
    "/contact",
    status_code=204,
    operation_id="sendContactMessage",
    summary="Envoyer un message à l'équipe GreenFinance-Scorer",
    responses={
        429: {"description": "Limite de trois demandes par heure et par adresse IP atteinte."},
        503: {"description": "Envoi indisponible ou message non accepté par le relais SMTP."},
    },
)
def send_contact_message(payload: ContactMessageRequest, request: Request) -> None:
    _enforce_rate_limit(request)
    try:
        envoyer_email_differe(
            recipient=get_settings().contact_to_email,
            subject=f"[GreenFinance-Scorer] {payload.subject}",
            reply_to=str(payload.email),
            body=(
                f"Nom : {payload.name}\nE-mail : {payload.email}\n"
                f"Sujet : {payload.subject}\n\n{payload.message}\n"
            ),
        )
    except EmailDeliveryError as exc:
        logger.error("contact_delivery_failed", error_type=type(exc.__cause__ or exc).__name__)
        raise ServiceUnavailableError(
            "Votre message n'a pas pu être transmis. Réessayez plus tard."
        ) from exc
