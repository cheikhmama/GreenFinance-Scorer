"""Consultation des entreprises publiées par l'Investisseur — lecture seule, jamais de saisie.

Projette le dernier rapport VALIDE d'une entreprise publiée vers les schémas Investisseur
(app/investor/schemas.py) ; app/ingestion/models.py et app/scoring/models.py restent l'unique
source de vérité, jamais dupliquée ici.
"""

import uuid

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, or_, select

from app.company.models import Entreprise
from app.company.schemas import EntreprisePublic
from app.core.enums import StatutRapport
from app.core.exceptions import NotFoundError
from app.ingestion.models import DonneeCarbone, IndicateurESG, RapportESG
from app.investor.schemas import (
    DonneesCarboneAgregees,
    EntrepriseDetailInvestisseur,
    EntreprisePublieePublic,
    ScoreEntreprisePublic,
)
from app.scoring.models import ConfigurationPonderation, ScoreESG

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


def dernier_rapport_valide(session: Session, entreprise_id: uuid.UUID) -> RapportESG | None:
    """La publication (Entreprise.date_publication) ne pointe pas explicitement vers un rapport
    précis — c'est toujours le RapportESG VALIDE le plus récent qui fait foi, cohérent avec la
    republication (app/admin/dashboard.py::demandes_republication)."""
    return session.exec(
        select(RapportESG)
        .where(RapportESG.entreprise_id == entreprise_id, RapportESG.statut == StatutRapport.VALIDE)
        .order_by(col(RapportESG.date_depot).desc())
    ).first()


def score_public(session: Session, rapport: RapportESG | None) -> ScoreEntreprisePublic:
    if rapport is None:
        return _SCORE_VIDE
    score = session.exec(select(ScoreESG).where(ScoreESG.rapport_id == rapport.id)).first()
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


def carbone_agrege(session: Session, rapport: RapportESG | None) -> DonneesCarboneAgregees:
    if rapport is None:
        return _CARBONE_VIDE
    donnees = session.exec(select(DonneeCarbone).where(DonneeCarbone.rapport_id == rapport.id)).all()
    par_cle = {(d.scope, d.categorie_ges): d.valeur_tonnes_co2e for d in donnees}
    return DonneesCarboneAgregees(
        scope_1=par_cle.get((1, None)),
        scope_2_market_based=par_cle.get((2, "market_based")),
        scope_2_location_based=par_cle.get((2, "location_based")),
        scope_3=par_cle.get((3, None)),
    )


def entreprise_publiee_publique(session: Session, entreprise: Entreprise) -> EntreprisePublieePublic:
    rapport = dernier_rapport_valide(session, entreprise.id)
    return EntreprisePublieePublic(
        **EntreprisePublic.model_validate(entreprise).model_dump(),
        score=score_public(session, rapport),
        carbone=carbone_agrege(session, rapport),
    )


def lister_entreprises_publiees(
    session: Session,
    *,
    secteur: str | None = None,
    pays: str | None = None,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[EntreprisePublieePublic], int]:
    filtres: list[ColumnElement[bool]] = [col(Entreprise.date_publication).is_not(None)]
    if secteur:
        filtres.append(col(Entreprise.secteur) == secteur)
    if pays:
        filtres.append(col(Entreprise.pays) == pays)
    if recherche:
        motif = f"%{recherche}%"
        filtres.append(or_(col(Entreprise.nom).ilike(motif), col(Entreprise.secteur).ilike(motif)))

    total = session.exec(select(func.count()).select_from(Entreprise).where(*filtres)).one()
    items = session.exec(
        select(Entreprise)
        .where(*filtres)
        .order_by(col(Entreprise.nom))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [entreprise_publiee_publique(session, e) for e in items], total


def consulter_entreprise_publiee(
    session: Session, entreprise_id: uuid.UUID
) -> EntrepriseDetailInvestisseur:
    entreprise = session.get(Entreprise, entreprise_id)
    if entreprise is None or entreprise.date_publication is None:
        # Même code que l'entreprise soit inconnue ou pas encore publiée — jamais de 403 qui
        # confirmerait l'existence d'une fiche non publiée à un Investisseur.
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")

    rapport = dernier_rapport_valide(session, entreprise_id)
    indicateurs = []
    donnees_carbone = []
    if rapport is not None:
        indicateurs = list(
            session.exec(select(IndicateurESG).where(IndicateurESG.rapport_id == rapport.id)).all()
        )
        donnees_carbone = list(
            session.exec(select(DonneeCarbone).where(DonneeCarbone.rapport_id == rapport.id)).all()
        )

    base = entreprise_publiee_publique(session, entreprise)
    return EntrepriseDetailInvestisseur(
        **base.model_dump(), indicateurs=indicateurs, donnees_carbone=donnees_carbone
    )


def comparer_entreprises(
    session: Session, entreprise_ids: list[uuid.UUID]
) -> list[EntreprisePublieePublic]:
    resultats = []
    for entreprise_id in entreprise_ids:
        entreprise = session.get(Entreprise, entreprise_id)
        if entreprise is None or entreprise.date_publication is None:
            raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
        resultats.append(entreprise_publiee_publique(session, entreprise))
    return resultats
