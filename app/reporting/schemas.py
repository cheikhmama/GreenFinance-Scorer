"""Schémas du module reporting — nouveaux endpoints, donc contrat JSON directement en anglais
(docs/RENAME_PLAN.md §1, règle 3)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.database import utcnow
from app.core.enums import Currency, ReportStatus, ReportType
from app.ingestion.models import ESGReport


class ReportCreateRequest(BaseModel):
    """POST /reports — ouvre une déclaration (DRAFT) pour un exercice, avant tout fichier.

    `company_id` n'est lu que pour un Administrateur ; une Entreprise déclare toujours pour la
    sienne (même règle que l'import par URL, app/company/router.py).

    Données financières de l'exercice (tâche 5.9), facultatives : une devise pour le chiffre
    d'affaires et l'EVIC. Sans date, l'EVIC est datée de la clôture de l'exercice (31 décembre).
    Elles ne comptent pour PCAF qu'une fois le rapport validé (tâche 5.4) ; l'Administrateur peut
    toujours les corriger."""

    model_config = ConfigDict(extra="forbid")

    fiscal_year: int = Field(ge=2000)
    report_type: ReportType
    company_id: uuid.UUID | None = None
    currency: Currency | None = None
    revenue: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=2)
    enterprise_value: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=2)
    evic_date: date | None = None

    @model_validator(mode="after")
    def _montants_avec_devise(self) -> "ReportCreateRequest":
        if (self.revenue is not None or self.enterprise_value is not None) and self.currency is None:
            raise ValueError("Une devise est requise avec le chiffre d'affaires ou l'EVIC.")
        if self.enterprise_value is None and self.evic_date is not None:
            raise ValueError("evic_date n'a de sens qu'avec enterprise_value.")
        return self

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
    # Reçu de soumission (tâche 5.8) : empreinte du fichier joint, avec submitted_at.
    checksum_sha256: str | None
    # Analyse du fichier d'un brouillon (tâche 5.8) : terminée quand extraction_finished_at est
    # posé sans erreur ; sinon cause fixe de l'échec (jamais le texte d'une exception).
    extraction_finished_at: datetime | None
    extraction_error: str | None

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
            checksum_sha256=rapport.checksum_sha256,
            extraction_finished_at=rapport.extraction_finished_at,
            extraction_error=rapport.extraction_error,
        )


GROUPE_CARBONE = "CARBON"


class GroupeCompletude(BaseModel):
    """Liste de complétude d'un brouillon (tâche 5.8) : des comptes, jamais de valeurs.
    `group` : `CARBON` ou un pilier (`ENVIRONNEMENT`, `SOCIAL`, `GOUVERNANCE`)."""

    group: str
    expected: int
    found: int
