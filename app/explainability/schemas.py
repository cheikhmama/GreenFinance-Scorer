"""Contrat de GET /reports/{id}/score-explanation (tâche 3.2) — nouvel endpoint, JSON en anglais
(docs/RENAME_PLAN.md §1, règle 3)."""

import uuid

from pydantic import BaseModel

from app.core.enums import BaselineScope, Pillar


class BaselineInfo(BaseModel):
    """L'ensemble de référence réellement utilisé. `used` diffère de `requested` quand le secteur
    compte trop peu de pairs (repli sur toutes les entreprises publiées)."""

    requested: BaselineScope
    used: BaselineScope
    sector: str | None  # le secteur comparé, nul pour UNIVERSE
    peer_count: int  # nombre de rapports pairs (le rapport expliqué n'en fait jamais partie)


class MetricContribution(BaseModel):
    pillar: Pillar
    metric_code: str
    value: float  # valeur déclarée (correction de l'Auditeur incluse)
    normalized_value: float  # 0-100
    baseline_value: float | None  # moyenne normalisée des pairs ; nulle si aucun ne la publie
    effective_weight: float  # poids dans le score global après renormalisation
    contribution: float  # points de score au-dessus (> 0) ou en dessous (< 0) de la référence


class PillarContribution(BaseModel):
    pillar: Pillar
    contribution: float


class ScoreExplanation(BaseModel):
    """Cascade : baseline_score + Σ contributions = score, exactement (SHAP linéaire)."""

    report_id: uuid.UUID
    company_id: uuid.UUID
    config_version: int
    config_hash: str | None
    score: float
    baseline_score: float
    coverage_rate: float | None
    baseline: BaselineInfo
    pillars: list[PillarContribution]
    contributions: list[MetricContribution]
