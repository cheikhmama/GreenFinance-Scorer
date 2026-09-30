"""Activation de compte (tâche 4.5) : jetons à usage unique, un seul lien valide à la fois."""

import uuid

import pytest
import structlog
from fastapi import BackgroundTasks

from app.auth import activation
from app.auth.models import User
from app.core.email import EmailDeliveryError
from app.core.enums import Role
from app.core.exceptions import ValidationError

MOT_DE_PASSE = "un-mot-de-passe-solide"


def _compte(session) -> User:
    utilisateur = User(email=f"a-{uuid.uuid4()}@example.com", role=Role.INVESTOR)
    session.add(utilisateur)
    session.commit()
    return utilisateur


def _emettre(session, utilisateur: User) -> str:
    """Émet un lien et renvoie le jeton en clair, tel que la tâche d'envoi le recevrait."""
    taches = BackgroundTasks()
    activation.envoyer_lien_activation(session, utilisateur, taches)
    session.commit()
    [tache] = taches.tasks
    _email, jeton = tache.args
    assert isinstance(jeton, str)
    return jeton


def test_un_nouveau_lien_invalide_le_precedent(session) -> None:
    utilisateur = _compte(session)
    premier = _emettre(session, utilisateur)
    second = _emettre(session, utilisateur)

    with pytest.raises(ValidationError) as ancien:
        activation.activer_compte(session, premier, MOT_DE_PASSE)
    active = activation.activer_compte(session, second, MOT_DE_PASSE)

    assert ancien.value.code == "jeton_invalide"
    assert active.activated_at is not None and active.password_hash is not None


def test_lien_a_usage_unique(session) -> None:
    jeton = _emettre(session, _compte(session))
    activation.activer_compte(session, jeton, MOT_DE_PASSE)

    with pytest.raises(ValidationError) as rejoue:
        activation.activer_compte(session, jeton, MOT_DE_PASSE)

    assert rejoue.value.code == "jeton_invalide"


def test_compte_desactive_entre_temps_jamais_active(session) -> None:
    utilisateur = _compte(session)
    jeton = _emettre(session, utilisateur)
    utilisateur.active = False
    session.add(utilisateur)
    session.commit()

    with pytest.raises(ValidationError) as refus:
        activation.activer_compte(session, jeton, MOT_DE_PASSE)

    assert refus.value.code == "jeton_invalide"
    session.refresh(utilisateur)
    assert utilisateur.activated_at is None


def test_echec_d_envoi_journalise_sans_fuite(monkeypatch) -> None:
    def _panne(**_kwargs) -> None:
        raise EmailDeliveryError("File d'envoi indisponible.") from ConnectionError("redis")

    monkeypatch.setattr(activation, "envoyer_email_differe", _panne)

    with structlog.testing.capture_logs() as journaux:
        activation._envoyer_lien("secret@example.com", "jeton-secret")  # ne lève pas

    assert journaux == [
        {"event": "activation_delivery_failed", "error_type": "ConnectionError", "log_level": "error"}
    ]
    assert "jeton-secret" not in str(journaux) and "secret@example.com" not in str(journaux)
