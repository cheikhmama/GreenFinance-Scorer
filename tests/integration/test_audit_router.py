import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.audit.models import AuditOpinion
from app.auth.hashing import hash_password
from app.auth.models import User
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import (
    AuditDecision,
    DataMethod,
    Pillar,
    ReportStatus,
    ReportType,
    Role,
    SubmissionChannel,
)
from app.core.models import Notification
from app.ingestion.models import (
    CarbonEmission,
    ESGMetric,
    ESGReport,
    Evidence,
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
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        status=ReportStatus.IN_AUDIT if auditeur_id else ReportStatus.AWAITING_ASSIGNMENT,
        source_file="rapports/test/dummy.pdf",
        extraction_finished_at=utcnow(),
        auditor_id=auditeur_id,
        submitted_at=utcnow(),
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
    preuve = Evidence(
        document_name="rapport.pdf",
        year=2024,
        total_pages=25,
        page_start=3,
        page_end=3,
        excerpt_pdf_path="preuves/test/page_3.pdf",
    )
    session.add(preuve)
    session.commit()
    session.add(
        ESGMetric(
            report_id=rapport.id,
            pillar=Pillar.ENVIRONNEMENT,
            metric_code="intensite_scope_1_2_marketbased",
            value=42.0,
            unit="gCO2e/kWh",
            method=DataMethod.RAPPORTEE,
            proof_id=preuve.id,
        )
    )
    session.add(
        CarbonEmission(
            report_id=rapport.id,
            scope=1,
            tonnes_co2e=100.0,
            year=2024,
            method=DataMethod.RAPPORTEE,
            pcaf_data_quality=3,
            proof_id=preuve.id,
        )
    )
    session.commit()

    authed_client = _login(auditeur.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/audit/rapports/{rapport.id}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["metrics"]) == 1
    assert body["metrics"][0]["metric_code"] == "intensite_scope_1_2_marketbased"
    assert body["metrics"][0]["proof"]["page_start"] == 3
    assert len(body["carbon_data"]) == 1
    assert body["carbon_data"][0]["scope"] == 1


def test_soumettre_avis_fait_passer_le_statut_en_validation(session) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    rapport = _create_rapport_affecte(session, auditeur.id)

    authed_client = _login(auditeur.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/audit/rapports/{rapport.id}/avis",
        json={"decision": "FAVORABLE", "comment": "Données cohérentes."},
    )

    assert response.status_code == 201
    assert response.json()["decision"] == AuditDecision.FAVORABLE.value
    assert response.json()["auditor_id"] == str(auditeur.id)

    session.refresh(rapport)
    assert rapport.status == ReportStatus.PENDING_DECISION
    avis = session.exec(select(AuditOpinion).where(AuditOpinion.report_id == rapport.id)).first()
    assert avis is not None
    assert avis.auditor_id == auditeur.id


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
        json={"decision": "UNFAVORABLE", "comment": "Données incohérentes."},
    )

    notification = session.exec(
        select(Notification).where(
            Notification.user_id == admin.id, Notification.type == "RAPPORT_AVIS_RENDU_ADMIN"
        )
    ).one()
    assert notification.resource_id == rapport.id
    assert "défavorable" in notification.message

    notification_inactif = session.exec(
        select(Notification).where(
            Notification.user_id == admin_inactif.id,
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
        json={"decision": "FAVORABLE"},
    )
    assert premiere.status_code == 201

    deuxieme = authed_client.post(
        f"/api/v1/audit/rapports/{rapport.id}/avis",
        json={"decision": "UNFAVORABLE", "comment": "Changement d'avis."},
    )

    assert deuxieme.status_code == 422
    assert deuxieme.json()["error"]["code"] == "avis_deja_soumis"


@pytest.mark.parametrize(
    "decision", ["FAVORABLE", "FAVORABLE_WITH_RESERVATIONS", "CORRECTION_REQUIRED", "UNFAVORABLE"]
)
def test_soumettre_avis_accepte_les_quatre_avis(session, decision: str) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    rapport = _create_rapport_affecte(session, auditeur.id)
    authed_client = _login(auditeur.email, "s3cret-pass")

    response = authed_client.post(
        f"/api/v1/audit/rapports/{rapport.id}/avis",
        json={"decision": decision, "comment": "Motif de l'avis."},
    )

    assert response.status_code == 201
    assert response.json()["decision"] == decision


@pytest.mark.parametrize("decision", ["FAVORABLE_WITH_RESERVATIONS", "CORRECTION_REQUIRED", "UNFAVORABLE"])
def test_avis_non_favorable_exige_un_commentaire(session, decision: str) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    rapport = _create_rapport_affecte(session, auditeur.id)

    response = _login(auditeur.email, "s3cret-pass").post(
        f"/api/v1/audit/rapports/{rapport.id}/avis", json={"decision": decision, "comment": "  "}
    )

    assert response.status_code == 422


def test_historique_liste_mes_avis_les_plus_recents_dabord(session) -> None:
    auditeur = _create_utilisateur(session, Role.AUDITOR)
    autre_auditeur = _create_utilisateur(session, Role.AUDITOR)
    rapport_a = _create_rapport_affecte(session, auditeur.id)
    rapport_b = _create_rapport_affecte(session, auditeur.id)
    rapport_dautrui = _create_rapport_affecte(session, autre_auditeur.id)
    authed_client = _login(auditeur.email, "s3cret-pass")

    authed_client.post(
        f"/api/v1/audit/rapports/{rapport_a.id}/avis", json={"decision": "FAVORABLE"}
    )
    authed_client.post(
        f"/api/v1/audit/rapports/{rapport_b.id}/avis",
        json={"decision": "UNFAVORABLE", "comment": "Données carbone sans preuve."},
    )
    _login(autre_auditeur.email, "s3cret-pass").post(
        f"/api/v1/audit/rapports/{rapport_dautrui.id}/avis",
        json={"decision": "FAVORABLE"},
    )

    response = authed_client.get("/api/v1/audit/historique")

    assert response.status_code == 200
    rapport_ids = [item["report_id"] for item in response.json()]
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
        json={"decision": "FAVORABLE"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_lister_mes_dossiers_avec_role_entreprise_est_rejete(session) -> None:
    user = _create_utilisateur(session, Role.ENTERPRISE)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.get("/api/v1/audit/rapports")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"
