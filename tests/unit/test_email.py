import smtplib
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.email import EmailDeliveryError, ensure_email_configured, send_email


@pytest.fixture
def smtp(monkeypatch):
    settings = Settings.model_construct(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="smtp-user",
        smtp_password=SecretStr("smtp-secret"),
        mail_from="no-reply@example.com",
    )
    monkeypatch.setattr("app.core.email.get_settings", lambda: settings)
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.send_message.return_value = {}
    starttls = Mock(return_value=connection)
    implicit_tls = Mock(return_value=connection)
    monkeypatch.setattr("app.core.email.smtplib.SMTP", starttls)
    monkeypatch.setattr("app.core.email.smtplib.SMTP_SSL", implicit_tls)
    return settings, connection, starttls, implicit_tls


def _send():
    send_email(
        recipient="equipe@example.com",
        reply_to="personne@example.com",
        subject="Une demande à traiter",
        body="Bonjour, voici les détails de ma demande.",
    )


def test_smtp_starttls_authenticates_and_uses_validated_envelope(smtp):
    settings, connection, starttls, implicit_tls = smtp
    _send()

    starttls.assert_called_once_with(host="smtp.example.com", port=587, timeout=10)
    implicit_tls.assert_not_called()
    connection.starttls.assert_called_once()
    connection.login.assert_called_once_with("smtp-user", "smtp-secret")
    sent = connection.send_message.call_args
    assert sent.kwargs == {"from_addr": settings.mail_from, "to_addrs": ["equipe@example.com"]}
    message = sent.args[0]
    assert message["From"] == "no-reply@example.com"
    assert message["Reply-To"] == "personne@example.com"
    assert "détails" in message.get_content()
    assert [call[0] for call in connection.method_calls] == ["starttls", "login", "send_message"]


def test_implicit_tls_does_not_upgrade_again(smtp):
    settings, connection, starttls, implicit_tls = smtp
    settings.smtp_security = "ssl"
    settings.smtp_port = 465
    _send()

    starttls.assert_not_called()
    implicit_tls.assert_called_once()
    assert implicit_tls.call_args.kwargs["port"] == 465
    assert implicit_tls.call_args.kwargs["context"].check_hostname
    connection.starttls.assert_not_called()


def test_development_relay_can_work_without_tls_or_authentication(smtp):
    settings, connection, _, _ = smtp
    settings.smtp_security = "plain"
    settings.smtp_username = ""
    settings.smtp_password = SecretStr("")
    _send()

    connection.starttls.assert_not_called()
    connection.login.assert_not_called()
    connection.send_message.assert_called_once()


@pytest.mark.parametrize("failure", [OSError("private host"), smtplib.SMTPException("private reply")])
def test_smtp_failure_is_wrapped_without_exposing_provider_details(smtp, failure):
    _, connection, _, _ = smtp
    connection.send_message.side_effect = failure
    with pytest.raises(EmailDeliveryError, match="Impossible de transmettre") as captured:
        _send()
    assert "private" not in str(captured.value)


def test_refused_recipient_is_not_success(smtp):
    _, connection, _, _ = smtp
    connection.send_message.return_value = {"equipe@example.com": (550, b"refused")}
    with pytest.raises(EmailDeliveryError, match="refusé"):
        _send()


@pytest.mark.parametrize(
    "overrides",
    [
        {"smtp_host": ""},
        {"mail_from": ""},
        {"mail_from": "bad-address"},
        {"smtp_username": ""},
        {"smtp_password": SecretStr("")},
    ],
)
def test_missing_or_invalid_configuration_is_rejected_before_connection(smtp, overrides):
    settings, _, starttls, implicit_tls = smtp
    for key, value in overrides.items():
        setattr(settings, key, value)
    with pytest.raises(EmailDeliveryError):
        ensure_email_configured()
    starttls.assert_not_called()
    implicit_tls.assert_not_called()


def test_header_injection_is_rejected_before_connection(smtp):
    _, _, starttls, _ = smtp
    with pytest.raises(EmailDeliveryError):
        send_email(
            recipient="equipe@example.com",
            subject="Sujet\r\nBcc: attacker@example.com",
            body="Message",
        )
    starttls.assert_not_called()
