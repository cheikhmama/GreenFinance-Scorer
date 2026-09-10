"""File de revue des soumissions en attente de validation administrateur.

Logique de file d'attente, de décision (valider/rejeter/demander correction) et de publication.
L'affectation elle-même vit dans app/audit/assignment.py (Étape 11 possède l'attribution des
dossiers) — ce module l'invoque depuis le router plutôt que de la réimplémenter localement (voir
ARCHITECTURE.md §1).
"""

import uuid
from datetime import datetime

import structlog
from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, or_, select

from app.audit.models import AvisAudit
from app.company.models import Entreprise
from app.core.database import utcnow
from app.core.enums import StatutRapport
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier
from app.ingestion.models import RapportESG
from app.scoring.engine import calculer_score
from app.scoring.models import ScoreESG

logger = structlog.get_logger(__name__)


def lister_rapports_a_affecter(session: Session) -> list[RapportESG]:
    return list(
        session.exec(
            select(RapportESG)
            .where(
                RapportESG.statut == StatutRapport.EN_EXTRACTION,
                col(RapportESG.extraction_terminee_le).is_not(None),
            )
            .order_by(col(RapportESG.extraction_terminee_le))
        ).all()
    )


def lister_rapports_en_validation(session: Session) -> list[RapportESG]:
    return list(
        session.exec(
            select(RapportESG)
            .join(AvisAudit, col(AvisAudit.rapport_id) == RapportESG.id)
            .where(RapportESG.statut == StatutRapport.EN_VALIDATION)
            .order_by(col(AvisAudit.date_avis))
        ).all()
    )


def lister_avis(session: Session, rapport_id: uuid.UUID) -> list[AvisAudit]:
    rapport = session.get(RapportESG, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    return list(session.exec(select(AvisAudit).where(AvisAudit.rapport_id == rapport_id)).all())


def lister_versions(session: Session, rapport_id: uuid.UUID) -> list[RapportESG]:
    """Reconstruit la chaîne de versions d'un rapport (originale + corrections), dans l'ordre
    chronologique — pas de Relationship() auto-référentielle pour rapport_precedent_id (choix
    déjà fait, voir app/ingestion/models.py), donc parcours explicite : remonter jusqu'à
    l'original, puis redescendre en cherchant à chaque étape la version qui la remplace."""
    rapport = session.get(RapportESG, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    original = rapport
    while original.rapport_precedent_id is not None:
        precedent = session.get(RapportESG, original.rapport_precedent_id)
        if precedent is None:
            break
        original = precedent

    chaine = [original]
    courant = original
    while True:
        suivant = session.exec(
            select(RapportESG).where(RapportESG.rapport_precedent_id == courant.id)
        ).first()
        if suivant is None:
            break
        chaine.append(suivant)
        courant = suivant
    return chaine


def _rapport_en_validation(session: Session, rapport_id: uuid.UUID) -> RapportESG:
    rapport = session.get(RapportESG, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    if rapport.statut != StatutRapport.EN_VALIDATION:
        raise ValidationError(
            "Ce rapport n'est pas en attente de décision.", code="transition_invalide"
        )
    # Inatteignable via l'API seule aujourd'hui (soumettre_avis est ce qui fait passer un rapport
    # en EN_VALIDATION, et crée toujours l'avis dans la même transaction) — gardé en défense, et
    # testable en semant l'état directement en base.
    a_un_avis = session.exec(
        select(AvisAudit.id).where(AvisAudit.rapport_id == rapport_id)
    ).first()
    if a_un_avis is None:
        raise ValidationError(
            "Aucun avis d'audit n'a été soumis pour ce rapport.", code="avis_manquant"
        )
    return rapport


def _decider(
    session: Session,
    rapport_id: uuid.UUID,
    statut: StatutRapport,
    type_notification: str,
    message: str,
) -> RapportESG:
    rapport = _rapport_en_validation(session, rapport_id)
    rapport.statut = statut
    session.add(rapport)
    if rapport.entreprise.utilisateur_id is not None:
        notifier(session, rapport.entreprise.utilisateur_id, type_notification, message)
    session.commit()
    session.refresh(rapport)
    logger.info("rapport_decision", rapport_id=str(rapport_id), statut=statut.value)
    return rapport


def valider_rapport(session: Session, rapport_id: uuid.UUID, commentaire: str | None) -> RapportESG:
    """Distinct de rejeter_rapport/demander_correction (restés sur _decider) : valider est la
    seule décision qui produit aussi un score (Phase 5 §9) — jamais un rapport REJETE ou
    DEMANDE_CORRECTION. La transition de statut et le calcul du score commitent ensemble : un
    score incalculable (calculer_score lève score_incalculable) annule toute la décision plutôt
    que de laisser un rapport VALIDE sans le score que le cahier des charges exige avant
    publication (voir publier_entreprise)."""
    rapport = _rapport_en_validation(session, rapport_id)
    rapport.statut = StatutRapport.VALIDE
    session.add(rapport)
    calculer_score(session, rapport_id)
    if rapport.entreprise.utilisateur_id is not None:
        notifier(
            session,
            rapport.entreprise.utilisateur_id,
            "RAPPORT_VALIDE",
            commentaire or "Votre rapport a été validé.",
        )
    session.commit()
    session.refresh(rapport)
    logger.info("rapport_decision", rapport_id=str(rapport_id), statut=StatutRapport.VALIDE.value)
    return rapport


def rejeter_rapport(session: Session, rapport_id: uuid.UUID, commentaire: str | None) -> RapportESG:
    return _decider(
        session,
        rapport_id,
        StatutRapport.REJETE,
        "RAPPORT_REJETE",
        commentaire or "Votre rapport a été rejeté.",
    )


def demander_correction(
    session: Session, rapport_id: uuid.UUID, commentaire: str | None
) -> RapportESG:
    return _decider(
        session,
        rapport_id,
        StatutRapport.DEMANDE_CORRECTION,
        "RAPPORT_CORRECTION_DEMANDEE",
        commentaire or "Une correction est demandée sur votre rapport.",
    )


def lister_entreprises_publiables(
    session: Session,
    *,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[Entreprise], int]:
    """Page d'entreprises publiables, filtrée par nom/secteur/pays si `recherche` est fourni —
    même principe de pagination par offset/limit que lister_utilisateurs_par_role."""
    entreprises_avec_rapport_valide = select(RapportESG.entreprise_id).where(
        RapportESG.statut == StatutRapport.VALIDE
    )
    filtres: list[ColumnElement[bool]] = [
        col(Entreprise.id).in_(entreprises_avec_rapport_valide),
        col(Entreprise.date_publication).is_(None),
    ]
    if recherche:
        motif = f"%{recherche}%"
        filtres.append(
            or_(
                col(Entreprise.nom).ilike(motif),
                col(Entreprise.secteur).ilike(motif),
                col(Entreprise.pays).ilike(motif),
            )
        )

    total = session.exec(select(func.count()).select_from(Entreprise).where(*filtres)).one()
    items = list(
        session.exec(
            select(Entreprise)
            .where(*filtres)
            .order_by(col(Entreprise.nom))
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def lister_toutes_les_entreprises(
    session: Session,
    *,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[tuple[Entreprise, int, StatutRapport | None]], int]:
    """Page de TOUTES les entreprises (contrairement à lister_entreprises_publiables, sans filtre
    sur le statut de rapport ni la publication) — vue de suivi pour l'Administrateur, avec un
    résumé par entreprise : nombre de rapports déposés et statut du plus récent (None si aucun
    rapport, ex. une entreprise provisionnée sans compte rattaché). Même pagination par
    offset/limit que les autres listes Admin."""
    filtres: list[ColumnElement[bool]] = []
    if recherche:
        motif = f"%{recherche}%"
        filtres.append(
            or_(
                col(Entreprise.nom).ilike(motif),
                col(Entreprise.secteur).ilike(motif),
                col(Entreprise.pays).ilike(motif),
            )
        )

    total = session.exec(select(func.count()).select_from(Entreprise).where(*filtres)).one()
    entreprises = list(
        session.exec(
            select(Entreprise)
            .where(*filtres)
            .order_by(col(Entreprise.nom))
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )

    ids = [entreprise.id for entreprise in entreprises]
    rapports = (
        list(
            session.exec(
                select(RapportESG.entreprise_id, RapportESG.statut, RapportESG.date_depot).where(
                    col(RapportESG.entreprise_id).in_(ids)
                )
            ).all()
        )
        if ids
        else []
    )

    nb_par_entreprise: dict[uuid.UUID, int] = {}
    dernier_par_entreprise: dict[uuid.UUID, tuple[datetime, StatutRapport]] = {}
    for entreprise_id, statut, date_depot in rapports:
        nb_par_entreprise[entreprise_id] = nb_par_entreprise.get(entreprise_id, 0) + 1
        plus_recent = dernier_par_entreprise.get(entreprise_id)
        if plus_recent is None or date_depot > plus_recent[0]:
            dernier_par_entreprise[entreprise_id] = (date_depot, StatutRapport(statut))

    resultats = [
        (
            entreprise,
            nb_par_entreprise.get(entreprise.id, 0),
            dernier_par_entreprise[entreprise.id][1] if entreprise.id in dernier_par_entreprise else None,
        )
        for entreprise in entreprises
    ]
    return resultats, total


def publier_entreprise(session: Session, entreprise_id: uuid.UUID) -> Entreprise:
    entreprise = session.get(Entreprise, entreprise_id)
    if entreprise is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")

    rapport_valide_id = session.exec(
        select(RapportESG.id).where(
            RapportESG.entreprise_id == entreprise_id,
            RapportESG.statut == StatutRapport.VALIDE,
        )
    ).first()
    if rapport_valide_id is None:
        raise ValidationError(
            "Cette entreprise n'a aucun rapport validé.", code="aucun_rapport_valide"
        )
    # Inatteignable via l'API seule aujourd'hui (valider_rapport calcule toujours un score dans
    # la même transaction que la transition VALIDE) — gardé en défense, même principe que
    # _rapport_en_validation ci-dessus : jamais de publication sans preuve de score (cahier des
    # charges §9), quelle que soit la façon dont un rapport a pu atteindre VALIDE.
    a_un_score = session.exec(
        select(ScoreESG.id).where(ScoreESG.rapport_id == rapport_valide_id)
    ).first()
    if a_un_score is None:
        raise ValidationError(
            "Le rapport validé de cette entreprise n'a aucun score calculé.",
            code="score_manquant",
        )

    entreprise.date_publication = utcnow()
    session.add(entreprise)
    if entreprise.utilisateur_id is not None:
        notifier(
            session,
            entreprise.utilisateur_id,
            "ENTREPRISE_PUBLIEE",
            "Votre entreprise est maintenant publiée sur la plateforme.",
        )
    session.commit()
    session.refresh(entreprise)
    logger.info("entreprise_publiee", entreprise_id=str(entreprise_id))
    return entreprise


def suspendre_entreprise(session: Session, entreprise_id: uuid.UUID) -> Entreprise:
    """Bloque tout nouveau dépôt de rapport (app/company/rapports.py::_creer_rapport) — les
    rapports déjà déposés et leur historique restent inchangés, seule l'entreprise passe
    inactive. Pas d'auditer() ici : JournalAudit reste scopé aux événements de compte/session
    (voir app/core/models.py::JournalAudit), jamais aux entreprises — même choix que
    publier_entreprise ci-dessus (structlog + Notification)."""
    entreprise = session.get(Entreprise, entreprise_id)
    if entreprise is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")

    entreprise.actif = False
    session.add(entreprise)
    if entreprise.utilisateur_id is not None:
        notifier(
            session,
            entreprise.utilisateur_id,
            "ENTREPRISE_SUSPENDUE",
            "Votre entreprise a été suspendue : aucun nouveau rapport ne peut être déposé.",
        )
    session.commit()
    session.refresh(entreprise)
    logger.info("entreprise_suspendue", entreprise_id=str(entreprise_id))
    return entreprise


def reactiver_entreprise(session: Session, entreprise_id: uuid.UUID) -> Entreprise:
    entreprise = session.get(Entreprise, entreprise_id)
    if entreprise is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")

    entreprise.actif = True
    session.add(entreprise)
    if entreprise.utilisateur_id is not None:
        notifier(
            session,
            entreprise.utilisateur_id,
            "ENTREPRISE_REACTIVEE",
            "Votre entreprise a été réactivée : le dépôt de rapports est de nouveau possible.",
        )
    session.commit()
    session.refresh(entreprise)
    logger.info("entreprise_reactivee", entreprise_id=str(entreprise_id))
    return entreprise
