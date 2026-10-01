"""Schémas du module reporting — nouveaux endpoints, donc contrat JSON directement en anglais
(docs/RENAME_PLAN.md §1, règle 3)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.database import utcnow
from app.core.enums import ReportStatus, ReportType
from app.ingestion.models import ESGReport


class ReportCreateRequest(BaseModel):
    """POST /reports — ouvre une déclaration (DRAFT) pour un exercice, avant tout fichier.

    `company_id` n'est lu que pour un Administrateur ; une Entreprise déclare toujours pour la
    sienne (même règle que l'import par URL, app/company/router.py)."""

    model_config = ConfigDict(extra="forbid")

    fiscal_year: int = Field(ge=2000)
    report_type: ReportType
    company_id: uuid.UUID | None = None

    @field_validator("fiscal_year")
    @classmethod
    def _exercice_passe_ou_courant(cls, valeur: int) -> int:
        if valeur > utcnow().year:
            raise ValueError("L'exercice ne peut pas être postérieur à l'année en cours.")
        return valeur


class ReportResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    report_type: ReportType
    fiscal_year: int | None
    status: ReportStatus
    version: int
    previous_report_id: uuid.UUID | None
    created_at: datetime
    submitted_at: datetime | None
    original_filename: str | None
    official_score: float | None

    @classmethod
    def depuis(cls, rapport: ESGReport) -> "ReportResponse":
        return cls(
            id=rapport.id,
            company_id=rapport.company_id,
            report_type=rapport.type,
            fiscal_year=rapport.fiscal_year,
            status=rapport.status,
            version=rapport.version,
            previous_report_id=rapport.previous_report_id,
            created_at=rapport.created_at,
            submitted_at=rapport.submitted_at,
            original_filename=rapport.original_filename,
            official_score=rapport.official_score,
        )
