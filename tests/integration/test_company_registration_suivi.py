"""Suivi d'une demande d'inscription par le demandeur (tâche 5.2) : jeton reçu par e-mail, réponse
à une demande d'informations, réouverture d'une demande refusée, lien d'activation de 72 heures."""

import hashlib
import re
import uuid
from datetime import timedelta
from unittest.mock import Mock

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlmodel import col, select

from app.auth.activation import ACTIVATION_TOKEN_TTL, envoyer_lien_activation
from app.auth.models import AccountActivationToken, User
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import RegistrationStatus, Role
from app.core.models import AuditLogEntry, Notification
from app.core.redis import get_redis_client
from app.main import app
from tests.integration.test_company_registration import (
    _demande,
    _lei_aleatoire,
    inscrire_http,
    pdf_minimal,
)

URL_SUIVI = "/api/v1/companies/registration-status"
URL_REPONSE = "/api/v1/companies/registration-status/reply"


@pytest.fixture(autouse=True)
def _envoi_simule(monkeypatch) -> Mock:
    monkeypatch.setattr("app.company.registration.ensure_email_configured", lambda: None)
    envoi = Mock()
    monkeypatch.setattr("app.company.registration.envoyer_email_differe", envoi)
    return envoi


@pytest.fixture(autouse=True)
def _reinitialiser_limites():
    empreinte = hashlib.sha256(b"testclient").hexdigest()
    cles = [f"company_registrations:{empreinte}", f"company_registration_replies:{empreinte}"]
    get_redis_client().delete(*cles)
    yield
    get_redis_client().delete(*cles)


def _client() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _jeton_envoye(envoi: Mock) -> str:
    trouve = re.search(r"token=([\w-]+)", envoi.call_args.kwargs["body"])
    assert trouve is not None, "aucun lien de suivi dans le dernier e-mail"
    return trouve[1]


def _inscrire(session, envoi: Mock, **surcharges) -> tuple[Company, str]:
    demande = _demande(**surcharges)
    assert inscrire_http(demande).status_code == 202
    session.expire_all()
    entreprise = session.exec(
        select(Company).where(col(Company.name) == demande["company_name"])
    ).one()
    return entreprise, _jeton_envoye(envoi)


def _passer_en(session, entreprise: Company, statut: RegistrationStatus, **champs) -> None:
    entreprise.status = statut
    for nom, valeur in champs.items():
        setattr(entreprise, nom, valeur)
    session.add(entreprise)
    session.commit()


def test_suivi_avec_le_jeton_recu_par_email(session, _envoi_simule) -> None:
    entreprise, jeton = _inscrire(session, _envoi_simule)

    suivi = _client().post(URL_SUIVI, json={"token": jeton})

    assert suivi.status_code == 200
    assert suivi.json() == {
        "company_name": entreprise.name,
        "status": "PENDING_ONBOARDING",
        "registered_at": suivi.json()["registered_at"],
        "info_request_message": None,
        "info_requested_at": None,
        "rejection_reason": None,
        "rejected_at": None,
        "can_respond": False,
    }
    assert suivi.json()["registered_at"] is not None
    assert "/inscription-entreprise/suivi?token=" in _envoi_simule.call_args.kwargs["body"]


@pytest.mark.parametrize("jeton", ["x" * 43, "jeton-trop-court"], ids=["inconnu", "trop-court"])
def test_jeton_inconnu_ou_mal_forme(session, jeton) -> None:
    reponse = _client().post(URL_SUIVI, json={"token": jeton})

    assert reponse.status_code in (404, 422)
    if reponse.status_code == 404:
        assert reponse.json()["error"]["code"] == "suivi_introuvable"


def test_reponse_a_une_demande_dinformations(session, _envoi_simule) -> None:
    admin = User(email=f"admin-{uuid.uuid4()}@example.com", role=Role.ADMIN, password_hash="x")
    session.add(admin)
    session.commit()
    entreprise, jeton = _inscrire(session, _envoi_simule)
    ancienne_lettre = entreprise.mandate_letter_path
    _passer_en(
        session,
        entreprise,
        RegistrationStatus.INFO_REQUESTED,
        info_request_message="La lettre n'est pas signée.",
        info_requested_at=utcnow(),
    )
    assert _client().post(URL_SUIVI, json={"token": jeton}).json()["can_respond"] is True

    reponse = _client().post(
        URL_REPONSE,
        data={"token": jeton, "message": "  Version signée jointe.  "},
        files={"mandate_letter": ("mandat-signe.pdf", pdf_minimal(), "application/pdf")},
    )

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["status"] == "PENDING_ONBOARDING"
    assert reponse.json()["can_respond"] is False
    session.expire_all()
    relue = session.get(Company, entreprise.id)
    assert relue is not None
    assert relue.mandate_letter_path not in (None, ancienne_lettre)
    assert relue.info_response_message == "Version signée jointe."
    assert session.exec(
        select(Notification).where(
            Notification.user_id == admin.id,
            Notification.resource_id == entreprise.id,
            Notification.type == "ENTREPRISE_INFOS_COMPLETEES",
        )
    ).first() is not None
    assert session.exec(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "registration_info_provided",
            AuditLogEntry.resource_id == entreprise.id,
        )
    ).first() is not None


def test_reponse_impossible_sans_demande_dinformations(session, _envoi_simule) -> None:
    _, jeton = _inscrire(session, _envoi_simule)

    reponse = _client().post(
        URL_REPONSE,
        data={"token": jeton},
        files={"mandate_letter": ("m.pdf", pdf_minimal(), "application/pdf")},
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "transition_invalide"


def test_reponse_refuse_un_fichier_qui_nest_pas_un_pdf(session, _envoi_simule) -> None:
    entreprise, jeton = _inscrire(session, _envoi_simule)
    _passer_en(session, entreprise, RegistrationStatus.INFO_REQUESTED)

    reponse = _client().post(
        URL_REPONSE,
        data={"token": jeton},
        files={"mandate_letter": ("m.pdf", b"texte", "application/pdf")},
    )

    assert reponse.status_code == 422
    session.expire_all()
    relue = session.get(Company, entreprise.id)
    assert relue is not None and relue.status == RegistrationStatus.INFO_REQUESTED


def test_refus_lisible_puis_reouverture_avec_les_memes_identifiants(session, _envoi_simule) -> None:
    lei = _lei_aleatoire()
    entreprise, ancien_jeton = _inscrire(session, _envoi_simule, lei=lei)
    _passer_en(
        session,
        entreprise,
        RegistrationStatus.REJECTED,
        rejection_reason="Mandat non conforme.",
        rejected_at=utcnow(),
    )
    suivi = _client().post(URL_SUIVI, json={"token": ancien_jeton}).json()
    assert suivi["status"] == "REJECTED"
    assert suivi["rejection_reason"] == "Mandat non conforme."

    nouvelle = _demande(lei=lei, isin=None)
    assert inscrire_http(nouvelle).status_code == 202

    session.expire_all()
    rouverte = session.get(Company, entreprise.id)
    assert rouverte is not None
    assert rouverte.status == RegistrationStatus.PENDING_ONBOARDING
    assert rouverte.name == nouvelle["company_name"]
    assert rouverte.rejection_reason is None
    titulaire = session.get(User, rouverte.owner_user_id)
    assert titulaire is not None
    assert titulaire.email == nouvelle["contact_email"].lower()
    assert titulaire.active is True and titulaire.password_hash is None
    # Une seule entreprise porte ce LEI, et l'ancien lien de suivi ne fonctionne plus.
    assert len(session.exec(select(Company).where(col(Company.lei) == lei)).all()) == 1
    assert _client().post(URL_SUIVI, json={"token": ancien_jeton}).status_code == 404
    nouveau_jeton = _jeton_envoye(_envoi_simule)
    assert _client().post(URL_SUIVI, json={"token": nouveau_jeton}).json()["status"] == (
        "PENDING_ONBOARDING"
    )
    assert session.exec(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "registration_resubmitted",
            AuditLogEntry.resource_id == entreprise.id,
        )
    ).first() is not None


def test_reouverture_impossible_si_un_identifiant_appartient_a_autre_chose(
    session, _envoi_simule
) -> None:
    lei = _lei_aleatoire()
    entreprise, _ = _inscrire(session, _envoi_simule, lei=lei)
    _passer_en(session, entreprise, RegistrationStatus.REJECTED, rejection_reason="Non.")
    investisseur = User(
        email=f"inv-{uuid.uuid4()}@example.com", role=Role.INVESTOR, password_hash="x"
    )
    session.add(investisseur)
    session.commit()

    reponse = inscrire_http(
        _demande(lei=lei, isin=None, contact_email=investisseur.email, website=None)
    )

    assert reponse.status_code == 202
    session.expire_all()
    relue = session.get(Company, entreprise.id)
    assert relue is not None and relue.status == RegistrationStatus.REJECTED
    assert "déjà associé" in _envoi_simule.call_args.kwargs["body"]


@pytest.mark.parametrize(
    "statut",
    [RegistrationStatus.PENDING_ONBOARDING, RegistrationStatus.ACTIVE],
)
def test_une_demande_en_cours_ou_validee_ne_se_rouvre_pas(session, _envoi_simule, statut) -> None:
    lei = _lei_aleatoire()
    entreprise, _ = _inscrire(session, _envoi_simule, lei=lei)
    _passer_en(session, entreprise, statut)

    assert inscrire_http(_demande(lei=lei, isin=None)).status_code == 202

    session.expire_all()
    assert len(session.exec(select(Company).where(col(Company.lei) == lei)).all()) == 1
    assert "déjà associé" in _envoi_simule.call_args.kwargs["body"]


def test_lien_dactivation_valable_72_heures(session) -> None:
    utilisateur = User(email=f"act-{uuid.uuid4()}@example.com", role=Role.ENTERPRISE)
    session.add(utilisateur)
    session.commit()

    avant = utcnow()
    envoyer_lien_activation(session, utilisateur, BackgroundTasks())
    session.commit()

    assert ACTIVATION_TOKEN_TTL == timedelta(hours=72)
    jeton = session.exec(
        select(AccountActivationToken).where(AccountActivationToken.user_id == utilisateur.id)
    ).one()
    assert abs((jeton.expires_at - avant) - timedelta(hours=72)) < timedelta(minutes=1)
