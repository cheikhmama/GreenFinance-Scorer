"""Revue des valeurs extraites par l'Auditeur affecté (tâche 5.6).

Séparation des tâches :
- seul l'Auditeur affecté au rapport revoit ses valeurs, et seulement tant que le rapport est
  IN_AUDIT — une fois l'avis rendu, la revue est close ;
- l'Administrateur lit le journal mais n'y écrit jamais ; il décide ensuite, depuis
  PENDING_DECISION seulement (app/admin/review_queue.py).

Chaque décision ajoute une ligne au journal append-only metric_reviews (jamais modifiée, voir
app/audit/models.py::MetricReview) et met à jour, dans la même transaction, l'état courant porté
par la valeur (review_status, audited_value) — que lisent le score et le module carbone.

Le pré-score (score de référence avec les valeurs revues) n'est montré à l'Auditeur qu'après son
avis : le chiffre ne doit pas orienter la revue.
"""

import uuid

import structlog
from sqlmodel import Session, col, select

from app.audit.models import MetricReview
from app.audit.schemas import MetricReviewRequest, PreScore
from app.core.enums import MetricReviewStatus, Pillar, ReportStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.ingestion.models import CarbonEmission, ESGMetric, ESGReport
from app.scoring.engine import calculer_apercu_complet

logger = structlog.get_logger(__name__)


def _rapport_de_l_auditeur(
    session: Session, rapport_id: uuid.UUID, auditeur_id: uuid.UUID, *, verrouiller: bool = False
) -> ESGReport:
    rapport = session.get(ESGReport, rapport_id, with_for_update=verrouiller)
    # Même réponse qu'un rapport inexistant : jamais confirmer l'existence d'un rapport affecté
    # à un autre auditeur (même règle que app/audit/opinion.py).
    if rapport is None or rapport.auditor_id != auditeur_id:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    return rapport


def enregistrer_revue(
    session: Session, rapport_id: uuid.UUID, auditeur_id: uuid.UUID, demande: MetricReviewRequest
) -> MetricReview:
    rapport = _rapport_de_l_auditeur(session, rapport_id, auditeur_id, verrouiller=True)
    if rapport.status != ReportStatus.IN_AUDIT:
        raise ValidationError(
            "La revue de ce rapport est close : l'avis a été rendu.", code="revue_close"
        )

    cible: ESGMetric | CarbonEmission | None
    if demande.metric_id is not None:
        cible = session.get(ESGMetric, demande.metric_id)
        valeur_extraite = cible.value if cible is not None else None
    else:
        cible = session.get(CarbonEmission, demande.emission_id)
        valeur_extraite = cible.tonnes_co2e if cible is not None else None
    if cible is None or cible.report_id != rapport_id or valeur_extraite is None:
        raise NotFoundError("Valeur introuvable dans ce rapport.", code="valeur_introuvable")

    revue = MetricReview(
        report_id=rapport_id,
        metric_id=demande.metric_id,
        emission_id=demande.emission_id,
        decision=demande.decision,
        original_value=valeur_extraite,
        new_value=demande.new_value,
        reason=demande.reason,
        comment=demande.comment or None,
        auditor_id=auditeur_id,
    )
    session.add(revue)
    cible.review_status = demande.decision
    cible.audited_value = demande.new_value if demande.decision == MetricReviewStatus.OVERRIDDEN else None
    session.add(cible)
    session.commit()
    session.refresh(revue)
    logger.info(
        "valeur_revue",
        rapport_id=str(rapport_id),
        decision=demande.decision.value,
        cible="metric" if demande.metric_id else "emission",
    )
    return revue


def valeurs_non_revues(session: Session, rapport_id: uuid.UUID) -> int:
    """Nombre de valeurs extraites (indicateurs et données carbone) encore PENDING."""
    total = 0
    for modele in (ESGMetric, CarbonEmission):
        total += len(
            session.exec(
                select(modele.id).where(
                    col(modele.report_id) == rapport_id,
                    col(modele.review_status) == MetricReviewStatus.PENDING,
                )
            ).all()
        )
    return total


def lister_revues(session: Session, rapport_id: uuid.UUID) -> list[MetricReview]:
    return list(
        session.exec(
            select(MetricReview)
            .where(col(MetricReview.report_id) == rapport_id)
            .order_by(col(MetricReview.created_at))
        ).all()
    )


def lister_revues_de_l_auditeur(
    session: Session, rapport_id: uuid.UUID, auditeur_id: uuid.UUID
) -> list[MetricReview]:
    _rapport_de_l_auditeur(session, rapport_id, auditeur_id)
    return lister_revues(session, rapport_id)


def pre_score(session: Session, rapport_id: uuid.UUID, auditeur_id: uuid.UUID) -> PreScore:
    rapport = _rapport_de_l_auditeur(session, rapport_id, auditeur_id)
    if rapport.status == ReportStatus.IN_AUDIT:
        raise ConflictError(
            "Le pré-score n'est visible qu'une fois votre avis rendu.", code="avis_requis"
        )
    resultat = calculer_apercu_complet(session, rapport_id)
    if resultat is None:
        return PreScore(
            computable=False,
            global_score=None,
            environmental_score=None,
            social_score=None,
            governance_score=None,
            coverage_rate=None,
        )
    return PreScore(
        computable=True,
        global_score=resultat.global_score,
        environmental_score=resultat.scores_par_pilier.get(Pillar.ENVIRONNEMENT),
        social_score=resultat.scores_par_pilier.get(Pillar.SOCIAL),
        governance_score=resultat.scores_par_pilier.get(Pillar.GOUVERNANCE),
        coverage_rate=resultat.coverage_rate,
    )
