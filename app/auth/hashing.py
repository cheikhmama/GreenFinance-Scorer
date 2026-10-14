"""Hachage et vérification des mots de passe.

pwdlib — jamais de hachage maison. Le mot de passe en clair ne doit jamais être conservé ni
journalisé (voir la règle absolue posée dans app/core/logging.py : ne jamais logger un secret).

- Nouveaux hachages : Argon2id, paramètres minimaux OWASP (19 Mio, 2 passes, 1 fil) plutôt que
  les 64 Mio par défaut — l'API tourne sous 768 Mo avec deux processus uvicorn, et une rafale de
  connexions multiplierait cette mémoire par le nombre de vérifications simultanées.
- Hachages bcrypt existants ($2b$, écrits par passlib) : toujours vérifiés, et remplacés par un
  hachage Argon2id à la première connexion réussie (verifier_et_mettre_a_jour).
"""

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

BCRYPT_OCTETS_MAX = 72


class _BcryptHerite(BcryptHasher):
    """bcrypt >= 5 lève ValueError au-delà de 72 octets au lieu de tronquer. Aucun mot de passe
    posé ne dépasse cette longueur (app/auth/schemas.py::NouveauMotDePasse) : un mot de passe plus
    long ne peut correspondre à un hachage bcrypt — refus, jamais une erreur 500 à la connexion."""

    def verify(self, password: str | bytes, hash: str | bytes) -> bool:
        octets = password.encode("utf-8") if isinstance(password, str) else password
        if len(octets) > BCRYPT_OCTETS_MAX:
            return False
        return super().verify(password, hash)


# Le premier hacheur produit les nouveaux hachages ; les suivants ne servent qu'à vérifier.
_pwd_hash = PasswordHash(
    (Argon2Hasher(time_cost=2, memory_cost=19 * 1024, parallelism=1), _BcryptHerite())
)


def hash_password(password: str) -> str:
    return _pwd_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_hash.verify(password, password_hash)


def verifier_et_mettre_a_jour(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Vérifie, et renvoie un nouveau hachage quand l'ancien doit être remplacé (bcrypt, ou
    paramètres Argon2 différents) — à enregistrer par l'appelant, None sinon."""
    return _pwd_hash.verify_and_update(password, password_hash)
