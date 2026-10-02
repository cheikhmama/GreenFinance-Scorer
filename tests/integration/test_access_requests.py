"""Demandes d'accès Investisseur / Chercheur (tâche 5.10) : dépôt public, examen par
l'Administrateur, activation."""

import hashlib
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import col, select

from app.access_requests.models import AccessRequest
from app.auth.models import User
from app.core.enums import AccessRequestStatus, Role
from app.core.models import AuditLogEntry, Notification
from app.core.redis import get_redis_client
from app.main import app
from tests.integration.test_company_onboarding import _admin, _client_connecte

URL = "/api/v1/access-requests"


@pytest.fixture(autouse=True)
def _envoi_simule(monkeypatch) -> Mock:
    envoi = Mock()
    for module in ("app.access_requests.service", "app.auth.activation"):
        monkeypatch.setattr(f"{module}.envoyer_email_differe", envoi)
    monkeypatch.setattr("app.access_requests.service.ensure_email_configured", lambda: None)
    monkeypatch.setattr("app.company.registration.ensure_email_configured", lambda: None)
    return envoi


@pytest.fixture(autouse=True)
def _reinitialiser_limite():
    cle = f"access_requests:{hashlib.sha256(b'testclient').hexdigest()}"
    get_redis_client().delete(cle)
    yield
    get_redis_client().delete(cle)


def _public() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _investisseur(**surcharges) -> dict:
    return {
        "role": "INVESTOR",
        "full_name": "Claire Martin",
        "email": f"Claire-{uuid.uuid4()}@Fonds-Sahel.com",
        "organization": "Fonds Sahel Capital",
        "investor_type": "INVESTMENT_FUND",
        **surcharges,
    }


def _chercheur(**surcharges) -> dict:
    return {
        "role": "RESEARCHER",
        "full_name": "Moussa Diop",
        "email": f"moussa-{uuid.uuid4()}@univ-nkc.mr",
        "organization": "Université de Nouakchott",
        "research_domain": "CARBON_FOOTPRINT",
        **surcharges,
    }


def _demande_de(session, email: str) -> tuple[User, AccessRequest]:
    session.expire_all()
    utilisateur = session.exec(select(User).where(col(User.email) == email.lower())).one()
    acces = session.exec(
        select(AccessRequest).where(col(AccessRequest.user_id) == utilisateur.id)
    ).one()
    return utilisateur, acces


@pytest.mark.parametrize(
    ("corps", "role", "precision"),
    [
        (_investisseur, Role.INVESTOR, "investor_type"),
        (_chercheur, Role.RESEARCHER, "research_domain"),
    ],
)
def test_une_demande_cree_un_compte_sans_mot_de_passe_en_attente(
    session, _envoi_simule, corps, role, precision
) -> None:
    demande = corps()

    reponse = _public().post(URL, json=demande)

    assert reponse.status_code == 202
    utilisateur, acces = _demande_de(session, demande["email"])
    assert utilisateur.role == role
    assert utilisateur.password_hash is None
    assert utilisateur.name == demande["full_name"]
    assert acces.status == AccessRequestStatus.PENDING_APPROVAL
    assert acces.organization == demande["organization"]
    assert getattr(acces, precision) is not None
    # Accusé de réception envoyé ; impossible de se connecter avant l'activation.
    assert _envoi_simule.call_args.kwargs["recipient"] == demande["email"].lower()
    connexion = _public().post(
        "/api/v1/auth/login", json={"email": demande["email"], "password": "nimporte-quoi"}
    )
    assert connexion.status_code == 401


def test_precision_exigee_selon_le_role(session) -> None:
    sans_type = _public().post(URL, json=_investisseur(investor_type=None))
    sans_domaine = _public().post(URL, json=_chercheur(research_domain=None))
    role_interdit = _public().post(URL, json=_investisseur(role="ADMIN"))

    for refus in (sans_type, sans_domaine, role_interdit):
        assert refus.status_code == 422


def test_adresse_deja_connue_meme_reponse_sans_rien_creer(session, _envoi_simule) -> None:
    deja = User(email=f"deja-{uuid.uuid4()}@example.com", role=Role.ENTERPRISE)
    session.add(deja)
    session.commit()

    reponse = _public().post(URL, json=_investisseur(email=deja.email))

    assert reponse.status_code == 202
    session.expire_all()
    assert session.exec(
        select(AccessRequest).where(col(AccessRequest.user_id) == deja.id)
    ).first() is None
    assert "déjà associée" in _envoi_simule.call_args.kwargs["body"]


def test_champ_piege_ignore(session) -> None:
    demande = _investisseur(website_fax="http://spam")

    assert _public().post(URL, json=demande).status_code == 202
    session.expire_all()
    assert session.exec(select(User).where(col(User.email) == demande["email"].lower())).first() is None


def test_approbation_envoie_le_lien_et_journalise(session, _envoi_simule) -> None:
    demande = _chercheur()
    _public().post(URL, json=demande)
    utilisateur, acces = _demande_de(session, demande["email"])
    admin = _admin(session)

    liste = admin.get("/api/v1/admin/access-requests", params={"status": "PENDING_APPROVAL"})
    approuvee = admin.patch(f"/api/v1/admin/access-requests/{acces.id}", json={"decision": "approve"})
    encore = admin.patch(f"/api/v1/admin/access-requests/{acces.id}", json={"decision": "approve"})

    assert liste.status_code == 200
    ligne = next(d for d in liste.json() if d["id"] == str(acces.id))
    assert ligne["email"] == demande["email"].lower()
    assert ligne["role"] == "RESEARCHER" and ligne["research_domain"] == "CARBON_FOOTPRINT"
    assert approuvee.status_code == 200, approuvee.text
    assert approuvee.json()["status"] == "APPROVED"
    assert encore.json()["error"]["code"] == "transition_invalide"
    # Lien d'activation envoyé au demandeur.
    assert any(
        appel.kwargs["recipient"] == demande["email"].lower() and "activ" in appel.kwargs["body"].lower()
        for appel in _envoi_simule.call_args_list
    )
    session.expire_all()
    journal = session.exec(
        select(AuditLogEntry).where(col(AuditLogEntry.resource_id) == utilisateur.id)
    ).all()
    assert {e.action for e in journal} >= {"access_requested", "access_request_approved"}


def test_refus_exige_un_motif_puis_la_demande_peut_etre_rouverte(session, _envoi_simule) -> None:
    demande = _investisseur()
    _public().post(URL, json=demande)
    utilisateur, acces = _demande_de(session, demande["email"])
    admin = _admin(session)

    sans_motif = admin.patch(f"/api/v1/admin/access-requests/{acces.id}", json={"decision": "reject"})
    refus = admin.patch(
        f"/api/v1/admin/access-requests/{acces.id}",
        json={"decision": "reject", "reason": "Organisme non identifiable."},
    )

    assert sans_motif.status_code == 422
    assert refus.status_code == 200
    assert refus.json()["rejection_reason"] == "Organisme non identifiable."
    session.expire_all()
    session.refresh(utilisateur)
    assert utilisateur.active is False

    # Même adresse : la demande refusée est rouverte (ici en chercheur).
    rouverte = _public().post(URL, json=_chercheur(email=demande["email"]))
    assert rouverte.status_code == 202
    utilisateur, acces = _demande_de(session, demande["email"])
    assert acces.status == AccessRequestStatus.PENDING_APPROVAL
    assert acces.role == Role.RESEARCHER and utilisateur.role == Role.RESEARCHER
    assert acces.investor_type is None and acces.rejection_reason is None
    assert utilisateur.active is True


def test_seul_ladministrateur_examine_les_demandes(session) -> None:
    from app.auth.hashing import hash_password

    investisseur = User(
        email=f"inv-{uuid.uuid4()}@example.com",
        role=Role.INVESTOR,
        password_hash=hash_password("s3cret-pass"),
    )
    session.add(investisseur)
    session.commit()
    client = _client_connecte(investisseur.email, "s3cret-pass")

    assert client.get("/api/v1/admin/access-requests").status_code == 403


def test_les_administrateurs_actifs_sont_prevenus(session) -> None:
    _admin(session)
    demande = _investisseur()

    _public().post(URL, json=demande)

    _utilisateur, acces = _demande_de(session, demande["email"])
    notifications = session.exec(
        select(Notification).where(
            col(Notification.type) == "DEMANDE_ACCES", col(Notification.resource_id) == acces.id
        )
    ).all()
    assert notifications
    assert "Fonds Sahel Capital" in notifications[0].message


def test_une_demande_en_attente_nest_pas_un_compte_en_attente_dactivation(session) -> None:
    demande = _investisseur()
    _public().post(URL, json=demande)
    _utilisateur, acces = _demande_de(session, demande["email"])
    admin = _admin(session)

    avant = {u["email"] for u in admin.get("/api/v1/admin/utilisateurs/en-attente").json()}
    admin.patch(f"/api/v1/admin/access-requests/{acces.id}", json={"decision": "approve"})
    apres = {u["email"] for u in admin.get("/api/v1/admin/utilisateurs/en-attente").json()}

    # Aucun lien n'est parti avant l'approbation ; ensuite, le compte attend son activation.
    assert demande["email"].lower() not in avant
    assert demande["email"].lower() in apres
