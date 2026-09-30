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
from app.core.enums import CompanyStatus, Role
from app.core.models import JournalAudit
from app.core.redis import get_redis_client
from app.main import app
from tests.integration.test_company_registration import URL as URL_INSCRIPTION
from tests.integration.test_company_registration import _demande


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
    reponse = TestClient(app, base_url="https://testserver").post(URL_INSCRIPTION, json=demande)
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
    assert validation.json()["status"] == CompanyStatus.ACTIVE.value
    session.expire_all()
    entreprise = session.get(Company, entreprise.id)
    assert entreprise is not None
    assert entreprise.status == CompanyStatus.ACTIVE
    assert entreprise.onboarded_at is not None
    assert entreprise.onboarded_by_id is not None

    activation = TestClient(app, base_url="https://testserver").post(
        "/api/v1/auth/activer-compte",
        json={"token": jeton, "nouveau_mot_de_passe": "premier-secret-12"},
    )
    assert activation.status_code == 204

    titulaire = _client_connecte(demande["contact_email"].lower(), "premier-secret-12")
    profil = titulaire.get("/api/v1/company/profil")
    assert profil.status_code == 200
    assert profil.json()["statut"] == CompanyStatus.ACTIVE.value


def test_le_lien_dactivation_part_seulement_a_la_validation(session, _envoi_simule) -> None:
    demande, entreprise = _inscrire(session)
    admin = _admin(session)
    _envoi_simule.reset_mock()  # l'accusé de réception de l'inscription ne compte pas

    admin.patch(_url(entreprise.id), json={"decision": "approve"})

    envois = _envoi_simule.call_args_list
    assert [appel.kwargs["recipient"] for appel in envois] == [demande["contact_email"].lower()]
    assert "/activer-compte?token=" in envois[0].kwargs["body"]


def test_refus_supprime_linscription_et_transmet_le_motif(session, _envoi_simule) -> None:
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
    assert refus.json()["status"] is None
    session.expire_all()
    assert session.get(Company, entreprise_id) is None
    assert session.get(User, titulaire_id) is None
    assert "introuvable au registre" in _envoi_simule.call_args.kwargs["body"]
    trace = session.exec(
        select(JournalAudit).where(
            JournalAudit.action == "refus_inscription", JournalAudit.id_ressource == entreprise_id
        )
    ).one()
    assert trace.nouvelle_valeur == "Entreprise introuvable au registre."

    # Le demandeur peut redéposer une demande avec la même adresse.
    nouvelle = TestClient(app, base_url="https://testserver").post(
        URL_INSCRIPTION, json={**_demande(), "contact_email": demande["contact_email"]}
    )
    assert nouvelle.status_code == 202
    session.expire_all()
    assert session.exec(
        select(User).where(col(User.email) == demande["contact_email"].lower())
    ).first() is not None


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
