"""Entité de persistance de l'espace Entreprise (table `companies`, docs/RENAME_PLAN.md §2.1).

Le compte utilisateur associé est optionnel : une Company peut exister en base (par exemple créée
par le pipeline d'ingestion à partir d'un dépôt automatique) avant qu'un compte ne lui soit
rattaché. minimum_investment_amount, nul par défaut, signifie « aucun minimum imposé » — distinct
d'un minimum à zéro.

status (cycle de vie du compte / KYC) et published_at (publication du score officiel) sont deux
notions distinctes, voir docs/WORKFLOWS.md §1.1 : une entreprise SUSPENDED reste visible des
investisseurs qui la détiennent déjà, et seule une entreprise publiée apparaît aux catalogues
Investisseur et Chercheur.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Numeric
from sqlmodel import Field, Relationship, SQLModel

from app.core.enums import CompanyStatus, DevisePosition, sa_enum_column

if TYPE_CHECKING:
    from app.auth.models import User
    from app.ingestion.models import ESGReport, SignalementEcart
    from app.investor.models import PositionPortefeuille


class Company(SQLModel, table=True):
    __tablename__ = "companies"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    sector: str
    country: str
    logo: str | None = None
    description: str | None = None
    website: str | None = None
    status: CompanyStatus = Field(
        default=CompanyStatus.ACTIVE, sa_column=sa_enum_column(CompanyStatus)
    )
    owner_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL", index=True
    )
    # Identifiants de marché (ISO 6166 / ISO 17442) — uniques quand renseignés, clé de
    # rapprochement des positions importées (tâche 2.2) et des jeux de données publics (tâche 3.3).
    isin: str | None = Field(default=None, max_length=12, unique=True)
    lei: str | None = Field(default=None, max_length=20, unique=True)
    # Données financières requises par PCAF (docs/WORKFLOWS.md §2.4) : chiffre d'affaires pour la
    # WACI, valeur d'entreprise trésorerie incluse (EVIC) pour le facteur d'attribution. Montants
    # en Decimal, jamais en float.
    revenue: Decimal | None = Field(default=None, sa_column=Column(Numeric(20, 2), nullable=True))
    revenue_currency: DevisePosition | None = Field(
        default=None, sa_column=sa_enum_column(DevisePosition, nullable=True)
    )
    enterprise_value: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(20, 2), nullable=True)
    )
    enterprise_value_currency: DevisePosition | None = Field(
        default=None, sa_column=sa_enum_column(DevisePosition, nullable=True)
    )
    enterprise_value_as_of: date | None = None
    minimum_investment_amount: float | None = None
    # Devise dans laquelle minimum_investment_amount est exprimé — toujours renseignée de pair
    # avec lui (voir app/admin/review_queue.py::modifier_entreprise_admin), jamais l'une sans
    # l'autre : app/investor/portfolio.py::_verifier_montant_minimum en a besoin pour convertir le
    # minimum dans la devise de référence du portefeuille avant comparaison.
    minimum_investment_currency: DevisePosition | None = Field(
        default=None, sa_column=sa_enum_column(DevisePosition, nullable=True)
    )
    # Dernière publication du score officiel par l'Administrateur : sert à la fois de booléen
    # (publiée dès que non nul) et de "depuis quand". Distinct du statut du rapport et du statut
    # de la Company — "valider" un rapport et "publier" une entreprise sont deux gestes
    # délibérément séparés côté Administrateur.
    published_at: datetime | None = Field(default=None)

    owner: Optional["User"] = Relationship(back_populates="company")
    reports: list["ESGReport"] = Relationship(back_populates="company")
    positions: list["PositionPortefeuille"] = Relationship(back_populates="entreprise")
    discrepancy_flags: list["SignalementEcart"] = Relationship(back_populates="entreprise")
