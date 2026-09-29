"""Cycle de vie des projets Institution (Étape 17).

Un projet ne peut affecter qu'un Chercheur déjà ACCEPTE (voir app/auth/models.py::ChercheurInstitution)
— l'invitation et l'affectation restent deux gestes distincts, jamais fusionnés.
"""

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app.auth.models import ChercheurInstitution, Utilisateur
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import StatutAnalyse, StatutProjet, StatutRattachement
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier
from app.ingestion.models import ESGReport
from app.institution.models import (
    AffectationProjet,
    Projet,
    ProjetDocument,
    ProjetEntreprise,
)
from app.investor.entreprises import dernier_rapport_valide
from app.researcher.models import Analyse


def _verifier_coherence_dates(
    date_debut: datetime | None,
    date_fin_prevue: datetime | None,
    date_limite: datetime | None,
) -> None:
    if (
        date_debut is not None
        and date_fin_prevue is not None
        and date_debut > date_fin_prevue
    ):
        raise ValidationError(
            "La date de début doit précéder la date de fin prévue.",
            code="periode_incoherente",
        )
    if date_limite is not None and date_debut is not None and date_limite < date_debut:
        raise ValidationError(
            "La date limite ne peut pas précéder la date de début.",
            code="date_limite_incoherente",
        )


def creer_projet(
    session: Session,
    institution_id: uuid.UUID,
    nom: str,
    description: str | None,
    objectif: str | None = None,
    date_debut: datetime | None = None,
    date_fin_prevue: datetime | None = None,
    date_limite: datetime | None = None,
) -> Projet:
    _verifier_coherence_dates(date_debut, date_fin_prevue, date_limite)
    projet = Projet(
        institution_id=institution_id,
        nom=nom,
        description=description,
        objectif=objectif,
        date_debut=date_debut,
        date_fin_prevue=date_fin_prevue,
        date_limite=date_limite,
    )
    session.add(projet)
    session.commit()
    session.refresh(projet)
    return projet


def lister_mes_projets(session: Session, institution_id: uuid.UUID) -> list[Projet]:
    return list(
        session.exec(
            select(Projet).where(col(Projet.institution_id) == institution_id)
        ).all()
    )


def _projet_de_institution(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID
) -> Projet:
    projet = session.get(Projet, projet_id)
    if projet is None or projet.institution_id != institution_id:
        raise NotFoundError("Projet introuvable.", code="projet_introuvable")
    return projet


def consulter_projet(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID
) -> Projet:
    return _projet_de_institution(session, institution_id, projet_id)


def affecter_chercheur(
    session: Session,
    institution_id: uuid.UUID,
    projet_id: uuid.UUID,
    chercheur_id: uuid.UUID,
) -> AffectationProjet:
    projet = _projet_de_institution(session, institution_id, projet_id)
    if projet.statut != StatutProjet.OUVERT:
        raise ValidationError("Ce projet est clôturé.", code="projet_cloture")

    rattachement = session.exec(
        select(ChercheurInstitution).where(
            ChercheurInstitution.institution_id == institution_id,
            ChercheurInstitution.chercheur_id == chercheur_id,
        )
    ).first()
    if rattachement is None or rattachement.statut != StatutRattachement.ACCEPTE:
        raise ValidationError(
            "Ce chercheur n'a pas accepté de rattachement avec votre institution.",
            code="rattachement_requis",
        )

    deja_affecte = session.exec(
        select(AffectationProjet).where(
            AffectationProjet.projet_id == projet_id,
            AffectationProjet.chercheur_id == chercheur_id,
        )
    ).first()
    if deja_affecte is not None:
        raise ValidationError(
            "Ce chercheur est déjà affecté à ce projet.", code="deja_affecte"
        )

    affectation = AffectationProjet(projet_id=projet_id, chercheur_id=chercheur_id)
    session.add(affectation)
    notifier(
        session,
        chercheur_id,
        "PROJET_AFFECTATION",
        f"Vous avez été affecté au projet « {projet.nom} ».",
        id_ressource=projet.id,
    )
    session.commit()
    session.refresh(affectation)
    return affectation


def cloturer_projet(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID
) -> Projet:
    projet = _projet_de_institution(session, institution_id, projet_id)
    if projet.statut == StatutProjet.CLOTURE:
        raise ValidationError("Ce projet est déjà clôturé.", code="projet_deja_cloture")
    projet.statut = StatutProjet.CLOTURE
    projet.date_cloture = utcnow()
    session.add(projet)
    session.commit()
    session.refresh(projet)
    return projet


def lister_perimetre(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID
) -> list[ProjetEntreprise]:
    _projet_de_institution(session, institution_id, projet_id)
    return list(
        session.exec(
            select(ProjetEntreprise).where(ProjetEntreprise.projet_id == projet_id)
        ).all()
    )


def entreprises_perimetre_institution(session: Session, institution_id: uuid.UUID) -> set[uuid.UUID]:
    """Union des périmètres de TOUS les projets de cette institution — restreint la fiche détail
    et le fichier de preuve d'une entreprise (app/institution/router.py) au même périmètre que
    celui qu'elle a elle-même construit pour ses projets (voir ajouter_entreprise_perimetre),
    conformément à la décision de gouvernance du 2026-09-02. Le catalogue de recherche
    (/institution/entreprises, liste) reste volontairement non filtré : l'Institution doit pouvoir
    parcourir les entreprises publiées pour choisir lesquelles ajouter à un périmètre."""
    projet_ids = select(Projet.id).where(Projet.institution_id == institution_id)
    return set(
        session.exec(
            select(ProjetEntreprise.entreprise_id).where(col(ProjetEntreprise.projet_id).in_(projet_ids))
        ).all()
    )


def ajouter_entreprise_perimetre(
    session: Session,
    institution_id: uuid.UUID,
    projet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
) -> ProjetEntreprise:
    """N'autorise dans le périmètre qu'une entreprise déjà publiée (Étape 17bis) — jamais une
    entreprise non publiée, dont les données brutes ne doivent jamais atteindre un Chercheur."""
    projet = _projet_de_institution(session, institution_id, projet_id)
    if projet.statut != StatutProjet.OUVERT:
        raise ValidationError("Ce projet est clôturé.", code="projet_cloture")

    entreprise = session.get(Company, entreprise_id)
    if entreprise is None or entreprise.published_at is None:
        raise ValidationError(
            "Cette entreprise n'est pas publiée.", code="entreprise_non_publiee"
        )

    deja_present = session.exec(
        select(ProjetEntreprise).where(
            ProjetEntreprise.projet_id == projet_id,
            ProjetEntreprise.entreprise_id == entreprise_id,
        )
    ).first()
    if deja_present is not None:
        raise ValidationError(
            "Cette entreprise fait déjà partie du périmètre du projet.",
            code="deja_dans_perimetre",
        )

    lien = ProjetEntreprise(projet_id=projet_id, entreprise_id=entreprise_id)
    session.add(lien)
    session.commit()
    session.refresh(lien)
    return lien


def lister_documents(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID
) -> list[ProjetDocument]:
    _projet_de_institution(session, institution_id, projet_id)
    return list(
        session.exec(
            select(ProjetDocument).where(ProjetDocument.projet_id == projet_id)
        ).all()
    )


def ajouter_document(
    session: Session,
    institution_id: uuid.UUID,
    projet_id: uuid.UUID,
    rapport_id: uuid.UUID,
) -> ProjetDocument:
    """N'accepte que le rapport actuellement publié de l'entreprise (Étape 17bis) — jamais
    seulement statut == VALIDATED : validation et publication restent deux gestes distincts (voir
    app/company/models.py::Company.published_at), et un ancien rapport VALIDATED remplacé
    depuis ne redevient jamais accessible ainsi. L'entreprise doit d'abord appartenir au périmètre
    du projet — mettre un document à disposition ne peut jamais élargir le périmètre en silence."""
    projet = _projet_de_institution(session, institution_id, projet_id)
    if projet.statut != StatutProjet.OUVERT:
        raise ValidationError("Ce projet est clôturé.", code="projet_cloture")

    rapport = session.get(ESGReport, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    dans_perimetre = session.exec(
        select(ProjetEntreprise).where(
            ProjetEntreprise.projet_id == projet_id,
            ProjetEntreprise.entreprise_id == rapport.company_id,
        )
    ).first()
    if dans_perimetre is None:
        raise ValidationError(
            "Cette entreprise ne fait pas partie du périmètre du projet.",
            code="entreprise_hors_perimetre",
        )

    rapport_public = dernier_rapport_valide(session, rapport.company_id)
    if rapport_public is None or rapport_public.id != rapport.id:
        raise ValidationError(
            "Seul le rapport actuellement publié de l'entreprise peut être mis à disposition.",
            code="rapport_non_publie",
        )

    deja_present = session.exec(
        select(ProjetDocument).where(
            ProjetDocument.projet_id == projet_id,
            ProjetDocument.rapport_id == rapport_id,
        )
    ).first()
    if deja_present is not None:
        raise ValidationError(
            "Ce document est déjà mis à disposition sur ce projet.", code="deja_ajoute"
        )

    document = ProjetDocument(projet_id=projet_id, rapport_id=rapport_id)
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def statistiques_admin(session: Session) -> tuple[int, int, int, int]:
    """(projets ouverts, projets clôturés, invitations en attente, analyses soumises à examiner)
    toutes Institutions confondues — synthèse pour l'Aperçu Administrateur (app/admin/apercu.py).
    institutions_actives (comptes) est déjà calculé ailleurs (voir app/admin/dashboard.py)."""
    projets_ouverts = session.exec(
        select(func.count()).select_from(Projet).where(col(Projet.statut) == StatutProjet.OUVERT)
    ).one()
    projets_clotures = session.exec(
        select(func.count()).select_from(Projet).where(col(Projet.statut) == StatutProjet.CLOTURE)
    ).one()
    invitations_en_attente = session.exec(
        select(func.count())
        .select_from(ChercheurInstitution)
        .where(col(ChercheurInstitution.statut) == StatutRattachement.EN_ATTENTE)
    ).one()
    analyses_a_examiner = session.exec(
        select(func.count()).select_from(Analyse).where(col(Analyse.statut) == StatutAnalyse.SOUMISE)
    ).one()
    return projets_ouverts, projets_clotures, invitations_en_attente, analyses_a_examiner


def lister_projets_admin(
    session: Session,
    *,
    statut: StatutProjet | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[tuple[Projet, str, int]], int]:
    """Vue de suivi Administrateur de tous les projets, avec filtre optionnel sur le statut — le
    détail derrière "Projets ouverts/clôturés" de l'Aperçu. Renvoie (Projet, e-mail de
    l'institution, nombre de chercheurs affectés) par ligne."""
    filtres: list[ColumnElement[bool]] = []
    if statut is not None:
        filtres.append(col(Projet.statut) == statut)

    total = session.exec(select(func.count()).select_from(Projet).where(*filtres)).one()
    projets = list(
        session.exec(
            select(Projet)
            .where(*filtres)
            .order_by(col(Projet.date_creation).desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )

    resultats: list[tuple[Projet, str, int]] = []
    for projet in projets:
        institution = session.get(Utilisateur, projet.institution_id)
        assert institution is not None  # FK NOT NULL, ne peut pas être absent
        nb_chercheurs = session.exec(
            select(func.count())
            .select_from(AffectationProjet)
            .where(col(AffectationProjet.projet_id) == projet.id)
        ).one()
        resultats.append((projet, institution.email, nb_chercheurs))
    return resultats, total
