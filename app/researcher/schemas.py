"""Schémas Pydantic d'entrée/sortie du module Chercheur.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import AnalysisStatus, ComparedScore, ProjectStatus, UnmatchedReason


class CreerAnalyseRequest(BaseModel):
    title: str
    content: str
    company_ids: list[uuid.UUID]


class ModifierAnalyseRequest(BaseModel):
    title: str
    content: str
    company_ids: list[uuid.UUID]


class AnalysePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    researcher_id: uuid.UUID
    title: str
    content: str
    status: AnalysisStatus
    version: int
    previous_analysis_id: uuid.UUID | None
    institution_comment: str | None
    created_at: datetime
    submitted_at: datetime | None
    decided_at: datetime | None


class AnalyseDetail(AnalysePublic):
    company_ids: list[uuid.UUID]


class ProjetAffecte(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    objective: str | None
    start_date: datetime | None
    planned_end_date: datetime | None
    deadline: datetime | None
    status: ProjectStatus
    institution_email: str


# --- Validation croisée (tâche 3.3) — nouveaux endpoints, contrat JSON en anglais -------------


class ReferenceDatasetRequest(BaseModel):
    """Métadonnées d'un jeu de données public importé : sa source et sa licence (obligatoires,
    c'est une donnée tierce), et l'échelle de ses scores pour les ramener sur 0-100."""

    # Pas de extra="forbid" : reçu en champs de formulaire à côté du fichier (même formulaire).
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=200)
    source_url: str = Field(max_length=500)
    licence: str = Field(min_length=2, max_length=200)
    scale_min: float = 0
    scale_max: float = 100
    higher_is_better: bool = True

    @field_validator("source_url")
    @classmethod
    def _url(cls, valeur: str) -> str:
        if not valeur.startswith(("https://", "http://")):
            raise ValueError("Adresse web attendue (https://…).")
        return valeur

    @model_validator(mode="after")
    def _echelle(self) -> "ReferenceDatasetRequest":
        if not self.scale_max > self.scale_min:
            raise ValueError("scale_max doit être strictement supérieur à scale_min.")
        return self


class ReferenceDatasetSummary(BaseModel):
    id: uuid.UUID
    name: str
    source_url: str
    licence: str
    scale_min: float
    scale_max: float
    higher_is_better: bool
    created_at: datetime
    row_count: int


class SkippedLine(BaseModel):
    line: int  # numéro de ligne dans le fichier (en-tête = 1)
    reason: str


class ReferenceDatasetImportResult(BaseModel):
    dataset: ReferenceDatasetSummary
    imported: int
    skipped: int
    skipped_lines: list[SkippedLine]  # les 100 premières


class ScoreAgreement(BaseModel):
    """Accord entre le jeu de données et la plateforme sur un score. Spearman nul sous 3 paires ou
    pour une série constante ; écart absolu moyen sur l'échelle 0-100 de la plateforme."""

    score: ComparedScore
    pairs: int
    spearman: float | None
    mean_absolute_difference: float | None


class CrossValidationMatch(BaseModel):
    line: int
    company_id: uuid.UUID
    company_name: str
    dataset_scores: dict[ComparedScore, float | None]  # ramenés sur 0-100
    platform_scores: dict[ComparedScore, float | None]


class UnmatchedLine(BaseModel):
    line: int
    isin: str | None
    lei: str | None
    company_name: str | None
    reason: UnmatchedReason


class CrossValidationReport(BaseModel):
    dataset: ReferenceDatasetSummary
    matched: int
    unmatched: int
    agreement: list[ScoreAgreement]
    matches: list[CrossValidationMatch]
    unmatched_lines: list[UnmatchedLine]

