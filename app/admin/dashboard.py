"""Agrégation des indicateurs du tableau de bord Administrateur.

Un seul endpoint (GET /admin/dashboard) plutôt qu'un appel par tuile — évite l'accumulation de
routes qui ne renvoient chacune qu'un entier. Réutilise les requêtes déjà écrites pour les files
d'attente (app/admin/review_queue.py) plutôt que de dupliquer leurs filtres.
"""

from sqlmodel import Session, col, func, select

from app.admin.review_queue import (
    lister_entreprises_a_republier,
    lister_rapports_a_affecter,
    lister_rapports_echec_extraction,
    lister_rapports_en_retard,
    lister_rapports_en_validation,
    lister_rapports_orphelins_en_validation,
)
from app.admin.schemas import TableauDeBordAdmin
from app.admin.utilisateurs import lister_utilisateurs_en_attente
from app.auth.models import Utilisateur
from app.company.models import Company
from app.core.enums import ReportStatus, Role
from app.ingestion.models import ESGReport


def construire_tableau_de_bord(session: Session) -> TableauDeBordAdmin:
    entreprises_inscrites = session.exec(select(func.count()).select_from(Company)).one()
    rapports_soumis = session.exec(select(func.count()).select_from(ESGReport)).one()
    rapports_valides = session.exec(
        select(func.count())
        .select_from(ESGReport)
        .where(col(ESGReport.status) == ReportStatus.VALIDATED)
    ).one()
    rapports_rejetes = session.exec(
        select(func.count())
        .select_from(ESGReport)
        .where(col(ESGReport.status) == ReportStatus.REJECTED)
    ).one()
    entreprises_publiees = session.exec(
        select(func.count())
        .select_from(Company)
        .where(col(Company.published_at).is_not(None))
    ).one()

    _, total_a_republier = lister_entreprises_a_republier(session, page=1, page_size=1)

    # Une seule requête groupée plutôt qu'un COUNT par rôle — comptes actifs uniquement (un compte
    # désactivé n'a plus de raison d'être suivi comme effectif de la plateforme ici). ENTREPRISE
    # n'y figure pas : entreprises_inscrites (compte les fiches Entreprise, pas les comptes
    # Utilisateur liés) est la mesure pertinente pour ce rôle, les deux nombres peuvent diverger
    # (une Entreprise peut être "sans compte", voir app/admin/schemas.py::EntrepriseAdmin) — les
    # afficher tous les deux côte à côte sèmerait la confusion plutôt que d'informer.
    comptes_par_role = dict(
        session.exec(
            select(Utilisateur.role, func.count())
            .where(col(Utilisateur.actif).is_(True))
            .group_by(col(Utilisateur.role))
        ).all()
    )

    return TableauDeBordAdmin(
        entreprises_inscrites=entreprises_inscrites,
        rapports_soumis=rapports_soumis,
        rapports_valides=rapports_valides,
        rapports_rejetes=rapports_rejetes,
        entreprises_publiees=entreprises_publiees,
        audits_en_retard=len(lister_rapports_en_retard(session)),
        rapports_a_affecter=len(lister_rapports_a_affecter(session)),
        decisions_a_rendre=len(lister_rapports_en_validation(session)),
        demandes_republication=total_a_republier,
        utilisateurs_en_attente=len(lister_utilisateurs_en_attente(session)),
        rapports_echec_extraction=len(lister_rapports_echec_extraction(session)),
        rapports_orphelins=len(lister_rapports_orphelins_en_validation(session)),
        administrateurs_actifs=comptes_par_role.get(Role.ADMINISTRATEUR, 0),
        auditeurs_actifs=comptes_par_role.get(Role.AUDITEUR, 0),
        investisseurs_actifs=comptes_par_role.get(Role.INVESTISSEUR, 0),
        chercheurs_actifs=comptes_par_role.get(Role.CHERCHEUR, 0),
        institutions_actives=comptes_par_role.get(Role.INSTITUTION, 0),
    )
