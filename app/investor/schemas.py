"""Schémas Pydantic d'entrée/sortie du module Investisseur.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2). Réutilise les schémas
déjà exposés par app/ingestion/schemas.py (IndicateurESGDetail, DonneeCarboneDetail,
PreuveDocumentairePublic) plutôt que d'en dupliquer une variante Investisseur — même contrat,
même garantie (jamais l'auditeur_id, voir RapportESGDetail).
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.carbon.pcaf import CarbonExclusionReason
from app.company.schemas import CompanyContractMixin, EntreprisePublic
from app.core.enums import (
    DevisePosition,
    IdentifierType,
    MatchStatus,
    TypeDureeInvestissement,
)
from app.ingestion.schemas import (
    CouvertureResume,
    DonneeCarboneDetail,
    IndicateurESGDetail,
)


def _vers_naif_utc(valeur: datetime) -> datetime:
    """Normalise un datetime éventuellement "aware" (ex. suffixe Z produit par
    Date.toISOString() côté frontend) vers un naïf en UTC — même convention que
    app/core/database.py::utcnow() et les colonnes TIMESTAMP WITHOUT TIME ZONE. Sans cette
    normalisation à la frontière, comparer ce champ à une valeur déjà stockée (toujours naïve)
    lève TypeError: can't compare offset-naive and offset-aware datetimes, jamais rattrapé
    comme une simple erreur de validation (voir app/investor/portfolio.py::fermer_position)."""
    if valeur.tzinfo is not None:
        return valeur.astimezone(UTC).replace(tzinfo=None)
    return valeur


class EtatPosition(str, Enum):
    PLANIFIEE = "PLANIFIEE"
    ACTIVE = "ACTIVE"
    CLOTUREE = "CLOTUREE"
    ENTREPRISE_SUSPENDUE = "ENTREPRISE_SUSPENDUE"


class ScoreEntreprisePublic(BaseModel):
    """Score de la dernière publication d'une entreprise — jamais fabriqué : absent (tous les
    champs à None) si l'entreprise n'a en réalité aucun score calculé, ce qui n'arrive normalement
    jamais pour une entreprise publiée (publier_entreprise l'exige), mais reste possible en
    lecture défensive."""

    valeur_globale: float | None
    score_environnement: float | None
    score_social: float | None
    score_gouvernance: float | None
    taux_couverture: float | None = None  # 0-1, voir app/scoring/schemas.py::ScoreESGPublic
    configuration_version: int | None


class DonneesCarboneAgregees(BaseModel):
    scope_1: float | None
    scope_2_market_based: float | None
    scope_2_location_based: float | None
    scope_3: float | None


class EntreprisePublieePublic(EntreprisePublic):
    """Entreprise publiée, telle que consultable par l'Investisseur — étend EntreprisePublic
    (déjà utilisé côté Entreprise/Admin) avec le score, les émissions Scope 1/2/3 de son dernier
    rapport validé, et son montant minimum d'investissement pré-converti dans les 3 devises (voir
    app/investor/entreprises.py::montant_minimum_par_devise) — le frontend n'a qu'à lire la
    valeur de la devise déjà choisie pour la position, jamais de conversion côté client."""

    score: ScoreEntreprisePublic
    carbone: DonneesCarboneAgregees
    montant_minimum_par_devise: dict[DevisePosition, float] | None


class EntrepriseDetailInvestisseur(EntreprisePublieePublic):
    """Détail d'une entreprise publiée, avec les indicateurs et données carbone sources (chacun
    portant sa preuve documentaire) — c'est ici que l'Investisseur vérifie une source, pas
    seulement le score agrégé."""

    indicateurs: list[IndicateurESGDetail]
    donnees_carbone: list[DonneeCarboneDetail]
    couverture: CouvertureResume
    # Le rapport publié affiché (tâche 3.2) : clé de GET /reports/{id}/score-explanation.
    rapport_id: uuid.UUID | None = None


class CreerPortefeuilleRequest(BaseModel):
    nom: str


class RenommerPortefeuilleRequest(BaseModel):
    nom: str


class AjouterPositionRequest(BaseModel):
    entreprise_id: uuid.UUID
    # gt=0, jamais seulement le CheckConstraint SQL ("montant_investi > 0", voir
    # app/investor/models.py) : sans cette validation ici, un montant négatif ou nul remonterait
    # comme une IntegrityError Postgres non rattrapée (500) plutôt qu'un 422 propre. Decimal au
    # centime près (tâche 2.3) : un montant à plus de deux décimales est refusé, jamais arrondi
    # en silence.
    montant: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    devise: DevisePosition
    type_duree: TypeDureeInvestissement
    date_debut: datetime
    date_fin: datetime | None = None

    @field_validator("date_debut", "date_fin")
    @classmethod
    def _normaliser_dates(cls, valeur: datetime | None) -> datetime | None:
        return _vers_naif_utc(valeur) if valeur is not None else None


class ModifierPositionRequest(BaseModel):
    """Une position ne peut être modifiée que tant qu'elle est encore PLANIFIEE (voir
    app/investor/portfolio.py) — l'entreprise concernée n'est jamais modifiable après création,
    seule une fermeture puis une nouvelle position permet de changer de cible."""

    montant: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    devise: DevisePosition
    type_duree: TypeDureeInvestissement
    date_debut: datetime
    date_fin: datetime | None = None

    @field_validator("date_debut", "date_fin")
    @classmethod
    def _normaliser_dates(cls, valeur: datetime | None) -> datetime | None:
        return _vers_naif_utc(valeur) if valeur is not None else None


class FermerPositionRequest(BaseModel):
    date_fin: datetime | None = None

    @field_validator("date_fin")
    @classmethod
    def _normaliser_date_fin(cls, valeur: datetime | None) -> datetime | None:
        return _vers_naif_utc(valeur) if valeur is not None else None


class EntrepriseSommaire(CompanyContractMixin):
    """Vue minimale d'une entreprise, imbriquée dans une position — jamais le détail complet
    (indicateurs/preuves), qui se consulte séparément via GET /investor/entreprises/{id}."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom: str
    secteur: str
    pays: str
    logo: str | None
    actif: bool


class PositionDetail(BaseModel):
    id: uuid.UUID
    portefeuille_id: uuid.UUID
    # Nulle pour une ligne importée qu'aucune entreprise publiée ne reconnaît (tâche 2.2) : elle
    # reste listée avec son identifiant d'origine et statut_rapprochement.
    entreprise: EntrepriseSommaire | None
    identifiant: str | None = None
    type_identifiant: IdentifierType | None = None
    statut_rapprochement: MatchStatus = MatchStatus.MATCHED
    montant_investi: float
    devise: DevisePosition
    montant_converti: float
    taux_change_utilise: float | None
    poids: float
    type_duree: TypeDureeInvestissement
    date_debut: datetime
    date_fin: datetime | None
    etat: EtatPosition
    score: ScoreEntreprisePublic
    date_publication_utilisee: datetime | None
    preuves_disponibles: bool


class PortefeuilleResume(BaseModel):
    id: uuid.UUID
    nom: str
    devise_reference: DevisePosition
    montant_total: float
    nombre_positions: int
    score_esg_agrege: float | None
    score_environnement_agrege: float | None
    score_social_agrege: float | None
    score_gouvernance_agrege: float | None
    couverture_esg: float
    date_creation: datetime
    archive: bool


class PortefeuilleDetail(PortefeuilleResume):
    nombre_positions_planifiees: int
    nombre_positions_actives: int
    nombre_positions_cloturees: int
    positions: list[PositionDetail]


class RepartitionSecteur(BaseModel):
    secteur: str
    montant_usd: float


class TableauDeBordInvestisseur(BaseModel):
    nombre_portefeuilles: int
    nombre_entreprises_publiees: int
    taux_couverture_esg_plateforme: float
    nombre_nouvelles_publications_suivies: int
    repartition_secteur: list[RepartitionSecteur]
    publications_recentes: list[EntreprisePublieePublic]
    entreprises_suivies_suspendues: list[EntrepriseSommaire]


class PortfolioImportResult(BaseModel):
    """POST /portfolios/{id}/positions/import (tâche 2.2) — contrat JSON en anglais. Les lignes en
    erreur ne figurent jamais ici : un import refusé répond 422 avec `fields.line_<n>`."""

    portfolio_id: uuid.UUID
    imported: int
    matched: int
    unmatched: int
    ambiguous: int


class PositionCarbon(BaseModel):
    """Une position active dans l'empreinte carbone PCAF (tâche 2.3). `excluded_reason` dit
    pourquoi elle ne compte pas dans les émissions financées Scopes 1+2 — une donnée manquante
    n'est jamais comptée comme zéro."""

    position_id: uuid.UUID
    company_id: uuid.UUID | None
    company_name: str | None
    identifier: str | None
    amount: float  # dans la devise du portefeuille
    attribution_factor: float | None
    financed_emissions_scope_1_2: float | None  # tCO₂e
    financed_emissions_scope_3: float | None  # tCO₂e, jamais additionné aux Scopes 1+2
    carbon_intensity: float | None  # tCO₂e par million de chiffre d'affaires
    data_quality: int | None  # score PCAF 1 (meilleur) à 5
    emissions_year: int | None
    scope_2_basis: str | None  # market_based, location_based, ou null si non précisé
    enterprise_value_as_of: date | None
    excluded_reason: CarbonExclusionReason | None


class PortfolioCarbon(BaseModel):
    """GET /portfolios/{id}/carbon (tâche 2.3, contrat JSON en anglais, docs/WORKFLOWS.md §2.4).
    Les couvertures sont des parts du montant total, entre 0 et 1 ; chaque agrégat est nul quand
    aucune position ne le permet."""

    portfolio_id: uuid.UUID
    currency: DevisePosition
    total_value: float
    financed_emissions_scope_1_2: float | None
    financed_emissions_scope_3: float | None
    carbon_footprint_scope_1_2: float | None  # tCO₂e par million investi
    waci_scope_1_2: float | None  # tCO₂e par million de chiffre d'affaires
    data_quality_scope_1_2: float | None
    data_quality_scope_3: float | None
    coverage_scope_1_2: float
    coverage_scope_3: float
    coverage_waci: float
    positions: list[PositionCarbon]

