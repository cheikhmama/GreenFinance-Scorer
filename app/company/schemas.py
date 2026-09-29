"""Schémas Pydantic d'entrée/sortie du module Entreprise.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).

Contrat HTTP inchangé pendant le renommage anglais (docs/RENAME_PLAN.md §1, règle 3) : les champs
JSON restent en français, CompanyContractMixin traduit explicitement une Company vers ce contrat.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from app.company.models import Company
from app.core.enums import CompanyStatus, DevisePosition, TypeRapport


def company_vers_contrat(company: Company) -> dict[str, Any]:
    """Point unique de traduction Company -> champs JSON historiques. `actif` reste le booléen
    exposé au frontend : vrai seulement pour une entreprise ACTIVE."""
    return {
        "id": company.id,
        "nom": company.name,
        "secteur": company.sector,
        "pays": company.country,
        "logo": company.logo,
        "description": company.description,
        "site_officiel": company.website,
        "actif": company.status == CompanyStatus.ACTIVE,
        "montant_minimum_investissement": company.minimum_investment_amount,
        "devise_montant_minimum": company.minimum_investment_currency,
        "date_publication": company.published_at,
        "utilisateur_id": company.owner_user_id,
    }


class CompanyContractMixin(BaseModel):
    """À hériter par tout schéma de réponse validé depuis une Company (model_validate ou
    response_model) : la validation part alors du contrat traduit, jamais des attributs anglais."""

    @model_validator(mode="before")
    @classmethod
    def _depuis_company(cls, data: Any) -> Any:
        if isinstance(data, Company):
            return company_vers_contrat(data)
        return data


class EntreprisePublic(CompanyContractMixin):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom: str
    secteur: str
    pays: str
    logo: str | None
    description: str | None
    site_officiel: str | None
    actif: bool
    montant_minimum_investissement: float | None
    devise_montant_minimum: DevisePosition | None
    date_publication: datetime | None


class ImporterRapportParURLRequest(BaseModel):
    """Corps de POST /company/rapports/import-url (CanalDepot.AUTOMATIQUE). entreprise_id n'est
    lu que pour un appelant Administrateur -- un appelant Entreprise est toujours rattaché à sa
    propre entreprise (voir app/company/router.py), un entreprise_id fourni par lui est ignoré."""

    url: str
    type: TypeRapport
    annee_reporting: int
    entreprise_id: uuid.UUID | None = None
