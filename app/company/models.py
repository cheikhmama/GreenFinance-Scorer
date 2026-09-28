"""Entité de persistance de l'espace Entreprise.

Le compte utilisateur associé est optionnel : une Entreprise peut exister
en base (par exemple créée par le pipeline d'ingestion à partir d'un
dépôt automatique) avant qu'un compte ne lui soit rattaché.
montant_minimum_investissement, nul par défaut, signifie « aucun minimum
imposé » — distinct d'un minimum à zéro. La logique de dépôt de documents
et de consultation du score reste implémentée à l'Étape 10 (Espace
Entreprise + Administrateur).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.core.enums import DevisePosition, sa_enum_column

if TYPE_CHECKING:
    from app.auth.models import Utilisateur
    from app.ingestion.models import RapportESG, SignalementEcart
    from app.investor.models import PositionPortefeuille


class Entreprise(SQLModel, table=True):
    __tablename__ = "entreprise"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    nom: str
    secteur: str
    pays: str
    logo: str | None = None
    description: str | None = None
    site_officiel: str | None = None
    actif: bool = Field(default=True)
    utilisateur_id: uuid.UUID | None = Field(
        default=None, foreign_key="utilisateur.id"
    )
    montant_minimum_investissement: float | None = None
    # Devise dans laquelle montant_minimum_investissement est exprimé — toujours renseignée de
    # pair avec lui (voir app/admin/review_queue.py::modifier_entreprise_admin), jamais l'une sans
    # l'autre : app/investor/portfolio.py::_verifier_montant_minimum en a besoin pour convertir le
    # minimum dans la devise de référence du portefeuille avant comparaison.
    devise_montant_minimum: DevisePosition | None = Field(
        default=None, sa_column=sa_enum_column(DevisePosition, nullable=True)
    )
    # Signal de publication (Étape 10), nullable comme RapportESG.extraction_terminee_le : sert à
    # la fois de booléen (publiée dès que non nul) et de "depuis quand". Distinct du statut du
    # rapport (StatutRapport n'a pas de valeur PUBLIE, et ça reste ainsi) — "valider" un rapport et
    # "publier" une entreprise sont deux gestes délibérément séparés côté Administrateur.
    date_publication: datetime | None = Field(default=None)

    utilisateur: Optional["Utilisateur"] = Relationship(back_populates="entreprise")
    rapports: list["RapportESG"] = Relationship(back_populates="entreprise")
    positions: list["PositionPortefeuille"] = Relationship(back_populates="entreprise")
    signalements_ecart: list["SignalementEcart"] = Relationship(back_populates="entreprise")
