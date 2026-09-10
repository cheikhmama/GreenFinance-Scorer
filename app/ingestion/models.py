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

from sqlalchemy import CheckConstraint, UniqueConstraint
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
    # Un même fichier (même empreinte) ne peut être déposé deux fois pour la même entreprise
    # (Phase 5 §6) — plusieurs NULL restent autorisés (rapports déposés avant l'introduction du
    # checksum), PostgreSQL ne les compare jamais égaux entre eux dans une contrainte UNIQUE.
    __table_args__ = (
        UniqueConstraint(
            "entreprise_id", "checksum_sha256", name="uq_rapport_esg_entreprise_checksum"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    entreprise_id: uuid.UUID = Field(foreign_key="entreprise.id")
    type: TypeRapport = Field(sa_column=sa_enum_column(TypeRapport))
    canal: CanalDepot = Field(sa_column=sa_enum_column(CanalDepot))
    date_depot: datetime = Field(default_factory=utcnow)
    statut: StatutRapport = Field(
        default=StatutRapport.ENVOYE, sa_column=sa_enum_column(StatutRapport)
    )
    fichier_source: str
    # Persisté dès le dépôt (Phase 4 §4.3) — auparavant transmis uniquement en paramètre au
    # pipeline d'extraction (run_extraction_pipeline) puis perdu, aucune trace si l'extraction
    # échouait ou devait être rejouée plus tard. Nullable comme extraction_terminee_le/
    # checksum_sha256 : les rapports déposés avant cette passe n'ont pas cette valeur.
    annee_reporting: int | None = Field(default=None)
    # Champ interne réservé à l'accountability (voir aussi
    # AvisAudit.auditeur_id, Prompt 3.8) : jamais exposé à l'Entreprise
    # dans les couches API futures — règle d'accès à faire respecter à
    # partir de l'Étape 9.
    auditeur_id: uuid.UUID | None = Field(default=None, foreign_key="utilisateur.id")
    # Posée par affecter_auditeur (app/audit/assignment.py) au moment de l'affectation — distincte
    # de date_depot/extraction_terminee_le, nécessaire pour calculer un retard d'audit (SLA fixe,
    # app/core/config.py::sla_audit_jours) sans quoi aucune colonne ne porte ce moment précis.
    date_affectation: datetime | None = Field(default=None)
    # Signal de fin du pipeline d'extraction (Étape 5), distinct de `statut` : `statut` reste
    # EN_EXTRACTION jusqu'à l'affectation d'un auditeur (Étape 10), ces deux colonnes nullable
    # permettent de distinguer en cours / réussi / échoué sans ajouter de valeur à StatutRapport.
    # extraction_erreur ne contient jamais str(exception) (fuite potentielle de contenu sensible),
    # seulement une chaîne de classification fixe — voir app/ingestion/extractor.py.
    extraction_terminee_le: datetime | None = Field(default=None)
    extraction_erreur: str | None = Field(default=None)
    # Versioning (Phase 4 §4.1) : une correction ne réécrit jamais l'original — elle crée une
    # nouvelle ligne, rapport_precedent_id pointant vers celle qu'elle remplace. version=1 par
    # défaut pour un dépôt initial, jamais recalculé après coup. Pas de Relationship() ORM
    # dédiée ici (auto-référence) — la chaîne se parcourt par requête explicite quand nécessaire,
    # plus simple qu'une relationship auto-référentielle.
    version: int = Field(default=1)
    rapport_precedent_id: uuid.UUID | None = Field(default=None, foreign_key="rapport_esg.id")
    # Empreinte du contenu déposé (Phase 4 §4.2) — détecte un doublon avant tout traitement.
    # Nul pour les rapports déposés avant cette passe.
    checksum_sha256: str | None = Field(default=None, index=True)

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
    """Scope/qualité PCAF/valeur sont bornés à la fois côté Pydantic (Field ci-dessous) et côté
    PostgreSQL (__table_args__, Phase 5 §6) — un INSERT direct ou un futur endpoint qui
    contournerait le modèle Pydantic reste protégé par la contrainte SQL."""

    __tablename__ = "donnee_carbone"
    __table_args__ = (
        CheckConstraint("scope IN (1, 2, 3)", name="ck_donnee_carbone_scope_valide"),
        CheckConstraint(
            "score_qualite_pcaf BETWEEN 1 AND 5", name="ck_donnee_carbone_pcaf_borne"
        ),
        CheckConstraint(
            "valeur_tonnes_co2e >= 0", name="ck_donnee_carbone_valeur_non_negative"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rapport_id: uuid.UUID = Field(foreign_key="rapport_esg.id")
    scope: int = Field(ge=1, le=3)
    categorie_ges: str | None = None
    valeur_tonnes_co2e: float = Field(ge=0)
    annee: int
    methode: MethodeDonnee = Field(sa_column=sa_enum_column(MethodeDonnee))
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
