"""Schémas Pydantic d'entrée/sortie du module auth.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2) —
UtilisateurPublic en particulier n'expose jamais password_hash.

Contrat JSON en anglais depuis la tâche 4.7 (docs/RENAME_PLAN.md §3e) : les champs portent les
noms des attributs de User ; UserContractMixin n'ajoute que ce qui se calcule (l'URL d'avatar).
"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)

from app.auth.avatar import url_avatar
from app.auth.models import User
from app.core.enums import Role

MOT_DE_PASSE_LONGUEUR_MIN = 12
MOT_DE_PASSE_OCTETS_MAX = 72


def _valider_longueur_bcrypt(mot_de_passe: str) -> str:
    """bcrypt tronque silencieusement au-delà de 72 octets — refuser explicitement plutôt que de
    laisser un mot de passe plus long être accepté puis vérifié sur un préfixe seulement."""
    if len(mot_de_passe.encode("utf-8")) > MOT_DE_PASSE_OCTETS_MAX:
        raise ValueError("Le mot de passe ne doit pas dépasser 72 octets en UTF-8.")
    return mot_de_passe


def _normaliser_email(email: str) -> str:
    return email.strip().lower()


# Règle unique pour tout mot de passe NOUVELLEMENT posé (activation, réinitialisation, changement —
# décision D4) : 12 caractères minimum, 72 octets UTF-8 maximum. Jamais appliquée à la connexion :
# un mot de passe existant plus court reste valide, seul le prochain qui sera posé doit la suivre.
NouveauMotDePasse = Annotated[
    str,
    Field(min_length=MOT_DE_PASSE_LONGUEUR_MIN, max_length=MOT_DE_PASSE_OCTETS_MAX),
    AfterValidator(_valider_longueur_bcrypt),
]

# L'e-mail est stocké en minuscules (ck_users_email_lowercase, app/auth/models.py) : toute entrée
# d'e-mail est normalisée ici, à la frontière HTTP, avant toute recherche ou écriture.
EmailNormalise = Annotated[EmailStr, AfterValidator(_normaliser_email)]


class LoginRequest(BaseModel):
    email: EmailNormalise
    password: str


def user_vers_contrat(user: User) -> dict[str, Any]:
    """Point unique de passage User -> contrat JSON : liste blanche des champs exposés (jamais
    password_hash) et URL d'avatar calculée."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        # URL du fichier (tâche 4.3), plus un data URI : même usage côté client (src d'image).
        "avatar": url_avatar(user),
        "role": user.role,
        "created_at": user.created_at,
        "active": user.active,
        "activated_at": user.activated_at,
    }


class UserContractMixin(BaseModel):
    """À hériter par tout schéma de réponse validé depuis un User (model_validate ou
    response_model) : la validation part de la liste blanche user_vers_contrat."""

    @model_validator(mode="before")
    @classmethod
    def _depuis_user(cls, data: Any) -> Any:
        if isinstance(data, User):
            return user_vers_contrat(data)
        return data


class UtilisateurPublic(UserContractMixin):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None
    avatar: str | None
    role: Role
    created_at: datetime
    active: bool
    # None tant que le compte n'a pas cliqué son lien d'activation (app/auth/activation.py) —
    # inatteignable pour /auth/me (un compte non activé ne peut pas ouvrir de session), utile
    # uniquement aux listes Administrateur qui parcourent des comptes autres que le sien.
    activated_at: datetime | None
    # Renseigné uniquement par PATCH /auth/me quand un changement d'e-mail vient d'être demandé :
    # l'adresse à laquelle le lien de confirmation a été envoyé. `email` reste l'ancienne adresse
    # tant que ce lien n'a pas été confirmé.
    pending_email: str | None = None


class ChangerMotDePasseRequest(BaseModel):
    current_password: str
    new_password: NouveauMotDePasse


class ModifierProfilRequest(BaseModel):
    """Auto-service, restreint à nom et email — jamais role : fixé une seule fois à la création
    du compte (app/admin/utilisateurs.py::creer_utilisateur), jamais modifiable ensuite, ni par
    l'Admin ni par l'intéressé.

    L'email est l'identifiant de connexion : le changer exige mot_de_passe_actuel et ne prend effet
    qu'à la confirmation du lien envoyé à la nouvelle adresse (app/auth/email_change.py) — une
    session volée ne suffit jamais à détourner le compte."""

    name: str
    email: EmailNormalise
    current_password: str | None = None


class ConfirmerChangementEmailRequest(BaseModel):
    """POST /auth/confirmer-changement-email — jeton reçu à la nouvelle adresse
    (app/auth/email_change.py::TOKEN_TTL, usage unique)."""

    token: str = Field(min_length=1, max_length=512)


class DemanderReinitialisationRequest(BaseModel):
    """POST /auth/mot-de-passe-oublie — réponse indépendante du fait que l'e-mail
    corresponde ou non à un compte (voir app/auth/password_reset.py::demander_reinitialisation)."""

    email: EmailNormalise


class ReinitialiserMotDePasseRequest(BaseModel):
    """POST /auth/reinitialiser-mot-de-passe — jeton reçu via le lien généré par la demande
    ci-dessus (app/auth/password_reset.py::TOKEN_TTL, 30 minutes, usage unique)."""

    token: str = Field(min_length=1, max_length=512)
    new_password: NouveauMotDePasse


class ActiverCompteRequest(BaseModel):
    """POST /auth/activer-compte — jeton reçu via le lien envoyé à la création du compte
    (app/auth/activation.py::ACTIVATION_TOKEN_TTL, 72 heures, usage unique)."""

    token: str = Field(min_length=1, max_length=512)
    new_password: NouveauMotDePasse


class VerifierMotDePasseRequest(BaseModel):
    """Étape 1 du changement de mot de passe progressif côté frontend — vérifie sans rien
    modifier, pour afficher une erreur au bon endroit avant même de proposer un nouveau mot de
    passe. Jamais de contenu retourné au-delà du statut HTTP : ni confirmer ni infirmer autre
    chose que "ce mot de passe est-il le bon" (voir app/auth/router.py::verifier_mon_mot_de_passe)."""

    password: str
