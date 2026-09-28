"""Schémas Pydantic d'entrée/sortie du module auth.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2) —
UtilisateurPublic en particulier n'expose jamais mot_de_passe_hache.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import Role


def _valider_longueur_bcrypt(mot_de_passe: str) -> str:
    """bcrypt tronque silencieusement au-delà de 72 octets — refuser explicitement plutôt que de
    laisser un mot de passe plus long être accepté puis vérifié sur un préfixe seulement."""
    if len(mot_de_passe.encode("utf-8")) > 72:
        raise ValueError("Le mot de passe ne doit pas dépasser 72 octets en UTF-8.")
    return mot_de_passe


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UtilisateurPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nom: str | None
    avatar: str | None
    role: Role
    date_creation: datetime
    actif: bool
    # None tant que le compte n'a pas cliqué son lien d'activation (app/auth/activation.py) —
    # inatteignable pour /auth/me (un compte non activé ne peut pas ouvrir de session), utile
    # uniquement aux listes Administrateur qui parcourent des comptes autres que le sien.
    date_activation: datetime | None


class ChangerMotDePasseRequest(BaseModel):
    mot_de_passe_actuel: str
    nouveau_mot_de_passe: str


class ModifierProfilRequest(BaseModel):
    """Auto-service, restreint à nom et email — jamais role : fixé une seule fois à la création
    du compte (app/admin/utilisateurs.py::creer_utilisateur), jamais modifiable ensuite, ni par
    l'Admin ni par l'intéressé. L'email reste l'identifiant de connexion :
    app/auth/router.py::modifier_mon_profil vérifie son unicité avant d'accepter le changement,
    comme creer_utilisateur le fait à la création."""

    nom: str
    email: EmailStr


class DemanderReinitialisationRequest(BaseModel):
    """POST /auth/mot-de-passe-oublie — réponse indépendante du fait que l'e-mail
    corresponde ou non à un compte (voir app/auth/password_reset.py::demander_reinitialisation)."""

    email: EmailStr


class ReinitialiserMotDePasseRequest(BaseModel):
    """POST /auth/reinitialiser-mot-de-passe — jeton reçu via le lien généré par la demande
    ci-dessus (app/auth/password_reset.py::TOKEN_TTL, 30 minutes, usage unique)."""

    token: str = Field(min_length=1, max_length=512)
    nouveau_mot_de_passe: str = Field(min_length=8, max_length=72)

    @field_validator("nouveau_mot_de_passe")
    @classmethod
    def password_bcrypt_limit(cls, value: str) -> str:
        return _valider_longueur_bcrypt(value)


class ActiverCompteRequest(BaseModel):
    """POST /auth/activer-compte — jeton reçu via le lien envoyé à la création du compte
    (app/auth/activation.py::ACTIVATION_TOKEN_TTL, 7 jours, usage unique)."""

    token: str = Field(min_length=1, max_length=512)
    nouveau_mot_de_passe: str = Field(min_length=8, max_length=72)

    @field_validator("nouveau_mot_de_passe")
    @classmethod
    def password_bcrypt_limit(cls, value: str) -> str:
        return _valider_longueur_bcrypt(value)


class VerifierMotDePasseRequest(BaseModel):
    """Étape 1 du changement de mot de passe progressif côté frontend — vérifie sans rien
    modifier, pour afficher une erreur au bon endroit avant même de proposer un nouveau mot de
    passe. Jamais de contenu retourné au-delà du statut HTTP : ni confirmer ni infirmer autre
    chose que "ce mot de passe est-il le bon" (voir app/auth/router.py::verifier_mon_mot_de_passe)."""

    mot_de_passe: str
