"""Consultation des entreprises publiées par l'Investisseur — lecture seule, jamais de saisie.

Projette le dernier rapport VALIDATED d'une entreprise publiée vers les schémas Investisseur
(app/investor/schemas.py) ; app/ingestion/models.py et app/scoring/models.py restent l'unique
source de vérité, jamais dupliquée ici.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, or_, select

from app.company.models import Company
from app.company.schemas import EntreprisePublic
from app.core.config import get_settings
from app.core.enums import DevisePosition, ReportStatus, StatutCouvertureIndicateur
from app.core.exceptions import NotFoundError, ValidationError
from app.ingestion.models import (
    CarbonEmission,
    ESGMetric,
    ESGReport,
    Evidence,
    MetricCoverage,
)
from app.ingestion.schemas import CouvertureResume
from app.investor import fx
from app.investor.schemas import (
    DonneesCarboneAgregees,
    EntrepriseDetailInvestisseur,
    EntreprisePublieePublic,
    ScoreEntreprisePublic,
)

_COUVERTURE_VIDE = CouvertureResume(total_cibles=0, trouves=0, codes_manquants=[])


def couverture_publique(session: Session, rapport: ESGReport | None) -> CouvertureResume:
    """Même donnée que RapportESGDetail.couverture (app/ingestion/schemas.py), reconstruite ici
    car EntrepriseDetailInvestisseur s'assemble manuellement (jamais via from_attributes sur
    l'ORM, voir consulter_entreprise_publiee) plutôt que par un computed_field."""
    if rapport is None:
        return _COUVERTURE_VIDE
    couvertures = session.exec(
        select(MetricCoverage).where(MetricCoverage.report_id == rapport.id)
    ).all()
    return CouvertureResume(
        total_cibles=len(couvertures),
        trouves=sum(1 for c in couvertures if c.status == StatutCouvertureIndicateur.TROUVE),
        codes_manquants=[
            c.metric_code for c in couvertures if c.status != StatutCouvertureIndicateur.TROUVE
        ],
    )
from app.scoring.engine import score_officiel
from app.scoring.models import ConfigurationPonderation

_SCORE_VIDE = ScoreEntreprisePublic(
    valeur_globale=None,
    score_environnement=None,
    score_social=None,
    score_gouvernance=None,
    configuration_version=None,
)
_CARBONE_VIDE = DonneesCarboneAgregees(
    scope_1=None, scope_2_market_based=None, scope_2_location_based=None, scope_3=None
)


def dernier_rapport_valide(session: Session, entreprise_id: uuid.UUID) -> ESGReport | None:
    """La publication (Company.published_at) ne pointe pas explicitement vers un rapport
    précis — c'est toujours le ESGReport VALIDATED le plus récent qui fait foi, cohérent avec la
    republication (app/admin/dashboard.py::demandes_republication)."""
    return session.exec(
        select(ESGReport)
        .where(ESGReport.company_id == entreprise_id, ESGReport.status == ReportStatus.VALIDATED)
        .order_by(col(ESGReport.submitted_at).desc())
    ).first()


def score_public(session: Session, rapport: ESGReport | None) -> ScoreEntreprisePublic:
    if rapport is None:
        return _SCORE_VIDE
    score = score_officiel(session, rapport.id)
    if score is None:
        return _SCORE_VIDE
    configuration = session.get(ConfigurationPonderation, score.configuration_id)
    return ScoreEntreprisePublic(
        valeur_globale=score.valeur_globale,
        score_environnement=score.score_environnement,
        score_social=score.score_social,
        score_gouvernance=score.score_gouvernance,
        configuration_version=configuration.version if configuration else None,
    )


def carbone_agrege(session: Session, rapport: ESGReport | None) -> DonneesCarboneAgregees:
    if rapport is None:
        return _CARBONE_VIDE
    donnees = session.exec(select(CarbonEmission).where(CarbonEmission.report_id == rapport.id)).all()
    par_cle = {(d.scope, d.ghg_category): d.tonnes_co2e for d in donnees}
    return DonneesCarboneAgregees(
        scope_1=par_cle.get((1, None)),
        scope_2_market_based=par_cle.get((2, "market_based")),
        scope_2_location_based=par_cle.get((2, "location_based")),
        scope_3=par_cle.get((3, None)),
    )


def montant_minimum_par_devise(
    entreprise: Company, chemin_taux: str
) -> dict[DevisePosition, Decimal] | None:
    """None si l'entreprise n'impose aucun minimum — jamais une carte à 3 zéros qui laisserait
    croire à un minimum réel de 0. Sinon, converti dans les 3 devises depuis
    Company.minimum_investment_currency (toujours renseignée de pair, voir
    app/company/models.py) avec la même logique FX que app/investor/portfolio.py."""
    if entreprise.minimum_investment_amount is None:
        return None
    assert entreprise.minimum_investment_currency is not None
    return {
        devise: fx.convertir(
            entreprise.minimum_investment_amount,
            entreprise.minimum_investment_currency,
            devise,
            chemin_taux,
        )[0]
        for devise in DevisePosition
    }


def entreprise_publiee_publique(session: Session, entreprise: Company) -> EntreprisePublieePublic:
    rapport = dernier_rapport_valide(session, entreprise.id)
    return EntreprisePublieePublic(
        **EntreprisePublic.model_validate(entreprise).model_dump(),
        score=score_public(session, rapport),
        carbone=carbone_agrege(session, rapport),
        montant_minimum_par_devise=montant_minimum_par_devise(
            entreprise, get_settings().fx_rates_path
        ),
    )


def lister_entreprises_publiees(
    session: Session,
    *,
    secteur: str | None = None,
    pays: str | None = None,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 20,
    perimetre_autorise: set[uuid.UUID] | None = None,
) -> tuple[list[EntreprisePublieePublic], int]:
    """perimetre_autorise restreint le catalogue à un sous-ensemble d'ids (Chercheur/Institution,
    voir app/researcher/router.py et app/institution/router.py) — None (par défaut, cas
    Investisseur) laisse le catalogue complet inchangé. Un ensemble vide renvoie une page vide,
    jamais tout le catalogue par accident."""
    filtres: list[ColumnElement[bool]] = [col(Company.published_at).is_not(None)]
    if perimetre_autorise is not None:
        filtres.append(col(Company.id).in_(perimetre_autorise))
    if secteur:
        filtres.append(col(Company.sector) == secteur)
    if pays:
        filtres.append(col(Company.country) == pays)
    if recherche:
        motif = f"%{recherche}%"
        filtres.append(or_(col(Company.name).ilike(motif), col(Company.sector).ilike(motif)))

    total = session.exec(select(func.count()).select_from(Company).where(*filtres)).one()
    items = session.exec(
        select(Company)
        .where(*filtres)
        .order_by(col(Company.name))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [entreprise_publiee_publique(session, e) for e in items], total


def consulter_entreprise_publiee(
    session: Session,
    entreprise_id: uuid.UUID,
    *,
    perimetre_autorise: set[uuid.UUID] | None = None,
) -> EntrepriseDetailInvestisseur:
    entreprise = session.get(Company, entreprise_id)
    if (
        entreprise is None
        or entreprise.published_at is None
        or (perimetre_autorise is not None and entreprise_id not in perimetre_autorise)
    ):
        # Même code dans les trois cas — entreprise inconnue, pas encore publiée, ou hors du
        # périmètre autorisé (Chercheur/Institution) — jamais de 403 qui confirmerait l'existence
        # d'une fiche à un acteur qui n'y a pas droit.
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")

    rapport = dernier_rapport_valide(session, entreprise_id)
    indicateurs = []
    donnees_carbone = []
    if rapport is not None:
        # Trié par pilier puis code : le frontend regroupe visuellement les lignes d'un même
        # pilier (rowSpan sur la colonne Pilier) et a donc besoin qu'elles arrivent déjà
        # contiguës, jamais dans un ordre d'insertion arbitraire (voir EvidenceTables.tsx).
        indicateurs = list(
            session.exec(
                select(ESGMetric)
                .where(ESGMetric.report_id == rapport.id)
                .order_by(col(ESGMetric.pillar), col(ESGMetric.metric_code))
            ).all()
        )
        donnees_carbone = list(
            session.exec(
                select(CarbonEmission)
                .where(CarbonEmission.report_id == rapport.id)
                .order_by(col(CarbonEmission.scope), col(CarbonEmission.ghg_category))
            ).all()
        )

    base = entreprise_publiee_publique(session, entreprise)
    return EntrepriseDetailInvestisseur(
        **base.model_dump(),
        indicateurs=indicateurs,
        donnees_carbone=donnees_carbone,
        couverture=couverture_publique(session, rapport),
    )


def fichier_preuve(
    session: Session,
    entreprise_id: uuid.UUID,
    preuve_id: uuid.UUID,
    *,
    perimetre_autorise: set[uuid.UUID] | None = None,
) -> str:
    """Chemin de stockage du mini-PDF (une page) prouvant un indicateur ou une donnée carbone —
    jamais un simple session.get(Evidence, preuve_id) : sans vérifier que cette preuve
    appartient bien au rapport VALIDATED actuellement publié de CETTE entreprise, un UUID de preuve
    deviné donnerait accès à l'extrait d'un rapport non publié ou d'une autre entreprise."""
    entreprise = session.get(Company, entreprise_id)
    if (
        entreprise is None
        or entreprise.published_at is None
        or (perimetre_autorise is not None and entreprise_id not in perimetre_autorise)
    ):
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")

    rapport = dernier_rapport_valide(session, entreprise_id)
    appartient_au_rapport = rapport is not None and (
        session.exec(
            select(ESGMetric.id).where(
                ESGMetric.proof_id == preuve_id, ESGMetric.report_id == rapport.id
            )
        ).first()
        is not None
        or session.exec(
            select(CarbonEmission.id).where(
                CarbonEmission.proof_id == preuve_id, CarbonEmission.report_id == rapport.id
            )
        ).first()
        is not None
    )
    if not appartient_au_rapport:
        raise NotFoundError("Preuve introuvable.", code="preuve_introuvable")

    preuve = session.get(Evidence, preuve_id)
    assert preuve is not None  # invariant : la requête ci-dessus vient de la trouver par FK
    return preuve.excerpt_pdf_path


_MAX_ENTREPRISES_COMPARAISON = 4


def comparer_entreprises(
    session: Session,
    entreprise_ids: list[uuid.UUID],
    *,
    perimetre_autorise: set[uuid.UUID] | None = None,
) -> list[EntrepriseDetailInvestisseur]:
    """Même détail que la fiche entreprise (indicateurs + carbone, pas seulement le score
    agrégé) : la comparaison a besoin de la valeur, l'unité et la période de chaque indicateur,
    jamais seulement de sa moyenne pondérée — voir consulter_entreprise_publiee, réutilisée ici
    plutôt que dupliquée (perimetre_autorise est simplement propagé)."""
    if len(entreprise_ids) > _MAX_ENTREPRISES_COMPARAISON:
        raise ValidationError(
            f"La comparaison est limitée à {_MAX_ENTREPRISES_COMPARAISON} entreprises.",
            code="comparaison_trop_large",
        )
    return [
        consulter_entreprise_publiee(session, entreprise_id, perimetre_autorise=perimetre_autorise)
        for entreprise_id in entreprise_ids
    ]
