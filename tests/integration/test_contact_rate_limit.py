import hashlib
import uuid
from ipaddress import IPv6Address

import pytest
from starlette.requests import Request

from app.contact.router import _enforce_rate_limit
from app.core.exceptions import TooManyRequestsError
from app.core.redis import get_redis_client


def test_contact_redis_script_limits_requests_and_expires_the_counter():
    # Chaque exécution utilise sa propre adresse pour ne toucher aucun compteur existant.
    address = str(IPv6Address(uuid.uuid4().int))
    key = f"contact_requests:{hashlib.sha256(address.encode()).hexdigest()}"
    request = Request({"type": "http", "client": (address, 12345)})
    client = get_redis_client()
    try:
        for _ in range(3):
            _enforce_rate_limit(request)
        assert client.get(key) == "3"
        assert 0 < client.ttl(key) <= 3600
        with pytest.raises(TooManyRequestsError):
            _enforce_rate_limit(request)
        assert client.get(key) == "4"
        assert 0 < client.ttl(key) <= 3600
    finally:
        client.delete(key)
