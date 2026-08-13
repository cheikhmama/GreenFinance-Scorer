"""Entités de persistance de l'espace Investisseur : portefeuilles et positions.

Le formulaire de saisie, la conversion de devise affichée en temps réel et
le calcul du taux de change appartiennent à l'Étape 16 (Espace
Investisseur) ; ce module ne pose que le schéma qui les rendra possibles.
Le modèle d'agrégation de portefeuille (app/investor/portfolio.py) reste
implémenté à l'Étape 15.

Notes d'implémentation :
- taux_change_utilise et montant_converti sont figés au moment de la
  création de la position, jamais recalculés rétroactivement.
- PositionPortefeuille active validate_assignment=True : les règles de
  durée (FIXE/OUVERTE) s'appliquent aussi bien à la création qu'à une
  fermeture ultérieure d'une position OUVERTE (date_fin renseignée après
  coup), pas seulement à la construction initiale.
"""

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import ConfigDict, ValidationInfo, model_validator
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import DevisePosition, TypeDureeInvestissement, sa_enum_column

if TYPE_CHECKING:
    from app.auth.models import Utilisateur
    from app.company.models import Entreprise


class Portefeuille(SQLModel, table=True):
    __tablename__ = "portefeuille"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    investisseur_id: uuid.UUID = Field(foreign_key="utilisateur.id")
    nom: str
    date_creation: datetime = Field(default_factory=utcnow)

    investisseur: "Utilisateur" = Relationship(back_populates="portefeuilles")
    positions: list["PositionPortefeuille"] = Relationship(back_populates="portefeuille")


class PositionPortefeuille(SQLModel, table=True):
    __tablename__ = "position_portefeuille"
    model_config = ConfigDict(validate_assignment=True)  # type: ignore[assignment]

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    portefeuille_id: uuid.UUID = Field(foreign_key="portefeuille.id")
    entreprise_id: uuid.UUID = Field(foreign_key="entreprise.id")
    # Montant tel que saisi par l'investisseur, dans la devise ci-dessous.
    montant_investi: float
    devise: DevisePosition = Field(sa_column=sa_enum_column(DevisePosition))
    # Nul si aucune conversion n'était nécessaire ; sinon figé à la valeur
    # en vigueur au moment de la création, jamais recalculé après coup.
    taux_change_utilise: float | None = None
    # Dans la devise de référence de la plateforme ; nul si aucune
    # conversion n'était nécessaire.
    montant_converti: float | None = None
    type_duree: TypeDureeInvestissement = Field(
        sa_column=sa_enum_column(TypeDureeInvestissement)
    )
    date_debut: datetime
    # Obligatoire et validée à la création si FIXE ; nulle à la création
    # si OUVERTE, renseignable plus tard à la fermeture.
    date_fin: datetime | None = None

    portefeuille: Portefeuille = Relationship(back_populates="positions")
    entreprise: "Entreprise" = Relationship(back_populates="positions")

    @model_validator(mode="after")
    def _valider_regles_duree(self) -> "PositionPortefeuille":
        if self.type_duree == TypeDureeInvestissement.FIXE:
            if self.date_fin is None:
                raise ValueError(
                    "date_fin est obligatoire pour une position à durée FIXE"
                )
            if self.date_debut < utcnow():
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
            if self.date_fin is not None and self.date_fin <= self.date_debut:
                raise ValueError(
                    "date_fin, si renseignée, doit être postérieure à date_debut"
                )
        return self

    @model_validator(mode="after")
    def _valider_montant_minimum(self, info: ValidationInfo) -> "PositionPortefeuille":
        context = info.context or {}
        entreprise = context.get("entreprise")
        minimum = entreprise.montant_minimum_investissement if entreprise else None
        if minimum is not None and self.montant_investi < minimum:
            raise ValueError(
                "montant_investi est inférieur au minimum requis par l'entreprise"
            )
        return self
