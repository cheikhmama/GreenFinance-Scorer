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
from typing import Any

import pydantic
from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app.company.models import Entreprise
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import DevisePosition, TypeDureeInvestissement
from app.core.exceptions import NotFoundError, ValidationError
from app.ingestion.models import IndicateurESG
from app.investor import entreprises as entreprises_investisseur
from app.investor import fx
from app.investor.models import Portefeuille, PositionPortefeuille
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


def _portefeuille_de_investisseur(
    session: Session, investisseur_id: uuid.UUID, portefeuille_id: uuid.UUID
) -> Portefeuille:
    portefeuille = session.get(Portefeuille, portefeuille_id)
    if portefeuille is None or portefeuille.investisseur_id != investisseur_id:
        raise NotFoundError("Portefeuille introuvable.", code="portefeuille_introuvable")
    return portefeuille


def _position_du_portefeuille(
    session: Session, portefeuille_id: uuid.UUID, position_id: uuid.UUID
) -> PositionPortefeuille:
    position = session.get(PositionPortefeuille, position_id)
    if position is None or position.portefeuille_id != portefeuille_id:
        raise NotFoundError("Position introuvable.", code="position_introuvable")
    return position


def _etat_temporel(position: PositionPortefeuille) -> EtatPosition:
    maintenant = utcnow()
    if position.date_debut > maintenant:
        return EtatPosition.PLANIFIEE
    if position.date_fin is not None and position.date_fin <= maintenant:
        return EtatPosition.CLOTUREE
    return EtatPosition.ACTIVE


def etat_position(position: PositionPortefeuille, entreprise_actif: bool) -> EtatPosition:
    """L'entreprise suspendue prime sur l'état temporel dans l'affichage (voir le cahier des
    charges) — la position n'est jamais perdue, seule une nouvelle opération est bloquée
    (voir ajouter_position)."""
    if not entreprise_actif:
        return EtatPosition.ENTREPRISE_SUSPENDUE
    return _etat_temporel(position)


def _construire_position(valeurs: dict[str, Any]) -> PositionPortefeuille:
    """.model_validate() (jamais une construction directe) : déclenche volontairement les
    model_validator de PositionPortefeuille (règles de durée FIXE/OUVERTE). pydantic.ValidationError
    n'est pas gérée par les handlers globaux de l'app (seulement GreenFinanceError et
    RequestValidationError, voir app/core/exceptions.py) — sans cette conversion, une règle de
    durée violée deviendrait un 500 au lieu d'un 422 exploitable par le frontend."""
    try:
        return PositionPortefeuille.model_validate(valeurs)
    except pydantic.ValidationError as exc:
        message = exc.errors()[0]["msg"] if exc.errors() else "Position invalide."
        raise ValidationError(message, code="position_invalide") from exc


def _verifier_montant_minimum(entreprise: Entreprise, montant_converti: float) -> None:
    minimum = entreprise.montant_minimum_investissement
    if minimum is not None and montant_converti < minimum:
        raise ValidationError(
            "Le montant est inférieur au minimum requis par cette entreprise.",
            code="montant_insuffisant",
        )


def _agreger(
    session: Session, positions: list[PositionPortefeuille]
) -> tuple[float, float | None, float | None, float | None, float | None, float]:
    """Retourne (montant_total, score_global, score_e, score_s, score_g, couverture_pct).

    Chaque agrégat pondéré n'inclut que les positions dont l'entreprise a effectivement ce
    score/pilier calculé — jamais comptée comme 0 si absente (même principe que
    app/scoring/engine.py sur les piliers manquants)."""
    montant_total = sum(p.montant_converti for p in positions)
    if montant_total == 0:
        return 0.0, None, None, None, None, 0.0

    scores = {
        p.id: entreprises_investisseur.score_public(
            session, entreprises_investisseur.dernier_rapport_valide(session, p.entreprise_id)
        )
        for p in positions
    }

    def agreger_pilier(valeur_pilier: Callable[[ScoreEntreprisePublic], float | None]) -> float | None:
        numerateur = 0.0
        denominateur = 0.0
        for p in positions:
            valeur = valeur_pilier(scores[p.id])
            if valeur is not None:
                numerateur += p.montant_converti * valeur
                denominateur += p.montant_converti
        return (numerateur / denominateur) if denominateur > 0 else None

    score_global = agreger_pilier(lambda s: s.valeur_globale)
    score_e = agreger_pilier(lambda s: s.score_environnement)
    score_s = agreger_pilier(lambda s: s.score_social)
    score_g = agreger_pilier(lambda s: s.score_gouvernance)

    montant_couvert = sum(
        p.montant_converti for p in positions if scores[p.id].valeur_globale is not None
    )
    couverture = (montant_couvert / montant_total * 100) if montant_total else 0.0
    return montant_total, score_global, score_e, score_s, score_g, couverture


def position_detail(
    session: Session, position: PositionPortefeuille, montant_total_portefeuille: float
) -> PositionDetail:
    entreprise = session.get(Entreprise, position.entreprise_id)
    assert entreprise is not None  # invariant : FK entreprise_id garantie par la base
    rapport = entreprises_investisseur.dernier_rapport_valide(session, position.entreprise_id)
    score = entreprises_investisseur.score_public(session, rapport)
    preuves_disponibles = rapport is not None and (
        session.exec(
            select(IndicateurESG.id).where(IndicateurESG.rapport_id == rapport.id)
        ).first()
        is not None
    )
    poids = position.montant_converti / montant_total_portefeuille if montant_total_portefeuille else 0.0

    return PositionDetail(
        id=position.id,
        portefeuille_id=position.portefeuille_id,
        entreprise=EntrepriseSommaire.model_validate(entreprise),
        montant_investi=position.montant_investi,
        devise=position.devise,
        montant_converti=position.montant_converti,
        taux_change_utilise=position.taux_change_utilise,
        poids=poids,
        type_duree=position.type_duree,
        date_debut=position.date_debut,
        date_fin=position.date_fin,
        etat=etat_position(position, entreprise.actif),
        score=score,
        date_publication_utilisee=entreprise.date_publication,
        preuves_disponibles=preuves_disponibles,
    )


def resume_portefeuille(session: Session, portefeuille: Portefeuille) -> PortefeuilleResume:
    positions = list(
        session.exec(
            select(PositionPortefeuille).where(PositionPortefeuille.portefeuille_id == portefeuille.id)
        ).all()
    )
    montant_total, score_global, score_e, score_s, score_g, couverture = _agreger(session, positions)
    return PortefeuilleResume(
        id=portefeuille.id,
        nom=portefeuille.nom,
        devise_reference=portefeuille.devise_reference,
        montant_total=montant_total,
        nombre_positions=len(positions),
        score_esg_agrege=score_global,
        score_environnement_agrege=score_e,
        score_social_agrege=score_s,
        score_gouvernance_agrege=score_g,
        couverture_esg=couverture,
        date_creation=portefeuille.date_creation,
        archive=portefeuille.archive,
    )


def detail_portefeuille(session: Session, portefeuille: Portefeuille) -> PortefeuilleDetail:
    positions = list(
        session.exec(
            select(PositionPortefeuille).where(PositionPortefeuille.portefeuille_id == portefeuille.id)
        ).all()
    )
    montant_total, score_global, score_e, score_s, score_g, couverture = _agreger(session, positions)
    positions_detail = [position_detail(session, p, montant_total) for p in positions]
    compte = Counter(_etat_temporel(p) for p in positions)

    return PortefeuilleDetail(
        id=portefeuille.id,
        nom=portefeuille.nom,
        devise_reference=portefeuille.devise_reference,
        montant_total=montant_total,
        nombre_positions=len(positions),
        score_esg_agrege=score_global,
        score_environnement_agrege=score_e,
        score_social_agrege=score_s,
        score_gouvernance_agrege=score_g,
        couverture_esg=couverture,
        date_creation=portefeuille.date_creation,
        archive=portefeuille.archive,
        nombre_positions_planifiees=compte.get(EtatPosition.PLANIFIEE, 0),
        nombre_positions_actives=compte.get(EtatPosition.ACTIVE, 0),
        nombre_positions_cloturees=compte.get(EtatPosition.CLOTUREE, 0),
        positions=positions_detail,
    )


def creer_portefeuille(
    session: Session, investisseur_id: uuid.UUID, nom: str, devise_reference: DevisePosition
) -> Portefeuille:
    portefeuille = Portefeuille(
        investisseur_id=investisseur_id, nom=nom, devise_reference=devise_reference
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
    filtres: list[ColumnElement[bool]] = [col(Portefeuille.investisseur_id) == investisseur_id]
    if archive is not None:
        filtres.append(col(Portefeuille.archive) == archive)
    if recherche:
        filtres.append(col(Portefeuille.nom).ilike(f"%{recherche}%"))

    tous = list(
        session.exec(
            select(Portefeuille).where(*filtres).order_by(col(Portefeuille.date_creation).desc())
        ).all()
    )
    resumes = [resume_portefeuille(session, p) for p in tous]
    if avec_position is not None:
        resumes = [r for r in resumes if (r.nombre_positions > 0) == avec_position]

    total = len(resumes)
    debut = (page - 1) * page_size
    return resumes[debut : debut + page_size], total


def renommer_portefeuille(
    session: Session, investisseur_id: uuid.UUID, portefeuille_id: uuid.UUID, nom: str
) -> Portefeuille:
    portefeuille = _portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    portefeuille.nom = nom
    session.add(portefeuille)
    session.commit()
    session.refresh(portefeuille)
    return portefeuille


def archiver_portefeuille(
    session: Session, investisseur_id: uuid.UUID, portefeuille_id: uuid.UUID
) -> Portefeuille:
    portefeuille = _portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    portefeuille.archive = True
    session.add(portefeuille)
    session.commit()
    session.refresh(portefeuille)
    return portefeuille


def restaurer_portefeuille(
    session: Session, investisseur_id: uuid.UUID, portefeuille_id: uuid.UUID
) -> Portefeuille:
    portefeuille = _portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    portefeuille.archive = False
    session.add(portefeuille)
    session.commit()
    session.refresh(portefeuille)
    return portefeuille


def supprimer_portefeuille(
    session: Session, investisseur_id: uuid.UUID, portefeuille_id: uuid.UUID
) -> None:
    portefeuille = _portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    nb_positions = session.exec(
        select(func.count())
        .select_from(PositionPortefeuille)
        .where(PositionPortefeuille.portefeuille_id == portefeuille_id)
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
) -> PositionPortefeuille:
    portefeuille = _portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    entreprise = session.get(Entreprise, payload.entreprise_id)
    if entreprise is None or entreprise.date_publication is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
    if not entreprise.actif:
        raise ValidationError(
            "Cette entreprise est suspendue — aucune nouvelle position ne peut y être ouverte.",
            code="entreprise_suspendue",
        )

    montant_converti, taux = fx.convertir(
        payload.montant, payload.devise, portefeuille.devise_reference, get_settings().fx_rates_path
    )
    _verifier_montant_minimum(entreprise, montant_converti)

    # Sans context "entreprise" (voir _construire_position) : le model_validator
    # _valider_montant_minimum, qui compare au montant AVANT conversion, reste un no-op —
    # c'est _verifier_montant_minimum ci-dessus, sur le montant CONVERTI, qui fait foi.
    position = _construire_position(
        {
            "portefeuille_id": portefeuille_id,
            "entreprise_id": payload.entreprise_id,
            "montant_investi": payload.montant,
            "devise": payload.devise,
            "taux_change_utilise": taux,
            "montant_converti": montant_converti,
            "type_duree": payload.type_duree,
            "date_debut": payload.date_debut,
            "date_fin": payload.date_fin,
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
) -> PositionPortefeuille:
    """Remplace la position (nouvel id) plutôt qu'une mutation champ par champ : avec
    validate_assignment=True sur PositionPortefeuille, modifier plusieurs champs un par un
    exposerait des états intermédiaires invalides (ex. nouvelle date_debut posée avant l'ancienne
    date_fin). Sûr uniquement parce que la position est encore PLANIFIEE — jamais activée, donc
    rien à tracer côté historique (contrairement au renforcement, qui crée toujours une position
    en plus d'une existante déjà active)."""
    portefeuille = _portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    position = _position_du_portefeuille(session, portefeuille_id, position_id)
    entreprise = session.get(Entreprise, position.entreprise_id)
    assert entreprise is not None

    if etat_position(position, entreprise.actif) != EtatPosition.PLANIFIEE:
        raise ValidationError(
            "Seule une position encore planifiée peut être modifiée.",
            code="position_non_modifiable",
        )

    montant_converti, taux = fx.convertir(
        payload.montant, payload.devise, portefeuille.devise_reference, get_settings().fx_rates_path
    )
    _verifier_montant_minimum(entreprise, montant_converti)

    # Validée AVANT toute suppression : une position invalide ne doit jamais laisser le
    # portefeuille avec une position en moins (voir _construire_position).
    nouvelle = _construire_position(
        {
            "portefeuille_id": portefeuille_id,
            "entreprise_id": entreprise.id,
            "montant_investi": payload.montant,
            "devise": payload.devise,
            "taux_change_utilise": taux,
            "montant_converti": montant_converti,
            "type_duree": payload.type_duree,
            "date_debut": payload.date_debut,
            "date_fin": payload.date_fin,
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
) -> PositionPortefeuille:
    _portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    position = _position_du_portefeuille(session, portefeuille_id, position_id)
    if position.type_duree != TypeDureeInvestissement.OUVERTE:
        raise ValidationError(
            "Seule une position à durée ouverte peut être fermée manuellement.",
            code="fermeture_impossible",
        )
    if position.date_fin is not None:
        raise ValidationError("Cette position est déjà clôturée.", code="position_deja_cloturee")

    try:
        # validate_assignment=True revalide ici même (date_fin > date_debut) — pydantic.ValidationError
        # n'est pas gérée par les handlers globaux, voir _construire_position.
        position.date_fin = date_fin or utcnow()
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
    _portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    position = _position_du_portefeuille(session, portefeuille_id, position_id)
    entreprise = session.get(Entreprise, position.entreprise_id)
    assert entreprise is not None
    if etat_position(position, entreprise.actif) != EtatPosition.PLANIFIEE:
        raise ValidationError(
            "Seule une position encore planifiée peut être supprimée.",
            code="position_non_supprimable",
        )
    session.delete(position)
    session.commit()


def exporter_positions_csv(session: Session, portefeuille: Portefeuille) -> str:
    positions = list(
        session.exec(
            select(PositionPortefeuille).where(PositionPortefeuille.portefeuille_id == portefeuille.id)
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
                detail.entreprise.nom,
                detail.entreprise.secteur,
                detail.entreprise.pays,
                detail.montant_investi,
                detail.devise.value,
                round(detail.montant_converti, 2),
                portefeuille.devise_reference.value,
                round(detail.poids * 100, 2),
                detail.type_duree.value,
                detail.date_debut.isoformat(),
                detail.date_fin.isoformat() if detail.date_fin else "",
                detail.etat.value,
                detail.score.valeur_globale if detail.score.valeur_globale is not None else "",
            ]
        )
    return buffer.getvalue()
