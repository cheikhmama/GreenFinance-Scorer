"""Explication du score officiel d'un rapport (tâche 3.2, docs/WORKFLOWS.md §3.3).

Assemble les données — la configuration STOCKÉE qui a produit le score officiel, les valeurs du
rapport, celles de ses pairs — et délègue l'attribution au calcul pur
app/explainability/decomposition.py. Lecture seule, calculée à la demande.

Pairs : le dernier rapport validé de chaque AUTRE entreprise publiée — du même secteur par défaut,
de toutes les entreprises publiées si le secteur en compte moins de MIN_PAIRS_SECTEUR (repli
signalé dans la réponse). Normalisés sous la même configuration que le rapport expliqué : la
comparaison se fait toujours avec la même méthodologie.

Accès : Administrateur, Entreprise titulaire et Auditeur affecté selon le périmètre de /reports
(app/reporting/sessions.py) ; Investisseur, Chercheur et Institution seulement pour ce qu'ils
voient déjà — le dernier rapport validé d'une entreprise publiée, dans leur périmètre de projets
pour Chercheur et Institution.
"""

import uuid

import structlog
from sqlmodel import Session, col, select

from app.auth.models import User
from app.company.models import Company
from app.core.enums import BaselineScope, Pillar, ReportStatus, Role
from app.core.exceptions import NotFoundError, ValidationError
from app.explainability.decomposition import decomposer, references_moyennes
from app.explainability.schemas import (
    BaselineInfo,
    MetricContribution,
    PillarContribution,
    ScoreExplanation,
)
from app.ingestion.models import ESGReport
from app.institution.projets import entreprises_perimetre_institution
from app.investor.entreprises import dernier_rapport_valide
from app.reporting.sessions import rapport_visible
from app.researcher.projets import entreprises_perimetre_chercheur
from app.scoring.engine import (
    schema_configuration,
    score_officiel,
    termes_effectifs,
    valeurs_des_rapports,
)
from app.scoring.models import ScoringConfig

logger = structlog.get_logger(__name__)

MIN_PAIRS_SECTEUR = 3
_ROLES_PERIMETRE_REPORTS = (Role.ADMIN, Role.ENTERPRISE, Role.AUDITOR)


def _rapport_accessible(session: Session, user: User, rapport_id: uuid.UUID) -> ESGReport:
    if user.role in _ROLES_PERIMETRE_REPORTS:
        return rapport_visible(session, user, rapport_id)
    rapport = session.get(ESGReport, rapport_id)
    entreprise = session.get(Company, rapport.company_id) if rapport else None
    publie = (
        rapport is not None
        and entreprise is not None
        and entreprise.published_at is not None
        and (dernier := dernier_rapport_valide(session, entreprise.id)) is not None
        and dernier.id == rapport.id
    )
    # Chercheur et Institution ne voient que les entreprises de leur périmètre de projets — même
    # règle que la fiche entreprise (app/investor/entreprises.py::consulter_entreprise_publiee).
    if publie and entreprise is not None and user.role == Role.RESEARCHER:
        publie = entreprise.id in entreprises_perimetre_chercheur(session, user.id)
    if publie and entreprise is not None and user.role == Role.INSTITUTION:
        publie = entreprise.id in entreprises_perimetre_institution(session, user.id)
    if not publie or rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    return rapport


def _rapports_pairs(session: Session, entreprise: Company, portee: BaselineScope) -> list[uuid.UUID]:
    """Dernier rapport validé de chaque autre entreprise publiée (du même secteur si demandé)."""
    filtres = [
        col(ESGReport.status) == ReportStatus.VALIDATED,
        col(Company.published_at).is_not(None),
        col(Company.id) != entreprise.id,
    ]
    if portee == BaselineScope.SECTOR:
        filtres.append(col(Company.sector) == entreprise.sector)
    lignes = session.exec(
        select(ESGReport.id, ESGReport.company_id)
        .join(Company, col(Company.id) == col(ESGReport.company_id))
        .where(*filtres)
        .order_by(col(ESGReport.company_id), col(ESGReport.submitted_at).desc())
    ).all()
    derniers: dict[uuid.UUID, uuid.UUID] = {}
    for rapport_id, entreprise_id in lignes:
        derniers.setdefault(entreprise_id, rapport_id)
    return list(derniers.values())


def expliquer_score(
    session: Session, user: User, rapport_id: uuid.UUID, portee: BaselineScope
) -> ScoreExplanation:
    rapport = _rapport_accessible(session, user, rapport_id)
    score = score_officiel(session, rapport.id)
    if score is None:
        raise ValidationError(
            "Ce rapport n'a pas encore de score officiel à expliquer.", code="score_absent"
        )
    configuration = session.get(ScoringConfig, score.config_id)
    assert configuration is not None  # FK NOT NULL
    schema = schema_configuration(configuration)
    entreprise = session.get(Company, rapport.company_id)
    assert entreprise is not None  # FK NOT NULL

    portee_utilisee = portee
    pairs = _rapports_pairs(session, entreprise, portee)
    if portee == BaselineScope.SECTOR and len(pairs) < MIN_PAIRS_SECTEUR:
        portee_utilisee = BaselineScope.UNIVERSE
        pairs = _rapports_pairs(session, entreprise, BaselineScope.UNIVERSE)

    valeurs = valeurs_des_rapports(session, [rapport.id, *pairs])
    termes = termes_effectifs(schema, valeurs[rapport.id])
    decomposition = decomposer(
        termes, references_moyennes([termes_effectifs(schema, valeurs[p]) for p in pairs])
    )
    if abs(decomposition.score - score.global_score) > 1e-6:
        # Les valeurs d'un rapport validé ne changent plus : un écart signalerait un bug.
        logger.warning(
            "explication_score_ecart",
            rapport_id=str(rapport.id),
            score_officiel=score.global_score,
            score_recalcule=decomposition.score,
        )

    par_pilier = {pilier: 0.0 for pilier in Pillar}
    for contribution in decomposition.contributions:
        par_pilier[contribution.pilier] += contribution.contribution
    piliers_presents = {c.pilier for c in decomposition.contributions}
    return ScoreExplanation(
        report_id=rapport.id,
        company_id=entreprise.id,
        config_version=configuration.version,
        config_hash=configuration.content_hash,
        score=decomposition.score,
        baseline_score=decomposition.score_reference,
        coverage_rate=score.coverage_rate,
        baseline=BaselineInfo(
            requested=portee,
            used=portee_utilisee,
            sector=entreprise.sector if portee_utilisee == BaselineScope.SECTOR else None,
            peer_count=len(pairs),
        ),
        pillars=[
            PillarContribution(pillar=pilier, contribution=total)
            for pilier, total in par_pilier.items()
            if pilier in piliers_presents
        ],
        contributions=[
            MetricContribution(
                pillar=c.pilier,
                metric_code=c.code,
                value=c.valeur,
                normalized_value=c.valeur_normalisee,
                baseline_value=c.reference,
                effective_weight=c.poids_effectif,
                contribution=c.contribution,
            )
            for c in decomposition.contributions
        ],
    )
