"""Schémas Pydantic d'entrée/sortie du module auth.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2) —
UtilisateurPublic en particulier n'expose jamais mot_de_passe_hache.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.core.enums import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UtilisateurPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nom: str | None
    role: Role
    date_creation: datetime
    actif: bool
    doit_changer_mot_de_passe: bool


class ChangerMotDePasseRequest(BaseModel):
    mot_de_passe_actuel: str
    nouveau_mot_de_passe: str
