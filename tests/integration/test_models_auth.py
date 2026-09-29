import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.models import ChercheurInstitution, InstitutionProfil, User
from app.core.enums import Role


def _utilisateur(role: Role, email: str | None = None) -> User:
    return User(
        email=email or f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        password_hash="hash",
        role=role,
    )


@pytest.mark.parametrize("role", list(Role))
def test_creation_utilisateur_par_role(session, role: Role) -> None:
    utilisateur = _utilisateur(role)
    session.add(utilisateur)
    session.flush()

    assert utilisateur.id is not None
    assert utilisateur.active is True


def test_rattachement_chercheur_institution(session) -> None:
    chercheur = _utilisateur(Role.RESEARCHER)
    institution = _utilisateur(Role.INSTITUTION)
    session.add(chercheur)
    session.add(institution)
    session.flush()

    profil = InstitutionProfil(utilisateur_id=institution.id, quota_export=10)
    session.add(profil)
    session.flush()

    rattachement = ChercheurInstitution(
        chercheur_id=chercheur.id, institution_id=institution.id
    )
    session.add(rattachement)
    session.flush()

    assert rattachement.id is not None
    assert profil.utilisateur_id == institution.id


def test_email_unique_constraint(session) -> None:
    email = f"unique-{uuid.uuid4()}@example.com"
    session.add(_utilisateur(Role.ENTERPRISE, email=email))
    session.flush()

    session.add(_utilisateur(Role.ENTERPRISE, email=email))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
