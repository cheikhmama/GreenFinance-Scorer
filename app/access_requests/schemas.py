"""Contrat HTTP des demandes d'accès (tâche 5.10) — nouveaux endpoints, donc en anglais."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.auth.schemas import EmailNormalise
from app.core.enums import AccessRequestStatus, InvestorType, ResearchDomain, Role


class RequestedRole(str, Enum):
    INVESTOR = "INVESTOR"
    RESEARCHER = "RESEARCHER"


class AccessRequestCreate(BaseModel):
    """POST /access-requests — public. `organization` : le fonds ou la société d'investissement,
    l'université ou l'organisme de recherche. `website_fax` est un champ piège : un humain le
    laisse vide (même principe que l'inscription d'une entreprise)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    role: RequestedRole
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailNormalise
    organization: str = Field(min_length=2, max_length=200)
    investor_type: InvestorType | None = None
    research_domain: ResearchDomain | None = None
    website_fax: str | None = None

    @field_validator("full_name", "organization")
    @classmethod
    def _une_ligne(cls, valeur: str) -> str:
        if "\n" in valeur or "\r" in valeur:
            raise ValueError("Une seule ligne attendue.")
        return valeur

    @model_validator(mode="after")
    def _precision_du_role(self) -> "AccessRequestCreate":
        if self.role == RequestedRole.INVESTOR:
            if self.investor_type is None:
                raise ValueError("Le type d'investisseur est requis.")
            self.research_domain = None
        else:
            if self.research_domain is None:
                raise ValueError("Le domaine de recherche est requis.")
            self.investor_type = None
        return self


class AccessRequestView(BaseModel):
    """Une demande vue par l'Administrateur."""

    id: uuid.UUID
    user_id: uuid.UUID
    role: Role
    full_name: str | None
    email: str
    organization: str
    investor_type: InvestorType | None
    research_domain: ResearchDomain | None
    status: AccessRequestStatus
    requested_at: datetime
    decided_at: datetime | None
    rejection_reason: str | None


class AccessDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class AccessDecisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    decision: AccessDecision
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _motif_du_refus(self) -> "AccessDecisionRequest":
        if self.decision == AccessDecision.REJECT and not self.reason:
            raise ValueError("Un motif est requis pour refuser une demande.")
        return self
