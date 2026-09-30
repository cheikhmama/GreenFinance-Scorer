from unittest.mock import Mock

import pytest
from fastapi import BackgroundTasks
from pydantic import ValidationError

from app.auth.password_reset import demander_reinitialisation
from app.auth.schemas import ReinitialiserMotDePasseRequest
from app.core.email import EmailDeliveryError
from app.core.exceptions import ServiceUnavailableError


def test_missing_mail_configuration_is_checked_before_account_lookup(monkeypatch):
    session = Mock()
    monkeypatch.setattr(
        "app.auth.password_reset.ensure_email_configured",
        Mock(side_effect=EmailDeliveryError("absent")),
    )
    with pytest.raises(ServiceUnavailableError):
        demander_reinitialisation(session, "personne@example.com", BackgroundTasks())
    session.exec.assert_not_called()


@pytest.mark.parametrize("password", ["court", "x" * 73, "é" * 37])
def test_reset_rejects_short_passwords_and_bcrypt_truncation(password):
    with pytest.raises(ValidationError):
        ReinitialiserMotDePasseRequest(token="jeton", new_password=password)


def test_reset_preserves_spaces_and_accepts_72_utf8_bytes():
    password = " " + "é" * 35 + " "
    payload = ReinitialiserMotDePasseRequest(token="jeton", new_password=password)
    assert payload.new_password == password
