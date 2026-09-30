"""Envoi SMTP partagé, sans journalisation des messages ni des secrets."""

import smtplib
import ssl
from email.message import EmailMessage

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.config import Settings, get_settings

_EMAIL = TypeAdapter(EmailStr)


class EmailDeliveryError(Exception):
    """Configuration absente, connexion échouée ou message refusé par SMTP."""


def ensure_email_configured() -> Settings:
    settings = get_settings()
    try:
        _EMAIL.validate_python(settings.mail_from)
    except ValidationError as exc:
        raise EmailDeliveryError("Adresse d'expédition non configurée.") from exc
    if not settings.smtp_host.strip():
        raise EmailDeliveryError("Serveur SMTP non configuré.")
    if bool(settings.smtp_username) != bool(settings.smtp_password.get_secret_value()):
        raise EmailDeliveryError("Identifiants SMTP incomplets.")
    return settings


def send_email(*, recipient: str, subject: str, body: str, reply_to: str | None = None) -> None:
    """Le succès signifie que le relais a accepté le message, pas sa réception finale."""
    settings = ensure_email_configured()
    try:
        recipient = str(_EMAIL.validate_python(recipient))
        message = EmailMessage()
        message["From"] = settings.mail_from
        message["To"] = recipient
        message["Subject"] = subject
        if reply_to is not None:
            message["Reply-To"] = str(_EMAIL.validate_python(reply_to))
        message.set_content(body)

        connection: smtplib.SMTP
        if settings.smtp_security == "ssl":
            connection = smtplib.SMTP_SSL(
                host=settings.smtp_host,
                port=settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
                context=ssl.create_default_context(),
            )
        else:
            connection = smtplib.SMTP(
                host=settings.smtp_host,
                port=settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            )
        with connection as smtp:
            if settings.smtp_security == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            refused = smtp.send_message(
                message, from_addr=settings.mail_from, to_addrs=[recipient]
            )
            if refused:
                raise EmailDeliveryError("Message refusé par le relais SMTP.")
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        raise EmailDeliveryError("Impossible de transmettre le message.") from exc


def envoyer_email_differe(
    *, recipient: str, subject: str, body: str, reply_to: str | None = None
) -> None:
    """Dépose l'e-mail dans la file (job send_email, app/worker/jobs.py, tâche 4.1) : l'envoi SMTP
    et ses reprises se font dans le worker, jamais dans une requête. Adresses vérifiées ici (une
    adresse invalide ne serait jamais délivrée, inutile de la retenter). EmailDeliveryError si
    une adresse est invalide ou si la file est indisponible — même contrat qu'avant pour les
    appelants."""
    from app.worker.queue import FileIndisponible, enfiler

    try:
        recipient = str(_EMAIL.validate_python(recipient))
        reply_to = str(_EMAIL.validate_python(reply_to)) if reply_to is not None else None
    except ValidationError as exc:
        raise EmailDeliveryError("Adresse invalide.") from exc
    try:
        enfiler("send_email", recipient, subject, body, reply_to)
    except FileIndisponible as exc:
        raise EmailDeliveryError("File d'envoi indisponible.") from exc

