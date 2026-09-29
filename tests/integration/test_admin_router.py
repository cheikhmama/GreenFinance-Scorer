import base64
import random
import re
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import col, select

from app.audit.models import AvisAudit
from app.auth.hashing import hash_password
from app.auth.models import AccountActivationToken, User
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Company
from app.core import storage
from app.core.audit import auditer
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import (
    CanalDepot,
    DecisionAudit,
    ExtractionStatus,
    MethodeDonnee,
    Pilier,
    ReportStatus,
    Role,
    TypeRapport,
)
from app.core.models import JournalAudit, Notification
from app.ingestion.models import ESGMetric, ESGReport, Evidence
from app.main import app
from app.scoring.engine import obtenir_configuration_reference
from app.scoring.models import ConfigurationPonderation, ScoreESG

client = TestClient(app, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _smtp_configure(monkeypatch):
    """creer_utilisateur refuse toute création si le SMTP n'est pas configuré
    (app/admin/utilisateurs.py::ensure_email_configured) — ces tests n'ont besoin ni d'un vrai
    envoi ni d'une tentative réseau réelle depuis la tâche de fond qui poste le lien d'activation
    (app/auth/activation.py::_envoyer_lien)."""
    settings = get_settings().model_copy(
        update={"smtp_host": "smtp.example.com", "mail_from": "no-reply@example.com"}
    )
    monkeypatch.setattr("app.core.email.get_settings", lambda: settings)
    monkeypatch.setattr("app.auth.activation.send_email", Mock())


def _create_utilisateur(session, role: Role, *, password: str = "s3cret-pass", actif: bool = True) -> User:
    user = User(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        password_hash=hash_password(password),
        role=role,
        active=actif,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_utilisateur_avec_email(
    session, role: Role, email: str, *, password: str = "s3cret-pass"
) -> User:
    user = User(email=email, password_hash=hash_password(password), role=role, active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_entreprise_avec_utilisateur(session) -> tuple[Company, User]:
    entreprise = Company(name=f"Cible {uuid.uuid4()}", sector="Technologies", country="France")
    session.add(entreprise)
    session.commit()
    utilisateur = _create_utilisateur(session, Role.ENTERPRISE)
    entreprise.owner_user_id = utilisateur.id
    session.add(entreprise)
    session.commit()
    session.refresh(entreprise)
    return entreprise, utilisateur


def _create_rapport(session, entreprise_id: uuid.UUID, **overrides) -> ESGReport:
    valeurs = {
        "company_id": entreprise_id,
        "type": TypeRapport.RAPPORT_ESG,
        "channel": CanalDepot.ENTREPRISE,
        "status": ReportStatus.SUBMITTED,
        "submitted_at": utcnow(),
        "source_file": "rapports/test/dummy.pdf",
    }
    valeurs.update(overrides)
    # SQLModel ignore silencieusement un kwarg inconnu : jamais un champ de test perdu en route.
    assert set(valeurs) <= set(ESGReport.model_fields), set(valeurs) - set(ESGReport.model_fields)
    rapport = ESGReport(**valeurs)
    session.add(rapport)
    session.commit()
    session.refresh(rapport)
    return rapport


def _create_rapport_en_validation(session, entreprise_id: uuid.UUID, auditeur_id: uuid.UUID) -> ESGReport:
    rapport = _create_rapport(
        session,
        entreprise_id,
        status=ReportStatus.PENDING_DECISION,
        extraction_finished_at=utcnow(), extraction_status=ExtractionStatus.DONE,
        auditor_id=auditeur_id,
    )
    session.add(
        AvisAudit(
            rapport_id=rapport.id,
            auditeur_id=auditeur_id,
            decision=DecisionAudit.RECOMMANDE_VALIDATION,
        )
    )
    # Au moins un ESGMetric (Phase 5 §9) : valider_rapport calcule désormais un score dans la
    # même transaction que la transition VALIDE (app/admin/review_queue.py) -- sans indicateur,
    # calculer_score lèverait score_incalculable et /valider échouerait pour ce fixture partagé.
    preuve = Evidence(
        document_name="rapport-test.pdf",
        year=2025,
        total_pages=1,
        page_start=1,
        page_end=1,
        excerpt_pdf_path="preuves/test/page_1.pdf",
    )
    session.add(preuve)
    session.flush()
    session.add(
        ESGMetric(
            report_id=rapport.id,
            pillar=Pilier.GOUVERNANCE,
            metric_code="femmes_conseil_pourcentage",
            value=40.0,
            unit="%",
            method=MethodeDonnee.RAPPORTEE,
            proof_id=preuve.id,
        )
    )
    session.commit()
    return rapport


def _create_score(session, rapport_id: uuid.UUID) -> ScoreESG:
    """Sème un ScoreESG directement (sans passer par app/scoring/engine.py::calculer_score) --
    utile pour les tests qui seedent un rapport VALIDE directement via _create_rapport plutôt
    que via le vrai parcours /valider (donc sans score réellement calculé). Réutilise la vraie
    configuration de référence (obtenir_configuration_reference) plutôt que d'en créer une
    seconde : une ConfigurationPonderation ad hoc avec utilisateur_id=None aurait exactement la
    forme d'une configuration de référence et fausserait tout test d'idempotence sur celle-ci."""
    configuration = obtenir_configuration_reference(session)
    score = ScoreESG(
        rapport_id=rapport_id,
        configuration_id=configuration.id,
        valeur_globale=70.0,
        score_environnement=70.0,
        score_social=70.0,
        score_gouvernance=70.0,
    )
    session.add(score)
    session.commit()
    return score


def _login(email: str, password: str) -> TestClient:
    authed_client = TestClient(app, base_url="https://testserver")
    response = authed_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    # Toute requête mutante ultérieure passe par CSRFMiddleware (app/auth/csrf.py) : le jeton
    # posé par le cookie __Host-csrf_token à la connexion doit être rejoué dans l'en-tête dédié.
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})
    return authed_client


def test_lister_utilisateurs_par_role_ne_montre_que_le_role_et_les_actifs(session) -> None:
    # `recherche` scope la requête aux seuls comptes de ce test — la base de développement
    # partagée (voir tests/integration : pas d'isolation transactionnelle par test) accumule des
    # dizaines de comptes AUDITEUR au fil des sessions, qui dépasseraient une simple page_size
    # large et masqueraient les comptes créés ici.
    marqueur = f"marqueur-{uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur_actif = _create_utilisateur_avec_email(session, Role.AUDITOR, f"{marqueur}-actif@example.com")
    auditeur_inactif = _create_utilisateur_avec_email(
        session, Role.AUDITOR, f"{marqueur}-inactif@example.com"
    )
    auditeur_inactif.active = False
    session.add(auditeur_inactif)
    chercheur = _create_utilisateur_avec_email(session, Role.RESEARCHER, f"{marqueur}-chercheur@example.com")
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITOR", "recherche": marqueur, "page_size": 50},
    )

    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body["items"]]
    assert str(auditeur_actif.id) in ids
    assert str(auditeur_inactif.id) not in ids
    assert str(chercheur.id) not in ids


def test_lister_utilisateurs_pagine_par_defaut_a_trois_par_page(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    role_isole = f"pagination-{uuid.uuid4()}"
    crees = [
        _create_utilisateur_avec_email(
            session, Role.AUDITOR, f"{role_isole}-{i}@example.com"
        )
        for i in range(5)
    ]

    authed_client = _login(admin.email, "s3cret-pass")
    premiere_page = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITOR", "recherche": role_isole, "page": 1},
    ).json()
    deuxieme_page = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITOR", "recherche": role_isole, "page": 2},
    ).json()

    assert premiere_page["total"] == 5
    assert premiere_page["pages"] == 2
    assert len(premiere_page["items"]) == 3
    assert len(deuxieme_page["items"]) == 2
    # Aucun chevauchement entre les deux pages -- l'offset avance bien de page_size.
    ids_page_1 = {item["id"] for item in premiere_page["items"]}
    ids_page_2 = {item["id"] for item in deuxieme_page["items"]}
    assert ids_page_1.isdisjoint(ids_page_2)
    assert ids_page_1 | ids_page_2 == {str(u.id) for u in crees}


def test_lister_utilisateurs_recherche_filtre_par_email(session) -> None:
    # Le domaine porte l'uuid, pas seulement la partie locale -- une exécution précédente de ce
    # même test laisse un compte "@audit-conseil.test" en base (pas d'isolation transactionnelle
    # inter-tests), donc un motif de recherche statique ramasserait aussi ce résidu.
    domaine_unique = f"audit-conseil-{uuid.uuid4().hex}.test"
    admin = _create_utilisateur(session, Role.ADMIN)
    cible = _create_utilisateur_avec_email(session, Role.AUDITOR, f"cible@{domaine_unique}")
    _create_utilisateur_avec_email(session, Role.AUDITOR, f"autre-{uuid.uuid4()}@example.com")

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITOR", "recherche": domaine_unique},
    )

    body = response.json()
    ids = [item["id"] for item in body["items"]]
    assert ids == [str(cible.id)]


def test_lister_utilisateurs_avec_role_entreprise_est_rejete(session) -> None:
    user = _create_utilisateur(session, Role.ENTERPRISE)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.get("/api/v1/admin/utilisateurs", params={"role": "AUDITOR"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_creer_utilisateur_envoie_un_lien_dactivation(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    authed_client = _login(admin.email, "s3cret-pass")
    email_cible = f"nouveau-{uuid.uuid4()}@example.com"

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={"email": email_cible, "nom": "Nouvel Auditeur", "role": "AUDITOR"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email_cible
    assert body["role"] == "AUDITOR"
    assert body["actif"] is True
    assert "mot_de_passe_temporaire" not in body

    # Aucun mot de passe n'est généré — le compte reste inutilisable tant que le lien
    # d'activation à usage unique n'a pas été consommé.
    login_response = client.post(
        "/api/v1/auth/login", json={"email": email_cible, "password": "peu-importe"}
    )
    assert login_response.status_code == 401

    activation = session.exec(
        select(AccountActivationToken).where(AccountActivationToken.user_id == uuid.UUID(body["id"]))
    ).first()
    assert activation is not None
    assert activation.used_at is None
    assert activation.expires_at > utcnow()


def test_creer_utilisateur_sans_nom_le_deduit_de_lemail(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    authed_client = _login(admin.email, "s3cret-pass")
    email_cible = f"jean.dupont-{uuid.uuid4()}@example.com"

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={"email": email_cible, "role": "AUDITOR"},
    )

    assert response.status_code == 201
    assert response.json()["nom"] == email_cible.split("@")[0]


def test_lister_utilisateurs_recherche_filtre_aussi_par_nom(session) -> None:
    marqueur = f"marqueur-{uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMIN)
    cible = _create_utilisateur_avec_email(session, Role.AUDITOR, f"autre-email-{uuid.uuid4()}@example.com")
    cible.name = f"{marqueur} Dupont"
    session.add(cible)
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITOR", "recherche": marqueur},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(cible.id)


def test_creer_utilisateur_refuse_le_role_administrateur(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={
            "email": f"nouvel-admin-{uuid.uuid4()}@example.com",
            "nom": "Nouvel Admin",
            "role": "ADMIN",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "role_non_autorise"


def test_creer_utilisateur_refuse_un_email_deja_utilise(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    existant = _create_utilisateur(session, Role.RESEARCHER)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={"email": existant.email, "nom": "Doublon", "role": "AUDITOR"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "email_deja_utilise"


def test_creer_utilisateur_avec_role_entreprise_cree_le_profil_entreprise(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    authed_client = _login(admin.email, "s3cret-pass")
    email_cible = f"nouvelle-entreprise-{uuid.uuid4()}@example.com"

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={
            "email": email_cible,
            "role": "ENTERPRISE",
            "nom": "Contact Acme",
            "nom_entreprise": "Acme Corp",
            "secteur": "Industrie",
            "pays": "France",
        },
    )

    assert response.status_code == 201
    utilisateur_id = uuid.UUID(response.json()["id"])
    entreprise = session.exec(
        select(Company).where(Company.owner_user_id == utilisateur_id)
    ).first()
    assert entreprise is not None
    assert entreprise.name == "Acme Corp"
    assert entreprise.sector == "Industrie"
    assert entreprise.country == "France"

    # Le compte peut déposer un rapport une fois activé — la relation n'est plus manquante.
    compte = session.get(User, utilisateur_id)
    assert compte is not None
    compte.password_hash = hash_password("s3cret-pass")
    compte.activated_at = utcnow()
    session.add(compte)
    session.commit()
    authed_entreprise = _login(email_cible, "s3cret-pass")
    liste_response = authed_entreprise.get("/api/v1/company/rapports")
    assert liste_response.status_code == 200


def test_creer_utilisateur_role_entreprise_sans_profil_est_rejete(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={
            "email": f"sans-profil-{uuid.uuid4()}@example.com",
            "nom": "Compte Sans Profil",
            "role": "ENTERPRISE",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "profil_entreprise_requis"
    assert set(body["error"]["fields"]) == {"nom_entreprise", "secteur", "pays"}


def test_creer_utilisateur_avec_role_entreprise_est_rejete(session) -> None:
    user = _create_utilisateur(session, Role.ENTERPRISE)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={"email": f"x-{uuid.uuid4()}@example.com", "nom": "X", "role": "AUDITOR"},
    )

    assert response.status_code == 403


def test_desactiver_utilisateur_revoque_ses_sessions_en_cours(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    admin_client = _login(admin.email, "s3cret-pass")
    cible = _create_utilisateur(session, Role.AUDITOR)
    cible_client = _login(cible.email, "s3cret-pass")
    assert cible_client.get("/api/v1/auth/me").status_code == 200

    response = admin_client.post(f"/api/v1/admin/utilisateurs/{cible.id}/desactiver")

    assert response.status_code == 200
    assert response.json()["actif"] is False
    assert cible_client.get("/api/v1/auth/me").status_code == 401


def test_desactiver_utilisateur_inconnu_est_404(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    admin_client = _login(admin.email, "s3cret-pass")

    response = admin_client.post(f"/api/v1/admin/utilisateurs/{uuid.uuid4()}/desactiver")

    assert response.status_code == 404


def test_creation_et_desactivation_de_compte_sont_journalisees(session) -> None:
    """Phase 3 §3.5 — ces deux actions de cycle de vie de compte tracent l'acteur qui a agi
    (l'administrateur), pas le compte cible."""
    admin = _create_utilisateur(session, Role.ADMIN)
    admin_client = _login(admin.email, "s3cret-pass")
    cible = _create_utilisateur(session, Role.RESEARCHER)

    admin_client.post(
        "/api/v1/admin/utilisateurs",
        json={"email": f"journal-{uuid.uuid4()}@example.com", "nom": "Journal", "role": "AUDITOR"},
    )
    admin_client.post(f"/api/v1/admin/utilisateurs/{cible.id}/desactiver")

    entrees = session.exec(
        select(JournalAudit).where(JournalAudit.acteur_id == admin.id)
    ).all()
    actions = [e.action for e in entrees]
    assert "creation_compte" in actions
    assert "desactivation_compte" in actions


def test_lister_rapports_a_affecter_filtre_correctement(session) -> None:
    # Requête globale par conception (file d'attente admin, pas scopée par entreprise) : la base
    # partagée des tests peut déjà contenir d'autres rapports qualifiants issus d'autres tests ou
    # d'une vérification manuelle -- on vérifie une inclusion/exclusion relative, jamais une
    # égalité de liste absolue.
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    non_extrait = _create_rapport(session, entreprise.id, status=ReportStatus.SUBMITTED)
    en_cours = _create_rapport(session, entreprise.id, status=ReportStatus.SUBMITTED, extraction_status=ExtractionStatus.RUNNING)
    qualifiant = _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.SUBMITTED, extraction_status=ExtractionStatus.DONE,
        extraction_finished_at=utcnow(),
    )

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get("/api/v1/admin/rapports/a-affecter")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(qualifiant.id) in ids
    assert str(non_extrait.id) not in ids
    assert str(en_cours.id) not in ids


def test_affecter_happy_path(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.SUBMITTED, extraction_status=ExtractionStatus.DONE,
        extraction_finished_at=utcnow(),
    )

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/affecter", json={"auditeur_id": str(auditeur.id)}
    )

    assert response.status_code == 200
    assert response.json()["statut"] == ReportStatus.PENDING_AUDIT.value

    notifications = session.exec(
        select(Notification).where(Notification.utilisateur_id == auditeur.id)
    ).all()
    assert len(notifications) == 1


def test_affecter_rapport_deja_affecte(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(session, entreprise.id, status=ReportStatus.VALIDATED)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/affecter", json={"auditeur_id": str(auditeur.id)}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "rapport_deja_affecte"


def test_affecter_extraction_non_terminee(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(session, entreprise.id, status=ReportStatus.SUBMITTED, extraction_status=ExtractionStatus.RUNNING)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/affecter", json={"auditeur_id": str(auditeur.id)}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "extraction_non_terminee"


def test_affecter_auditeur_invalide(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    investisseur = _create_utilisateur(session, Role.INVESTOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.SUBMITTED, extraction_status=ExtractionStatus.DONE,
        extraction_finished_at=utcnow(),
    )

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/affecter", json={"auditeur_id": str(investisseur.id)}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "auditeur_invalide"


def test_lister_rapports_en_validation_respecte_lordre_des_avis(session) -> None:
    # Requête globale par conception, même remarque que le test précédent : on vérifie l'ordre
    # RELATIF de nos deux rapports l'un par rapport à l'autre, jamais une liste exacte -- la base
    # partagée des tests peut contenir d'autres rapports EN_VALIDATION issus d'ailleurs.
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)

    second = _create_rapport_en_validation(session, entreprise.id, auditeur.id)
    avis_second = session.exec(
        select(AvisAudit).where(AvisAudit.rapport_id == second.id)
    ).first()
    avis_second.date_avis = utcnow()
    session.add(avis_second)

    premier = _create_rapport_en_validation(session, entreprise.id, auditeur.id)
    avis_premier = session.exec(
        select(AvisAudit).where(AvisAudit.rapport_id == premier.id)
    ).first()
    avis_premier.date_avis = utcnow() - timedelta(hours=1)
    session.add(avis_premier)
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get("/api/v1/admin/rapports/en-validation")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(premier.id) in ids
    assert str(second.id) in ids
    assert ids.index(str(premier.id)) < ids.index(str(second.id))


def test_valider_happy_path(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, utilisateur_entreprise = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport_en_validation(session, entreprise.id, auditeur.id)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/valider", json={"commentaire": "Conforme."}
    )

    assert response.status_code == 200
    assert response.json()["statut"] == ReportStatus.VALIDATED.value
    notifications = session.exec(
        select(Notification).where(Notification.utilisateur_id == utilisateur_entreprise.id)
    ).all()
    assert any(n.type == "RAPPORT_VALIDE" for n in notifications)
    score = session.exec(select(ScoreESG).where(ScoreESG.rapport_id == rapport.id)).first()
    assert score is not None
    assert score.score_gouvernance == 80.0  # femmes_conseil_pourcentage=40 -> 40/50 borne -> 80
    assert score.score_environnement is None  # aucun indicateur ENVIRONNEMENT semé pour ce test
    assert score.score_social is None


def test_rejeter_happy_path(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport_en_validation(session, entreprise.id, auditeur.id)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/rapports/{rapport.id}/rejeter", json={})

    assert response.status_code == 200
    assert response.json()["statut"] == ReportStatus.REJECTED.value


def test_demander_correction_happy_path(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport_en_validation(session, entreprise.id, auditeur.id)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/demander-correction", json={}
    )

    assert response.status_code == 200
    assert response.json()["statut"] == ReportStatus.REVISION_REQUESTED.value


def test_decision_avec_statut_invalide_est_rejetee(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(session, entreprise.id, status=ReportStatus.SUBMITTED)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/rapports/{rapport.id}/valider", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "transition_invalide"


def test_valider_sans_aucun_indicateur_est_rejete(session) -> None:
    """Distinct de test_decision_sans_avis_est_rejetee : ici l'avis existe, mais le rapport n'a
    aucun ESGMetric -- calculer_score (Phase 5 §9) refuse de fabriquer un score sans
    substance, et la transition VALIDE n'a pas lieu (transaction unique, voir valider_rapport)."""
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.PENDING_DECISION,
        extraction_finished_at=utcnow(), extraction_status=ExtractionStatus.DONE,
        auditor_id=auditeur.id,
    )
    session.add(
        AvisAudit(
            rapport_id=rapport.id, auditeur_id=auditeur.id, decision=DecisionAudit.RECOMMANDE_VALIDATION
        )
    )
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/rapports/{rapport.id}/valider", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "score_incalculable"
    session.refresh(rapport)
    assert rapport.status == ReportStatus.PENDING_DECISION  # transition annulée, pas de VALIDE partiel


def test_decision_sans_avis_est_rejetee(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    # EN_VALIDATION semé directement, sans AvisAudit -- état normalement inatteignable via l'API.
    rapport = _create_rapport(session, entreprise.id, status=ReportStatus.PENDING_DECISION)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/rapports/{rapport.id}/valider", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "avis_manquant"


def test_lister_entreprises_publiables_exclut_deja_publiees_et_sans_rapport_valide(session) -> None:
    # `recherche` scope la requête aux seules entreprises de ce test, même raison que
    # test_lister_utilisateurs_par_role_ne_montre_que_le_role_et_les_actifs ci-dessus.
    marqueur = f"Marqueur {uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMIN)

    publiable, _ = _create_entreprise_avec_utilisateur(session)
    publiable.name = f"{marqueur} publiable"
    session.add(publiable)
    session.commit()
    _create_rapport(session, publiable.id, status=ReportStatus.VALIDATED)

    deja_publiee, _ = _create_entreprise_avec_utilisateur(session)
    deja_publiee.name = f"{marqueur} deja-publiee"
    _create_rapport(session, deja_publiee.id, status=ReportStatus.VALIDATED)
    deja_publiee.published_at = utcnow()
    session.add(deja_publiee)

    sans_rapport_valide, _ = _create_entreprise_avec_utilisateur(session)
    sans_rapport_valide.name = f"{marqueur} sans-rapport-valide"
    session.add(sans_rapport_valide)
    _create_rapport(session, sans_rapport_valide.id, status=ReportStatus.REJECTED)
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/entreprises/publiables", params={"recherche": marqueur, "page_size": 50}
    )

    ids = [item["id"] for item in response.json()["items"]]
    assert str(publiable.id) in ids
    assert str(deja_publiee.id) not in ids
    assert str(sans_rapport_valide.id) not in ids


def test_lister_entreprises_publiables_pagine_par_defaut_a_trois_par_page(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    prefixe = f"Pagination {uuid.uuid4()}"
    for i in range(4):
        entreprise = Company(name=f"{prefixe} {i}", sector="Technologies", country="France")
        session.add(entreprise)
        session.commit()
        _create_rapport(session, entreprise.id, status=ReportStatus.VALIDATED)

    authed_client = _login(admin.email, "s3cret-pass")
    premiere_page = authed_client.get(
        "/api/v1/admin/entreprises/publiables", params={"recherche": prefixe, "page": 1}
    ).json()
    deuxieme_page = authed_client.get(
        "/api/v1/admin/entreprises/publiables", params={"recherche": prefixe, "page": 2}
    ).json()

    assert premiere_page["total"] == 4
    assert premiere_page["pages"] == 2
    assert len(premiere_page["items"]) == 3
    assert len(deuxieme_page["items"]) == 1


def test_lister_entreprises_publiables_recherche_filtre_par_nom(session) -> None:
    # Le nom complet (uuid inclus) sert de motif de recherche, pas juste "Ferme Solaire" -- une
    # exécution précédente de ce test laisse une autre "Ferme Solaire ..." en base (même raison
    # que test_lister_utilisateurs_recherche_filtre_par_email ci-dessus).
    nom_cible = f"Ferme Solaire {uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMIN)
    cible, _ = _create_entreprise_avec_utilisateur(session)
    cible.name = nom_cible
    session.add(cible)
    session.commit()
    _create_rapport(session, cible.id, status=ReportStatus.VALIDATED)

    autre, _ = _create_entreprise_avec_utilisateur(session)
    _create_rapport(session, autre.id, status=ReportStatus.VALIDATED)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/entreprises/publiables", params={"recherche": nom_cible}
    )

    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [str(cible.id)]


def test_lister_toutes_les_entreprises_inclut_celles_sans_rapport_ni_compte(session) -> None:
    # Contrairement à /admin/entreprises/publiables, cette route doit remonter une entreprise
    # même sans rapport (statut à None) et même sans compte utilisateur rattaché
    # (utilisateur_id à None) -- c'est précisément ce qui manquait pour piloter les entreprises
    # de référence orphelines (voir la conversation qui a motivé cette route).
    marqueur = f"Marqueur {uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMIN)

    orpheline = Company(name=f"{marqueur} orpheline", sector="Mines", country="Mauritanie")
    session.add(orpheline)
    session.commit()
    session.refresh(orpheline)

    avec_compte, utilisateur = _create_entreprise_avec_utilisateur(session)
    avec_compte.name = f"{marqueur} avec-compte"
    session.add(avec_compte)
    session.commit()
    # Horodatage explicite : deux dépôts consécutifs peuvent recevoir le même utcnow() (résolution
    # de l'horloge), ce qui rendait "le plus récent" aléatoire.
    _create_rapport(
        session,
        avec_compte.id,
        status=ReportStatus.REJECTED,
        submitted_at=utcnow() - timedelta(minutes=1),
    )
    plus_recent = _create_rapport(session, avec_compte.id, status=ReportStatus.VALIDATED)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get("/api/v1/admin/entreprises", params={"recherche": marqueur})

    items = {item["id"]: item for item in response.json()["items"]}
    assert str(orpheline.id) in items
    assert items[str(orpheline.id)]["utilisateur_id"] is None
    assert items[str(orpheline.id)]["nombre_rapports"] == 0
    assert items[str(orpheline.id)]["dernier_statut_rapport"] is None
    assert items[str(orpheline.id)]["dernier_rapport_id"] is None

    assert items[str(avec_compte.id)]["utilisateur_id"] == str(utilisateur.id)
    assert items[str(avec_compte.id)]["nombre_rapports"] == 2
    # Le plus récent des deux rapports (par date_depot), pas le premier créé.
    assert items[str(avec_compte.id)]["dernier_statut_rapport"] == plus_recent.status.value
    assert items[str(avec_compte.id)]["dernier_rapport_id"] == str(plus_recent.id)


_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_consulter_entreprise_admin_retourne_le_detail_complet(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, utilisateur = _create_entreprise_avec_utilisateur(session)
    entreprise.description = "Une description."
    entreprise.website = "https://exemple.test"
    session.add(entreprise)
    session.commit()
    rapport = _create_rapport(session, entreprise.id, status=ReportStatus.REJECTED)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/admin/entreprises/{entreprise.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["nom"] == entreprise.name
    assert body["description"] == "Une description."
    assert body["site_officiel"] == "https://exemple.test"
    assert body["utilisateur_id"] == str(utilisateur.id)
    assert body["nombre_rapports"] == 1
    assert body["dernier_statut_rapport"] == ReportStatus.REJECTED.value
    assert body["dernier_rapport_id"] == str(rapport.id)


def test_consulter_entreprise_admin_inconnue_est_404(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.get(f"/api/v1/admin/entreprises/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "entreprise_introuvable"


def test_modifier_entreprise_met_a_jour_le_profil_complet(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.patch(
        f"/api/v1/admin/entreprises/{entreprise.id}",
        json={
            "nom": "Nouveau Nom",
            "secteur": "Énergie",
            "pays": "Mauritanie",
            "description": "Description mise à jour.",
            "site_officiel": "https://nouveau-site.test",
            "montant_minimum_investissement": 1000.0,
            "devise_montant_minimum": "USD",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["nom"] == "Nouveau Nom"
    assert body["secteur"] == "Énergie"
    assert body["pays"] == "Mauritanie"
    assert body["description"] == "Description mise à jour."
    assert body["site_officiel"] == "https://nouveau-site.test"
    assert body["montant_minimum_investissement"] == 1000.0
    assert body["devise_montant_minimum"] == "USD"
    # Réponse au même format que le détail -- pas de refetch nécessaire côté frontend.
    assert "nombre_rapports" in body
    assert "utilisateur_id" in body


def test_modifier_entreprise_exige_montant_et_devise_ensemble(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.patch(
        f"/api/v1/admin/entreprises/{entreprise.id}",
        json={
            "nom": entreprise.name,
            "secteur": entreprise.sector,
            "pays": entreprise.country,
            "montant_minimum_investissement": 1000.0,
        },
    )

    assert response.status_code == 422


def test_modifier_entreprise_refuse_nom_vide(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.patch(
        f"/api/v1/admin/entreprises/{entreprise.id}",
        json={"nom": "   ", "secteur": entreprise.sector, "pays": entreprise.country},
    )

    assert response.status_code == 422


def test_modifier_entreprise_inconnue_est_404(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.patch(
        f"/api/v1/admin/entreprises/{uuid.uuid4()}",
        json={"nom": "X", "secteur": "Y", "pays": "Z"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "entreprise_introuvable"


def test_televerser_puis_supprimer_logo_entreprise(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    authed_client = _login(admin.email, "s3cret-pass")

    upload = authed_client.post(
        f"/api/v1/admin/entreprises/{entreprise.id}/logo",
        files={"fichier": ("logo.png", _PNG_1X1, "image/png")},
    )
    assert upload.status_code == 200
    assert upload.json()["logo"].startswith("data:image/png;base64,")

    delete = authed_client.delete(f"/api/v1/admin/entreprises/{entreprise.id}/logo")
    assert delete.status_code == 200
    assert delete.json()["logo"] is None


def test_televerser_logo_entreprise_non_image_est_refuse(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(
        f"/api/v1/admin/entreprises/{entreprise.id}/logo",
        files={"fichier": ("pas-une-image.txt", b"contenu texte quelconque", "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "signature_invalide"


def test_televerser_logo_entreprise_inconnue_est_404(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(
        f"/api/v1/admin/entreprises/{uuid.uuid4()}/logo",
        files={"fichier": ("logo.png", _PNG_1X1, "image/png")},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "entreprise_introuvable"


def test_logo_entreprise_routes_avec_role_entreprise_sont_rejetees(session) -> None:
    user = _create_utilisateur(session, Role.ENTERPRISE)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        f"/api/v1/admin/entreprises/{entreprise.id}/logo",
        files={"fichier": ("logo.png", _PNG_1X1, "image/png")},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_publier_happy_path_et_idempotence(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, utilisateur_entreprise = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(session, entreprise.id, status=ReportStatus.VALIDATED)
    _create_score(session, rapport.id)

    authed_client = _login(admin.email, "s3cret-pass")
    premiere = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/publier")
    assert premiere.status_code == 200
    assert premiere.json()["date_publication"] is not None

    deuxieme = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/publier")
    assert deuxieme.status_code == 200

    notifications = session.exec(
        select(Notification).where(Notification.utilisateur_id == utilisateur_entreprise.id)
    ).all()
    assert any(n.type == "ENTREPRISE_PUBLIEE" for n in notifications)


def test_publier_sans_rapport_valide_est_rejete(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/publier")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "aucun_rapport_valide"


def test_publier_sans_score_est_rejete(session) -> None:
    """Rapport VALIDE semé directement (sans passer par /valider, donc sans ScoreESG) -- état
    normalement inatteignable via l'API seule depuis que valider_rapport calcule toujours un
    score dans la même transaction (Phase 5 §9), gardé en défense dans publier_entreprise."""
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    _create_rapport(session, entreprise.id, status=ReportStatus.VALIDATED)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/publier")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "score_manquant"


def test_admin_routes_sans_authentification_sont_rejetees() -> None:
    # Un client dédié, jamais celui du module : `client` peut porter le cookie de session
    # laissé par un test antérieur qui s'est connecté avec (ex. les tests de création de
    # compte plus haut) — "sans authentification" doit être garanti, pas supposé par ordre
    # d'exécution.
    anonymous_client = TestClient(app, base_url="https://testserver")
    response = anonymous_client.get("/api/v1/admin/rapports/a-affecter")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_admin_routes_avec_role_entreprise_sont_rejetees(session) -> None:
    user = _create_utilisateur(session, Role.ENTERPRISE)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.get("/api/v1/admin/rapports/a-affecter")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_consulter_fichier_retourne_le_pdf_et_404_si_absent(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    chemin_relatif = f"rapports/test/{uuid.uuid4()}.pdf"
    storage.save_bytes(chemin_relatif, b"%PDF-1.4 contenu de test")
    rapport = _create_rapport(session, entreprise.id, source_file=chemin_relatif)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/admin/rapports/{rapport.id}/fichier")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 contenu de test"

    reponse_absente = authed_client.get(f"/api/v1/admin/rapports/{uuid.uuid4()}/fichier")
    assert reponse_absente.status_code == 404
    assert reponse_absente.json()["error"]["code"] == "rapport_introuvable"


def test_lister_versions_reconstruit_la_chaine_dans_l_ordre(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    original = _create_rapport(session, entreprise.id, version=1)
    correction_1 = _create_rapport(
        session, entreprise.id, version=2, previous_report_id=original.id
    )
    correction_2 = _create_rapport(
        session, entreprise.id, version=3, previous_report_id=correction_1.id
    )

    authed_client = _login(admin.email, "s3cret-pass")
    # Interroger depuis n'importe quel maillon de la chaîne doit renvoyer la même séquence
    # complète — c'est tout l'intérêt de remonter d'abord à l'original.
    response = authed_client.get(f"/api/v1/admin/rapports/{correction_1.id}/versions")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids == [str(original.id), str(correction_1.id), str(correction_2.id)]


def test_reactiver_utilisateur_reactive_et_journalise(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    cible = _create_utilisateur(session, Role.AUDITOR, actif=False)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(f"/api/v1/admin/utilisateurs/{cible.id}/reactiver")

    assert response.status_code == 200
    assert response.json()["actif"] is True

    entree = session.exec(
        select(JournalAudit).where(
            JournalAudit.acteur_id == admin.id,
            JournalAudit.action == "reactivation_compte",
            JournalAudit.id_ressource == cible.id,
        )
    ).first()
    assert entree is not None
    assert entree.ancienne_valeur == "inactif"
    assert entree.nouvelle_valeur == "actif"


def test_lister_utilisateurs_inclut_les_inactifs_seulement_si_demande(session) -> None:
    marqueur = f"marqueur-{uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMIN)
    inactif = _create_utilisateur_avec_email(session, Role.AUDITOR, f"{marqueur}-inactif@example.com")
    inactif.active = False
    session.add(inactif)
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")

    sans_flag = authed_client.get(
        "/api/v1/admin/utilisateurs", params={"role": "AUDITOR", "recherche": marqueur}
    )
    assert sans_flag.json()["total"] == 0

    avec_flag = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITOR", "recherche": marqueur, "inclure_inactifs": True},
    )
    assert avec_flag.json()["total"] == 1
    assert avec_flag.json()["items"][0]["id"] == str(inactif.id)


def test_lister_journal_audit_concerne_id_couvre_acteur_et_cible(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    autre_admin = _create_utilisateur(session, Role.ADMIN)
    cible = _create_utilisateur(session, Role.AUDITOR)

    # cible agit elle-même (acteur_id=cible.id)
    auditer(session, cible.id, "connexion", "Utilisateur", cible.id, "succes")
    # un autre admin agit SUR cible (id_ressource=cible.id)
    auditer(session, autre_admin.id, "desactivation_compte", "Utilisateur", cible.id, "succes")
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/journal-audit", params={"concerne_id": str(cible.id), "page_size": 50}
    )

    assert response.status_code == 200
    actions = {item["action"] for item in response.json()["items"]}
    assert "connexion" in actions
    assert "desactivation_compte" in actions


def test_suspendre_et_reactiver_entreprise(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    authed_client = _login(admin.email, "s3cret-pass")

    suspension = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/suspendre")
    assert suspension.status_code == 200
    assert suspension.json()["actif"] is False

    reactivation = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/reactiver")
    assert reactivation.status_code == 200
    assert reactivation.json()["actif"] is True


def test_lister_rapports_entreprise_filtre_par_entreprise(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    autre_entreprise, _ = _create_entreprise_avec_utilisateur(session)
    mien = _create_rapport(session, entreprise.id)
    _create_rapport(session, autre_entreprise.id)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/admin/entreprises/{entreprise.id}/rapports")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids == [str(mien.id)]


def test_lister_journal_audit_pagine_et_filtre_par_action(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    marqueur_action = f"action-test-{uuid.uuid4()}"
    autre_action = f"autre-action-{uuid.uuid4()}"
    for _ in range(3):
        auditer(session, admin.id, marqueur_action, "Utilisateur", admin.id, "succes")
    auditer(session, admin.id, autre_action, "Utilisateur", admin.id, "succes")
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/journal-audit",
        params={"action": marqueur_action, "page_size": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 2
    assert all(item["action"] == marqueur_action for item in body["items"])


def _dashboard(authed_client: TestClient) -> dict:
    response = authed_client.get("/api/v1/admin/dashboard")
    assert response.status_code == 200
    return response.json()


def test_dashboard_agrege_les_compteurs(session) -> None:
    # Base de test partagée, jamais vide entre les runs — on mesure une DELTA avant/après plutôt
    # qu'une valeur absolue (même principe que les autres listes globales de ce module).
    admin = _create_utilisateur(session, Role.ADMIN)
    authed_client = _login(admin.email, "s3cret-pass")
    avant = _dashboard(authed_client)

    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    _create_rapport(session, entreprise.id, status=ReportStatus.VALIDATED)
    _create_rapport(session, entreprise.id, status=ReportStatus.REJECTED)

    apres = _dashboard(authed_client)
    assert apres["entreprises_inscrites"] - avant["entreprises_inscrites"] == 1
    assert apres["rapports_soumis"] - avant["rapports_soumis"] == 2
    assert apres["rapports_valides"] - avant["rapports_valides"] == 1
    assert apres["rapports_rejetes"] - avant["rapports_rejetes"] == 1


def test_audits_en_retard_respecte_le_sla(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    authed_client = _login(admin.email, "s3cret-pass")
    sla = get_settings().sla_audit_jours
    entreprise, _ = _create_entreprise_avec_utilisateur(session)

    avant = _dashboard(authed_client)
    _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.PENDING_AUDIT,
        assigned_at=utcnow() - timedelta(days=sla + 1),
    )
    _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.PENDING_AUDIT,
        assigned_at=utcnow() - timedelta(days=sla - 1),
    )
    apres = _dashboard(authed_client)

    assert apres["audits_en_retard"] - avant["audits_en_retard"] == 1


def test_demandes_republication_detecte_le_rapport_posterieur(session) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    authed_client = _login(admin.email, "s3cret-pass")
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    entreprise.published_at = utcnow() - timedelta(days=5)
    session.add(entreprise)
    session.commit()

    avant = _dashboard(authed_client)
    _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.VALIDATED,
        submitted_at=utcnow() - timedelta(days=10),
    )
    apres_anterieur = _dashboard(authed_client)
    assert apres_anterieur["demandes_republication"] - avant["demandes_republication"] == 0

    _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.VALIDATED,
        submitted_at=utcnow() - timedelta(days=1),
    )
    apres_posterieur = _dashboard(authed_client)
    assert apres_posterieur["demandes_republication"] - avant["demandes_republication"] == 1


def test_lister_utilisateurs_filtre_par_en_attente_activation(session) -> None:
    marqueur = f"marqueur-{uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMIN)
    en_attente = _create_utilisateur_avec_email(
        session, Role.AUDITOR, f"{marqueur}-attente@example.com"
    )
    en_attente.activated_at = None
    deja_active = _create_utilisateur_avec_email(
        session, Role.AUDITOR, f"{marqueur}-ok@example.com"
    )
    deja_active.activated_at = utcnow()
    session.add_all([en_attente, deja_active])
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITOR", "recherche": marqueur, "en_attente_activation": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(en_attente.id)


def test_lister_rapports_echec_extraction_filtre_correctement(session) -> None:
    """Un échec d'extraction (extraction_erreur renseigné) doit être visible quelque part côté
    Admin — invisible de /admin/rapports/a-affecter, qui ne filtre que sur
    extraction_terminee_le (voir BUG-017)."""
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    echec = _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.SUBMITTED, extraction_status=ExtractionStatus.FAILED,
        extraction_error="appel_claude_echoue",
    )
    en_cours = _create_rapport(session, entreprise.id, status=ReportStatus.SUBMITTED, extraction_status=ExtractionStatus.RUNNING)
    qualifiant = _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.SUBMITTED, extraction_status=ExtractionStatus.DONE,
        extraction_finished_at=utcnow(),
    )

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get("/api/v1/admin/rapports/echec-extraction")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(echec.id) in ids
    assert str(en_cours.id) not in ids
    assert str(qualifiant.id) not in ids


def test_lister_rapports_orphelins_en_validation(session) -> None:
    """Un rapport EN_VALIDATION sans aucun avis d'audit est un état incohérent, inatteignable via
    l'API seule (voir app/admin/review_queue.py::_rapport_en_validation) mais qui doit rester
    visible d'une file Admin s'il survient (données historiques) — jamais invisible de partout à
    la fois comme avant ce correctif (voir BUG-018)."""
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    orphelin = _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.PENDING_DECISION,
        extraction_finished_at=utcnow(), extraction_status=ExtractionStatus.DONE,
    )
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    avec_avis = _create_rapport_en_validation(session, entreprise.id, auditeur.id)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get("/api/v1/admin/rapports/orphelins")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(orphelin.id) in ids
    assert str(avec_avis.id) not in ids

    normale = authed_client.get("/api/v1/admin/rapports/en-validation")
    ids_normale = [item["id"] for item in normale.json()]
    assert str(orphelin.id) not in ids_normale
    assert str(avec_avis.id) in ids_normale


def test_verifier_score_calculable_route(session) -> None:
    """Aperçu avant décision (BUG-019) : un rapport dont les indicateurs ne recoupent aucun code
    de la configuration de référence doit être signalé non calculable AVANT que l'Admin ne
    clique Valider, jamais seulement après coup."""
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)

    calculable = _create_rapport_en_validation(session, entreprise.id, auditeur.id)

    non_calculable = _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.PENDING_DECISION,
        extraction_finished_at=utcnow(), extraction_status=ExtractionStatus.DONE,
    )
    preuve = Evidence(
        document_name="rapport-test.pdf",
        year=2025,
        total_pages=1,
        page_start=1,
        page_end=1,
        excerpt_pdf_path="preuves/test/page_1.pdf",
    )
    session.add(preuve)
    session.flush()
    session.add(
        ESGMetric(
            report_id=non_calculable.id,
            pillar=Pilier.SOCIAL,
            metric_code="effectif_total",
            value=1200.0,
            unit="personnes",
            method=MethodeDonnee.RAPPORTEE,
            proof_id=preuve.id,
        )
    )
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")

    reponse_calculable = authed_client.get(f"/api/v1/admin/rapports/{calculable.id}/score-verification")
    assert reponse_calculable.status_code == 200
    assert reponse_calculable.json()["calculable"] is True

    reponse_non_calculable = authed_client.get(
        f"/api/v1/admin/rapports/{non_calculable.id}/score-verification"
    )
    assert reponse_non_calculable.status_code == 200
    assert reponse_non_calculable.json()["calculable"] is False


def test_recalculer_score_route(session) -> None:
    """Action de récupération (BUG-020) pour un rapport VALIDE historiquement sans ScoreESG —
    état inatteignable via le parcours normal mais qui doit avoir une issue explicite depuis
    l'UI plutôt que de bloquer publier_entreprise indéfiniment sans recours."""
    admin = _create_utilisateur(session, Role.ADMIN)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)

    sans_score = _create_rapport(session, entreprise.id, status=ReportStatus.VALIDATED)
    preuve = Evidence(
        document_name="rapport-test.pdf",
        year=2025,
        total_pages=1,
        page_start=1,
        page_end=1,
        excerpt_pdf_path="preuves/test/page_1.pdf",
    )
    session.add(preuve)
    session.flush()
    session.add(
        ESGMetric(
            report_id=sans_score.id,
            pillar=Pilier.GOUVERNANCE,
            metric_code="femmes_conseil_pourcentage",
            value=40.0,
            unit="%",
            method=MethodeDonnee.RAPPORTEE,
            proof_id=preuve.id,
        )
    )
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")

    reponse = authed_client.post(f"/api/v1/admin/rapports/{sans_score.id}/recalculer-score")
    assert reponse.status_code == 200
    assert reponse.json()["valeur_globale"] is not None

    deja_calcule = authed_client.post(f"/api/v1/admin/rapports/{sans_score.id}/recalculer-score")
    assert deja_calcule.status_code == 422
    assert deja_calcule.json()["error"]["code"] == "score_deja_calcule"

    non_valide = _create_rapport(session, entreprise.id, status=ReportStatus.SUBMITTED, extraction_status=ExtractionStatus.RUNNING)
    reponse_invalide = authed_client.post(f"/api/v1/admin/rapports/{non_valide.id}/recalculer-score")
    assert reponse_invalide.status_code == 422
    assert reponse_invalide.json()["error"]["code"] == "transition_invalide"


@pytest.fixture()
def version_de_reference_inedite(monkeypatch, tmp_path) -> int:
    """Pointe la configuration de référence vers une copie de config/weights/default.yaml portant
    une version jamais vue en base : reproduit « première validation sous une nouvelle version »
    (table sans ligne de référence pour cette version) sans vider la base de test partagée."""
    version = random.randint(10_000, 10_000_000)
    source = Path(get_settings().default_scoring_config).read_text(encoding="utf-8")
    copie = tmp_path / "reference.yaml"
    copie.write_text(re.sub(r"(?m)^version: \d+$", f"version: {version}", source), encoding="utf-8")
    monkeypatch.setattr(get_settings(), "default_scoring_config", str(copie))
    return version


def _references_de_version(session, version: int) -> list[ConfigurationPonderation]:
    session.expire_all()
    return list(
        session.exec(
            select(ConfigurationPonderation).where(
                col(ConfigurationPonderation.utilisateur_id).is_(None),
                col(ConfigurationPonderation.version) == version,
            )
        ).all()
    )


def test_premiere_validation_incalculable_sous_une_nouvelle_version_ne_valide_rien(
    session, version_de_reference_inedite
) -> None:
    """Régression tâche 1.6 : l'ancien obtenir_configuration_reference commitait AU MILIEU de
    valider_rapport quand la ligne de référence manquait — le statut VALIDATED était alors déjà
    persisté quand score_incalculable annulait la suite, laissant un rapport validé sans score."""
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(
        session,
        entreprise.id,
        status=ReportStatus.PENDING_DECISION,
        extraction_status=ExtractionStatus.DONE,
        auditor_id=auditeur.id,
    )
    session.add(
        AvisAudit(
            rapport_id=rapport.id, auditeur_id=auditeur.id, decision=DecisionAudit.RECOMMANDE_VALIDATION
        )
    )
    session.commit()

    response = _login(admin.email, "s3cret-pass").post(
        f"/api/v1/admin/rapports/{rapport.id}/valider", json={}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "score_incalculable"
    session.expire_all()
    rapport_apres = session.get(ESGReport, rapport.id)
    assert rapport_apres is not None
    assert rapport_apres.status == ReportStatus.PENDING_DECISION
    assert rapport_apres.official_score is None
    assert session.exec(select(ScoreESG).where(ScoreESG.rapport_id == rapport.id)).first() is None
    assert _references_de_version(session, version_de_reference_inedite) == []


def test_premiere_validation_sous_une_nouvelle_version_cree_une_seule_reference(
    session, version_de_reference_inedite
) -> None:
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport_en_validation(session, entreprise.id, auditeur.id)

    response = _login(admin.email, "s3cret-pass").post(
        f"/api/v1/admin/rapports/{rapport.id}/valider", json={}
    )

    assert response.status_code == 200
    references = _references_de_version(session, version_de_reference_inedite)
    assert len(references) == 1
    score = session.exec(select(ScoreESG).where(ScoreESG.rapport_id == rapport.id)).one()
    assert score.configuration_id == references[0].id
    rapport_apres = session.get(ESGReport, rapport.id)
    assert rapport_apres is not None
    assert rapport_apres.official_score == score.valeur_globale


def test_consulter_un_rapport_ou_son_score_ne_cree_aucune_configuration(
    session, version_de_reference_inedite
) -> None:
    """Une lecture (GET) n'écrit jamais : ni le détail d'un rapport (score_public), ni l'aperçu
    « le score serait-il calculable ? » ne créent la ligne de référence manquante."""
    admin = _create_utilisateur(session, Role.ADMIN)
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport_en_validation(session, entreprise.id, auditeur.id)
    authed_client = _login(admin.email, "s3cret-pass")

    detail = authed_client.get(f"/api/v1/admin/rapports/{rapport.id}")
    verification = authed_client.get(f"/api/v1/admin/rapports/{rapport.id}/score-verification")

    assert detail.status_code == 200
    assert detail.json()["score_officiel"] is None
    assert verification.status_code == 200
    assert verification.json()["calculable"] is True
    assert _references_de_version(session, version_de_reference_inedite) == []
