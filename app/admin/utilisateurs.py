"""Gestion des comptes utilisateurs par l'Administrateur — consultation, création, désactivation
et changement de rôle (Phase 3 §3.3).

Sert aussi de brique de sélection pour les relations acteur-à-acteur du système (ex. affectation
d'un rapport à un auditeur, app/audit/assignment.py) : un acteur choisit toujours un compte déjà
enregistré et correspondant au rôle recherché, jamais une identité saisie librement.
"""

import secrets
import uuid

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, or_, select

from app.auth.hashing import hash_password
from app.auth.models import Utilisateur
from app.auth.revocation import revoke_all_sessions
from app.company.models import Entreprise
from app.core.audit import auditer
from app.core.enums import Role
from app.core.exceptions import NotFoundError, ValidationError


def lister_utilisateurs_par_role(
    session: Session,
    role: Role,
    *,
    recherche: str | None = None,
    inclure_inactifs: bool = False,
    doit_changer_mot_de_passe: bool | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[Utilisateur], int]:
    """Page de comptes d'un rôle donné, filtrée par e-mail OU nom si `recherche` est fourni —
    seuls les comptes actifs par défaut, tous si `inclure_inactifs` (nécessaire pour retrouver un
    compte à réactiver, sinon invisible dès qu'il est désactivé). `doit_changer_mot_de_passe`
    retrouve les comptes provisionnés dont le mot de passe temporaire n'a pas encore été changé
    (tuile "en attente" du tableau de bord, app/admin/dashboard.py, qui calcule son compteur tous
    rôles confondus — ce filtre reste scopé à un rôle, comme le reste de cette liste).

    Pagination par offset/limit — le total ne descend jamais à la base entière : seule la page
    demandée est chargée (voir app/core/schemas.py::Page, posé pour ce cas précisément)."""
    filtres: list[ColumnElement[bool]] = [col(Utilisateur.role) == role]
    if not inclure_inactifs:
        filtres.append(col(Utilisateur.actif).is_(True))
    if doit_changer_mot_de_passe is not None:
        filtres.append(col(Utilisateur.doit_changer_mot_de_passe).is_(doit_changer_mot_de_passe))
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
) -> tuple[Utilisateur, str]:
    """Provisionne un compte avec un mot de passe temporaire à usage unique — aucune
    infrastructure d'e-mail : le mot de passe est renvoyé une seule fois dans la réponse HTTP
    (app/admin/schemas.py::UtilisateurCree), à relayer manuellement. doit_changer_mot_de_passe
    force le changement dès la première connexion (voir app/core/dependencies.py).

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

    existant = session.exec(select(Utilisateur).where(Utilisateur.email == email)).first()
    if existant is not None:
        raise ValidationError("Un compte existe déjà avec cet e-mail.", code="email_deja_utilise")

    mot_de_passe_temporaire = secrets.token_urlsafe(12)
    utilisateur = Utilisateur(
        email=email,
        nom=nom or email.split("@")[0],
        mot_de_passe_hache=hash_password(mot_de_passe_temporaire),
        role=role,
        actif=True,
        doit_changer_mot_de_passe=True,
    )
    session.add(utilisateur)
    session.flush()  # attribue utilisateur.id avant de construire l'entrée d'audit / l'entreprise

    if role == Role.ENTREPRISE:
        assert nom_entreprise is not None and secteur is not None and pays is not None  # validé ci-dessus
        entreprise = Entreprise(
            nom=nom_entreprise, secteur=secteur, pays=pays, utilisateur_id=utilisateur.id
        )
        session.add(entreprise)

    auditer(session, acteur_id, "creation_compte", "Utilisateur", utilisateur.id, "succes")
    session.commit()
    session.refresh(utilisateur)
    return utilisateur, mot_de_passe_temporaire


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


def changer_role(session: Session, acteur_id: uuid.UUID, cible_id: uuid.UUID, nouveau_role: Role) -> Utilisateur:
    if nouveau_role == Role.ADMINISTRATEUR:
        raise ValidationError(
            "Ce formulaire ne permet pas d'attribuer le rôle Administrateur.",
            code="role_non_autorise",
        )

    utilisateur = session.get(Utilisateur, cible_id)
    if utilisateur is None:
        raise NotFoundError("Utilisateur introuvable.", code="utilisateur_introuvable")

    ancien_role = utilisateur.role
    utilisateur.role = nouveau_role
    session.add(utilisateur)
    auditer(
        session,
        acteur_id,
        "changement_role",
        "Utilisateur",
        cible_id,
        "succes",
        ancienne_valeur=ancien_role.value,
        nouvelle_valeur=nouveau_role.value,
    )
    session.commit()
    session.refresh(utilisateur)

    # Un jeton déjà émis porte l'ancien rôle (claim "role", app/auth/tokens.py) : le laisser
    # valide laisserait agir sous une autorisation périmée jusqu'à expiration naturelle.
    revoke_all_sessions(cible_id)
    return utilisateur
