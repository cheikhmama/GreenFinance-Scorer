"""Modèle et agrégation des portefeuilles d'investissement (Étape 15/16).

Composition (positions), agrégation du score ESG et de la couverture, et actions de cycle de vie
(créer/renommer/archiver/restaurer/supprimer un portefeuille ; ajouter/modifier/fermer/supprimer
une position). La conversion de devise vit dans app/investor/fx.py, la consultation en lecture
d'une entreprise publiée dans app/investor/entreprises.py — jamais dupliquée ici.
"""

import csv
import io
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import pydantic
from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app.auth.models import User
from app.company.models import Company
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import Currency, DurationType, RegistrationStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.core.recherche import contient
from app.ingestion.models import ESGMetric
from app.investor import entreprises as entreprises_investisseur
from app.investor import fx
from app.investor.models import Portfolio, PortfolioPosition
from app.investor.schemas import (
    AjouterPositionRequest,
    EntrepriseSommaire,
    EtatPosition,
    ModifierPositionRequest,
    PortefeuilleDetail,
    PortefeuilleResume,
    PositionDetail,
    ScoreEntreprisePublic,
)


def portefeuille_de_investisseur(
    session: Session, investisseur_id: uuid.UUID, portefeuille_id: uuid.UUID
) -> Portfolio:
    portefeuille = session.get(Portfolio, portefeuille_id)
    if portefeuille is None or portefeuille.user_id != investisseur_id:
        raise NotFoundError("Portefeuille introuvable.", code="portefeuille_introuvable")
    return portefeuille


def _position_du_portefeuille(
    session: Session, portefeuille_id: uuid.UUID, position_id: uuid.UUID
) -> PortfolioPosition:
    position = session.get(PortfolioPosition, position_id)
    if position is None or position.portfolio_id != portefeuille_id:
        raise NotFoundError("Position introuvable.", code="position_introuvable")
    return position


def etat_temporel(position: PortfolioPosition) -> EtatPosition:
    maintenant = utcnow()
    if position.start_date > maintenant:
        return EtatPosition.PLANIFIEE
    if position.end_date is not None and position.end_date <= maintenant:
        return EtatPosition.CLOTUREE
    return EtatPosition.ACTIVE


def etat_position(position: PortfolioPosition, entreprise_actif: bool) -> EtatPosition:
    """L'entreprise suspendue prime sur l'état temporel dans l'affichage (voir le cahier des
    charges) — la position n'est jamais perdue, seule une nouvelle opération est bloquée
    (voir ajouter_position)."""
    if not entreprise_actif:
        return EtatPosition.ENTREPRISE_SUSPENDUE
    return etat_temporel(position)


def _construire_position(valeurs: dict[str, Any]) -> PortfolioPosition:
    """.model_validate() (jamais une construction directe) : déclenche volontairement les
    model_validator de PositionPortefeuille (règles de durée FIXE/OUVERTE). pydantic.ValidationError
    n'est pas gérée par les handlers globaux de l'app (seulement GreenFinanceError et
    RequestValidationError, voir app/core/exceptions.py) — sans cette conversion, une règle de
    durée violée deviendrait un 500 au lieu d'un 422 exploitable par le frontend."""
    # SQLModel ignore silencieusement une clé inconnue : jamais un champ perdu en route.
    assert set(valeurs) <= set(PortfolioPosition.model_fields), set(valeurs) - set(
        PortfolioPosition.model_fields
    )
    try:
        return PortfolioPosition.model_validate(valeurs)
    except pydantic.ValidationError as exc:
        message = exc.errors()[0]["msg"] if exc.errors() else "Position invalide."
        raise ValidationError(message, code="position_invalide") from exc


def _verifier_montant_minimum(
    entreprise: Company,
    montant_converti: Decimal,
    devise_portefeuille: Currency,
    chemin_taux: str,
) -> None:
    """montant_converti est déjà dans devise_portefeuille (voir ajouter_position/
    modifier_position) — le minimum doit donc être converti depuis SA PROPRE devise
    (Company.minimum_investment_currency) vers devise_portefeuille avant comparaison, jamais
    comparé brut : deux montants dans des devises différentes ne sont pas comparables."""
    minimum = entreprise.minimum_investment_amount
    if minimum is None:
        return
    assert entreprise.minimum_investment_currency is not None
    minimum_converti, _ = fx.convertir(
        minimum, entreprise.minimum_investment_currency, devise_portefeuille, chemin_taux
    )
    if montant_converti < minimum_converti:
        raise ValidationError(
            "Le montant est inférieur au minimum requis par cette entreprise.",
            code="montant_insuffisant",
        )


def _agreger(
    session: Session, positions: list[PortfolioPosition]
) -> tuple[Decimal, float | None, float | None, float | None, float | None, float]:
    """Retourne (montant_total, score_global, score_e, score_s, score_g, couverture_pct).

    Le montant total reste en Decimal ; les pondérations de score, elles, sont des float (un
    score n'est pas de l'argent).

    Chaque agrégat pondéré n'inclut que les positions dont l'entreprise a effectivement ce
    score/pilier calculé — jamais comptée comme 0 si absente (même principe que
    app/scoring/engine.py sur les piliers manquants)."""
    montant_total = sum((p.converted_amount for p in positions), Decimal(0))
    if montant_total == 0:
        return Decimal(0), None, None, None, None, 0.0

    # Une ligne non rapprochée (company_id nul, tâche 2.2) compte dans le montant total mais n'a
    # aucun score : elle réduit la couverture, jamais les scores eux-mêmes.
    scores = {
        p.id: entreprises_investisseur.score_public(
            session,
            entreprises_investisseur.dernier_rapport_valide(session, p.company_id)
            if p.company_id is not None
            else None,
        )
        for p in positions
    }

    def agreger_pilier(valeur_pilier: Callable[[ScoreEntreprisePublic], float | None]) -> float | None:
        numerateur = 0.0
        denominateur = 0.0
        for p in positions:
            valeur = valeur_pilier(scores[p.id])
            if valeur is not None:
                numerateur += float(p.converted_amount) * valeur
                denominateur += float(p.converted_amount)
        return (numerateur / denominateur) if denominateur > 0 else None

    score_global = agreger_pilier(lambda s: s.global_score)
    score_e = agreger_pilier(lambda s: s.environmental_score)
    score_s = agreger_pilier(lambda s: s.social_score)
    score_g = agreger_pilier(lambda s: s.governance_score)

    montant_couvert = sum(
        (p.converted_amount for p in positions if scores[p.id].global_score is not None),
        Decimal(0),
    )
    couverture = float(montant_couvert / montant_total * 100)
    return montant_total, score_global, score_e, score_s, score_g, couverture


def position_detail(
    session: Session, position: PortfolioPosition, montant_total_portefeuille: Decimal
) -> PositionDetail:
    # Ligne importée non rapprochée (tâche 2.2) : ni entreprise, ni score, ni preuve — elle reste
    # affichée avec son identifiant d'origine.
    entreprise = session.get(Company, position.company_id) if position.company_id else None
    rapport = (
        entreprises_investisseur.dernier_rapport_valide(session, position.company_id)
        if position.company_id
        else None
    )
    score = entreprises_investisseur.score_public(session, rapport)
    preuves_disponibles = rapport is not None and (
        session.exec(
            select(ESGMetric.id).where(ESGMetric.report_id == rapport.id)
        ).first()
        is not None
    )
    poids = (
        float(position.converted_amount / montant_total_portefeuille)
        if montant_total_portefeuille
        else 0.0
    )

    return PositionDetail(
        id=position.id,
        portfolio_id=position.portfolio_id,
        company=EntrepriseSommaire.model_validate(entreprise) if entreprise else None,
        identifier=position.identifier_raw,
        identifier_type=position.identifier_type,
        match_status=position.match_status,
        outstanding_amount=position.outstanding_amount,
        currency=position.currency,
        converted_amount=position.converted_amount,
        fx_rate_used=position.fx_rate_used,
        weight=poids,
        duration_type=position.duration_type,
        start_date=position.start_date,
        end_date=position.end_date,
        # Sans entreprise, seul l'état temporel compte (jamais « entreprise suspendue »).
        state=etat_position(position, entreprise is None or entreprise.status == RegistrationStatus.ACTIVE),
        score=score,
        published_at_used=entreprise.published_at if entreprise else None,
        evidence_available=preuves_disponibles,
    )


def detail_position_du_portefeuille(session: Session, position: PortfolioPosition) -> PositionDetail:
    """Détail d'une position juste créée ou modifiée : son poids se calcule sur le montant total du
    portefeuille, sans recalculer les scores de toutes les autres positions."""
    montant_total = sum(
        session.exec(
            select(col(PortfolioPosition.converted_amount)).where(
                PortfolioPosition.portfolio_id == position.portfolio_id
            )
        ).all(),
        Decimal(0),
    )
    return position_detail(session, position, montant_total)


def resume_portefeuille(session: Session, portefeuille: Portfolio) -> PortefeuilleResume:
    positions = list(
        session.exec(
            select(PortfolioPosition).where(PortfolioPosition.portfolio_id == portefeuille.id)
        ).all()
    )
    montant_total, score_global, score_e, score_s, score_g, couverture = _agreger(session, positions)
    return PortefeuilleResume(
        id=portefeuille.id,
        name=portefeuille.name,
        reference_currency=portefeuille.reference_currency,
        total_amount=montant_total,
        position_count=len(positions),
        aggregated_esg_score=score_global,
        aggregated_environmental_score=score_e,
        aggregated_social_score=score_s,
        aggregated_governance_score=score_g,
        esg_coverage=couverture,
        created_at=portefeuille.created_at,
        archived=portefeuille.archived,
    )


def detail_portefeuille(session: Session, portefeuille: Portfolio) -> PortefeuilleDetail:
    positions = list(
        session.exec(
            select(PortfolioPosition).where(PortfolioPosition.portfolio_id == portefeuille.id)
        ).all()
    )
    montant_total, score_global, score_e, score_s, score_g, couverture = _agreger(session, positions)
    positions_detail = [position_detail(session, p, montant_total) for p in positions]
    compte = Counter(etat_temporel(p) for p in positions)

    return PortefeuilleDetail(
        id=portefeuille.id,
        name=portefeuille.name,
        reference_currency=portefeuille.reference_currency,
        total_amount=montant_total,
        position_count=len(positions),
        aggregated_esg_score=score_global,
        aggregated_environmental_score=score_e,
        aggregated_social_score=score_s,
        aggregated_governance_score=score_g,
        esg_coverage=couverture,
        created_at=portefeuille.created_at,
        archived=portefeuille.archived,
        planned_position_count=compte.get(EtatPosition.PLANIFIEE, 0),
        active_position_count=compte.get(EtatPosition.ACTIVE, 0),
        closed_position_count=compte.get(EtatPosition.CLOTUREE, 0),
        positions=positions_detail,
    )


def creer_portefeuille(session: Session, investisseur_id: uuid.UUID, nom: str) -> Portfolio:
    """USD, jamais une saisie de l'investisseur : devise pivot déjà utilisée partout ailleurs
    (voir app/investor/fx.py) — un portefeuille n'a plus besoin d'une devise choisie à la
    création, seulement d'un nom (Étape Dashboard/Portefeuille, simplification du formulaire)."""
    portefeuille = Portfolio(
        user_id=investisseur_id, name=nom, reference_currency=Currency.USD
    )
    session.add(portefeuille)
    session.commit()
    session.refresh(portefeuille)
    return portefeuille


def lister_mes_portefeuilles(
    session: Session,
    investisseur_id: uuid.UUID,
    *,
    archive: bool | None = None,
    avec_position: bool | None = None,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PortefeuilleResume], int]:
    filtres: list[ColumnElement[bool]] = [col(Portfolio.user_id) == investisseur_id]
    if archive is not None:
        filtres.append(col(Portfolio.archived) == archive)
    if recherche:
        filtres.append(contient(recherche, Portfolio.name))

    tous = list(
        session.exec(
            select(Portfolio).where(*filtres).order_by(col(Portfolio.created_at).desc())
        ).all()
    )
    resumes = [resume_portefeuille(session, p) for p in tous]
    if avec_position is not None:
        resumes = [r for r in resumes if (r.position_count > 0) == avec_position]

    total = len(resumes)
    debut = (page - 1) * page_size
    return resumes[debut : debut + page_size], total


def renommer_portefeuille(
    session: Session, investisseur_id: uuid.UUID, portefeuille_id: uuid.UUID, nom: str
) -> Portfolio:
    portefeuille = portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    portefeuille.name = nom
    session.add(portefeuille)
    session.commit()
    session.refresh(portefeuille)
    return portefeuille


def archiver_portefeuille(
    session: Session, investisseur_id: uuid.UUID, portefeuille_id: uuid.UUID
) -> Portfolio:
    portefeuille = portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    portefeuille.archived = True
    session.add(portefeuille)
    session.commit()
    session.refresh(portefeuille)
    return portefeuille


def restaurer_portefeuille(
    session: Session, investisseur_id: uuid.UUID, portefeuille_id: uuid.UUID
) -> Portfolio:
    portefeuille = portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    portefeuille.archived = False
    session.add(portefeuille)
    session.commit()
    session.refresh(portefeuille)
    return portefeuille


def supprimer_portefeuille(
    session: Session, investisseur_id: uuid.UUID, portefeuille_id: uuid.UUID
) -> None:
    portefeuille = portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    nb_positions = session.exec(
        select(func.count())
        .select_from(PortfolioPosition)
        .where(PortfolioPosition.portfolio_id == portefeuille_id)
    ).one()
    if nb_positions > 0:
        raise ValidationError(
            "Un portefeuille ayant des positions ne peut pas être supprimé — archivez-le.",
            code="suppression_impossible",
        )
    session.delete(portefeuille)
    session.commit()


def ajouter_position(
    session: Session,
    investisseur_id: uuid.UUID,
    portefeuille_id: uuid.UUID,
    payload: AjouterPositionRequest,
) -> PortfolioPosition:
    portefeuille = portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    entreprise = session.get(Company, payload.company_id)
    if entreprise is None or entreprise.published_at is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
    if entreprise.status != RegistrationStatus.ACTIVE:
        raise ValidationError(
            "Cette entreprise est suspendue — aucune nouvelle position ne peut y être ouverte.",
            code="entreprise_suspendue",
        )

    chemin_taux = get_settings().fx_rates_path
    montant_converti, taux = fx.convertir(
        payload.amount, payload.currency, portefeuille.reference_currency, chemin_taux
    )
    _verifier_montant_minimum(entreprise, montant_converti, portefeuille.reference_currency, chemin_taux)

    # Sans context "entreprise" (voir _construire_position) : le model_validator
    # _valider_montant_minimum, qui compare au montant AVANT conversion, reste un no-op —
    # c'est _verifier_montant_minimum ci-dessus, sur le montant CONVERTI, qui fait foi.
    position = _construire_position(
        {
            "portfolio_id": portefeuille_id,
            "company_id": payload.company_id,
            "outstanding_amount": payload.amount,
            "currency": payload.currency,
            "fx_rate_used": taux,
            "converted_amount": montant_converti,
            "duration_type": payload.duration_type,
            "start_date": payload.start_date,
            "end_date": payload.end_date,
        }
    )
    session.add(position)
    session.commit()
    session.refresh(position)
    return position


def modifier_position(
    session: Session,
    investisseur_id: uuid.UUID,
    portefeuille_id: uuid.UUID,
    position_id: uuid.UUID,
    payload: ModifierPositionRequest,
) -> PortfolioPosition:
    """Remplace la position (nouvel id) plutôt qu'une mutation champ par champ : avec
    validate_assignment=True sur PositionPortefeuille, modifier plusieurs champs un par un
    exposerait des états intermédiaires invalides (ex. nouvelle date_debut posée avant l'ancienne
    date_fin). Sûr uniquement parce que la position est encore PLANIFIEE — jamais activée, donc
    rien à tracer côté historique (contrairement au renforcement, qui crée toujours une position
    en plus d'une existante déjà active)."""
    portefeuille = portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    position = _position_du_portefeuille(session, portefeuille_id, position_id)
    if position.company_id is None:
        # Ligne importée non rapprochée (tâche 2.2) : aucune entreprise dont appliquer les règles.
        raise ValidationError(
            "Une ligne importée non rapprochée ne se modifie pas.",
            code="position_non_rapprochee",
        )
    entreprise = session.get(Company, position.company_id)
    assert entreprise is not None

    if etat_position(position, entreprise.status == RegistrationStatus.ACTIVE) != EtatPosition.PLANIFIEE:
        raise ValidationError(
            "Seule une position encore planifiée peut être modifiée.",
            code="position_non_modifiable",
        )

    chemin_taux = get_settings().fx_rates_path
    montant_converti, taux = fx.convertir(
        payload.amount, payload.currency, portefeuille.reference_currency, chemin_taux
    )
    _verifier_montant_minimum(entreprise, montant_converti, portefeuille.reference_currency, chemin_taux)

    # Validée AVANT toute suppression : une position invalide ne doit jamais laisser le
    # portefeuille avec une position en moins (voir _construire_position).
    nouvelle = _construire_position(
        {
            "portfolio_id": portefeuille_id,
            "company_id": entreprise.id,
            "outstanding_amount": payload.amount,
            "currency": payload.currency,
            "fx_rate_used": taux,
            "converted_amount": montant_converti,
            "duration_type": payload.duration_type,
            "start_date": payload.start_date,
            "end_date": payload.end_date,
        }
    )
    session.delete(position)
    session.flush()
    session.add(nouvelle)
    session.commit()
    session.refresh(nouvelle)
    return nouvelle


def fermer_position(
    session: Session,
    investisseur_id: uuid.UUID,
    portefeuille_id: uuid.UUID,
    position_id: uuid.UUID,
    date_fin: datetime | None,
) -> PortfolioPosition:
    portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    position = _position_du_portefeuille(session, portefeuille_id, position_id)
    if position.duration_type != DurationType.OUVERTE:
        raise ValidationError(
            "Seule une position à durée ouverte peut être fermée manuellement.",
            code="fermeture_impossible",
        )
    if position.end_date is not None:
        raise ValidationError("Cette position est déjà clôturée.", code="position_deja_cloturee")

    try:
        # validate_assignment=True revalide ici même (date_fin > date_debut) — pydantic.ValidationError
        # n'est pas gérée par les handlers globaux, voir _construire_position.
        position.end_date = date_fin or utcnow()
    except pydantic.ValidationError as exc:
        message = exc.errors()[0]["msg"] if exc.errors() else "Date de fermeture invalide."
        raise ValidationError(message, code="fermeture_invalide") from exc
    session.add(position)
    session.commit()
    session.refresh(position)
    return position


def supprimer_position(
    session: Session,
    investisseur_id: uuid.UUID,
    portefeuille_id: uuid.UUID,
    position_id: uuid.UUID,
) -> None:
    portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    position = _position_du_portefeuille(session, portefeuille_id, position_id)
    entreprise = session.get(Company, position.company_id) if position.company_id else None
    # Sans entreprise (ligne non rapprochée), seul l'état temporel compte.
    entreprise_active = entreprise is None or entreprise.status == RegistrationStatus.ACTIVE
    if etat_position(position, entreprise_active) != EtatPosition.PLANIFIEE:
        raise ValidationError(
            "Seule une position encore planifiée peut être supprimée.",
            code="position_non_supprimable",
        )
    session.delete(position)
    session.commit()


def exporter_positions_csv(session: Session, portefeuille: Portfolio) -> str:
    positions = list(
        session.exec(
            select(PortfolioPosition).where(PortfolioPosition.portfolio_id == portefeuille.id)
        ).all()
    )
    montant_total, *_reste = _agreger(session, positions)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "entreprise", "secteur", "pays", "montant_investi", "devise",
            "montant_converti", "devise_reference", "poids_pct", "type_duree",
            "date_debut", "date_fin", "etat", "score_esg",
        ]
    )
    for position in positions:
        detail = position_detail(session, position, montant_total)
        writer.writerow(
            [
                # Ligne non rapprochée (tâche 2.2) : son identifiant d'origine tient lieu de nom.
                detail.company.name if detail.company else f"[{detail.identifier}]",
                detail.company.sector if detail.company else "",
                detail.company.country if detail.company else "",
                detail.outstanding_amount,
                detail.currency.value,
                round(detail.converted_amount, 2),
                portefeuille.reference_currency.value,
                round(detail.weight * 100, 2),
                detail.duration_type.value,
                detail.start_date.isoformat(),
                detail.end_date.isoformat() if detail.end_date else "",
                detail.state.value,
                detail.score.global_score if detail.score.global_score is not None else "",
            ]
        )
    return buffer.getvalue()


def statistiques_admin(session: Session) -> tuple[int, int, int]:
    """(portefeuilles non archivés, positions déclarées, entreprises distinctes présentes dans au
    moins un portefeuille) tous Investisseurs confondus — synthèse pour l'Aperçu Administrateur
    (app/admin/apercu.py). investisseurs_actifs est déjà calculé ailleurs (voir
    app/admin/dashboard.py), pas dupliqué ici."""
    portefeuilles_non_archives = session.exec(
        select(func.count()).select_from(Portfolio).where(col(Portfolio.archived).is_(False))
    ).one()
    positions_declarees = session.exec(select(func.count()).select_from(PortfolioPosition)).one()
    entreprises_distinctes = session.exec(
        select(func.count(func.distinct(col(PortfolioPosition.company_id))))
    ).one()
    return portefeuilles_non_archives, positions_declarees, entreprises_distinctes


def lister_portefeuilles_admin(
    session: Session,
    *,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[tuple[Portfolio, User, int, Decimal]], int]:
    """Vue de suivi Administrateur de tous les portefeuilles non archivés, avec titulaire et nombre
    de positions — le détail derrière "Portefeuilles non archivés" de l'Aperçu (indicateur → liste
    filtrée). montant_total est déjà dans la devise de référence du portefeuille
    (PortfolioPosition.converted_amount, jamais recalculé) — jamais additionné entre
    portefeuilles de devises différentes."""
    filtres: list[ColumnElement[bool]] = [col(Portfolio.archived).is_(False)]
    if recherche:
        filtres.append(contient(recherche, Portfolio.name, User.email))

    total = session.exec(
        select(func.count())
        .select_from(Portfolio)
        .join(User, col(Portfolio.user_id) == col(User.id))
        .where(*filtres)
    ).one()
    portefeuilles = list(
        session.exec(
            select(Portfolio)
            .join(User, col(Portfolio.user_id) == col(User.id))
            .where(*filtres)
            .order_by(col(Portfolio.created_at).desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )

    resultats: list[tuple[Portfolio, User, int, Decimal]] = []
    for portefeuille in portefeuilles:
        investisseur = session.get(User, portefeuille.user_id)
        assert investisseur is not None  # FK NOT NULL, ne peut pas être absent
        positions = list(
            session.exec(
                select(PortfolioPosition).where(
                    PortfolioPosition.portfolio_id == portefeuille.id
                )
            ).all()
        )
        montant_total, *_reste = _agreger(session, positions)
        resultats.append((portefeuille, investisseur, len(positions), montant_total))
    return resultats, total
