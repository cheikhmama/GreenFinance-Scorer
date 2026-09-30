"""Schémas Pydantic d'entrée/sortie du module Entreprise.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).

Contrat JSON en anglais depuis la tâche 4.7 (docs/RENAME_PLAN.md §3e) : les champs portent les
noms des attributs de Company ; CompanyContractMixin n'ajoute que le booléen calculé `active`.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.auth.schemas import EmailNormalise
from app.company.identifiers import isin_valide, lei_valide
from app.company.models import Company
from app.core.enums import CompanyStatus, Currency, ReportType


def company_vers_contrat(company: Company) -> dict[str, Any]:
    """Point unique de passage Company -> contrat JSON. `active` est le booléen exposé au
    frontend : vrai seulement pour une entreprise ACTIVE."""
    return {
        "id": company.id,
        "name": company.name,
        "sector": company.sector,
        "country": company.country,
        "logo": company.logo,
        "description": company.description,
        "website": company.website,
        "active": company.status == CompanyStatus.ACTIVE,
        "status": company.status,
        "minimum_investment_amount": company.minimum_investment_amount,
        "minimum_investment_currency": company.minimum_investment_currency,
        "published_at": company.published_at,
        "owner_user_id": company.owner_user_id,
        "isin": company.isin,
        "lei": company.lei,
        "ticker": company.ticker,
    }


class CompanyContractMixin(BaseModel):
    """À hériter par tout schéma de réponse validé depuis une Company (model_validate ou
    response_model) : la validation part alors de company_vers_contrat."""

    @model_validator(mode="before")
    @classmethod
    def _depuis_company(cls, data: Any) -> Any:
        if isinstance(data, Company):
            return company_vers_contrat(data)
        return data


class EntreprisePublic(CompanyContractMixin):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sector: str
    country: str
    logo: str | None
    description: str | None
    website: str | None
    active: bool
    # Cycle de vie du compte (tâche 1.3) : distingue une entreprise en attente d'inscription
    # (PENDING_ONBOARDING) d'une entreprise suspendue — `actif` est faux dans les deux cas.
    status: CompanyStatus
    minimum_investment_amount: float | None
    minimum_investment_currency: Currency | None
    published_at: datetime | None
    # Identifiants de marché (tâches 1.3, 2.2) — donnée publique, clé de l'import de portefeuille.
    isin: str | None = None
    lei: str | None = None
    ticker: str | None = None


class ImporterRapportParURLRequest(BaseModel):
    """Corps de POST /company/rapports/import-url (SubmissionChannel.AUTOMATIQUE). entreprise_id n'est
    lu que pour un appelant Administrateur -- un appelant Entreprise est toujours rattaché à sa
    propre entreprise (voir app/company/router.py), un entreprise_id fourni par lui est ignoré."""

    url: str
    type: ReportType
    fiscal_year: int
    company_id: uuid.UUID | None = None


def _une_seule_ligne(valeur: str) -> str:
    if any(ord(caractere) < 32 or ord(caractere) == 127 for caractere in valeur):
        raise ValueError("Ce champ doit tenir sur une seule ligne.")
    return valeur


class CompanyRegistrationRequest(BaseModel):
    """POST /companies/register — inscription publique d'une entreprise (tâche 1.3, décision D5).

    Premier contrat HTTP en anglais (docs/RENAME_PLAN.md §1, règle 3, tâche 1.3) : nouvel endpoint, donc
    directement dans les noms cibles. ISIN et LEI restent facultatifs (beaucoup d'entreprises non
    cotées n'en ont pas) mais, fournis, leur chiffre de contrôle est vérifié.

    `company_fax` est un champ piège : invisible dans le formulaire, un humain le laisse vide ; un
    robot qui remplit tous les champs est ignoré sans le savoir (voir app/company/registration.py).
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_name: str = Field(min_length=2, max_length=200)
    sector: str = Field(min_length=2, max_length=100)
    country: str = Field(description="Code pays ISO 3166-1 alpha-2, ex. MR")
    isin: str | None = None
    lei: str | None = None
    website: str | None = Field(default=None, max_length=500)
    contact_name: str = Field(min_length=2, max_length=100)
    contact_email: EmailNormalise
    company_fax: str | None = None

    @field_validator("company_name", "sector", "contact_name")
    @classmethod
    def _une_ligne(cls, valeur: str) -> str:
        return _une_seule_ligne(valeur)

    @field_validator("country")
    @classmethod
    def _pays_iso(cls, valeur: str) -> str:
        valeur = valeur.upper()
        if len(valeur) != 2 or not valeur.isascii() or not valeur.isalpha():
            raise ValueError("Code pays ISO à deux lettres attendu (ex. MR).")
        return valeur

    @field_validator("isin")
    @classmethod
    def _isin(cls, valeur: str | None) -> str | None:
        if not valeur:
            return None
        valeur = valeur.replace(" ", "").upper()
        if not isin_valide(valeur):
            raise ValueError("ISIN invalide (12 caractères, chiffre de contrôle incorrect).")
        return valeur

    @field_validator("lei")
    @classmethod
    def _lei(cls, valeur: str | None) -> str | None:
        if not valeur:
            return None
        valeur = valeur.replace(" ", "").upper()
        if not lei_valide(valeur):
            raise ValueError("LEI invalide (20 caractères, chiffres de contrôle incorrects).")
        return valeur

    @field_validator("website")
    @classmethod
    def _site(cls, valeur: str | None) -> str | None:
        if not valeur:
            return None
        if not valeur.startswith(("https://", "http://")):
            raise ValueError("Adresse web attendue (https://…).")
        return valeur
