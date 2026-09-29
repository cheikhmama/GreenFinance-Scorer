"""Cycle de vie d'une analyse Chercheur (Étape 17, étendu Étape 17bis).

Une correction demandée par l'Institution ne réécrit jamais l'analyse existante — corriger_analyse
crée une nouvelle ligne (version+1, analyse_precedente_id), même principe que
app/company/rapports.py::creer_correction sur ESGReport.

Une entreprise ne peut être comparée dans une analyse que si elle appartient au périmètre du
projet (ProjetEntreprise, défini par l'Institution) — jamais n'importe quelle entreprise publiée
de la plateforme. rapport_id/score_esg_id sont figés sur AnalyseEntreprise au moment de l'ajout
(dernier_rapport_valide + score_officiel) pour que l'analyse restitue toujours exactement les
données utilisées à l'époque, même si l'entreprise est réévaluée ou republiée plus tard.
"""

import uuid

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app.auth.models import Utilisateur
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import StatutAnalyse, StatutProjet
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier
from app.institution.models import AffectationProjet, Projet, ProjetEntreprise
from app.investor.entreprises import dernier_rapport_valide
from app.researcher.models import Analyse, AnalyseEntreprise
from app.scoring.engine import score_officiel


def _projet_affecte(
    session: Session, chercheur_id: uuid.UUID, projet_id: uuid.UUID
) -> Projet:
    projet = session.get(Projet, projet_id)
    affectation = session.exec(
        select(AffectationProjet).where(
            AffectationProjet.projet_id == projet_id,
            AffectationProjet.chercheur_id == chercheur_id,
        )
    ).first()
    if projet is None or affectation is None:
        # Même code que le projet soit inconnu ou non affecté à ce chercheur — jamais de 403 qui
        # confirmerait l'existence d'un projet auquel il n'a pas accès.
        raise NotFoundError("Projet introuvable.", code="projet_introuvable")
    return projet


def _verifier_perimetre_et_recuperer_snapshots(
    session: Session, projet_id: uuid.UUID, entreprise_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[uuid.UUID, uuid.UUID]]:
    """Pour chaque entreprise demandée : doit appartenir au périmètre du projet, être publiée,
    avoir un rapport publié identifiable et un score officiel identifiable — sinon refus explicite
    (jamais une déduction silencieuse). Retourne {entreprise_id: (rapport_id, score_esg_id)},
    les valeurs à figer sur AnalyseEntreprise."""
    if not entreprise_ids:
        raise ValidationError(
            "Une analyse doit comparer au moins une entreprise.",
            code="entreprises_requises",
        )

    snapshots: dict[uuid.UUID, tuple[uuid.UUID, uuid.UUID]] = {}
    for entreprise_id in entreprise_ids:
        dans_perimetre = session.exec(
            select(ProjetEntreprise).where(
                ProjetEntreprise.projet_id == projet_id,
                ProjetEntreprise.entreprise_id == entreprise_id,
            )
        ).first()
        if dans_perimetre is None:
            raise ValidationError(
                "Cette entreprise ne fait pas partie du périmètre autorisé de ce projet.",
                code="entreprise_hors_perimetre",
            )

        entreprise = session.get(Company, entreprise_id)
        if entreprise is None or entreprise.published_at is None:
            raise NotFoundError(
                "Entreprise introuvable.", code="entreprise_introuvable"
            )

        rapport = dernier_rapport_valide(session, entreprise_id)
        if rapport is None:
            raise ValidationError(
                "Cette entreprise n'a pas encore d'évaluation ESG publiée.",
                code="entreprise_non_evaluee",
            )

        score = score_officiel(session, rapport.id)
        if score is None:
            raise ValidationError(
                "Le score ESG officiel de cette entreprise est introuvable.",
                code="score_officiel_introuvable",
            )

        snapshots[entreprise_id] = (rapport.id, score.id)
    return snapshots


def _remplacer_entreprises(
    session: Session,
    analyse_id: uuid.UUID,
    entreprise_ids: list[uuid.UUID],
    snapshots: dict[uuid.UUID, tuple[uuid.UUID, uuid.UUID]],
) -> None:
    existantes = session.exec(
        select(AnalyseEntreprise).where(AnalyseEntreprise.analyse_id == analyse_id)
    ).all()
    for lien in existantes:
        session.delete(lien)
    session.flush()
    for entreprise_id in entreprise_ids:
        rapport_id, score_esg_id = snapshots[entreprise_id]
        session.add(
            AnalyseEntreprise(
                analyse_id=analyse_id,
                entreprise_id=entreprise_id,
                rapport_id=rapport_id,
                score_esg_id=score_esg_id,
            )
        )


def lister_entreprise_ids(session: Session, analyse_id: uuid.UUID) -> list[uuid.UUID]:
    return [
        lien.entreprise_id
        for lien in session.exec(
            select(AnalyseEntreprise).where(AnalyseEntreprise.analyse_id == analyse_id)
        ).all()
    ]


def creer_analyse(
    session: Session,
    chercheur_id: uuid.UUID,
    projet_id: uuid.UUID,
    titre: str,
    contenu: str,
    entreprise_ids: list[uuid.UUID],
) -> Analyse:
    projet = _projet_affecte(session, chercheur_id, projet_id)
    if projet.statut != StatutProjet.OUVERT:
        raise ValidationError("Ce projet est clôturé.", code="projet_cloture")
    snapshots = _verifier_perimetre_et_recuperer_snapshots(
        session, projet_id, entreprise_ids
    )

    analyse = Analyse(
        projet_id=projet_id, chercheur_id=chercheur_id, titre=titre, contenu=contenu
    )
    session.add(analyse)
    session.flush()
    _remplacer_entreprises(session, analyse.id, entreprise_ids, snapshots)
    session.commit()
    session.refresh(analyse)
    return analyse


def _analyse_du_chercheur(
    session: Session, chercheur_id: uuid.UUID, analyse_id: uuid.UUID
) -> Analyse:
    analyse = session.get(Analyse, analyse_id)
    if analyse is None or analyse.chercheur_id != chercheur_id:
        raise NotFoundError("Analyse introuvable.", code="analyse_introuvable")
    return analyse


def modifier_analyse(
    session: Session,
    chercheur_id: uuid.UUID,
    analyse_id: uuid.UUID,
    titre: str,
    contenu: str,
    entreprise_ids: list[uuid.UUID],
) -> Analyse:
    analyse = _analyse_du_chercheur(session, chercheur_id, analyse_id)
    if analyse.statut != StatutAnalyse.BROUILLON:
        raise ValidationError(
            "Seule une analyse en brouillon peut être modifiée.",
            code="analyse_non_modifiable",
        )
    snapshots = _verifier_perimetre_et_recuperer_snapshots(
        session, analyse.projet_id, entreprise_ids
    )

    analyse.titre = titre
    analyse.contenu = contenu
    session.add(analyse)
    _remplacer_entreprises(session, analyse.id, entreprise_ids, snapshots)
    session.commit()
    session.refresh(analyse)
    return analyse


def soumettre_analyse(
    session: Session, chercheur_id: uuid.UUID, analyse_id: uuid.UUID
) -> Analyse:
    analyse = _analyse_du_chercheur(session, chercheur_id, analyse_id)
    if analyse.statut != StatutAnalyse.BROUILLON:
        raise ValidationError(
            "Seule une analyse en brouillon peut être soumise.",
            code="soumission_impossible",
        )
    a_des_entreprises = session.exec(
        select(AnalyseEntreprise.id).where(
            col(AnalyseEntreprise.analyse_id) == analyse.id
        )
    ).first()
    if a_des_entreprises is None:
        raise ValidationError(
            "Une analyse doit comparer au moins une entreprise avant d'être soumise.",
            code="entreprises_requises",
        )
    analyse.statut = StatutAnalyse.SOUMISE
    analyse.date_soumission = utcnow()
    session.add(analyse)
    projet = session.get(Projet, analyse.projet_id)
    assert (
        projet is not None
    )  # invariant : une analyse pointe toujours un projet existant
    notifier(
        session,
        projet.institution_id,
        "ANALYSE_SOUMISE",
        f"Une analyse « {analyse.titre} » a été soumise pour décision.",
        id_ressource=analyse.id,
    )
    session.commit()
    session.refresh(analyse)
    return analyse


def corriger_analyse(
    session: Session,
    chercheur_id: uuid.UUID,
    analyse_id: uuid.UUID,
    titre: str,
    contenu: str,
    entreprise_ids: list[uuid.UUID],
) -> Analyse:
    precedente = _analyse_du_chercheur(session, chercheur_id, analyse_id)
    if precedente.statut != StatutAnalyse.CORRECTION_DEMANDEE:
        raise ValidationError(
            "Cette analyse n'est pas en attente de correction.",
            code="correction_non_attendue",
        )
    snapshots = _verifier_perimetre_et_recuperer_snapshots(
        session, precedente.projet_id, entreprise_ids
    )

    nouvelle = Analyse(
        projet_id=precedente.projet_id,
        chercheur_id=chercheur_id,
        titre=titre,
        contenu=contenu,
        version=precedente.version + 1,
        analyse_precedente_id=precedente.id,
    )
    session.add(nouvelle)
    session.flush()
    _remplacer_entreprises(session, nouvelle.id, entreprise_ids, snapshots)
    session.commit()
    session.refresh(nouvelle)
    return nouvelle


def lister_versions(session: Session, analyse: Analyse) -> list[Analyse]:
    """Reconstruit la chaîne complète v1 -> correction -> v2 -> ... à partir de n'importe quelle
    version, dans l'ordre (voir Analyse.analyse_precedente_id) — remonte à la racine, puis
    redescend en interrogeant qui la remplace, jusqu'à la version la plus récente."""
    racine = analyse
    while racine.analyse_precedente_id is not None:
        precedente = session.get(Analyse, racine.analyse_precedente_id)
        assert (
            precedente is not None
        )  # invariant : analyse_precedente_id pointe toujours une ligne existante
        racine = precedente

    chaine = [racine]
    while True:
        suivante = session.exec(
            select(Analyse).where(col(Analyse.analyse_precedente_id) == chaine[-1].id)
        ).first()
        if suivante is None:
            break
        chaine.append(suivante)
    return chaine


def historique_analyse(
    session: Session, chercheur_id: uuid.UUID, analyse_id: uuid.UUID
) -> list[Analyse]:
    analyse = _analyse_du_chercheur(session, chercheur_id, analyse_id)
    return lister_versions(session, analyse)


def statistiques_admin(session: Session) -> tuple[int, dict[StatutAnalyse, int]]:
    """(chercheurs distincts avec une affectation sur un projet OUVERT, nombre d'analyses par
    statut) — synthèse pour l'Aperçu Administrateur (app/admin/apercu.py). chercheurs_actifs
    (comptes) est déjà calculé ailleurs (voir app/admin/dashboard.py) — ceci compte les chercheurs
    avec une affectation active, une mesure différente (un compte actif peut n'avoir aucune
    affectation en cours)."""
    chercheurs_affectes = session.exec(
        select(func.count(func.distinct(col(AffectationProjet.chercheur_id))))
        .select_from(AffectationProjet)
        .join(Projet, col(AffectationProjet.projet_id) == Projet.id)
        .where(col(Projet.statut) == StatutProjet.OUVERT)
    ).one()
    lignes = session.exec(
        select(Analyse.statut, func.count()).select_from(Analyse).group_by(col(Analyse.statut))
    ).all()
    par_statut = {StatutAnalyse(statut): total for statut, total in lignes}
    return chercheurs_affectes, par_statut


def lister_analyses_admin(
    session: Session,
    *,
    statut: StatutAnalyse | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[tuple[Analyse, str, str]], int]:
    """Vue de suivi Administrateur de toutes les analyses (toutes versions), avec filtre optionnel
    sur le statut — le détail derrière "Analyses par statut" / "Corrections demandées" de
    l'Aperçu. Renvoie (Analyse, e-mail du chercheur, nom du projet) par ligne. Chaque ligne reste
    une version précise (voir Analyse.analyse_precedente_id) — jamais fusionnée avec ses versions
    précédentes/suivantes, pas de double comptage d'une même unité de travail."""
    filtres: list[ColumnElement[bool]] = []
    if statut is not None:
        filtres.append(col(Analyse.statut) == statut)

    total = session.exec(select(func.count()).select_from(Analyse).where(*filtres)).one()
    lignes = list(
        session.exec(
            select(Analyse, Utilisateur.email, Projet.nom)
            .join(Utilisateur, col(Analyse.chercheur_id) == Utilisateur.id)
            .join(Projet, col(Analyse.projet_id) == Projet.id)
            .where(*filtres)
            .order_by(col(Analyse.date_creation).desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return lignes, total
