"""Schémas Pydantic d'entrée/sortie du module Auditeur.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import AuditDecision, MetricReviewStatus, ReviewReason


class AvisAuditPublic(BaseModel):
    """Sans auditeur_id — non utilisé par une route dans cette passe, gardé pour une future
    vue Entreprise-facing éventuelle. Documente explicitement la forme sans identité auditeur,
    plutôt que de laisser cette contrainte implicite."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    decision: AuditDecision
    comment: str | None
    submitted_at: datetime


class AvisAuditAdmin(AvisAuditPublic):
    """Réservé Administrateur/Auditeur — jamais exposé à un compte Entreprise (voir
    app/audit/models.py::AuditOpinion.auditor_id)."""

    auditor_id: uuid.UUID


class SoumettreAvisRequest(BaseModel):
    """Avis de l'Auditeur (tâche 5.6) : tout avis autre que FAVORABLE est motivé."""

    model_config = ConfigDict(str_strip_whitespace=True)

    decision: AuditDecision
    comment: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def _commentaire_si_reserve(self) -> "SoumettreAvisRequest":
        if self.decision != AuditDecision.FAVORABLE and not self.comment:
            raise ValueError("Un commentaire est requis pour tout avis autre que favorable.")
        return self


class MetricReviewRequest(BaseModel):
    """POST /audit/rapports/{id}/reviews (tâche 5.6) — décision de l'Auditeur affecté sur une valeur
    extraite : un indicateur (`metric_id`) ou une donnée carbone (`emission_id`), jamais les deux.
    Corriger exige la nouvelle valeur ; corriger ou déclarer non trouvée exige un motif."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    metric_id: uuid.UUID | None = None
    emission_id: uuid.UUID | None = None
    decision: MetricReviewStatus
    new_value: float | None = Field(default=None, allow_inf_nan=False)
    reason: ReviewReason | None = None
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _coherence(self) -> "MetricReviewRequest":
        if (self.metric_id is None) == (self.emission_id is None):
            raise ValueError("Indiquez soit metric_id, soit emission_id.")
        if self.decision == MetricReviewStatus.PENDING:
            raise ValueError("Une revue accepte, corrige ou déclare la valeur non trouvée.")
        if (self.decision == MetricReviewStatus.OVERRIDDEN) != (self.new_value is not None):
            raise ValueError("new_value accompagne une correction (OVERRIDDEN), et seulement elle.")
        if self.decision != MetricReviewStatus.ACCEPTED and self.reason is None:
            raise ValueError("Un motif est requis pour corriger ou déclarer une valeur non trouvée.")
        return self


class MetricReviewEntry(BaseModel):
    """Une entrée du journal des revues (tâche 5.6), jamais modifiée après coup."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    metric_id: uuid.UUID | None
    emission_id: uuid.UUID | None
    decision: MetricReviewStatus
    original_value: float
    new_value: float | None
    reason: ReviewReason | None
    comment: str | None
    auditor_id: uuid.UUID
    created_at: datetime


class PreScore(BaseModel):
    """Score calculé sous la configuration de référence avec les valeurs revues (tâche 5.6) —
    jamais officiel. Montré à l'Auditeur seulement APRÈS son avis, pour que le chiffre n'oriente
    pas la revue."""

    computable: bool
    global_score: float | None
    environmental_score: float | None
    social_score: float | None
    governance_score: float | None
    coverage_rate: float | None
