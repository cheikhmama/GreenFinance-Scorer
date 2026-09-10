"""Entités de persistance liées à l'authentification (utilisateurs, rôles, rattachements).

Le schéma pivot (Étape 3) est posé ici : Utilisateur reste une table
unique à discriminant `role`, jamais une table séparée par sous-rôle. La
logique métier d'authentification (connexion, hachage, MFA, permissions)
reste implémentée à l'Étape 9 (Authentification et autorisation).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import Role, sa_enum_column

if TYPE_CHECKING:
    from app.audit.models import AvisAudit
    from app.company.models import Entreprise
    from app.core.models import Notification
    from app.ingestion.models import RapportESG
    from app.investor.models import Portefeuille
    from app.scoring.models import ConfigurationPonderation


class Utilisateur(SQLModel, table=True):
    __tablename__ = "utilisateur"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    nom: str | None = None
    mot_de_passe_hache: str
    role: Role = Field(sa_column=sa_enum_column(Role))
    date_creation: datetime = Field(default_factory=utcnow)
    actif: bool = Field(default=True)
    # Vrai pour un compte provisionné par l'Administrateur avec un mot de passe temporaire
    # (Phase 3 §3.3) : get_current_user (app/core/dependencies.py) bloque alors tout accès hors
    # d'une liste explicite de routes tant que POST /auth/changer-mot-de-passe n'a pas été appelé.
    doit_changer_mot_de_passe: bool = Field(default=False)

    institution_profil: Optional["InstitutionProfil"] = Relationship(
        back_populates="utilisateur"
    )
    entreprise: Optional["Entreprise"] = Relationship(back_populates="utilisateur")
    rapports_audites: list["RapportESG"] = Relationship(back_populates="auditeur")
    configurations_ponderation: list["ConfigurationPonderation"] = Relationship(
        back_populates="utilisateur"
    )
    portefeuilles: list["Portefeuille"] = Relationship(back_populates="investisseur")
    avis_rendus: list["AvisAudit"] = Relationship(back_populates="auditeur")
    notifications: list["Notification"] = Relationship(back_populates="utilisateur")


class InstitutionProfil(SQLModel, table=True):
    """Profil complémentaire 1-1, uniquement pertinent pour un Utilisateur
    dont le role est INSTITUTION."""

    __tablename__ = "institution_profil"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    utilisateur_id: uuid.UUID = Field(foreign_key="utilisateur.id", unique=True)
    quota_export: int

    utilisateur: Utilisateur = Relationship(back_populates="institution_profil")


class ChercheurInstitution(SQLModel, table=True):
    """Table de rattachement plusieurs-à-plusieurs entre un Utilisateur
    Chercheur et un Utilisateur Institution."""

    __tablename__ = "chercheur_institution"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chercheur_id: uuid.UUID = Field(foreign_key="utilisateur.id")
    institution_id: uuid.UUID = Field(foreign_key="utilisateur.id")
