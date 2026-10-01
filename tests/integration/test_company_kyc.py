"""Fenêtre KYC de l'Administrateur (tâche 5.3) : contrôles, lettre de mandat, demande
d'informations puis réponse du demandeur, validation ou refus depuis INFO_REQUESTED."""

import hashlib
import re
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.admin import kyc
from app.auth.hashing import hash_password
from app.auth.models import User
from app.company.models import Company
from app.core.enums import RegistrationStatus, Role
from app.core.models import AuditLogEntry
from app.core.redis import get_redis_client
from app.main import app
from tests.integration.test_company_onboarding import _admin, _client_connecte, _url
from tests.integration.test_company_registration import (
    _demande,
    _lei_aleatoire,
    inscrire_http,
    pdf_minimal,
)


@pytest.fixture(autouse=True)
def envoi(monkeypatch) -> Mock:
    simule = Mock()
    for module in ("app.company.registration", "app.admin.onboarding", "app.auth.activation"):
        monkeypatch.setattr(f"{module}.envoyer_email_differe", simule)
    for module in ("app.company.registration", "app.admin.onboarding"):
        monkeypatch.setattr(f"{module}.ensure_email_configured", lambda: None)
    return simule


@pytest.fixture(autouse=True)
def _limites_par_ip():
    empreinte = hashlib.sha256(b"testclient").hexdigest()
    cles = [f"company_registrations:{empreinte}", f"company_registration_replies:{empreinte}"]
    get_redis_client().delete(*cles)
    yield
    get_redis_client().delete(*cles)


def _inscrire(session, **surcharges) -> tuple[dict, Company]:
    demande = _demande(**surcharges)
    assert inscrire_http(demande).status_code == 202
    session.expire_all()
    return demande, session.exec(select(Company).where(Company.name == demande["company_name"])).one()


def _jeton(envoi) -> str:
    trouve = re.search(r"token=([\w-]+)", envoi.call_args.kwargs["body"])
    assert trouve is not None
    return trouve[1]


def test_rapport_kyc_reunit_identite_contact_et_controles(session, monkeypatch) -> None:
    lei = _lei_aleatoire()
    # Domaine aléatoire : la base de test persiste d'une exécution à l'autre.
    domaine = f"miniere-{uuid.uuid4().hex[:8]}.mr"
    demande, entreprise = _inscrire(
        session, lei=lei, website=f"https://www.{domaine}", contact_email=f"rse@{domaine}"
    )
    fiche = {
        "entity": {"legalName": {"name": demande["company_name"]}, "status": "ACTIVE"},
        "registration": {"status": "ISSUED"},
    }
    monkeypatch.setattr(kyc, "recuperer_fiche_gleif", lambda valeur: fiche if valeur == lei else None)

    reponse = _admin(session).get(f"/api/v1/admin/companies/{entreprise.id}/kyc")

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["status"] == "PENDING_ONBOARDING"
    assert corps["contact_email"] == f"rse@{domaine}"
    assert corps["mandate_letter_available"] is True
    assert {c["code"]: c["result"] for c in corps["checks"]} == {
        "gleif_registration": "PASSED",
        "gleif_legal_name": "PASSED",
        "contact_domain": "PASSED",
        "mandate_letter": "PASSED",
    }
    assert all(c["source"] for c in corps["checks"])


def test_gleif_injoignable_ne_bloque_pas_la_fenetre(session) -> None:
    """Fixture gleif_hors_ligne (conftest) : le réseau est coupé."""
    _, entreprise = _inscrire(session, lei=_lei_aleatoire())

    corps = _admin(session).get(f"/api/v1/admin/companies/{entreprise.id}/kyc").json()

    resultats = {c["code"]: c["result"] for c in corps["checks"]}
    assert resultats["gleif_registration"] == "NOT_VERIFIABLE"
    assert resultats["gleif_legal_name"] == "NOT_VERIFIABLE"


def test_lettre_de_mandat_telechargeable_par_l_admin_seulement(session) -> None:
    _, entreprise = _inscrire(session)
    investisseur = User(
        email=f"inv-{uuid.uuid4()}@example.com",
        role=Role.INVESTOR,
        password_hash=hash_password("s3cret-pass"),
    )
    session.add(investisseur)
    session.commit()
    url = f"/api/v1/admin/companies/{entreprise.id}/mandate-letter"

    admin = _admin(session).get(url)
    autre = _client_connecte(investisseur.email, "s3cret-pass").get(url)

    assert admin.status_code == 200
    assert admin.headers["content-type"] == "application/pdf"
    assert admin.content.startswith(b"%PDF-")
    assert autre.status_code == 403


def test_lettre_absente_donne_404(session) -> None:
    sans_lettre = Company(name=f"Ancienne {uuid.uuid4()}", sector="X", country="MR")
    session.add(sans_lettre)
    session.commit()

    reponse = _admin(session).get(f"/api/v1/admin/companies/{sans_lettre.id}/mandate-letter")

    assert reponse.status_code == 404
    assert reponse.json()["error"]["code"] == "mandat_introuvable"


def test_demande_dinformations_puis_reponse_puis_validation(session, envoi) -> None:
    demande, entreprise = _inscrire(session)
    ancien_jeton = _jeton(envoi)
    admin = _admin(session)

    sans_message = admin.patch(_url(entreprise.id), json={"decision": "request_info"})
    demande_infos = admin.patch(
        _url(entreprise.id),
        json={"decision": "request_info", "message": "Merci de joindre une lettre signée."},
    )

    assert sans_message.status_code == 422
    assert demande_infos.status_code == 200, demande_infos.text
    assert demande_infos.json()["status"] == "INFO_REQUESTED"
    courriel = envoi.call_args.kwargs
    assert courriel["recipient"] == demande["contact_email"].lower()
    assert "Merci de joindre une lettre signée." in courriel["body"]
    nouveau_jeton = _jeton(envoi)
    assert nouveau_jeton != ancien_jeton
    session.expire_all()
    trace = session.exec(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "registration_info_requested",
            AuditLogEntry.resource_id == entreprise.id,
        )
    ).one()
    assert trace.new_value == "Merci de joindre une lettre signée."

    # L'ancien lien ne fonctionne plus ; le nouveau montre la demande et accepte la réponse.
    public = TestClient(app, base_url="https://testserver")
    ancien = public.post("/api/v1/companies/registration-status", json={"token": ancien_jeton})
    assert ancien.status_code == 404
    reponse = public.post(
        "/api/v1/companies/registration-status/reply",
        data={"token": nouveau_jeton, "message": "Lettre signée jointe."},
        files={"mandate_letter": ("signee.pdf", pdf_minimal(), "application/pdf")},
    )
    assert reponse.status_code == 200, reponse.text
    kyc_apres = admin.get(f"/api/v1/admin/companies/{entreprise.id}/kyc").json()
    assert kyc_apres["status"] == "PENDING_ONBOARDING"
    assert kyc_apres["info_request_message"] == "Merci de joindre une lettre signée."
    assert kyc_apres["info_response_message"] == "Lettre signée jointe."

    validation = admin.patch(_url(entreprise.id), json={"decision": "approve"})
    assert validation.status_code == 200
    assert validation.json()["status"] == RegistrationStatus.ACTIVE.value


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_decision_possible_depuis_info_requested(session, decision) -> None:
    _, entreprise = _inscrire(session)
    admin = _admin(session)
    admin.patch(_url(entreprise.id), json={"decision": "request_info", "message": "Précisez."})

    corps = {"decision": decision}
    if decision == "reject":
        corps["reason"] = "Pas de réponse."
    reponse = admin.patch(_url(entreprise.id), json=corps)

    assert reponse.status_code == 200
    assert reponse.json()["status"] == ("ACTIVE" if decision == "approve" else "REJECTED")


def test_aucune_decision_sur_une_entreprise_deja_validee(session) -> None:
    _, entreprise = _inscrire(session)
    admin = _admin(session)
    admin.patch(_url(entreprise.id), json={"decision": "approve"})

    reponse = admin.patch(_url(entreprise.id), json={"decision": "request_info", "message": "?"})

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "transition_invalide"
