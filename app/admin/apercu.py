"""Aperçu global multi-acteurs de l'Administrateur — statistiques par acteur (Auditeur,
Investisseur, Chercheur, Institution) et performance ESG agrégée.

Distinct de app/admin/dashboard.py (TableauDeBordAdmin, la vue compacte déjà en place et déjà
utilisée par le tableau de bord existant) : ce module répond au besoin de supervision plus large
des cinq espaces. Orchestre les fonctions déjà exposées par chaque domaine plutôt que de
réinterroger directement leurs tables (voir ARCHITECTURE.md §1 : l'admin invoque, ne réimplémente
jamais localement une requête qu'un domaine possède déjà) — Entreprise n'a pas son propre bloc de
statistiques ici : entreprises_inscrites/publiees et rapports_soumis/valides/rejetes/demandes_
republication de TableauDeBordAdmin couvrent déjà exactement ce que la section Entreprise
demande, les dupliquer aurait recréé la répétition déjà écartée pour le tableau de bord compact.
"""

from dataclasses import dataclass, field

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app.audit.assignment import statistiques_charge_globale
from app.company.models import Company
from app.core.enums import StatutAnalyse
from app.institution.projets import statistiques_admin as statistiques_institutions
from app.investor.entreprises import dernier_rapport_valide
from app.investor.portfolio import statistiques_admin as statistiques_investisseurs
from app.researcher.analyses import statistiques_admin as statistiques_chercheurs
from app.scoring.engine import score_officiel
from app.scoring.models import ScoreESG


@dataclass
class TrancheScore:
    borne_min: int
    borne_max: int
    nombre_entreprises: int


@dataclass
class PerformanceESG:
    score_global_moyen: float | None
    score_environnement_moyen: float | None
    score_social_moyen: float | None
    score_gouvernance_moyen: float | None
    entreprises_avec_score: int
    entreprises_perimetre: int
    distribution: list[TrancheScore] = field(default_factory=list)


@dataclass
class StatistiquesAuditeurs:
    dossiers_affectes: int
    avis_rendus: int


@dataclass
class StatistiquesInvestisseurs:
    portefeuilles_non_archives: int
    positions_declarees: int
    entreprises_distinctes: int


@dataclass
class StatistiquesChercheurs:
    chercheurs_affectes_projets_ouverts: int
    analyses_brouillon: int
    analyses_soumises: int
    analyses_validees: int
    analyses_correction_demandee: int


@dataclass
class StatistiquesInstitutions:
    projets_ouverts: int
    projets_clotures: int
    invitations_en_attente: int
    analyses_a_examiner: int


@dataclass
class ApercuActeurs:
    auditeurs: StatistiquesAuditeurs
    investisseurs: StatistiquesInvestisseurs
    chercheurs: StatistiquesChercheurs
    institutions: StatistiquesInstitutions


def _moyenne(valeurs: list[float]) -> float | None:
    return sum(valeurs) / len(valeurs) if valeurs else None


def entreprises_perimetre_esg(session: Session) -> list[Company]:
    """Périmètre de calcul de la performance ESG : les entreprises publiées — celles réellement
    montrées à l'Investisseur, cohérent avec ce que "couverture ESG" doit signifier ici (jamais
    une entreprise encore inconnue du catalogue public)."""
    return list(
        session.exec(select(Company).where(col(Company.published_at).is_not(None))).all()
    )


def calculer_performance_esg(session: Session, entreprises: list[Company]) -> PerformanceESG:
    """Score admissible par entreprise : celui du dernier ESGReport VALIDATED
    (dernier_rapport_valide, app/investor/entreprises.py), sous la configuration de référence
    (score_officiel, app/scoring/engine.py) — jamais une pondération personnalisée, jamais un
    rapport non validé ; même définition que celle déjà utilisée pour le score public affiché à
    l'Investisseur, pas une nouvelle règle inventée ici. Une entreprise sans rapport validé ou
    sans score sous la référence est exclue du calcul, jamais comptée comme 0 — voir
    entreprises_avec_score/entreprises_perimetre pour la couverture réelle."""
    scores: list[ScoreESG] = []
    for entreprise in entreprises:
        rapport = dernier_rapport_valide(session, entreprise.id)
        if rapport is None:
            continue
        score = score_officiel(session, rapport.id)
        if score is not None:
            scores.append(score)

    bornes = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 101)]
    distribution = [
        TrancheScore(
            borne_min=lo,
            borne_max=min(hi, 100),
            nombre_entreprises=sum(1 for s in scores if lo <= s.valeur_globale < hi),
        )
        for lo, hi in bornes
    ]

    return PerformanceESG(
        score_global_moyen=_moyenne([s.valeur_globale for s in scores]),
        score_environnement_moyen=_moyenne(
            [s.score_environnement for s in scores if s.score_environnement is not None]
        ),
        score_social_moyen=_moyenne([s.score_social for s in scores if s.score_social is not None]),
        score_gouvernance_moyen=_moyenne(
            [s.score_gouvernance for s in scores if s.score_gouvernance is not None]
        ),
        entreprises_avec_score=len(scores),
        entreprises_perimetre=len(entreprises),
        distribution=distribution,
    )


def lister_entreprises_avec_score(
    session: Session,
    *,
    secteur: str | None = None,
    pays: str | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[tuple[Company, ScoreESG | None]], int]:
    """Détail derrière les cartes de performance ESG (indicateur → liste filtrée) — chaque
    entreprise publiée avec son score admissible, None si absent plutôt que 0. Même périmètre que
    calculer_performance_esg (entreprises publiées), filtrable par secteur/pays."""
    filtres: list[ColumnElement[bool]] = [col(Company.published_at).is_not(None)]
    if secteur:
        filtres.append(col(Company.sector) == secteur)
    if pays:
        filtres.append(col(Company.country) == pays)

    total = session.exec(select(func.count()).select_from(Company).where(*filtres)).one()
    entreprises = list(
        session.exec(
            select(Company)
            .where(*filtres)
            .order_by(col(Company.name))
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )

    resultats: list[tuple[Company, ScoreESG | None]] = []
    for entreprise in entreprises:
        rapport = dernier_rapport_valide(session, entreprise.id)
        score = score_officiel(session, rapport.id) if rapport is not None else None
        resultats.append((entreprise, score))
    return resultats, total


def construire_apercu_acteurs(session: Session) -> ApercuActeurs:
    dossiers_affectes, avis_rendus = statistiques_charge_globale(session)

    portefeuilles_non_archives, positions_declarees, entreprises_distinctes = (
        statistiques_investisseurs(session)
    )

    chercheurs_affectes, analyses_par_statut = statistiques_chercheurs(session)

    projets_ouverts, projets_clotures, invitations_en_attente, analyses_a_examiner = (
        statistiques_institutions(session)
    )

    return ApercuActeurs(
        auditeurs=StatistiquesAuditeurs(
            dossiers_affectes=dossiers_affectes, avis_rendus=avis_rendus
        ),
        investisseurs=StatistiquesInvestisseurs(
            portefeuilles_non_archives=portefeuilles_non_archives,
            positions_declarees=positions_declarees,
            entreprises_distinctes=entreprises_distinctes,
        ),
        chercheurs=StatistiquesChercheurs(
            chercheurs_affectes_projets_ouverts=chercheurs_affectes,
            analyses_brouillon=analyses_par_statut.get(StatutAnalyse.BROUILLON, 0),
            analyses_soumises=analyses_par_statut.get(StatutAnalyse.SOUMISE, 0),
            analyses_validees=analyses_par_statut.get(StatutAnalyse.VALIDEE, 0),
            analyses_correction_demandee=analyses_par_statut.get(
                StatutAnalyse.CORRECTION_DEMANDEE, 0
            ),
        ),
        institutions=StatistiquesInstitutions(
            projets_ouverts=projets_ouverts,
            projets_clotures=projets_clotures,
            invitations_en_attente=invitations_en_attente,
            analyses_a_examiner=analyses_a_examiner,
        ),
    )
