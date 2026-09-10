"""Agrégation des indicateurs du tableau de bord Administrateur.

Un seul endpoint (GET /admin/dashboard) plutôt qu'un appel par tuile — évite l'accumulation de
routes qui ne renvoient chacune qu'un entier. Réutilise les requêtes déjà écrites pour les files
d'attente (app/admin/review_queue.py) plutôt que de dupliquer leurs filtres.
"""

from datetime import timedelta

from sqlmodel import Session, col, func, select

from app.admin.review_queue import (
    lister_rapports_a_affecter,
    lister_rapports_en_validation,
)
from app.admin.schemas import TableauDeBordAdmin
from app.auth.models import Utilisateur
from app.company.models import Entreprise
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import StatutRapport
from app.ingestion.models import RapportESG


def construire_tableau_de_bord(session: Session) -> TableauDeBordAdmin:
    settings = get_settings()
    seuil_retard = utcnow() - timedelta(days=settings.sla_audit_jours)

    entreprises_inscrites = session.exec(select(func.count()).select_from(Entreprise)).one()
    rapports_soumis = session.exec(select(func.count()).select_from(RapportESG)).one()
    rapports_valides = session.exec(
        select(func.count())
        .select_from(RapportESG)
        .where(col(RapportESG.statut) == StatutRapport.VALIDE)
    ).one()
    rapports_rejetes = session.exec(
        select(func.count())
        .select_from(RapportESG)
        .where(col(RapportESG.statut) == StatutRapport.REJETE)
    ).one()
    entreprises_publiees = session.exec(
        select(func.count())
        .select_from(Entreprise)
        .where(col(Entreprise.date_publication).is_not(None))
    ).one()
    audits_en_retard = session.exec(
        select(func.count())
        .select_from(RapportESG)
        .where(
            col(RapportESG.statut) == StatutRapport.AFFECTE_AUDITEUR,
            col(RapportESG.date_affectation).is_not(None),
            col(RapportESG.date_affectation) < seuil_retard,
        )
    ).one()

    # Une entreprise déjà publiée dont un rapport a été validé APRÈS sa date de publication : la
    # fiche publique ne reflète plus le dernier état validé.
    republication_existe = (
        select(RapportESG.id)
        .where(
            col(RapportESG.entreprise_id) == Entreprise.id,
            col(RapportESG.statut) == StatutRapport.VALIDE,
            col(RapportESG.date_depot) > Entreprise.date_publication,
        )
        .exists()
    )
    demandes_republication = session.exec(
        select(func.count())
        .select_from(Entreprise)
        .where(col(Entreprise.date_publication).is_not(None), republication_existe)
    ).one()

    utilisateurs_en_attente = session.exec(
        select(func.count())
        .select_from(Utilisateur)
        .where(
            col(Utilisateur.doit_changer_mot_de_passe).is_(True),
            col(Utilisateur.actif).is_(True),
        )
    ).one()

    return TableauDeBordAdmin(
        entreprises_inscrites=entreprises_inscrites,
        rapports_soumis=rapports_soumis,
        rapports_valides=rapports_valides,
        rapports_rejetes=rapports_rejetes,
        entreprises_publiees=entreprises_publiees,
        audits_en_retard=audits_en_retard,
        rapports_a_affecter=len(lister_rapports_a_affecter(session)),
        decisions_a_rendre=len(lister_rapports_en_validation(session)),
        demandes_republication=demandes_republication,
        utilisateurs_en_attente=utilisateurs_en_attente,
    )
