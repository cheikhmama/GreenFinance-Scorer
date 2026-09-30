import uuid

import jwt
import pytest

from app.auth.tokens import InvalidTokenError, create_access_token, decode_access_token
from app.core.config import get_settings
from app.core.enums import Role


def test_decode_access_token_round_trips_the_user_id_and_role() -> None:
    user_id = uuid.uuid4()

    token = create_access_token(user_id, Role.INVESTOR)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["role"] == Role.INVESTOR.value


def test_decode_access_token_rejects_a_tampered_signature() -> None:
    """Altère un caractère au MILIEU du segment de signature, jamais le
    dernier : en base64url non paddé, le dernier caractère d'un segment de 32
    octets ne porte que des bits de bourrage ignorés au décodage — le
    modifier peut ne rien changer à la signature décodée selon sa valeur
    d'origine, rendant le test silencieusement inopérant un run sur deux."""
    token = create_access_token(uuid.uuid4(), Role.ENTERPRISE)
    header, payload, signature = token.split(".")
    mid = len(signature) // 2
    flipped_char = "A" if signature[mid] != "A" else "B"
    tampered_signature = signature[:mid] + flipped_char + signature[mid + 1 :]
    tampered = f"{header}.{payload}.{tampered_signature}"

    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered)


def test_decode_access_token_rejects_an_expired_token() -> None:
    settings = get_settings()
    expired_payload = {"sub": str(uuid.uuid4()), "role": Role.AUDITOR.value, "exp": 0}
    expired_token = jwt.encode(expired_payload, settings.secret_key, algorithm="HS256")

    with pytest.raises(InvalidTokenError):
        decode_access_token(expired_token)


def test_decode_access_token_rejects_a_token_signed_with_a_different_key() -> None:
    payload = {"sub": str(uuid.uuid4()), "role": Role.RESEARCHER.value}
    token = jwt.encode(payload, "une-cle-de-signature-totalement-differente", algorithm="HS256")

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)
