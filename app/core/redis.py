"""Client Redis partagé, pour tout module ayant besoin d'un compteur ou d'un
cache transverse (ex. limitation de débit — voir app/auth/rate_limit.py).

Même pattern que app/core/database.py::engine : une instance construite une
fois depuis la configuration, jamais recréée par appel.
"""

from functools import lru_cache

import redis

from app.core.config import get_settings


@lru_cache
def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
