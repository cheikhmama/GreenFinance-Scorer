"""Entités de persistance de l'espace Investisseur : portefeuilles et positions (tables `portfolios`
et `portfolio_positions`, tâche 2.1, docs/RENAME_PLAN.md §4).

Notes d'implémentation :
- fx_rate_used et converted_amount sont figés au moment de la création de la position, jamais
  recalculés rétroactivement.
- PortfolioPosition active validate_assignment=True : les règles de durée (FIXE/OUVERTE)
  s'appliquent aussi bien à la création qu'à une fermeture ultérieure d'une position OUVERTE
  (end_date renseignée après coup), pas seulement à la construction initiale.
- Portfolio.reference_currency fixe la devise d'affichage des montants agrégés (taux statiques,
  voir app/investor/fx.py) ; archived distingue actif/archivé (jamais de suppression brutale d'un
  portefeuille ayant un historique de positions, voir app/investor/portfolio.py).
- Une position est rattachée à une entreprise de la plateforme (MATCHED) ou, pour une ligne
  importée par ISIN/ticker que rien ne reconnaît encore (tâche 2.2), conservée sans entreprise
  (UNMATCHED / AMBIGUOUS) — jamais écartée en silence. ck_portfolio_positions_company_iff_matched
  lie les deux.
- Montants et taux de change en Decimal (numeric en base, tâche 2.3) : jamais de float pour de
  l'argent, le moteur PCAF (app/carbon/pcaf.py) en dépend.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from pydantic import ConfigDict, ValidationInfo, model_validator
from sqlalchemy import CheckConstraint, Column, Numeric
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import (
    Currency,
    DurationType,
    IdentifierType,
    MatchStatus,
    sa_enum_column,
)

if TYPE_CHECKING:
    from app.auth.models import User
    from app.company.models import Company


class Portfolio(SQLModel, table=True):
    __tablename__ = "portfolios"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # CASCADE : un portefeuille n'appartient qu'à son investisseur (docs/RENAME_PLAN.md §3.2,
    # revu avec ce module). L'application ne supprime jamais un compte, elle le désactive.
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    name: str
    reference_currency: Currency = Field(sa_column=sa_enum_column(Currency))
    created_at: datetime = Field(default_factory=utcnow)
    # Jamais de suppression d'un portefeuille ayant déjà eu une position (voir
    # app/investor/portfolio.py) — l'archivage est la seule façon de le retirer de la vue "Mes
    # portefeuilles" par défaut sans perdre son historique.
    archived: bool = Field(default=False)
    # Agrégats mis en cache, recalculés par le moteur PCAF / la file de tâches (tâches 2.3, 4.1) :
    # nuls tant qu'aucun calcul n'a eu lieu, jamais 0 par défaut.
    total_esg_score: float | None = Field(default=None)
    waci: float | None = Field(default=None)
    financed_emissions_tco2e: float | None = Field(default=None)
    computed_at: datetime | None = Field(default=None)
    config_hash: str | None = Field(default=None, max_length=64)

    user: "User" = Relationship(back_populates="portfolios")
    positions: list["PortfolioPosition"] = Relationship(back_populates="portfolio")


class PortfolioPosition(SQLModel, table=True):
    __tablename__ = "portfolio_positions"
    __table_args__ = (
        CheckConstraint("outstanding_amount > 0", name="ck_portfolio_positions_amount_positive"),
        CheckConstraint(
            "weight IS NULL OR (weight > 0 AND weight <= 1)",
            name="ck_portfolio_positions_weight_range",
        ),
        CheckConstraint(
            "(match_status = 'MATCHED') = (company_id IS NOT NULL)",
            name="ck_portfolio_positions_company_iff_matched",
        ),
    )
    model_config = ConfigDict(validate_assignment=True)  # type: ignore[assignment]

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    portfolio_id: uuid.UUID = Field(foreign_key="portfolios.id", ondelete="CASCADE", index=True)
    company_id: uuid.UUID | None = Field(
        default=None, foreign_key="companies.id", ondelete="CASCADE", index=True
    )
    # Identifiant tel que fourni à l'import (tâche 2.2) — conservé même quand aucune entreprise
    # ne correspond. Nuls pour une position saisie en choisissant directement l'entreprise.
    identifier_type: IdentifierType | None = Field(
        default=None, sa_column=sa_enum_column(IdentifierType, nullable=True)
    )
    identifier_raw: str | None = Field(default=None, max_length=64)
    match_status: MatchStatus = Field(
        default=MatchStatus.MATCHED, sa_column=sa_enum_column(MatchStatus)
    )
    # Montant tel que saisi par l'investisseur, dans la devise ci-dessous — requis par PCAF
    # (facteur d'attribution = montant / EVIC, docs/WORKFLOWS.md §2.4).
    outstanding_amount: Decimal = Field(sa_column=Column(Numeric(20, 2), nullable=False))
    currency: Currency = Field(sa_column=sa_enum_column(Currency))
    # Nul si aucune conversion n'était nécessaire (currency == devise de référence du
    # portefeuille) ; sinon figé à la valeur en vigueur au moment de la création.
    fx_rate_used: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(20, 10), nullable=True)
    )
    # Toujours renseigné, dans la devise de référence du portefeuille — égal à outstanding_amount
    # quand aucune conversion n'était nécessaire. Jamais nul : l'agrégation de portefeuille
    # (app/investor/portfolio.py) a besoin d'une valeur exploitable pour CHAQUE position.
    converted_amount: Decimal = Field(sa_column=Column(Numeric(20, 2), nullable=False))
    # Poids déclaré à l'import (tâche 2.2), dans ]0, 1]. Nul pour une position saisie par montant :
    # le poids est alors dérivé des montants à l'affichage.
    weight: Decimal | None = Field(default=None, sa_column=Column(Numeric(11, 10), nullable=True))
    duration_type: DurationType = Field(
        sa_column=sa_enum_column(DurationType)
    )
    start_date: datetime
    # Obligatoire et validée à la création si FIXE ; nulle à la création si OUVERTE,
    # renseignable plus tard à la fermeture.
    end_date: datetime | None = None

    portfolio: Portfolio = Relationship(back_populates="positions")
    company: Optional["Company"] = Relationship(back_populates="positions")

    @model_validator(mode="after")
    def _valider_regles_duree(self) -> "PortfolioPosition":
        if self.duration_type == DurationType.FIXE:
            if self.end_date is None:
                raise ValueError("end_date est obligatoire pour une position à durée FIXE")
            if self.start_date.date() < utcnow().date():
                # Comparaison au jour près (voir cahier des charges : "date de début >= date du
                # jour"), jamais à l'instant précis — une comparaison datetime exacte échouerait
                # systématiquement à cause de la latence réseau normale entre la saisie côté
                # client et la validation côté serveur.
                raise ValueError(
                    "start_date doit être postérieure ou égale à la date actuelle "
                    "pour une position FIXE"
                )
            if self.end_date > self.start_date + timedelta(days=365):
                raise ValueError(
                    "end_date ne peut pas dépasser un an après start_date pour une position FIXE"
                )
            if self.end_date <= self.start_date:
                raise ValueError("end_date doit être postérieure à start_date")
        elif self.duration_type == DurationType.OUVERTE:
            if self.end_date is None and self.start_date.date() < utcnow().date():
                # Comparaison au jour près, même raison que la branche FIXE ci-dessus. La règle
                # "start_date >= aujourd'hui" ne s'applique qu'à la création (end_date encore
                # nulle) — une fermeture ultérieure (end_date renseignée après coup) fixe
                # forcément une start_date déjà passée, ce n'est jamais une erreur à ce moment-là.
                raise ValueError(
                    "start_date doit être postérieure ou égale à la date actuelle "
                    "pour une position OUVERTE"
                )
            if self.end_date is not None and self.end_date <= self.start_date:
                raise ValueError("end_date, si renseignée, doit être postérieure à start_date")
        return self

    @model_validator(mode="after")
    def _valider_montant_minimum(self, info: ValidationInfo) -> "PortfolioPosition":
        context = info.context or {}
        entreprise = context.get("entreprise")
        minimum = entreprise.minimum_investment_amount if entreprise else None
        if minimum is not None and self.outstanding_amount < minimum:
            raise ValueError(
                "outstanding_amount est inférieur au minimum requis par l'entreprise"
            )
        return self
