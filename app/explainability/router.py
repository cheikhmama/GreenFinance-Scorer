"""Route d'explicabilité du score (tâche 3.2). Le contrôle d'accès fin vit dans
app/explainability/explanation.py ; ce router n'exige qu'une session authentifiée."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.auth.models import User
from app.core.dependencies import get_current_user, get_session
from app.core.enums import BaselineScope
from app.explainability.explanation import expliquer_score
from app.explainability.schemas import ScoreExplanation

router = APIRouter(tags=["explainability"])


@router.get(
    "/reports/{report_id}/score-explanation",
    response_model=ScoreExplanation,
    operation_id="getScoreExplanation",
    summary="Décomposer le score officiel d'un rapport par indicateur (SHAP exact)",
)
def get_score_explanation(
    report_id: uuid.UUID,
    baseline: BaselineScope = Query(default=BaselineScope.SECTOR),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ScoreExplanation:
    return expliquer_score(session, current_user, report_id, baseline)
