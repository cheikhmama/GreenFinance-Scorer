"""Commande de création du premier Administrateur (app/admin/creer_premier_admin.py).

La base de test partagée contient déjà des Administrateurs créés par d'autres tests : la création
neutralise administrateur_existe, le refus en ajoute un explicitement. Rien n'est commit (la
fonction ne commit jamais ; la fixture session annule tout).
"""

import uuid

import pytest
from sqlmodel import select

from app.admin import creer_premier_admin as module
from app.auth.hashing import verify_password
from app.auth.models import Role, User
from app.core.models import AuditLogEntry


def _email() -> str:
    return f"premier-admin-{uuid.uuid4().hex[:8]}@exemple.org"


def test_cree_un_administrateur_active(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "administrateur_existe", lambda _session: False)
    email = _email()

    utilisateur = module.creer_premier_admin(
        session, f"  {email.upper()} ", "Admin Réel", "un-mot-de-passe-solide"
    )

    assert utilisateur.email == email
    assert utilisateur.role == Role.ADMIN
    assert utilisateur.active is True
    assert utilisateur.activated_at is not None
    assert utilisateur.password_hash is not None
    assert verify_password("un-mot-de-passe-solide", utilisateur.password_hash)
    entree = session.exec(
        select(AuditLogEntry).where(AuditLogEntry.resource_id == utilisateur.id)
    ).one()
    assert (entree.action, entree.actor_id) == ("account_created", None)


def test_refuse_quand_un_administrateur_existe(session) -> None:
    session.add(User(email=_email(), name="Déjà là", role=Role.ADMIN, active=True))
    session.flush()

    with pytest.raises(module.RefusCreation, match="existe déjà"):
        module.creer_premier_admin(
            session, _email(), "Second", "un-mot-de-passe-solide"
        )


def test_refuse_un_mot_de_passe_trop_court(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "administrateur_existe", lambda _session: False)

    with pytest.raises(module.RefusCreation, match="12 caractères"):
        module.creer_premier_admin(session, _email(), "Admin", "court")


def test_refuse_un_email_deja_utilise(session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "administrateur_existe", lambda _session: False)
    email = _email()
    session.add(User(email=email, name="Existant", role=Role.INVESTOR, active=True))
    session.flush()

    with pytest.raises(module.RefusCreation, match="e-mail"):
        module.creer_premier_admin(session, email, "Admin", "un-mot-de-passe-solide")


def test_main_affiche_l_usage_sans_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert module.main([]) == 2
    assert "creer_premier_admin" in capsys.readouterr().err
