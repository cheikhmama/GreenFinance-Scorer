"""Entités de persistance liées à l'authentification (utilisateurs, rôles, rattachements).

Le schéma pivot (Étape 3) est posé ici : Utilisateur reste une table
unique à discriminant `role`, jamais une table séparée par sous-rôle. La
logique métier d'authentification (connexion, hachage, MFA, permissions)
reste implémentée à l'Étape 9 (Authentification et autorisation).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import Role, StatutRattachement, sa_enum_column

if TYPE_CHECKING:
    from app.audit.models import AvisAudit
    from app.company.models import Company
    from app.core.models import Notification
    from app.ingestion.models import ESGReport
    from app.institution.models import AffectationProjet, Projet
    from app.investor.models import Portefeuille
    from app.researcher.models import Analyse
    from app.scoring.models import ConfigurationPonderation


class User(SQLModel, table=True):
    """Table `users` (docs/RENAME_PLAN.md §3, tâche 1.2).

    L'e-mail est l'identifiant de connexion, stocké exclusivement en minuscules
    (ck_users_email_lowercase) : l'unicité de `email` vaut donc unicité insensible à la casse, et
    toute recherche par e-mail compare une valeur normalisée à la frontière HTTP
    (app/auth/schemas.py::EmailNormalise)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str | None = None
    # Data URI complet (voir app/company/models.py::Company.logo, même convention) — jamais un
    # fichier séparé sur disque, une image d'avatar reste petite (voir
    # app/auth/avatar.py::TAILLE_MAX_OCTETS).
    avatar: str | None = None
    # None tant que le compte n'a pas été activé (voir activated_at ci-dessous) : un compte
    # provisionné par l'Administrateur n'a d'abord aucun mot de passe, la personne titulaire pose
    # le sien elle-même via le lien d'activation (app/auth/activation.py).
    password_hash: str | None = None
    role: Role = Field(sa_column=sa_enum_column(Role))
    created_at: datetime = Field(default_factory=utcnow)
    active: bool = Field(default=True)
    # None tant qu'un compte provisionné par l'Administrateur (Phase 3 §3.3) n'a pas encore été
    # activé via le lien reçu par e-mail (app/auth/activation.py::activer_compte, qui pose
    # password_hash et cette date dans le même geste) — login (app/auth/router.py) refuse
    # toute tentative tant que password_hash est None, jamais besoin de vérifier ce champ
    # séparément ailleurs.
    activated_at: datetime | None = Field(default=None)

    institution_profile: Optional["InstitutionProfil"] = Relationship(
        back_populates="utilisateur"
    )
    company: Optional["Company"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"foreign_keys": "[Company.owner_user_id]"},
    )
    audited_reports: list["ESGReport"] = Relationship(back_populates="auditor")
    scoring_configs: list["ConfigurationPonderation"] = Relationship(
        back_populates="utilisateur"
    )
    portfolios: list["Portefeuille"] = Relationship(back_populates="investisseur")
    audit_opinions: list["AvisAudit"] = Relationship(back_populates="auditeur")
    notifications: list["Notification"] = Relationship(back_populates="utilisateur")
    projects: list["Projet"] = Relationship(back_populates="institution")
    project_assignments: list["AffectationProjet"] = Relationship(back_populates="chercheur")
    analyses: list["Analyse"] = Relationship(back_populates="chercheur")


class PasswordResetToken(SQLModel, table=True):
    """Table `password_reset_tokens` — jeton à usage unique pour le flux « mot de passe oublié »
    (app/auth/password_reset.py).

    Le jeton en clair n'est jamais persisté : seule son empreinte SHA-256 (token_hash) l'est,
    même logique que ne jamais stocker un mot de passe en clair — un vidage de cette table ne
    doit permettre de rejouer aucun lien déjà émis. Une ligne est à usage unique (used_at posé à
    la consommation) et expire après app/auth/password_reset.py::TOKEN_TTL, qu'elle ait servi ou
    non."""

    __tablename__ = "password_reset_tokens"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    token_hash: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    used_at: datetime | None = Field(default=None)


class AccountActivationToken(SQLModel, table=True):
    """Table `account_activation_tokens` — jeton à usage unique pour le flux d'activation d'un
    compte provisionné par l'Administrateur (app/auth/activation.py), pendant de
    PasswordResetToken ci-dessus pour la première connexion plutôt qu'un mot de passe
    oublié. Mêmes garanties : empreinte SHA-256 seulement, usage unique, expiration
    (app/auth/activation.py::ACTIVATION_TOKEN_TTL)."""

    __tablename__ = "account_activation_tokens"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    token_hash: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    used_at: datetime | None = Field(default=None)


class EmailChangeRequest(SQLModel, table=True):
    """Changement d'e-mail en attente de confirmation (app/auth/email_change.py).

    L'e-mail est l'identifiant de connexion : il ne change qu'une fois le lien envoyé à la
    NOUVELLE adresse cliqué, jamais sur la seule foi d'une session (une session volée ne suffit
    plus à détourner le compte via « mot de passe oublié »). Mêmes garanties que les jetons
    ci-dessus : empreinte SHA-256 seulement, usage unique, expiration."""

    __tablename__ = "email_change_requests"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    new_email: str
    token_hash: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    used_at: datetime | None = Field(default=None)


class InstitutionProfil(SQLModel, table=True):
    """Profil complémentaire 1-1, uniquement pertinent pour un Utilisateur
    dont le role est INSTITUTION."""

    __tablename__ = "institution_profil"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    utilisateur_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", unique=True)
    quota_export: int

    utilisateur: User = Relationship(back_populates="institution_profile")


class ChercheurInstitution(SQLModel, table=True):
    """Table de rattachement plusieurs-à-plusieurs entre un Utilisateur Chercheur et un
    Utilisateur Institution (Étape 17). Pas de Relationship() vers Utilisateur : deux FK vers la
    même table exigeraient chacune un foreign_keys= explicite pour lever l'ambiguïté côté
    SQLAlchemy — les services interrogent chercheur_id/institution_id directement, plus simple.

    Une invitation refusée n'est jamais recréée en double : l'Institution peut réinviter le même
    Chercheur, ce qui remet statut à EN_ATTENTE sur la même ligne (voir uq_chercheur_institution
    ci-dessous, une seule ligne par couple)."""

    __tablename__ = "chercheur_institution"
    __table_args__ = (
        UniqueConstraint("chercheur_id", "institution_id", name="uq_chercheur_institution"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chercheur_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    institution_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    statut: StatutRattachement = Field(
        default=StatutRattachement.EN_ATTENTE, sa_column=sa_enum_column(StatutRattachement)
    )
    date_invitation: datetime = Field(default_factory=utcnow)
    date_reponse: datetime | None = Field(default=None)
    # Texte libre optionnel renseigné par l'Institution à l'invitation (conditions de
    # collaboration, périmètre annoncé...) — consultable par le Chercheur avant sa réponse. Pas de
    # système juridique dédié : un simple champ texte suffit (voir échange Étape 17bis).
    conditions_collaboration: str | None = Field(default=None)
