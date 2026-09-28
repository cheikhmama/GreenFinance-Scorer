"""Tableau de bord de l'espace Investisseur (Étape 16).

Synthèse en lecture pure sur PostgreSQL — jamais de valeur fabriquée : une entreprise sans score
n'est simplement pas comptée dans le taux de couverture, jamais comptée comme 0 (même principe
qu'ailleurs dans le projet, voir app/scoring/engine.py).
"""

import uuid
from datetime import timedelta

from sqlmodel import Session, col, select

from app.company.models import Entreprise
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import DevisePosition
from app.investor import entreprises as entreprises_investisseur
from app.investor import fx
from app.investor.models import Portefeuille, PositionPortefeuille
from app.investor.schemas import (
    EntrepriseSommaire,
    RepartitionSecteur,
    TableauDeBordInvestisseur,
)

_FENETRE_NOUVELLES_PUBLICATIONS_JOURS = 30
# Volontairement limité à 2 : la section "Publications récentes" du Dashboard Investisseur ne
# montre qu'un aperçu, pas une liste complète (voir /investor/entreprises pour la liste entière).
_PUBLICATIONS_RECENTES_LIMITE = 2


def construire_tableau_de_bord(
    session: Session, investisseur_id: uuid.UUID
) -> TableauDeBordInvestisseur:
    chemin_taux = get_settings().fx_rates_path

    portefeuilles = list(
        session.exec(select(Portefeuille).where(Portefeuille.investisseur_id == investisseur_id)).all()
    )
    devise_par_portefeuille = {p.id: p.devise_reference for p in portefeuilles}

    toutes_positions: list[PositionPortefeuille] = []
    for p in portefeuilles:
        toutes_positions.extend(
            session.exec(
                select(PositionPortefeuille).where(PositionPortefeuille.portefeuille_id == p.id)
            ).all()
        )

    entreprises_publiees = list(
        session.exec(select(Entreprise).where(col(Entreprise.date_publication).is_not(None))).all()
    )

    # Couverture ESG plateforme : part des entreprises publiées dont les 3 piliers sont calculés.
    nb_complets = 0
    for entreprise in entreprises_publiees:
        score = entreprises_investisseur.score_public(
            session, entreprises_investisseur.dernier_rapport_valide(session, entreprise.id)
        )
        if (
            score.score_environnement is not None
            and score.score_social is not None
            and score.score_gouvernance is not None
        ):
            nb_complets += 1
    taux_couverture_esg_plateforme = (
        nb_complets / len(entreprises_publiees) * 100 if entreprises_publiees else 0.0
    )

    # Répartition par secteur, convertie en USD (devise pivot commune, nécessaire car chaque
    # portefeuille peut avoir sa propre devise de référence).
    repartition_usd: dict[str, float] = {}
    entreprises_suivies_ids: set[uuid.UUID] = set()
    for position in toutes_positions:
        entreprises_suivies_ids.add(position.entreprise_id)
        entreprise_de_la_position = session.get(Entreprise, position.entreprise_id)
        assert entreprise_de_la_position is not None
        devise_portefeuille = devise_par_portefeuille[position.portefeuille_id]
        montant_usd, _ = fx.convertir(
            position.montant_converti, devise_portefeuille, DevisePosition.USD, chemin_taux
        )
        repartition_usd[entreprise_de_la_position.secteur] = (
            repartition_usd.get(entreprise_de_la_position.secteur, 0.0) + montant_usd
        )

    repartition_secteur = [
        RepartitionSecteur(secteur=secteur, montant_usd=montant)
        for secteur, montant in sorted(repartition_usd.items(), key=lambda item: item[1], reverse=True)
    ]

    seuil_nouvelles_publications = utcnow() - timedelta(days=_FENETRE_NOUVELLES_PUBLICATIONS_JOURS)
    nombre_nouvelles_publications_suivies = sum(
        1
        for entreprise in entreprises_publiees
        if entreprise.id in entreprises_suivies_ids
        and entreprise.date_publication is not None
        and entreprise.date_publication >= seuil_nouvelles_publications
    )

    publications_recentes = [
        entreprises_investisseur.entreprise_publiee_publique(session, e)
        for e in sorted(
            entreprises_publiees, key=lambda e: e.date_publication or utcnow(), reverse=True
        )[:_PUBLICATIONS_RECENTES_LIMITE]
    ]

    entreprises_suivies_suspendues = [
        EntrepriseSommaire.model_validate(e)
        for e in entreprises_publiees
        if e.id in entreprises_suivies_ids and not e.actif
    ]

    return TableauDeBordInvestisseur(
        nombre_portefeuilles=len(portefeuilles),
        nombre_entreprises_publiees=len(entreprises_publiees),
        taux_couverture_esg_plateforme=taux_couverture_esg_plateforme,
        nombre_nouvelles_publications_suivies=nombre_nouvelles_publications_suivies,
        repartition_secteur=repartition_secteur,
        publications_recentes=publications_recentes,
        entreprises_suivies_suspendues=entreprises_suivies_suspendues,
    )
