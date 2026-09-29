"""Entités de persistance de l'espace Investisseur : portefeuilles et positions.

Le formulaire de saisie, la conversion de devise affichée en temps réel et le calcul du taux de
change sont implémentés dans app/investor/{fx,portfolio}.py (Étape 15/16).

Notes d'implémentation :
- taux_change_utilise et montant_converti sont figés au moment de la
  création de la position, jamais recalculés rétroactivement.
- PositionPortefeuille active validate_assignment=True : les règles de
  durée (FIXE/OUVERTE) s'appliquent aussi bien à la création qu'à une
  fermeture ultérieure d'une position OUVERTE (date_fin renseignée après
  coup), pas seulement à la construction initiale.
- Portefeuille.devise_reference fixe la devise d'affichage des montants agrégés (taux statiques,
  voir app/investor/fx.py) ; archive distingue actif/archivé (jamais de suppression brutale d'un
  portefeuille ayant un historique de positions, voir app/investor/portfolio.py).
"""

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import ConfigDict, ValidationInfo, model_validator
from sqlalchemy import CheckConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import DevisePosition, TypeDureeInvestissement, sa_enum_column

if TYPE_CHECKING:
    from app.auth.models import User
    from app.company.models import Company


class Portefeuille(SQLModel, table=True):
    __tablename__ = "portefeuille"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    investisseur_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    nom: str
    devise_reference: DevisePosition = Field(sa_column=sa_enum_column(DevisePosition))
    date_creation: datetime = Field(default_factory=utcnow)
    # Jamais de suppression d'un portefeuille ayant déjà eu une position (voir
    # app/investor/portfolio.py) — l'archivage est la seule façon de le retirer de la vue "Mes
    # portefeuilles" par défaut sans perdre son historique.
    archive: bool = Field(default=False)

    investisseur: "User" = Relationship(back_populates="portfolios")
    positions: list["PositionPortefeuille"] = Relationship(back_populates="portefeuille")


class PositionPortefeuille(SQLModel, table=True):
    __tablename__ = "position_portefeuille"
    __table_args__ = (
        CheckConstraint("montant_investi > 0", name="ck_position_portefeuille_montant_positif"),
    )
    model_config = ConfigDict(validate_assignment=True)  # type: ignore[assignment]

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    portefeuille_id: uuid.UUID = Field(foreign_key="portefeuille.id")
    entreprise_id: uuid.UUID = Field(foreign_key="companies.id", ondelete="CASCADE", index=True)
    # Montant tel que saisi par l'investisseur, dans la devise ci-dessous.
    montant_investi: float
    devise: DevisePosition = Field(sa_column=sa_enum_column(DevisePosition))
    # Nul si aucune conversion n'était nécessaire (devise == devise de référence du
    # portefeuille) ; sinon figé à la valeur en vigueur au moment de la création, jamais
    # recalculé après coup.
    taux_change_utilise: float | None = None
    # Toujours renseigné, dans la devise de référence du portefeuille — égal à montant_investi
    # quand aucune conversion n'était nécessaire (voir taux_change_utilise, seul indicateur nul
    # de ce cas). Jamais nul : l'agrégation de portefeuille (app/investor/portfolio.py) a besoin
    # d'une valeur exploitable pour CHAQUE position, converties ou non.
    montant_converti: float
    type_duree: TypeDureeInvestissement = Field(
        sa_column=sa_enum_column(TypeDureeInvestissement)
    )
    date_debut: datetime
    # Obligatoire et validée à la création si FIXE ; nulle à la création
    # si OUVERTE, renseignable plus tard à la fermeture.
    date_fin: datetime | None = None

    portefeuille: Portefeuille = Relationship(back_populates="positions")
    entreprise: "Company" = Relationship(back_populates="positions")

    @model_validator(mode="after")
    def _valider_regles_duree(self) -> "PositionPortefeuille":
        if self.type_duree == TypeDureeInvestissement.FIXE:
            if self.date_fin is None:
                raise ValueError(
                    "date_fin est obligatoire pour une position à durée FIXE"
                )
            if self.date_debut.date() < utcnow().date():
                # Comparaison au jour près (voir cahier des charges : "date de début >= date du
                # jour"), jamais à l'instant précis — une comparaison datetime exacte échouerait
                # systématiquement à cause de la latence réseau normale entre la saisie côté
                # client et la validation côté serveur.
                raise ValueError(
                    "date_debut doit être postérieure ou égale à la date actuelle "
                    "pour une position FIXE"
                )
            if self.date_fin > self.date_debut + timedelta(days=365):
                raise ValueError(
                    "date_fin ne peut pas dépasser un an après date_debut "
                    "pour une position FIXE"
                )
            if self.date_fin <= self.date_debut:
                raise ValueError("date_fin doit être postérieure à date_debut")
        elif self.type_duree == TypeDureeInvestissement.OUVERTE:
            if self.date_fin is None and self.date_debut.date() < utcnow().date():
                # Comparaison au jour près, même raison que la branche FIXE ci-dessus. La règle
                # "date_debut >= aujourd'hui" ne s'applique qu'à la création (date_fin encore
                # nulle) — une fermeture ultérieure (date_fin renseignée après coup) fixe
                # forcément une date_debut déjà passée, ce n'est jamais une erreur à ce moment-là.
                raise ValueError(
                    "date_debut doit être postérieure ou égale à la date actuelle "
                    "pour une position OUVERTE"
                )
            if self.date_fin is not None and self.date_fin <= self.date_debut:
                raise ValueError(
                    "date_fin, si renseignée, doit être postérieure à date_debut"
                )
        return self

    @model_validator(mode="after")
    def _valider_montant_minimum(self, info: ValidationInfo) -> "PositionPortefeuille":
        context = info.context or {}
        entreprise = context.get("entreprise")
        minimum = entreprise.minimum_investment_amount if entreprise else None
        if minimum is not None and self.montant_investi < minimum:
            raise ValueError(
                "montant_investi est inférieur au minimum requis par l'entreprise"
            )
        return self
