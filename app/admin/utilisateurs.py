"""Gestion des comptes utilisateurs par l'Administrateur — consultation, création,
désactivation/réactivation (Phase 3 §3.3). Le rôle d'un compte se fixe à sa création et n'est
plus jamais modifié après coup (chaque rôle porte son propre espace et ses propres permissions).

Sert aussi de brique de sélection pour les relations acteur-à-acteur du système (ex. affectation
d'un rapport à un auditeur, app/audit/assignment.py) : un acteur choisit toujours un compte déjà
enregistré et correspondant au rôle recherché, jamais une identité saisie librement.
"""

import uuid

from fastapi import BackgroundTasks
from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, or_, select

from app.auth.activation import envoyer_lien_activation
from app.auth.models import InstitutionProfil, Utilisateur
from app.auth.revocation import revoke_all_sessions
from app.company.models import Entreprise
from app.core.audit import auditer
from app.core.email import EmailDeliveryError, ensure_email_configured
from app.core.enums import Role
from app.core.exceptions import NotFoundError, ServiceUnavailableError, ValidationError

# Quota de départ pour un compte Institution (Étape 17 §quota d'export) — pas encore un champ du
# formulaire de création (aucune institution réelle n'a encore exprimé un besoin différencié),
# ajusté directement en base par l'Administrateur si un besoin réel apparaît.
_QUOTA_EXPORT_INITIAL = 10


def lister_utilisateurs_par_role(
    session: Session,
    role: Role,
    *,
    recherche: str | None = None,
    inclure_inactifs: bool = False,
    en_attente_activation: bool | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[Utilisateur], int]:
    """Page de comptes d'un rôle donné, filtrée par e-mail OU nom si `recherche` est fourni —
    seuls les comptes actifs par défaut, tous si `inclure_inactifs` (nécessaire pour retrouver un
    compte à réactiver, sinon invisible dès qu'il est désactivé). `en_attente_activation`
    retrouve les comptes provisionnés qui n'ont pas encore cliqué leur lien d'activation (tuile
    "en attente" du tableau de bord, app/admin/dashboard.py, qui calcule son compteur tous rôles
    confondus — ce filtre reste scopé à un rôle, comme le reste de cette liste).

    Pagination par offset/limit — le total ne descend jamais à la base entière : seule la page
    demandée est chargée (voir app/core/schemas.py::Page, posé pour ce cas précisément)."""
    filtres: list[ColumnElement[bool]] = [col(Utilisateur.role) == role]
    if not inclure_inactifs:
        filtres.append(col(Utilisateur.actif).is_(True))
    if en_attente_activation is not None:
        if en_attente_activation:
            filtres.append(col(Utilisateur.date_activation).is_(None))
        else:
            filtres.append(col(Utilisateur.date_activation).is_not(None))
    if recherche:
        motif = f"%{recherche}%"
        filtres.append(or_(col(Utilisateur.email).ilike(motif), col(Utilisateur.nom).ilike(motif)))

    total = session.exec(select(func.count()).select_from(Utilisateur).where(*filtres)).one()
    items = list(
        session.exec(
            select(Utilisateur)
            .where(*filtres)
            .order_by(col(Utilisateur.email))
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def lister_utilisateurs_en_attente(session: Session) -> list[Utilisateur]:
    """Comptes actifs, tous rôles confondus, qui n'ont pas encore cliqué leur lien d'activation —
    extrait de construire_tableau_de_bord (app/admin/dashboard.py), qui jusqu'ici ne faisait que
    les compter (utilisateurs_en_attente). lister_utilisateurs_par_role exige un rôle unique ;
    cette vue transverse sert le raccourci "Utilisateurs en attente" du tableau de bord, qui
    n'est scopé à aucun rôle précis."""
    return list(
        session.exec(
            select(Utilisateur).where(
                col(Utilisateur.date_activation).is_(None),
                col(Utilisateur.actif).is_(True),
            )
        ).all()
    )


def creer_utilisateur(
    session: Session,
    acteur_id: uuid.UUID,
    email: str,
    nom: str | None,
    role: Role,
    *,
    nom_entreprise: str | None = None,
    secteur: str | None = None,
    pays: str | None = None,
) -> Utilisateur:
    """Provisionne un compte sans mot de passe — aucun secret généré ni transmis par
    l'Administrateur : le compte reste sans mot de passe (mot_de_passe_hache=None,
    date_activation=None) jusqu'à ce que la personne titulaire clique le lien d'activation reçu
    par e-mail (app/auth/activation.py::envoyer_lien_activation, appelée par le routeur juste
    après ce retour). Échoue avant toute écriture si le SMTP n'est pas configuré — créer un compte
    qu'il devient ensuite impossible d'activer serait pire qu'un refus immédiat.

    nom est le nom de la personne/institution titulaire du compte. L'Administrateur ne le saisit
    pas systématiquement (formulaire de création simplifié) — quand absent, déduit de la partie
    locale de l'e-mail, à défaut de mieux : compromis choisi sciemment, pas un oubli. Pour
    role == ENTREPRISE, crée aussi le profil Entreprise (nom_entreprise/secteur/pays) rattaché —
    distinct de nom (le compte et l'entreprise peuvent porter des noms différents, ex. un contact
    nommé pour un compte Entreprise) — sans ce profil, le compte ne peut rien déposer
    (app/company/router.py::_entreprise_id exige current_user.entreprise). nom_entreprise/
    secteur/pays sont ignorés pour tout autre rôle."""
    if role == Role.ADMINISTRATEUR:
        raise ValidationError(
            "La création d'un compte Administrateur n'est pas permise par ce formulaire.",
            code="role_non_autorise",
        )

    if role == Role.ENTREPRISE:
        champs_manquants = {
            champ: "Ce champ est requis pour créer une Entreprise."
            for champ, valeur in {
                "nom_entreprise": nom_entreprise,
                "secteur": secteur,
                "pays": pays,
            }.items()
            if not valeur
        }
        if champs_manquants:
            raise ValidationError(
                "Le profil de l'entreprise (nom, secteur, pays) est requis.",
                code="profil_entreprise_requis",
                fields=champs_manquants,
            )

    try:
        ensure_email_configured()
    except EmailDeliveryError as exc:
        raise ServiceUnavailableError(
            "Service d'activation de compte temporairement indisponible. Réessayez plus tard."
        ) from exc

    existant = session.exec(select(Utilisateur).where(Utilisateur.email == email)).first()
    if existant is not None:
        raise ValidationError("Un compte existe déjà avec cet e-mail.", code="email_deja_utilise")

    utilisateur = Utilisateur(
        email=email,
        nom=nom or email.split("@")[0],
        mot_de_passe_hache=None,
        role=role,
        actif=True,
        date_activation=None,
    )
    session.add(utilisateur)
    session.flush()  # attribue utilisateur.id avant de construire l'entrée d'audit / l'entreprise

    if role == Role.ENTREPRISE:
        assert nom_entreprise is not None and secteur is not None and pays is not None  # validé ci-dessus
        entreprise = Entreprise(
            nom=nom_entreprise, secteur=secteur, pays=pays, utilisateur_id=utilisateur.id
        )
        session.add(entreprise)
    elif role == Role.INSTITUTION:
        # Sans ce profil, aucun export n'est possible (app/institution/analyses.py exige un
        # InstitutionProfil pour décrémenter quota_export) — même raisonnement que le profil
        # Entreprise ci-dessus : créé dans le même geste, jamais après coup.
        session.add(InstitutionProfil(utilisateur_id=utilisateur.id, quota_export=_QUOTA_EXPORT_INITIAL))

    auditer(session, acteur_id, "creation_compte", "Utilisateur", utilisateur.id, "succes")
    session.commit()
    session.refresh(utilisateur)
    return utilisateur


def renvoyer_lien_activation(
    session: Session, acteur_id: uuid.UUID, cible_id: uuid.UUID, background_tasks: BackgroundTasks
) -> None:
    """Régénère et renvoie un lien d'activation — filet de secours pour un lien expiré ou un
    e-mail non reçu : sans cette action, un tel compte resterait bloqué indéfiniment (le flux
    « mot de passe oublié », app/auth/password_reset.py, ne fonctionne que pour un compte qui a
    déjà un mot de passe, donc jamais pour un compte encore en attente d'activation)."""
    utilisateur = session.get(Utilisateur, cible_id)
    if utilisateur is None:
        raise NotFoundError("Utilisateur introuvable.", code="utilisateur_introuvable")
    if utilisateur.date_activation is not None:
        raise ValidationError("Ce compte est déjà activé.", code="compte_deja_active")

    envoyer_lien_activation(session, utilisateur, background_tasks)
    auditer(session, acteur_id, "renvoi_lien_activation", "Utilisateur", utilisateur.id, "succes")
    session.commit()


def desactiver_utilisateur(session: Session, acteur_id: uuid.UUID, cible_id: uuid.UUID) -> Utilisateur:
    utilisateur = session.get(Utilisateur, cible_id)
    if utilisateur is None:
        raise NotFoundError("Utilisateur introuvable.", code="utilisateur_introuvable")

    utilisateur.actif = False
    session.add(utilisateur)
    auditer(
        session,
        acteur_id,
        "desactivation_compte",
        "Utilisateur",
        cible_id,
        "succes",
        ancienne_valeur="actif",
        nouvelle_valeur="inactif",
    )
    session.commit()
    session.refresh(utilisateur)

    # Un compte désactivé ne doit conserver aucune session déjà ouverte.
    revoke_all_sessions(cible_id)
    return utilisateur


def reactiver_utilisateur(session: Session, acteur_id: uuid.UUID, cible_id: uuid.UUID) -> Utilisateur:
    utilisateur = session.get(Utilisateur, cible_id)
    if utilisateur is None:
        raise NotFoundError("Utilisateur introuvable.", code="utilisateur_introuvable")

    utilisateur.actif = True
    session.add(utilisateur)
    auditer(
        session,
        acteur_id,
        "reactivation_compte",
        "Utilisateur",
        cible_id,
        "succes",
        ancienne_valeur="inactif",
        nouvelle_valeur="actif",
    )
    session.commit()
    session.refresh(utilisateur)
    return utilisateur
