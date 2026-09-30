from unittest.mock import Mock

import pytest
import redis
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.contact.router import router
from app.core.config import Settings
from app.core.email import EmailDeliveryError
from app.core.exceptions import register_exception_handlers

_PAYLOAD = {
    "name": "Aminata Diallo",
    "email": "aminata@example.com",
    "subject": "Accès à la plateforme",
    "message": "Bonjour, je souhaite en savoir plus sur la création de mon compte.",
}


@pytest.fixture
def contact(monkeypatch):
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    redis_client = Mock()
    redis_client.eval.return_value = 1
    monkeypatch.setattr("app.contact.router.get_redis_client", lambda: redis_client)
    settings = Settings.model_construct(contact_to_email="equipe@example.com")
    monkeypatch.setattr("app.contact.router.get_settings", lambda: settings)
    delivery = Mock()
    monkeypatch.setattr("app.contact.router.envoyer_email_differe", delivery)
    return TestClient(app), redis_client, delivery


def test_public_message_is_sent_to_configured_team_with_reply_to(contact):
    client, _, delivery = contact
    response = client.post("/api/v1/contact", json=_PAYLOAD)

    assert response.status_code == 204
    assert response.content == b""
    sent = delivery.call_args.kwargs
    assert sent["recipient"] == "equipe@example.com"
    assert sent["reply_to"] == _PAYLOAD["email"]
    assert _PAYLOAD["name"] in sent["body"]
    assert _PAYLOAD["message"] in sent["body"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", " "),
        ("name", "x" * 101),
        ("email", "invalid"),
        ("email", "a@example.com\r\nBcc: b@example.com"),
        ("subject", "a"),
        ("subject", "x" * 151),
        ("subject", "Sujet\r\nBcc: b@example.com"),
        ("message", "trop court"),
        ("message", "x" * 5001),
    ],
)
def test_invalid_fields_are_rejected_without_sending(contact, field, value):
    client, _, delivery = contact
    response = client.post("/api/v1/contact", json={**_PAYLOAD, field: value})

    assert response.status_code == 422
    assert field in response.json()["error"]["fields"]
    delivery.assert_not_called()


def test_fourth_message_is_blocked_and_forwarded_header_cannot_change_the_key(contact):
    client, redis_client, delivery = contact
    redis_client.eval.side_effect = [1, 2, 3, 4]

    for number in range(3):
        assert client.post(
            "/api/v1/contact",
            json=_PAYLOAD,
            headers={"x-forwarded-for": f"198.51.100.{number}"},
        ).status_code == 204
    response = client.post("/api/v1/contact", json=_PAYLOAD)

    assert response.status_code == 429
    assert delivery.call_count == 3
    arguments = [call.args for call in redis_client.eval.call_args_list]
    assert len({args[2] for args in arguments}) == 1
    # Envoyée en chaîne (typage redis-py 5, tâche 4.1) : identique sur le fil pour Redis.
    assert all(args[1] == 1 and args[3] == "3600" for args in arguments)


def test_redis_failure_blocks_delivery(contact):
    client, redis_client, delivery = contact
    redis_client.eval.side_effect = redis.ConnectionError("private redis address")

    response = client.post("/api/v1/contact", json=_PAYLOAD)

    assert response.status_code == 503
    assert "private" not in response.text
    delivery.assert_not_called()


def test_smtp_failure_does_not_claim_success_or_log_personal_message(contact):
    client, _, delivery = contact
    delivery.side_effect = EmailDeliveryError("private SMTP details")
    with structlog.testing.capture_logs() as logs:
        response = client.post("/api/v1/contact", json=_PAYLOAD)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert "private SMTP details" not in str(logs)
    assert _PAYLOAD["email"] not in str(logs)
    assert _PAYLOAD["message"] not in str(logs)
