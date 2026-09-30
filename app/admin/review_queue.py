"""File de revue des soumissions en attente de validation administrateur.

Logique de file d'attente, de décision (valider/rejeter/demander correction) et de publication.
L'affectation elle-même vit dans app/audit/assignment.py (Étape 11 possède l'attribution des
dossiers) — ce module l'invoque depuis le router plutôt que de la réimplémenter localement (voir
ARCHITECTURE.md §1).
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import ColumnElement
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.audit.models import AuditOpinion
from app.auth.avatar import construire_avatar_data_uri
from app.company.models import Company
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import CompanyStatus, Currency, ExtractionStatus, ReportStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier
from app.core.recherche import contient
from app.ingestion.models import ESGReport
from app.scoring.engine import calculer_score, score_officiel
from app.scoring.models import Score
from app.worker.queue import FileIndisponible, enfiler

logger = structlog.get_logger(__name__)


def lister_rapports_a_affecter(session: Session) -> list[ESGReport]:
    return list(
        session.exec(
            select(ESGReport)
            .where(
                ESGReport.status == ReportStatus.SUBMITTED,
                ESGReport.extraction_status == ExtractionStatus.DONE,
            )
            .order_by(col(ESGReport.extraction_finished_at))
        ).all()
    )


def lister_rapports_en_validation(session: Session) -> list[ESGReport]:
    return list(
        session.exec(
            select(ESGReport)
            .join(AuditOpinion, col(AuditOpinion.report_id) == ESGReport.id)
            .where(ESGReport.status == ReportStatus.PENDING_DECISION)
            .order_by(col(AuditOpinion.submitted_at))
        ).all()
    )


def lister_rapports_echec_extraction(session: Session) -> list[ESGReport]:
    """Rapports soumis dont l'extraction a échoué (ExtractionStatus.FAILED, cause classifiée dans
    extraction_error) — invisibles de lister_rapports_a_affecter, qui ne retient que DONE. Sans
    cette vue, un rapport déposé par une Entreprise reste bloqué en SUBMITTED indéfiniment,
    invisible de tout tableau de bord Admin."""
    return list(
        session.exec(
            select(ESGReport)
            .where(
                ESGReport.status == ReportStatus.SUBMITTED,
                ESGReport.extraction_status == ExtractionStatus.FAILED,
            )
            .order_by(col(ESGReport.submitted_at))
        ).all()
    )


def relancer_extraction(session: Session, rapport_id: uuid.UUID) -> ESGReport:
    """Autorise une nouvelle tentative d'extraction pour un rapport soumis en échec (cause classifiée,
    ou `delai_depasse` posé par la tâche planifiée) — jamais pour une extraction encore en cours ni
    pour un rapport déjà avancé dans le workflow. Le repassage à QUEUED DANS CETTE MÊME transaction est la
    garde de concurrence : un second appel simultané relit QUEUED et se fait rejeter par la
    vérification ci-dessous, sans verrou applicatif supplémentaire — même principe que les autres
    gardes d'état de ce fichier. Le dépôt du job d'extraction, après le commit, reste du
    ressort de la route (app/admin/router.py)."""
    rapport = session.get(ESGReport, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    if rapport.status != ReportStatus.SUBMITTED:
        raise ValidationError(
            "Seul un rapport en cours d'extraction peut être relancé.", code="transition_invalide"
        )

    if rapport.extraction_status != ExtractionStatus.FAILED:
        # Une extraction interrompue n'a plus à être repérée ici : la tâche planifiée du worker la
        # passe FAILED (`delai_depasse`, app/ingestion/supervision.py) — tâche 4.1.
        raise ValidationError(
            "Ce rapport n'est pas en échec d'extraction : rien à relancer.", code="relance_impossible"
        )
    if rapport.fiscal_year is None:
        # Rapport antérieur à l'introduction de cette colonne (nullable, voir app/ingestion/
        # models.py) — run_extraction_pipeline exige un int, jamais None. Cas résiduel de données
        # historiques, pas un chemin normal : pas de correctif automatique, juste un refus clair.
        raise ValidationError(
            "Ce rapport n'a pas d'année de reporting renseignée : relance impossible.",
            code="annee_reporting_manquante",
        )

    rapport.extraction_error = None
    rapport.extraction_status = ExtractionStatus.QUEUED
    session.add(rapport)
    session.commit()
    session.refresh(rapport)
    logger.info("extraction_relancee", rapport_id=str(rapport_id))
    return rapport


def lister_rapports_orphelins_en_validation(session: Session) -> list[ESGReport]:
    """Rapports PENDING_DECISION sans aucun avis d'audit associé — invisibles à la fois de
    lister_rapports_en_validation (INNER JOIN sur AuditOpinion) et de lister_rapports_a_affecter
    (mauvais statut) : un état orphelin permanent, sans file où l'Admin pourrait même le
    remarquer. Voir _rapport_en_validation ci-dessous, qui documente pourquoi cet état est
    aujourd'hui inatteignable via l'API seule (soumettre_avis crée toujours l'avis dans la même
    transaction que la transition PENDING_DECISION) — gardé en visibilité de défense, au cas où des
    données injectées hors parcours applicatif (ou un futur chemin de code) l'atteindraient."""
    sous_requete_avec_avis = select(AuditOpinion.report_id)
    return list(
        session.exec(
            select(ESGReport).where(
                ESGReport.status == ReportStatus.PENDING_DECISION,
                col(ESGReport.id).not_in(sous_requete_avec_avis),
            )
        ).all()
    )


def lister_rapports_en_retard(session: Session) -> list[ESGReport]:
    """Rapports affectés à un auditeur depuis plus longtemps que le délai attendu
    (settings.sla_audit_jours) sans qu'aucune décision n'ait encore été prise — extrait de
    construire_tableau_de_bord (app/admin/dashboard.py), qui jusqu'ici ne faisait que les compter
    (audits_en_retard) sans jamais les lister nommément."""
    seuil_retard = utcnow() - timedelta(days=get_settings().sla_audit_jours)
    return list(
        session.exec(
            select(ESGReport)
            .where(
                ESGReport.status == ReportStatus.PENDING_AUDIT,
                col(ESGReport.assigned_at).is_not(None),
                col(ESGReport.assigned_at) < seuil_retard,
            )
            .order_by(col(ESGReport.assigned_at))
        ).all()
    )


def lister_tous_les_rapports(
    session: Session,
    *,
    statut: ReportStatus | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[ESGReport], int]:
    """Vue globale de tous les rapports, tous statuts confondus, avec filtre optionnel sur le
    statut — contrairement aux files ci-dessus (chacune scopée à une étape précise du workflow),
    sert le suivi transverse depuis le tableau de bord (ex. "rapports validés", "rapports
    rejetés"), pour lequel aucune liste nommée n'existait jusqu'ici, seulement un compteur."""
    filtres: list[ColumnElement[bool]] = []
    if statut is not None:
        filtres.append(col(ESGReport.status) == statut)

    total = session.exec(select(func.count()).select_from(ESGReport).where(*filtres)).one()
    items = list(
        session.exec(
            select(ESGReport)
            .where(*filtres)
            .order_by(col(ESGReport.created_at).desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def lister_entreprises_a_republier(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[Company], int]:
    """Entreprises déjà publiées dont un rapport a été validé APRÈS la date de publication : la
    fiche publique ne reflète plus le dernier état validé — extrait de construire_tableau_de_bord,
    qui jusqu'ici ne faisait que les compter (demandes_republication) sans jamais les lister
    nommément."""
    republication_existe = (
        select(ESGReport.id)
        .where(
            col(ESGReport.company_id) == Company.id,
            col(ESGReport.status) == ReportStatus.VALIDATED,
            col(ESGReport.submitted_at) > Company.published_at,
        )
        .exists()
    )
    filtres: list[ColumnElement[bool]] = [
        col(Company.published_at).is_not(None),
        republication_existe,
    ]

    total = session.exec(select(func.count()).select_from(Company).where(*filtres)).one()
    items = list(
        session.exec(
            select(Company)
            .where(*filtres)
            .order_by(col(Company.name))
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def lister_avis(session: Session, rapport_id: uuid.UUID) -> list[AuditOpinion]:
    rapport = session.get(ESGReport, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    return list(session.exec(select(AuditOpinion).where(AuditOpinion.report_id == rapport_id)).all())


def lister_versions(session: Session, rapport_id: uuid.UUID) -> list[ESGReport]:
    """Reconstruit la chaîne de versions d'un rapport (originale + corrections), dans l'ordre
    chronologique — pas de Relationship() auto-référentielle pour rapport_precedent_id (choix
    déjà fait, voir app/ingestion/models.py), donc parcours explicite : remonter jusqu'à
    l'original, puis redescendre en cherchant à chaque étape la version qui la remplace."""
    rapport = session.get(ESGReport, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    original = rapport
    while original.previous_report_id is not None:
        precedent = session.get(ESGReport, original.previous_report_id)
        if precedent is None:
            break
        original = precedent

    chaine = [original]
    courant = original
    while True:
        suivant = session.exec(
            select(ESGReport).where(ESGReport.previous_report_id == courant.id)
        ).first()
        if suivant is None:
            break
        chaine.append(suivant)
        courant = suivant
    return chaine


def _rapport_en_validation(session: Session, rapport_id: uuid.UUID) -> ESGReport:
    """Charge le rapport VERROUILLÉ (SELECT ... FOR UPDATE) jusqu'à la fin de la transaction de
    décision : deux décisions concurrentes sur le même rapport (double clic, deux
    Administrateurs) se sérialisent, et la seconde relit un statut qui n'est plus
    PENDING_DECISION — jamais deux transitions ni deux scores (tâche 1.6)."""
    rapport = session.get(ESGReport, rapport_id, with_for_update=True)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    if rapport.status != ReportStatus.PENDING_DECISION:
        raise ValidationError(
            "Ce rapport n'est pas en attente de décision.", code="transition_invalide"
        )
    # Inatteignable via l'API seule aujourd'hui (soumettre_avis est ce qui fait passer un rapport
    # en PENDING_DECISION, et crée toujours l'avis dans la même transaction) — gardé en défense, et
    # testable en semant l'état directement en base.
    a_un_avis = session.exec(
        select(AuditOpinion.id).where(AuditOpinion.report_id == rapport_id)
    ).first()
    if a_un_avis is None:
        raise ValidationError(
            "Aucun avis d'audit n'a été soumis pour ce rapport.", code="avis_manquant"
        )
    return rapport


def _decider(
    session: Session,
    rapport_id: uuid.UUID,
    statut: ReportStatus,
    type_notification: str,
    message: str,
) -> ESGReport:
    rapport = _rapport_en_validation(session, rapport_id)
    rapport.status = statut
    session.add(rapport)
    if rapport.company.owner_user_id is not None:
        notifier(
            session,
            rapport.company.owner_user_id,
            type_notification,
            f"{rapport.type.value} ({rapport.fiscal_year}) : {message}",
            id_ressource=rapport_id,
        )
    session.commit()
    session.refresh(rapport)
    logger.info("rapport_decision", rapport_id=str(rapport_id), statut=statut.value)
    return rapport


def valider_rapport(session: Session, rapport_id: uuid.UUID, commentaire: str | None) -> ESGReport:
    """Distinct de rejeter_rapport/demander_correction (restés sur _decider) : valider est la
    seule décision qui produit aussi un score (Phase 5 §9).

    Transaction atomique (tâche 1.6, docs/WORKFLOWS.md §1.3) : statut VALIDATED, Score,
    official_score et notification commitent ensemble, ou rien du tout. Un score incalculable
    (score_incalculable) annule donc toute la décision — jamais un rapport VALIDATED sans le score
    que le cahier des charges exige avant publication. Aucune étape de cette transaction ne
    commite de son côté (voir app/scoring/engine.py). Le PDF de synthèse, effet de bord hors
    base, n'est produit qu'APRÈS le commit, par le worker (job generate_synthesis_pdf, tâche 4.1)."""
    rapport = _rapport_en_validation(session, rapport_id)
    rapport.status = ReportStatus.VALIDATED
    session.add(rapport)
    calculer_score(session, rapport_id)

    if rapport.company.owner_user_id is not None:
        notifier(
            session,
            rapport.company.owner_user_id,
            "RAPPORT_VALIDE",
            f"{rapport.type.value} ({rapport.fiscal_year}) : "
            f"{commentaire or 'Votre rapport a été validé.'}",
            id_ressource=rapport_id,
        )
    session.commit()
    logger.info("rapport_decision", rapport_id=str(rapport_id), statut=ReportStatus.VALIDATED.value)

    try:
        enfiler("generate_synthesis_pdf", rapport_id)
    except FileIndisponible:
        # Best-effort, comme avant : la validation est déjà commitée, le PDF se régénère plus tard.
        logger.error("synthese_pdf_non_programmee", rapport_id=str(rapport_id))
    session.refresh(rapport)
    return rapport


def recalculer_score(session: Session, rapport_id: uuid.UUID) -> Score:
    """Action de récupération pour un rapport VALIDATED sans Score — état incohérent qui bloque
    sinon indéfiniment publier_entreprise (code score_manquant) sans aucun moyen de s'en sortir
    depuis l'UI. Inatteignable via le parcours normal (valider_rapport calcule toujours le score
    dans la même transaction que la transition VALIDATED), mais peut survenir sur des données
    historiques injectées hors parcours applicatif. Lève score_incalculable (ValidationError,
    propagée telle quelle par calculer_score) si le vocabulaire d'indicateurs du rapport ne
    recoupe toujours aucun indicateur de la configuration de référence — jamais un score fabriqué
    sans substance, même ici."""
    # Verrouillé comme une décision : deux recalculs concurrents ne créent jamais deux scores.
    rapport = session.get(ESGReport, rapport_id, with_for_update=True)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    if rapport.status != ReportStatus.VALIDATED:
        raise ValidationError(
            "Seul un rapport validé peut voir son score recalculé.", code="transition_invalide"
        )
    if score_officiel(session, rapport_id) is not None:
        raise ValidationError("Ce rapport a déjà un score calculé.", code="score_deja_calcule")
    score = calculer_score(session, rapport_id)
    session.commit()
    session.refresh(score)
    logger.info("score_recalcule", rapport_id=str(rapport_id))
    return score


def rejeter_rapport(session: Session, rapport_id: uuid.UUID, commentaire: str | None) -> ESGReport:
    return _decider(
        session,
        rapport_id,
        ReportStatus.REJECTED,
        "RAPPORT_REJETE",
        commentaire or "Votre rapport a été rejeté.",
    )


def demander_correction(
    session: Session, rapport_id: uuid.UUID, commentaire: str | None
) -> ESGReport:
    return _decider(
        session,
        rapport_id,
        ReportStatus.REVISION_REQUESTED,
        "RAPPORT_CORRECTION_DEMANDEE",
        commentaire or "Une correction est demandée sur votre rapport.",
    )


def lister_entreprises_publiables(
    session: Session,
    *,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[Company], int]:
    """Page d'entreprises publiables, filtrée par nom/secteur/pays si `recherche` est fourni —
    même principe de pagination par offset/limit que lister_utilisateurs_par_role."""
    entreprises_avec_rapport_valide = select(ESGReport.company_id).where(
        ESGReport.status == ReportStatus.VALIDATED
    )
    filtres: list[ColumnElement[bool]] = [
        col(Company.id).in_(entreprises_avec_rapport_valide),
        col(Company.published_at).is_(None),
    ]
    if recherche:
        filtres.append(contient(recherche, Company.name, Company.sector, Company.country))

    total = session.exec(select(func.count()).select_from(Company).where(*filtres)).one()
    items = list(
        session.exec(
            select(Company)
            .where(*filtres)
            .order_by(col(Company.name))
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
) -> tuple[list[tuple[Company, int, ReportStatus | None, uuid.UUID | None]], int]:
    """Page de TOUTES les entreprises (contrairement à lister_entreprises_publiables, sans filtre
    sur le statut de rapport ni la publication) — vue de suivi pour l'Administrateur, avec un
    résumé par entreprise : nombre de rapports déposés, statut et id du plus récent (None si aucun
    rapport, ex. une entreprise provisionnée sans compte rattaché). Même pagination par
    offset/limit que les autres listes Admin."""
    filtres: list[ColumnElement[bool]] = []
    if recherche:
        filtres.append(contient(recherche, Company.name, Company.sector, Company.country))

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

    ids = [entreprise.id for entreprise in entreprises]
    rapports = (
        list(
            session.exec(
                select(
                    ESGReport.company_id, ESGReport.id, ESGReport.status, ESGReport.created_at
                ).where(col(ESGReport.company_id).in_(ids))
            ).all()
        )
        if ids
        else []
    )

    nb_par_entreprise: dict[uuid.UUID, int] = {}
    dernier_par_entreprise: dict[uuid.UUID, tuple[datetime, uuid.UUID, ReportStatus]] = {}
    # created_at, jamais submitted_at : un brouillon (tâche 1.5) n'a pas encore de date de dépôt
    # mais reste le rapport le plus récent de l'entreprise.
    for entreprise_id, rapport_id, statut, date_depot in rapports:
        nb_par_entreprise[entreprise_id] = nb_par_entreprise.get(entreprise_id, 0) + 1
        plus_recent = dernier_par_entreprise.get(entreprise_id)
        if plus_recent is None or date_depot > plus_recent[0]:
            dernier_par_entreprise[entreprise_id] = (date_depot, rapport_id, ReportStatus(statut))

    resultats = [
        (
            entreprise,
            nb_par_entreprise.get(entreprise.id, 0),
            dernier_par_entreprise[entreprise.id][2] if entreprise.id in dernier_par_entreprise else None,
            dernier_par_entreprise[entreprise.id][1] if entreprise.id in dernier_par_entreprise else None,
        )
        for entreprise in entreprises
    ]
    return resultats, total


def publier_entreprise(session: Session, entreprise_id: uuid.UUID) -> Company:
    entreprise = session.get(Company, entreprise_id)
    if entreprise is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")

    rapport_valide_id = session.exec(
        select(ESGReport.id).where(
            ESGReport.company_id == entreprise_id,
            ESGReport.status == ReportStatus.VALIDATED,
        )
    ).first()
    if rapport_valide_id is None:
        raise ValidationError(
            "Cette entreprise n'a aucun rapport validé.", code="aucun_rapport_valide"
        )
    # Inatteignable via l'API seule aujourd'hui (valider_rapport calcule toujours un score dans
    # la même transaction que la transition VALIDATED) — gardé en défense, même principe que
    # _rapport_en_validation ci-dessus : jamais de publication sans preuve de score (cahier des
    # charges §9), quelle que soit la façon dont un rapport a pu atteindre VALIDATED.
    a_un_score = session.exec(
        select(Score.id).where(Score.report_id == rapport_valide_id)
    ).first()
    if a_un_score is None:
        raise ValidationError(
            "Le rapport validé de cette entreprise n'a aucun score calculé.",
            code="score_manquant",
        )

    entreprise.published_at = utcnow()
    session.add(entreprise)
    if entreprise.owner_user_id is not None:
        notifier(
            session,
            entreprise.owner_user_id,
            "ENTREPRISE_PUBLIEE",
            "Votre entreprise est maintenant publiée sur la plateforme.",
            id_ressource=entreprise_id,
        )
    session.commit()
    session.refresh(entreprise)
    logger.info("entreprise_publiee", entreprise_id=str(entreprise_id))
    return entreprise


def suspendre_entreprise(session: Session, entreprise_id: uuid.UUID) -> Company:
    """Bloque tout nouveau dépôt de rapport (app/company/rapports.py::_creer_rapport) — les
    rapports déjà déposés et leur historique restent inchangés, seule l'entreprise passe
    SUSPENDED. Pas d'auditer() ici : AuditLogEntry reste scopé aux événements de compte/session
    (voir app/core/models.py::AuditLogEntry), jamais aux entreprises — même choix que
    publier_entreprise ci-dessus (structlog + Notification)."""
    entreprise = session.get(Company, entreprise_id)
    if entreprise is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
    if entreprise.status != CompanyStatus.ACTIVE:
        raise ValidationError(
            "Seule une entreprise active peut être suspendue.", code="transition_invalide"
        )

    entreprise.status = CompanyStatus.SUSPENDED
    session.add(entreprise)
    if entreprise.owner_user_id is not None:
        notifier(
            session,
            entreprise.owner_user_id,
            "ENTREPRISE_SUSPENDUE",
            "Votre entreprise a été suspendue : aucun nouveau rapport ne peut être déposé.",
            id_ressource=entreprise_id,
        )
    session.commit()
    session.refresh(entreprise)
    logger.info("entreprise_suspendue", entreprise_id=str(entreprise_id))
    return entreprise


def reactiver_entreprise(session: Session, entreprise_id: uuid.UUID) -> Company:
    entreprise = session.get(Company, entreprise_id)
    if entreprise is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
    # Jamais depuis PENDING_ONBOARDING : réactiver n'est pas valider une inscription (tâche 1.4).
    if entreprise.status != CompanyStatus.SUSPENDED:
        raise ValidationError(
            "Seule une entreprise suspendue peut être réactivée.", code="transition_invalide"
        )

    entreprise.status = CompanyStatus.ACTIVE
    session.add(entreprise)
    if entreprise.owner_user_id is not None:
        notifier(
            session,
            entreprise.owner_user_id,
            "ENTREPRISE_REACTIVEE",
            "Votre entreprise a été réactivée : le dépôt de rapports est de nouveau possible.",
            id_ressource=entreprise_id,
        )
    session.commit()
    session.refresh(entreprise)
    logger.info("entreprise_reactivee", entreprise_id=str(entreprise_id))
    return entreprise


def consulter_entreprise_admin(session: Session, entreprise_id: uuid.UUID) -> Company:
    entreprise = session.get(Company, entreprise_id)
    if entreprise is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
    return entreprise


def resume_rapports_entreprise(
    session: Session, entreprise_id: uuid.UUID
) -> tuple[int, ReportStatus | None, uuid.UUID | None]:
    """Même résumé (nombre de rapports + statut et id du plus récent) que
    lister_toutes_les_entreprises, pour une seule entreprise — utilisé par les routes qui
    renvoient une EntrepriseAdmin après une action ponctuelle (détail, modification, logo), où
    une jointure batchée n'a pas de sens."""
    rapports = session.exec(
        select(ESGReport.id, ESGReport.status, ESGReport.created_at).where(
            ESGReport.company_id == entreprise_id
        )
    ).all()
    if not rapports:
        return 0, None, None
    dernier_id, dernier_statut, _ = max(rapports, key=lambda rapport: rapport[2])
    return len(rapports), ReportStatus(dernier_statut), dernier_id


def modifier_entreprise_admin(
    session: Session,
    entreprise_id: uuid.UUID,
    *,
    nom: str,
    secteur: str,
    pays: str,
    description: str | None,
    site_officiel: str | None,
    montant_minimum_investissement: Decimal | None,
    devise_montant_minimum: Currency | None,
) -> Company:
    """Remplace le profil complet d'une entreprise — jamais de logique métier dérivée ici,
    seulement l'affectation des champs fournis (voir ModifierEntrepriseAdminRequest pour la
    contrainte "ensemble ou aucun" sur le couple montant/devise). Le logo n'est délibérément pas
    de la partie, voir televerser_logo_entreprise/supprimer_logo_entreprise ci-dessous."""
    entreprise = consulter_entreprise_admin(session, entreprise_id)

    entreprise.name = nom
    entreprise.sector = secteur
    entreprise.country = pays
    entreprise.description = description
    entreprise.website = site_officiel
    entreprise.minimum_investment_amount = montant_minimum_investissement
    entreprise.minimum_investment_currency = devise_montant_minimum
    session.add(entreprise)
    session.commit()
    session.refresh(entreprise)
    logger.info("entreprise_modifiee", entreprise_id=str(entreprise_id))
    return entreprise


def televerser_logo_entreprise(session: Session, entreprise_id: uuid.UUID, contenu: bytes) -> Company:
    """Valide et encode le logo en data URI via app/auth/avatar.py::construire_avatar_data_uri
    (même validation par signature que les avatars) — la vérification par signature binaire
    réelle ne dépend d'aucune notion propre à un compte utilisateur, la réutiliser évite de
    dupliquer une règle de sécurité (frontière fichier non fiable) dans deux modules."""
    entreprise = consulter_entreprise_admin(session, entreprise_id)
    entreprise.logo = construire_avatar_data_uri(contenu)
    session.add(entreprise)
    session.commit()
    session.refresh(entreprise)
    logger.info("entreprise_logo_televerse", entreprise_id=str(entreprise_id))
    return entreprise


def supprimer_logo_entreprise(session: Session, entreprise_id: uuid.UUID) -> Company:
    entreprise = consulter_entreprise_admin(session, entreprise_id)
    entreprise.logo = None
    session.add(entreprise)
    session.commit()
    session.refresh(entreprise)
    logger.info("entreprise_logo_supprime", entreprise_id=str(entreprise_id))
    return entreprise


def modifier_identifiants(
    session: Session, entreprise_id: uuid.UUID, valeurs: dict[str, str | None]
) -> Company:
    """Met à jour ISIN / LEI / ticker (tâche 2.2) — `valeurs` ne contient que les champs fournis
    par l'appelant. L'unicité de l'ISIN et du LEI est portée par la base
    (companies_isin_key / companies_lei_key) : un conflit devient une 422 lisible, jamais une 500."""
    entreprise = consulter_entreprise_admin(session, entreprise_id)
    for champ, valeur in valeurs.items():
        setattr(entreprise, champ, valeur)
    session.add(entreprise)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValidationError(
            "Cet ISIN ou ce LEI est déjà attribué à une autre entreprise.",
            code="identifiant_deja_utilise",
        ) from exc
    session.refresh(entreprise)
    logger.info("entreprise_identifiants_modifies", entreprise_id=str(entreprise_id))
    return entreprise


def modifier_donnees_financieres(
    session: Session, entreprise_id: uuid.UUID, valeurs: dict[str, Any]
) -> Company:
    """Remplace chiffre d'affaires et EVIC (tâche 2.3) — `valeurs` porte tous les champs de
    app/admin/schemas.py::CompanyFinancialsRequest, un champ nul efface la donnée."""
    entreprise = consulter_entreprise_admin(session, entreprise_id)
    assert set(valeurs) <= set(Company.model_fields), set(valeurs) - set(Company.model_fields)
    for champ, valeur in valeurs.items():
        setattr(entreprise, champ, valeur)
    session.add(entreprise)
    session.commit()
    session.refresh(entreprise)
    logger.info("entreprise_donnees_financieres_modifiees", entreprise_id=str(entreprise_id))
    return entreprise

