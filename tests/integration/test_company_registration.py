"""Inscription publique d'une entreprise (tâches 1.3 et 5.2, POST /api/v1/companies/register)."""

import hashlib
import random
import re
import string
import uuid
from unittest.mock import Mock

import pymupdf
import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import col, select

from app.auth.hashing import hash_password
from app.auth.models import User
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.identifiers import normaliser_identifiant_fiscal
from app.company.models import Company
from app.company.registration import MAX_DEMANDES_PAR_IP
from app.core.database import utcnow
from app.core.enums import RegistrationStatus, Role, TaxIdType
from app.core.models import Notification
from app.core.redis import get_redis_client
from app.main import app
from tests.conftest import CODE_DE_VERIFICATION

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
        # NIF mauritanien aléatoire (tâche 5.10) : la base de test persiste d'une exécution à l'autre.
        "tax_id": f"{uuid.uuid4().int % 10**8:08d}",
    }
    valeurs.update(surcharges)
    return valeurs


def _client() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def pdf_minimal() -> bytes:
    document = pymupdf.open()
    document.new_page()
    contenu = document.tobytes()
    document.close()
    return contenu


def inscrire_http(
    demande: dict,
    *,
    mandat: bytes | None = None,
    client: TestClient | None = None,
    confirmer: bool = True,
) -> Response:
    """POST multipart (tâche 5.2) : les champs à plat, la lettre de mandat en fichier. Puis, par
    défaut, la confirmation de l'adresse avec le code reçu (tâche 5.11, code fixé par
    tests/conftest.py) — la demande parvient alors à l'Administrateur. Renvoie la réponse de
    l'inscription."""
    champs = {cle: valeur for cle, valeur in demande.items() if valeur is not None}
    fichier = mandat if mandat is not None else pdf_minimal()
    reponse = (client or _client()).post(
        URL, data=champs, files={"mandate_letter": ("mandat.pdf", fichier, "application/pdf")}
    )
    if confirmer and reponse.status_code == 202 and demande.get("contact_email"):
        # Échoue sans bruit quand aucune demande n'a été créée (doublon, champ piège…).
        confirmer_http(demande["contact_email"])
    return reponse


def confirmer_http(email: str, code: str = CODE_DE_VERIFICATION) -> Response:
    return _client().post(
        "/api/v1/companies/registration/verify-email", json={"email": email, "code": code}
    )


def _entreprise_par_nom(session, nom: str) -> Company | None:
    session.expire_all()
    return session.exec(select(Company).where(col(Company.name) == nom)).first()


def test_inscription_cree_une_entreprise_en_attente_sans_mot_de_passe(session, _envoi_simule) -> None:
    admin = User(email=f"admin-{uuid.uuid4()}@example.com", role=Role.ADMIN, password_hash="x")
    session.add(admin)
    session.commit()
    demande = _demande()

    response = inscrire_http(demande)

    assert response.status_code == 202
    entreprise = _entreprise_par_nom(session, demande["company_name"])
    assert entreprise is not None
    assert entreprise.status == RegistrationStatus.PENDING_ONBOARDING
    assert entreprise.country == "MR"
    assert entreprise.isin == demande["isin"].upper()
    assert entreprise.published_at is None
    titulaire = session.get(User, entreprise.owner_user_id)
    assert titulaire is not None
    assert titulaire.email == demande["contact_email"].lower()
    assert titulaire.role == Role.ENTERPRISE
    assert titulaire.password_hash is None  # aucune connexion possible avant validation (1.4)
    assert entreprise.mandate_letter_path is not None
    assert entreprise.mandate_letter_path.startswith(f"mandats/{entreprise.id}/")
    assert entreprise.registered_at is not None
    assert entreprise.status_token_hash is not None
    jeton = re.search(r"token=([\w-]+)", _envoi_simule.call_args.kwargs["body"])
    assert jeton is not None
    assert hashlib.sha256(jeton[1].encode()).hexdigest() == entreprise.status_token_hash
    assert jeton[1] not in response.text
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

    response = inscrire_http(demande)

    assert response.status_code == 422
    assert _entreprise_par_nom(session, demande["company_name"]) is None


def test_un_champ_en_trop_ne_change_pas_le_statut(session) -> None:
    """En multipart, un champ inconnu est ignoré : il ne peut en tout cas jamais activer
    l'entreprise."""
    demande = _demande()

    response = inscrire_http({**demande, "status": "ACTIVE"})

    assert response.status_code == 202
    entreprise = _entreprise_par_nom(session, demande["company_name"])
    assert entreprise is not None
    assert entreprise.status == RegistrationStatus.PENDING_ONBOARDING


@pytest.mark.parametrize(
    ("fichier", "code"),
    [
        (b"", "fichier_vide"),
        (b"pas un pdf", "signature_invalide"),
        (b"%PDF-" + b"0" * (5 * 1024 * 1024), "fichier_trop_volumineux"),
    ],
    ids=["vide", "pas-un-pdf", "trop-gros"],
)
def test_lettre_de_mandat_invalide_refusee_sans_rien_creer(session, fichier, code) -> None:
    demande = _demande()

    response = inscrire_http(demande, mandat=fichier)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert _entreprise_par_nom(session, demande["company_name"]) is None


def test_lettre_de_mandat_obligatoire(session) -> None:
    demande = _demande()

    response = _client().post(URL, data=demande)

    assert response.status_code == 422
    assert _entreprise_par_nom(session, demande["company_name"]) is None


def test_email_deja_connu_repond_pareil_sans_rien_creer(session, _envoi_simule) -> None:
    existant = User(email=f"deja-{uuid.uuid4()}@example.com", role=Role.INVESTOR, password_hash="x")
    session.add(existant)
    session.commit()
    # Sans site web : la règle de domaine (tâche 5.11) n'entre pas en jeu ici.
    demande = _demande(contact_email=existant.email.upper(), website=None)

    response = inscrire_http(demande)

    assert response.status_code == 202
    assert _entreprise_par_nom(session, demande["company_name"]) is None
    # Le demandeur est informé par e-mail, jamais dans la réponse HTTP.
    assert [appel.kwargs["recipient"] for appel in _envoi_simule.call_args_list] == [existant.email]
    assert "déjà associé" in _envoi_simule.call_args.kwargs["body"]


def test_isin_deja_connu_repond_pareil_sans_rien_creer(session) -> None:
    premiere = _demande()
    assert inscrire_http(premiere).status_code == 202
    seconde = _demande(isin=premiere["isin"], lei=None)

    response = inscrire_http(seconde)

    assert response.status_code == 202
    assert _entreprise_par_nom(session, seconde["company_name"]) is None


def test_champ_piege_rempli_ignore_en_silence(session, _envoi_simule) -> None:
    demande = _demande(company_fax="+222 00 00 00")

    response = inscrire_http(demande)

    assert response.status_code == 202
    assert _entreprise_par_nom(session, demande["company_name"]) is None
    _envoi_simule.assert_not_called()


def test_inscription_limitee_par_ip(session) -> None:
    for _ in range(MAX_DEMANDES_PAR_IP):
        assert inscrire_http(_demande()).status_code == 202

    assert inscrire_http(_demande()).status_code == 429


def test_une_inscription_en_attente_ne_se_contourne_pas_par_les_actions_admin(session) -> None:
    """Réactiver ou renvoyer un lien d'activation ne valide jamais une inscription : seule la
    validation d'inscription (tâche 1.4) le fera."""
    demande = _demande()
    assert inscrire_http(demande).status_code == 202
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
    assert detail.json()["status"] == RegistrationStatus.PENDING_ONBOARDING.value
    assert detail.json()["active"] is False


def _siren_valide() -> str:
    """SIREN aléatoire dont la clé de Luhn est juste (une des dix clés possibles l'est)."""
    debut = f"{random.randrange(10**8):08d}"
    for cle in range(10):
        try:
            return normaliser_identifiant_fiscal("FR", debut + str(cle))[1]
        except ValueError:
            continue
    raise AssertionError("inatteignable")


def test_inscription_enregistre_lidentifiant_fiscal_selon_le_pays(session, _envoi_simule) -> None:
    siren = _siren_valide()
    demande = _demande(country="fr", tax_id=f"{siren[:3]} {siren[3:6]} {siren[6:]}")

    reponse = inscrire_http(demande)

    assert reponse.status_code == 202, reponse.text
    entreprise = _entreprise_par_nom(session, demande["company_name"])
    assert entreprise is not None
    assert entreprise.tax_id == siren
    assert entreprise.tax_id_type == TaxIdType.SIREN


@pytest.mark.parametrize(
    ("pays", "identifiant", "extrait"),
    [
        ("MR", "1234567", "8 chiffres"),
        ("FR", "732829321", "clé de contrôle"),
        ("US", "12345", "EIN"),
        ("SN", "", None),
    ],
)
def test_identifiant_fiscal_invalide_refuse_sur_son_champ(
    session, _envoi_simule, pays, identifiant, extrait
) -> None:
    reponse = inscrire_http(_demande(country=pays, tax_id=identifiant))

    assert reponse.status_code == 422
    champs = reponse.json()["error"]["fields"]
    assert "tax_id" in champs, champs
    if extrait:
        assert extrait in champs["tax_id"]


def test_un_identifiant_fiscal_deja_pris_dans_le_pays_naboutit_pas(session, _envoi_simule) -> None:
    premiere = _demande()
    assert inscrire_http(premiere).status_code == 202

    doublon = _demande(tax_id=premiere["tax_id"])
    reponse = inscrire_http(doublon)

    # Même réponse que toute demande ; rien n'est créé, le demandeur l'apprend par e-mail.
    assert reponse.status_code == 202
    assert _entreprise_par_nom(session, doublon["company_name"]) is None


# --- Tâche 5.11 : adresse professionnelle et code de vérification -----------------------------


@pytest.mark.parametrize(
    ("surcharges", "extrait"),
    [
        ({"contact_email": "rse.minière@gmail.com", "website": None}, "professionnelle"),
        ({"contact_email": "rse@autre-domaine.mr", "website": "https://www.exemple.mr"}, "exemple.mr"),
    ],
)
def test_adresse_non_professionnelle_refusee_sur_son_champ(session, surcharges, extrait) -> None:
    reponse = inscrire_http(_demande(**surcharges), confirmer=False)

    assert reponse.status_code == 422
    assert extrait in reponse.json()["error"]["fields"]["contact_email"]


def test_sous_domaine_du_site_accepte(session) -> None:
    demande = _demande(contact_email=f"rse-{uuid.uuid4().hex[:6]}@groupe.exemple.mr")

    assert inscrire_http(demande, confirmer=False).status_code == 202


def test_la_demande_attend_le_code_avant_de_parvenir_a_ladministrateur(
    session, _envoi_simule, envoi_code_verification
) -> None:
    demande = _demande()

    assert inscrire_http(demande, confirmer=False).status_code == 202

    entreprise = _entreprise_par_nom(session, demande["company_name"])
    assert entreprise is not None
    assert entreprise.status == RegistrationStatus.EMAIL_VERIFICATION_PENDING
    assert entreprise.status_token_hash is None
    assert entreprise.email_verification_code_hash not in (None, CODE_DE_VERIFICATION)
    # Le code part à l'adresse du demandeur ; aucun accusé avec lien de suivi avant la confirmation.
    envoi = envoi_code_verification.call_args.kwargs
    assert envoi["recipient"] == demande["contact_email"].lower()
    assert CODE_DE_VERIFICATION in envoi["body"] and CODE_DE_VERIFICATION in envoi["subject"]
    assert _envoi_simule.call_count == 0

    assert confirmer_http(demande["contact_email"]).status_code == 204

    entreprise = _entreprise_par_nom(session, demande["company_name"])
    assert entreprise is not None
    assert entreprise.status == RegistrationStatus.PENDING_ONBOARDING
    assert entreprise.email_verified_at is not None
    assert entreprise.email_verification_code_hash is None
    assert entreprise.status_token_hash is not None
    assert "suivi" in _envoi_simule.call_args.kwargs["body"]
    # Une seconde confirmation échoue : le code n'existe plus.
    assert confirmer_http(demande["contact_email"]).json()["error"]["code"] == "code_invalide"


def test_code_faux_puis_epuise_apres_cinq_essais(session) -> None:
    demande = _demande()
    inscrire_http(demande, confirmer=False)

    for _ in range(5):
        faux = confirmer_http(demande["contact_email"], code="000000")
        assert faux.status_code == 422
        assert faux.json()["error"]["code"] == "code_invalide"

    # Cinq essais : même le bon code ne vaut plus, il faut en redemander un.
    assert confirmer_http(demande["contact_email"]).status_code == 422
    entreprise = _entreprise_par_nom(session, demande["company_name"])
    assert entreprise is not None and entreprise.status == RegistrationStatus.EMAIL_VERIFICATION_PENDING


def test_code_expire(session) -> None:
    from datetime import timedelta

    demande = _demande()
    inscrire_http(demande, confirmer=False)
    entreprise = _entreprise_par_nom(session, demande["company_name"])
    assert entreprise is not None
    entreprise.email_verification_expires_at = utcnow() - timedelta(seconds=1)
    session.add(entreprise)
    session.commit()

    assert confirmer_http(demande["contact_email"]).json()["error"]["code"] == "code_invalide"


def test_adresse_inconnue_meme_reponse_quun_code_faux(session) -> None:
    reponse = confirmer_http(f"personne-{uuid.uuid4()}@exemple.mr")

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "code_invalide"


def test_renvoi_du_code_au_plus_une_fois_par_minute(session, envoi_code_verification) -> None:
    from datetime import timedelta

    demande = _demande()
    inscrire_http(demande, confirmer=False)
    url = "/api/v1/companies/registration/resend-code"

    trop_tot = _client().post(url, json={"email": demande["contact_email"]})
    assert trop_tot.status_code == 202
    assert envoi_code_verification.call_count == 1  # seulement l'envoi initial

    entreprise = _entreprise_par_nom(session, demande["company_name"])
    assert entreprise is not None
    entreprise.email_verification_sent_at = utcnow() - timedelta(minutes=2)
    session.add(entreprise)
    session.commit()
    renvoi = _client().post(url, json={"email": demande["contact_email"]})
    inconnue = _client().post(url, json={"email": f"x-{uuid.uuid4()}@exemple.mr"})

    assert renvoi.status_code == 202 and inconnue.status_code == 202
    assert envoi_code_verification.call_count == 2
    assert confirmer_http(demande["contact_email"]).status_code == 204


def test_une_demande_jamais_confirmee_se_reprend_par_une_nouvelle_inscription(session) -> None:
    demande = _demande()
    inscrire_http(demande, confirmer=False)
    premiere = _entreprise_par_nom(session, demande["company_name"])
    assert premiere is not None

    reprise = {**demande, "company_name": f"{demande['company_name']} (corrigé)"}
    assert inscrire_http(reprise).status_code == 202

    session.expire_all()
    relue = session.get(Company, premiere.id)
    assert relue is not None
    assert relue.name == reprise["company_name"]
    assert relue.status == RegistrationStatus.PENDING_ONBOARDING
