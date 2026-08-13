"""Entités de persistance produites par le pipeline d'extraction documentaire.

RapportESG porte le cycle de vie documentaire (sept statuts). Les entités
qui en dérivent (IndicateurESG, DonneeCarbone, PreuveDocumentaire —
Prompt 3.5 ; SignalementEcart — Prompt 3.8) sont exclusivement produites
par le pipeline automatique (Étapes 4 à 7) : un Auditeur les consulte et
les valide via AvisAudit (app/audit/models.py), il ne les crée jamais
lui-même — aucun champ ni table ici ne permet une saisie manuelle par
l'Auditeur.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import (
    CanalDepot,
    MethodeDonnee,
    Pilier,
    StatutRapport,
    TypeRapport,
    sa_enum_column,
)

if TYPE_CHECKING:
    from app.audit.models import AvisAudit
    from app.auth.models import Utilisateur
    from app.company.models import Entreprise
    from app.scoring.models import ScoreESG


class RapportESG(SQLModel, table=True):
    __tablename__ = "rapport_esg"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    entreprise_id: uuid.UUID = Field(foreign_key="entreprise.id")
    type: TypeRapport = Field(sa_column=sa_enum_column(TypeRapport))
    canal: CanalDepot = Field(sa_column=sa_enum_column(CanalDepot))
    date_depot: datetime = Field(default_factory=utcnow)
    statut: StatutRapport = Field(
        default=StatutRapport.ENVOYE, sa_column=sa_enum_column(StatutRapport)
    )
    fichier_source: str
    # Champ interne réservé à l'accountability (voir aussi
    # AvisAudit.auditeur_id, Prompt 3.8) : jamais exposé à l'Entreprise
    # dans les couches API futures — règle d'accès à faire respecter à
    # partir de l'Étape 9.
    auditeur_id: uuid.UUID | None = Field(default=None, foreign_key="utilisateur.id")

    entreprise: "Entreprise" = Relationship(back_populates="rapports")
    auditeur: Optional["Utilisateur"] = Relationship(back_populates="rapports_audites")
    indicateurs: list["IndicateurESG"] = Relationship(back_populates="rapport")
    donnees_carbone: list["DonneeCarbone"] = Relationship(back_populates="rapport")
    scores: list["ScoreESG"] = Relationship(back_populates="rapport")
    avis_audit: list["AvisAudit"] = Relationship(back_populates="rapport")


class PreuveDocumentaire(SQLModel, table=True):
    __tablename__ = "preuve_documentaire"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    nom_document: str
    annee: int
    nombre_pages_total: int
    page_debut: int
    page_fin: int
    pdf_extrait_genere: str

    indicateurs: list["IndicateurESG"] = Relationship(back_populates="preuve")
    donnees_carbone: list["DonneeCarbone"] = Relationship(back_populates="preuve")


class IndicateurESG(SQLModel, table=True):
    __tablename__ = "indicateur_esg"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rapport_id: uuid.UUID = Field(foreign_key="rapport_esg.id")
    pilier: Pilier = Field(sa_column=sa_enum_column(Pilier))
    code: str
    valeur: float
    unite: str
    methode: MethodeDonnee = Field(sa_column=sa_enum_column(MethodeDonnee))
    preuve_id: uuid.UUID = Field(foreign_key="preuve_documentaire.id")

    rapport: RapportESG = Relationship(back_populates="indicateurs")
    preuve: PreuveDocumentaire = Relationship(back_populates="indicateurs")
    signalements: list["SignalementEcart"] = Relationship(back_populates="indicateur")


class DonneeCarbone(SQLModel, table=True):
    __tablename__ = "donnee_carbone"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rapport_id: uuid.UUID = Field(foreign_key="rapport_esg.id")
    scope: int
    categorie_ges: str | None = None
    valeur_tonnes_co2e: float
    annee: int
    methode: MethodeDonnee = Field(sa_column=sa_enum_column(MethodeDonnee))
    # Bornée 1-5, validée au niveau Pydantic (pas seulement en base).
    score_qualite_pcaf: int = Field(ge=1, le=5)
    preuve_id: uuid.UUID = Field(foreign_key="preuve_documentaire.id")

    rapport: RapportESG = Relationship(back_populates="donnees_carbone")
    preuve: PreuveDocumentaire = Relationship(back_populates="donnees_carbone")


class SignalementEcart(SQLModel, table=True):
    """Écart signalé sur un indicateur précis — jamais uniquement sur un
    rapport entier."""

    __tablename__ = "signalement_ecart"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    indicateur_id: uuid.UUID = Field(foreign_key="indicateur_esg.id")
    entreprise_id: uuid.UUID = Field(foreign_key="entreprise.id")
    nature_ecart: str
    statut: str = Field(default="OUVERT")
    date_signalement: datetime = Field(default_factory=utcnow)

    indicateur: IndicateurESG = Relationship(back_populates="signalements")
    entreprise: "Entreprise" = Relationship(back_populates="signalements_ecart")
