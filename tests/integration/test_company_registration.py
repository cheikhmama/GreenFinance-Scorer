"""Inscription publique d'une entreprise (tâche 1.3, POST /api/v1/companies/register)."""

import hashlib
import random
import string
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import col, select

from app.auth.hashing import hash_password
from app.auth.models import User
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Company
from app.company.registration import MAX_DEMANDES_PAR_IP
from app.core.enums import CompanyStatus, Role
from app.core.models import Notification
from app.core.redis import get_redis_client
from app.main import app

URL = "/api/v1/companies/register"


def _chiffres(identifiant: str) -> str:
    return "".join(str(int(caractere, 36)) for caractere in identifiant)


def _isin_aleatoire() -> str:
    base = "MR" + "".join(random.choices(string.ascii_uppercase + string.digits, k=9))
    for controle in "0123456789":
        chiffres = _chiffres(base + controle)
        total = 0
        for position, caractere in enumerate(reversed(chiffres)):
            chiffre = int(caractere) * (2 if position % 2 else 1)
            total += chiffre - 9 if chiffre > 9 else chiffre
        if total % 10 == 0:
            return base + controle
    raise AssertionError("inatteignable : un chiffre de contrôle existe toujours")


def _lei_aleatoire() -> str:
    base = "".join(random.choices(string.ascii_uppercase + string.digits, k=18))
    return base + f"{98 - int(_chiffres(base + '00')) % 97:02d}"


@pytest.fixture(autouse=True)
def _envoi_simule(monkeypatch) -> Mock:
    monkeypatch.setattr("app.company.registration.ensure_email_configured", lambda: None)
    envoi = Mock()
    monkeypatch.setattr("app.company.registration.envoyer_email_differe", envoi)
    return envoi


@pytest.fixture(autouse=True)
def _reinitialiser_limite_par_ip():
    cle = f"company_registrations:{hashlib.sha256(b'testclient').hexdigest()}"
    get_redis_client().delete(cle)
    yield
    get_redis_client().delete(cle)


def _demande(**surcharges) -> dict:
    valeurs = {
        "company_name": f"Minière Test {uuid.uuid4()}",
        "sector": "Mines",
        "country": "mr",
        "isin": _isin_aleatoire().lower(),
        "lei": _lei_aleatoire(),
        "website": "https://exemple.mr",
        "contact_name": "Aïcha Ba",
        "contact_email": f"Contact-{uuid.uuid4()}@Exemple.MR",
    }
    valeurs.update(surcharges)
    return valeurs


def _client() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _entreprise_par_nom(session, nom: str) -> Company | None:
    session.expire_all()
    return session.exec(select(Company).where(col(Company.name) == nom)).first()


def test_inscription_cree_une_entreprise_en_attente_sans_mot_de_passe(session, _envoi_simule) -> None:
    admin = User(email=f"admin-{uuid.uuid4()}@example.com", role=Role.ADMIN, password_hash="x")
    session.add(admin)
    session.commit()
    demande = _demande()

    response = _client().post(URL, json=demande)

    assert response.status_code == 202
    entreprise = _entreprise_par_nom(session, demande["company_name"])
    assert entreprise is not None
    assert entreprise.status == CompanyStatus.PENDING_ONBOARDING
    assert entreprise.country == "MR"
    assert entreprise.isin == demande["isin"].upper()
    assert entreprise.published_at is None
    titulaire = session.get(User, entreprise.owner_user_id)
    assert titulaire is not None
    assert titulaire.email == demande["contact_email"].lower()
    assert titulaire.role == Role.ENTERPRISE
    assert titulaire.password_hash is None  # aucune connexion possible avant validation (1.4)
    assert [appel.kwargs["recipient"] for appel in _envoi_simule.call_args_list] == [
        titulaire.email
    ]
    notification = session.exec(
        select(Notification).where(
            Notification.user_id == admin.id, Notification.resource_id == entreprise.id
        )
    ).one()
    assert notification.type == "ENTREPRISE_INSCRITE"


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("isin", "US0378331004"),  # chiffre de contrôle faux
        ("lei", "HWUPKR0MPOU8FGXBT395"),
        ("country", "Mauritanie"),
        ("website", "exemple.mr"),
        ("company_name", "Nom\\nsur deux lignes"),
    ],
)
def test_inscription_mal_formee_est_refusee(session, champ, valeur) -> None:
    demande = _demande(**{champ: valeur.replace("\\n", "\n")})

    response = _client().post(URL, json=demande)

    assert response.status_code == 422
    assert _entreprise_par_nom(session, demande["company_name"]) is None


def test_champ_inconnu_refuse(session) -> None:
    response = _client().post(URL, json={**_demande(), "status": "ACTIVE"})

    assert response.status_code == 422


def test_email_deja_connu_repond_pareil_sans_rien_creer(session, _envoi_simule) -> None:
    existant = User(email=f"deja-{uuid.uuid4()}@example.com", role=Role.INVESTOR, password_hash="x")
    session.add(existant)
    session.commit()
    demande = _demande(contact_email=existant.email.upper())

    response = _client().post(URL, json=demande)

    assert response.status_code == 202
    assert _entreprise_par_nom(session, demande["company_name"]) is None
    # Le demandeur est informé par e-mail, jamais dans la réponse HTTP.
    assert [appel.kwargs["recipient"] for appel in _envoi_simule.call_args_list] == [existant.email]
    assert "déjà associé" in _envoi_simule.call_args.kwargs["body"]


def test_isin_deja_connu_repond_pareil_sans_rien_creer(session) -> None:
    premiere = _demande()
    assert _client().post(URL, json=premiere).status_code == 202
    seconde = _demande(isin=premiere["isin"], lei=None)

    response = _client().post(URL, json=seconde)

    assert response.status_code == 202
    assert _entreprise_par_nom(session, seconde["company_name"]) is None


def test_champ_piege_rempli_ignore_en_silence(session, _envoi_simule) -> None:
    demande = _demande(company_fax="+222 00 00 00")

    response = _client().post(URL, json=demande)

    assert response.status_code == 202
    assert _entreprise_par_nom(session, demande["company_name"]) is None
    _envoi_simule.assert_not_called()


def test_inscription_limitee_par_ip(session) -> None:
    for _ in range(MAX_DEMANDES_PAR_IP):
        assert _client().post(URL, json=_demande()).status_code == 202

    assert _client().post(URL, json=_demande()).status_code == 429


def test_une_inscription_en_attente_ne_se_contourne_pas_par_les_actions_admin(session) -> None:
    """Réactiver ou renvoyer un lien d'activation ne valide jamais une inscription : seule la
    validation d'inscription (tâche 1.4) le fera."""
    demande = _demande()
    assert _client().post(URL, json=demande).status_code == 202
    entreprise = _entreprise_par_nom(session, demande["company_name"])
    assert entreprise is not None
    admin = User(
        email=f"admin-{uuid.uuid4()}@example.com",
        role=Role.ADMIN,
        password_hash=hash_password("s3cret-pass"),
    )
    session.add(admin)
    session.commit()
    client = _client()
    client.post("/api/v1/auth/login", json={"email": admin.email, "password": "s3cret-pass"})
    client.headers.update({CSRF_HEADER_NAME: client.cookies[CSRF_COOKIE_NAME]})

    reactiver = client.post(f"/api/v1/admin/entreprises/{entreprise.id}/reactiver")
    renvoyer = client.post(
        f"/api/v1/admin/utilisateurs/{entreprise.owner_user_id}/renvoyer-activation"
    )
    detail = client.get(f"/api/v1/admin/entreprises/{entreprise.id}")

    assert reactiver.status_code == 422
    assert reactiver.json()["error"]["code"] == "transition_invalide"
    assert renvoyer.status_code == 422
    assert renvoyer.json()["error"]["code"] == "inscription_non_validee"
    assert detail.json()["status"] == CompanyStatus.PENDING_ONBOARDING.value
    assert detail.json()["active"] is False
