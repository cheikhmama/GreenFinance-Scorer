import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.audit.models import AvisAudit
from app.auth.hashing import hash_password
from app.auth.models import User
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Company
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
from app.core.models import Notification
from app.ingestion.models import (
    DonneeCarbone,
    ESGMetric,
    ESGReport,
    PreuveDocumentaire,
)
from app.main import app

client = TestClient(app, base_url="https://testserver")


def _create_utilisateur(session, role: Role, *, password: str = "s3cret-pass") -> User:
    user = User(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        password_hash=hash_password(password),
        role=role,
        active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_rapport_affecte(session, auditeur_id: uuid.UUID | None) -> ESGReport:
    entreprise = Company(name=f"Cible {uuid.uuid4()}", sector="Technologies", country="France")
    session.add(entreprise)
    session.commit()
    rapport = ESGReport(
        company_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.ENTREPRISE,
        status=ReportStatus.PENDING_AUDIT if auditeur_id else ReportStatus.SUBMITTED,
        source_file="rapports/test/dummy.pdf",
        extraction_finished_at=utcnow(), extraction_status=ExtractionStatus.DONE,
        auditor_id=auditeur_id,
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)
    return rapport


def _login(email: str, password: str) -> TestClient:
    authed_client = TestClient(app, base_url="https://testserver")
    response = authed_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})
    return authed_client


def test_lister_mes_dossiers_ne_montre_que_mes_rapports_affectes(session) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    autre_auditeur = _create_utilisateur(session, Role.AUDITOR)
    mon_rapport = _create_rapport_affecte(session, auditeur.id)
    _create_rapport_affecte(session, autre_auditeur.id)

    authed_client = _login(auditeur.email, "s3cret-pass")
    response = authed_client.get("/api/v1/audit/rapports")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(mon_rapport.id) in ids
    assert len(ids) == 1


def test_consulter_dossier_dun_autre_auditeur_est_404(session) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    autre_auditeur = _create_utilisateur(session, Role.AUDITOR)
    rapport = _create_rapport_affecte(session, autre_auditeur.id)

    authed_client = _login(auditeur.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/audit/rapports/{rapport.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "rapport_introuvable"


def test_consulter_dossier_retourne_indicateurs_et_donnees_carbone(session) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    rapport = _create_rapport_affecte(session, auditeur.id)
    preuve = PreuveDocumentaire(
        nom_document="rapport.pdf",
        annee=2024,
        nombre_pages_total=25,
        page_debut=3,
        page_fin=3,
        pdf_extrait_genere="preuves/test/page_3.pdf",
    )
    session.add(preuve)
    session.commit()
    session.add(
        ESGMetric(
            report_id=rapport.id,
            pillar=Pilier.ENVIRONNEMENT,
            metric_code="intensite_scope_1_2_marketbased",
            value=42.0,
            unit="gCO2e/kWh",
            method=MethodeDonnee.RAPPORTEE,
            proof_id=preuve.id,
        )
    )
    session.add(
        DonneeCarbone(
            rapport_id=rapport.id,
            scope=1,
            valeur_tonnes_co2e=100.0,
            annee=2024,
            methode=MethodeDonnee.RAPPORTEE,
            score_qualite_pcaf=3,
            preuve_id=preuve.id,
        )
    )
    session.commit()

    authed_client = _login(auditeur.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/audit/rapports/{rapport.id}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["indicateurs"]) == 1
    assert body["indicateurs"][0]["code"] == "intensite_scope_1_2_marketbased"
    assert body["indicateurs"][0]["preuve"]["page_debut"] == 3
    assert len(body["donnees_carbone"]) == 1
    assert body["donnees_carbone"][0]["scope"] == 1


def test_soumettre_avis_fait_passer_le_statut_en_validation(session) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    rapport = _create_rapport_affecte(session, auditeur.id)

    authed_client = _login(auditeur.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/audit/rapports/{rapport.id}/avis",
        json={"decision": "RECOMMANDE_VALIDATION", "commentaire": "Données cohérentes."},
    )

    assert response.status_code == 201
    assert response.json()["decision"] == DecisionAudit.RECOMMANDE_VALIDATION.value
    assert response.json()["auditeur_id"] == str(auditeur.id)

    session.refresh(rapport)
    assert rapport.status == ReportStatus.PENDING_DECISION
    avis = session.exec(select(AvisAudit).where(AvisAudit.rapport_id == rapport.id)).first()
    assert avis is not None
    assert avis.auditeur_id == auditeur.id


def test_soumettre_avis_notifie_les_administrateurs_actifs(session) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    admin = _create_utilisateur(session, Role.ADMIN)
    admin_inactif = _create_utilisateur(session, Role.ADMIN)
    admin_inactif.active = False
    session.add(admin_inactif)
    session.commit()
    rapport = _create_rapport_affecte(session, auditeur.id)
    authed_client = _login(auditeur.email, "s3cret-pass")

    authed_client.post(
        f"/api/v1/audit/rapports/{rapport.id}/avis",
        json={"decision": "RECOMMANDE_REJET", "commentaire": "Données incohérentes."},
    )

    notification = session.exec(
        select(Notification).where(
            Notification.utilisateur_id == admin.id, Notification.type == "RAPPORT_AVIS_RENDU_ADMIN"
        )
    ).one()
    assert notification.id_ressource == rapport.id
    assert "rejet" in notification.message

    notification_inactif = session.exec(
        select(Notification).where(
            Notification.utilisateur_id == admin_inactif.id,
            Notification.type == "RAPPORT_AVIS_RENDU_ADMIN",
        )
    ).first()
    assert notification_inactif is None


def test_soumettre_avis_deux_fois_est_rejete(session) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    rapport = _create_rapport_affecte(session, auditeur.id)
    authed_client = _login(auditeur.email, "s3cret-pass")

    premiere = authed_client.post(
        f"/api/v1/audit/rapports/{rapport.id}/avis",
        json={"decision": "RECOMMANDE_VALIDATION"},
    )
    assert premiere.status_code == 201

    deuxieme = authed_client.post(
        f"/api/v1/audit/rapports/{rapport.id}/avis",
        json={"decision": "RECOMMANDE_REJET"},
    )

    assert deuxieme.status_code == 422
    assert deuxieme.json()["error"]["code"] == "avis_deja_soumis"


@pytest.mark.parametrize(
    "decision", ["RECOMMANDE_VALIDATION", "RECOMMANDE_REJET", "DEMANDE_CLARIFICATION"]
)
def test_soumettre_avis_accepte_les_trois_recommandations(session, decision: str) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    rapport = _create_rapport_affecte(session, auditeur.id)
    authed_client = _login(auditeur.email, "s3cret-pass")

    response = authed_client.post(
        f"/api/v1/audit/rapports/{rapport.id}/avis",
        json={"decision": decision},
    )

    assert response.status_code == 201
    assert response.json()["decision"] == decision


def test_historique_liste_mes_avis_les_plus_recents_dabord(session) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    autre_auditeur = _create_utilisateur(session, Role.AUDITOR)
    rapport_a = _create_rapport_affecte(session, auditeur.id)
    rapport_b = _create_rapport_affecte(session, auditeur.id)
    rapport_dautrui = _create_rapport_affecte(session, autre_auditeur.id)
    authed_client = _login(auditeur.email, "s3cret-pass")

    authed_client.post(
        f"/api/v1/audit/rapports/{rapport_a.id}/avis", json={"decision": "RECOMMANDE_VALIDATION"}
    )
    authed_client.post(
        f"/api/v1/audit/rapports/{rapport_b.id}/avis", json={"decision": "RECOMMANDE_REJET"}
    )
    _login(autre_auditeur.email, "s3cret-pass").post(
        f"/api/v1/audit/rapports/{rapport_dautrui.id}/avis",
        json={"decision": "RECOMMANDE_VALIDATION"},
    )

    response = authed_client.get("/api/v1/audit/historique")

    assert response.status_code == 200
    rapport_ids = [item["rapport_id"] for item in response.json()]
    assert str(rapport_a.id) in rapport_ids
    assert str(rapport_b.id) in rapport_ids
    assert str(rapport_dautrui.id) not in rapport_ids
    # Le plus récent (rapport_b, soumis en second) apparaît avant rapport_a.
    assert rapport_ids.index(str(rapport_b.id)) < rapport_ids.index(str(rapport_a.id))


def test_historique_sans_authentification_est_rejete() -> None:
    response = client.get("/api/v1/audit/historique")

    assert response.status_code == 401


def test_soumettre_avis_sans_authentification_est_rejete() -> None:
    response = client.post(
        f"/api/v1/audit/rapports/{uuid.uuid4()}/avis",
        json={"decision": "RECOMMANDE_VALIDATION"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_lister_mes_dossiers_avec_role_entreprise_est_rejete(session) -> None:
    user = _create_utilisateur(session, Role.ENTERPRISE)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.get("/api/v1/audit/rapports")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"
