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


# Une seule opération Redis : aucune fenêtre entre INCR et EXPIRE. Deux appels séparés laissaient
# une clé sans expiration si le process s'arrêtait entre les deux — un compteur (et donc un
# blocage) permanent.
_SCRIPT_INCREMENT_FENETRE = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


def incrementer_fenetre(client: redis.Redis, cle: str, fenetre_secondes: int) -> int:
    """Incrémente le compteur `cle` d'une fenêtre fixe de `fenetre_secondes` et renvoie sa valeur
    — l'expiration n'est posée qu'au premier incrément de la fenêtre. Point unique pour toute
    limitation de débit (connexion, réinitialisation, contact, import par URL)."""
    return int(client.eval(_SCRIPT_INCREMENT_FENETRE, 1, cle, fenetre_secondes))
