"""Validation des inscriptions d'entreprises (tâche 1.4, PATCH /api/v1/admin/companies/{id}/onboard)."""

import hashlib
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import col, select

from app.auth.hashing import hash_password
from app.auth.models import User
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Company
from app.core.enums import RegistrationStatus, Role
from app.core.models import AuditLogEntry
from app.core.redis import get_redis_client
from app.main import app
from tests.integration.test_company_registration import _demande, inscrire_http


@pytest.fixture(autouse=True)
def _envoi_simule(monkeypatch) -> Mock:
    envoi = Mock()
    for module in ("app.company.registration", "app.admin.onboarding", "app.auth.activation"):
        monkeypatch.setattr(f"{module}.envoyer_email_differe", envoi)
    for module in ("app.company.registration", "app.admin.onboarding"):
        monkeypatch.setattr(f"{module}.ensure_email_configured", lambda: None)
    return envoi


@pytest.fixture(autouse=True)
def _reinitialiser_limite_inscription():
    cle = f"company_registrations:{hashlib.sha256(b'testclient').hexdigest()}"
    get_redis_client().delete(cle)
    yield
    get_redis_client().delete(cle)


def _client_connecte(email: str, password: str) -> TestClient:
    client = TestClient(app, base_url="https://testserver")
    reponse = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert reponse.status_code == 200
    client.headers.update({CSRF_HEADER_NAME: client.cookies[CSRF_COOKIE_NAME]})
    return client


def _admin(session) -> TestClient:
    admin = User(
        email=f"admin-{uuid.uuid4()}@example.com",
        role=Role.ADMIN,
        password_hash=hash_password("s3cret-pass"),
    )
    session.add(admin)
    session.commit()
    return _client_connecte(admin.email, "s3cret-pass")


def _inscrire(session) -> tuple[dict, Company]:
    demande = _demande()
    reponse = inscrire_http(demande)
    assert reponse.status_code == 202
    session.expire_all()
    entreprise = session.exec(
        select(Company).where(col(Company.name) == demande["company_name"])
    ).one()
    return demande, entreprise


def _url(entreprise_id: uuid.UUID) -> str:
    return f"/api/v1/admin/companies/{entreprise_id}/onboard"


def test_parcours_complet_inscription_validation_activation_connexion(session, monkeypatch) -> None:
    demande, entreprise = _inscrire(session)
    admin = _admin(session)
    jeton = f"jeton-activation-{uuid.uuid4()}"
    monkeypatch.setattr("app.auth.activation.secrets.token_urlsafe", lambda _n: jeton)

    validation = admin.patch(_url(entreprise.id), json={"decision": "approve"})

    assert validation.status_code == 200
    assert validation.json()["status"] == RegistrationStatus.ACTIVE.value
    session.expire_all()
    entreprise = session.get(Company, entreprise.id)
    assert entreprise is not None
    assert entreprise.status == RegistrationStatus.ACTIVE
    assert entreprise.onboarded_at is not None
    assert entreprise.onboarded_by_id is not None

    nouveau = TestClient(app, base_url="https://testserver")
    activation = nouveau.post(
        "/api/v1/auth/activer-compte",
        json={"token": jeton, "new_password": "premier-secret-12"},
    )
    assert activation.status_code == 200
    assert activation.json()["role"] == "ENTERPRISE"
    # La session est ouverte par l'activation elle-même : l'espace répond sans nouveau login.
    assert nouveau.get("/api/v1/company/profil").status_code == 200

    titulaire = _client_connecte(demande["contact_email"].lower(), "premier-secret-12")
    profil = titulaire.get("/api/v1/company/profil")
    assert profil.status_code == 200
    assert profil.json()["status"] == RegistrationStatus.ACTIVE.value


def test_le_lien_dactivation_part_seulement_a_la_validation(session, _envoi_simule) -> None:
    demande, entreprise = _inscrire(session)
    admin = _admin(session)
    _envoi_simule.reset_mock()  # l'accusé de réception de l'inscription ne compte pas

    admin.patch(_url(entreprise.id), json={"decision": "approve"})

    envois = _envoi_simule.call_args_list
    assert [appel.kwargs["recipient"] for appel in envois] == [demande["contact_email"].lower()]
    assert "/activer-compte?token=" in envois[0].kwargs["body"]


def test_refus_conserve_linscription_et_transmet_le_motif(session, _envoi_simule) -> None:
    demande, entreprise = _inscrire(session)
    admin = _admin(session)
    entreprise_id, titulaire_id = entreprise.id, entreprise.owner_user_id
    _envoi_simule.reset_mock()

    sans_motif = admin.patch(_url(entreprise_id), json={"decision": "reject"})
    refus = admin.patch(
        _url(entreprise_id), json={"decision": "reject", "reason": "Entreprise introuvable au registre."}
    )

    assert sans_motif.status_code == 422
    assert refus.status_code == 200
    assert refus.json()["status"] == RegistrationStatus.REJECTED.value
    session.expire_all()
    refusee = session.get(Company, entreprise_id)
    assert refusee is not None
    assert refusee.status == RegistrationStatus.REJECTED
    assert refusee.rejection_reason == "Entreprise introuvable au registre."
    assert refusee.rejected_at is not None
    titulaire = session.get(User, titulaire_id)
    assert titulaire is not None and titulaire.active is False and titulaire.password_hash is None
    assert "introuvable au registre" in _envoi_simule.call_args.kwargs["body"]
    trace = session.exec(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "registration_rejected", AuditLogEntry.resource_id == entreprise_id
        )
    ).one()
    assert trace.new_value == "Entreprise introuvable au registre."

    # Une nouvelle demande à la même adresse rouvre cette même inscription.
    nouvelle = inscrire_http({**_demande(), "contact_email": demande["contact_email"]})
    assert nouvelle.status_code == 202
    session.expire_all()
    rouverte = session.get(Company, entreprise_id)
    assert rouverte is not None
    assert rouverte.status == RegistrationStatus.PENDING_ONBOARDING
    assert rouverte.rejection_reason is None


def test_une_inscription_ne_se_decide_quune_fois(session) -> None:
    _demande_initiale, entreprise = _inscrire(session)
    admin = _admin(session)

    premiere = admin.patch(_url(entreprise.id), json={"decision": "approve"})
    seconde = admin.patch(_url(entreprise.id), json={"decision": "approve"})
    refus_apres = admin.patch(_url(entreprise.id), json={"decision": "reject", "reason": "x"})

    assert premiere.status_code == 200
    assert seconde.status_code == 422
    assert seconde.json()["error"]["code"] == "transition_invalide"
    assert refus_apres.status_code == 422


def test_seul_ladministrateur_decide(session) -> None:
    _demande_initiale, entreprise = _inscrire(session)
    investisseur = User(
        email=f"investisseur-{uuid.uuid4()}@example.com",
        role=Role.INVESTOR,
        password_hash=hash_password("s3cret-pass"),
    )
    session.add(investisseur)
    session.commit()

    reponse = _client_connecte(investisseur.email, "s3cret-pass").patch(
        _url(entreprise.id), json={"decision": "approve"}
    )

    assert reponse.status_code == 403


def test_les_inscriptions_a_examiner_sont_listees_pour_ladministrateur(session) -> None:
    from tests.integration.test_company_registration import _demande

    confirmee, entreprise = _inscrire(session)
    non_confirmee = _demande()
    inscrire_http(non_confirmee, confirmer=False)
    admin = _admin(session)

    reponse = admin.get("/api/v1/admin/companies/pending-registrations")

    assert reponse.status_code == 200, reponse.text
    ids = [ligne["company_id"] for ligne in reponse.json()]
    assert str(entreprise.id) in ids
    ligne = next(l for l in reponse.json() if l["company_id"] == str(entreprise.id))
    assert ligne["status"] == "PENDING_ONBOARDING"
    assert ligne["contact_email"] == confirmee["contact_email"].lower()
    assert ligne["tax_id_type"] == "NIF"
    # Une demande dont l'adresse n'est pas confirmée n'est pas encore transmise.
    assert non_confirmee["company_name"] not in {l["company_name"] for l in reponse.json()}
