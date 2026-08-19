"""Hachage et vérification des mots de passe.

bcrypt via passlib — jamais de hachage maison. Le mot de passe en clair ne
doit jamais être conservé ni journalisé (voir la règle absolue posée dans
app/core/logging.py : ne jamais logger un secret).
"""

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)
