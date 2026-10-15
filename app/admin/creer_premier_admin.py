"""Création du premier compte Administrateur d'un déploiement.

creer_utilisateur (app/admin/utilisateurs.py) exige un Administrateur acteur et refuse le rôle
ADMIN : une base de production vierge n'aurait donc aucun moyen d'obtenir son premier compte, et
scripts/ (seed_demo.py) n'est pas copié dans l'image. Cette commande est livrée dans app/, donc
dans l'image :

    docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api \\
        python -m app.admin.creer_premier_admin admin@domaine.tld "Prénom Nom"

Elle refuse dès qu'un Administrateur existe (les suivants se créent depuis l'interface) et lit le
mot de passe au clavier — jamais en argument, qui resterait dans l'historique du shell.
"""

import getpass
import sys

from sqlmodel import Session, col, select

from app.auth.hashing import hash_password
from app.auth.models import Role, User
from app.core.audit import auditer
from app.core.database import engine, utcnow

LONGUEUR_MIN_MOT_DE_PASSE = 12  # même minimum que app/auth/schemas.py


class RefusCreation(Exception):
    """Motif de refus affiché tel quel à l'opérateur."""


def administrateur_existe(session: Session) -> bool:
    return (
        session.exec(select(User.id).where(col(User.role) == Role.ADMIN)).first()
        is not None
    )


def creer_premier_admin(
    session: Session, email: str, nom: str, mot_de_passe: str
) -> User:
    """Ajoute le compte à la session, déjà activé — ne commit jamais (l'appelant décide)."""
    email = email.strip().lower()
    if "@" not in email:
        raise RefusCreation("Adresse e-mail invalide.")
    if len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
        raise RefusCreation(
            f"Le mot de passe doit contenir au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères."
        )
    if administrateur_existe(session):
        raise RefusCreation(
            "Un Administrateur existe déjà : créez les comptes suivants depuis l'interface."
        )
    if session.exec(select(User.id).where(User.email == email)).first() is not None:
        raise RefusCreation("Un compte existe déjà avec cet e-mail.")

    maintenant = utcnow()
    utilisateur = User(
        email=email,
        name=nom.strip() or email.split("@")[0],
        password_hash=hash_password(mot_de_passe),
        role=Role.ADMIN,
        active=True,
        activated_at=maintenant,
    )
    session.add(utilisateur)
    session.flush()
    # Même action que creer_utilisateur ; acteur absent : la commande s'exécute hors session.
    auditer(
        session,
        None,
        "account_created",
        "User",
        utilisateur.id,
        "success",
        new_value=Role.ADMIN.value,
    )
    return utilisateur


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    email, nom = arguments
    mot_de_passe = getpass.getpass(
        f"Mot de passe ({LONGUEUR_MIN_MOT_DE_PASSE} caractères min.) : "
    )
    if mot_de_passe != getpass.getpass("Confirmation : "):
        print("La confirmation ne correspond pas.", file=sys.stderr)
        return 1
    with Session(engine) as session:
        try:
            creer_premier_admin(session, email, nom, mot_de_passe)
        except RefusCreation as refus:
            print(refus, file=sys.stderr)
            return 1
        session.commit()
    print("Administrateur créé : connectez-vous avec cet e-mail.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
