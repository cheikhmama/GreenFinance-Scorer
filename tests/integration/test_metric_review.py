"""Revue des valeurs extraites par l'Auditeur (tâche 5.6) : journal append-only, état courant,
effet sur le score et le module carbone, séparation des tâches, pré-score après l'avis."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlmodel import select

from app.audit.models import MetricReview
from app.auth.hashing import hash_password
from app.auth.models import User
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import (
    DataMethod,
    MetricReviewStatus,
    Pillar,
    ReportStatus,
    ReportType,
    Role,
    SubmissionChannel,
)
from app.ingestion.models import CarbonEmission, ESGMetric, ESGReport, Evidence
from app.scoring.engine import valeurs_des_rapports
from tests.integration.test_audit_router import _create_utilisateur, _login


def _dossier(session, auditeur_id: uuid.UUID | None) -> tuple[ESGReport, ESGMetric, ESGMetric, CarbonEmission, User]:
    """Rapport en audit : deux indicateurs notés par la méthodologie, une donnée carbone, et le
    compte titulaire de l'entreprise."""
    titulaire = User(
        email=f"titulaire-{uuid.uuid4()}@example.com",
        role=Role.ENTERPRISE,
        password_hash=hash_password("s3cret-pass"),
        activated_at=utcnow(),
    )
    session.add(titulaire)
    session.flush()
    entreprise = Company(name=f"Revue {uuid.uuid4()}", sector="Mines", country="MR", owner_user_id=titulaire.id)
    session.add(entreprise)
    session.flush()
    rapport = ESGReport(
        company_id=entreprise.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        status=ReportStatus.IN_AUDIT,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
        fiscal_year=2025,
        auditor_id=auditeur_id,
    )
    preuve = Evidence(document_name="r.pdf", year=2025, total_pages=4, page_start=3, page_end=3, excerpt_pdf_path="p.pdf")
    session.add_all([rapport, preuve])
    session.flush()
    conseil = ESGMetric(
        report_id=rapport.id, pillar=Pillar.GOUVERNANCE, metric_code="femmes_conseil_pourcentage",
        value=40.0, unit="%", method=DataMethod.RAPPORTEE, proof_id=preuve.id,
    )
    management = ESGMetric(
        report_id=rapport.id, pillar=Pillar.SOCIAL, metric_code="femmes_management_pourcentage",
        value=30.0, unit="%", method=DataMethod.RAPPORTEE, proof_id=preuve.id,
    )
    scope_1 = CarbonEmission(
        report_id=rapport.id, scope=1, tonnes_co2e=1000.0, year=2025, method=DataMethod.RAPPORTEE,
        proof_id=preuve.id,
    )
    session.add_all([conseil, management, scope_1])
    session.commit()
    return rapport, conseil, management, scope_1, titulaire


@pytest.fixture()
def auditeur(session) -> User:
    return _create_utilisateur(session, Role.AUDITOR)


def _url(rapport: ESGReport) -> str:
    return f"/api/v1/audit/rapports/{rapport.id}/reviews"


def test_revues_journalisees_et_etat_courant(session, auditeur) -> None:
    rapport, conseil, management, scope_1, _ = _dossier(session, auditeur.id)
    client = _login(auditeur.email, "s3cret-pass")

    accepte = client.post(_url(rapport), json={"metric_id": str(conseil.id), "decision": "ACCEPTED"})
    corrige = client.post(
        _url(rapport),
        json={
            "metric_id": str(management.id), "decision": "OVERRIDDEN", "new_value": 35.0,
            "reason": "EXTRACTION_ERROR", "comment": "Lu 30 au lieu de 35 (tableau p. 3).",
        },
    )
    non_trouve = client.post(
        _url(rapport), json={"emission_id": str(scope_1.id), "decision": "NOT_FOUND", "reason": "NOT_IN_SOURCE"}
    )
    # Changer d'avis ajoute une ligne, n'en efface aucune.
    rejoue = client.post(_url(rapport), json={"metric_id": str(conseil.id), "decision": "ACCEPTED"})

    assert [r.status_code for r in (accepte, corrige, non_trouve, rejoue)] == [201] * 4
    assert corrige.json()["original_value"] == 30.0 and corrige.json()["new_value"] == 35.0
    journal = client.get(_url(rapport)).json()
    assert [e["decision"] for e in journal] == ["ACCEPTED", "OVERRIDDEN", "NOT_FOUND", "ACCEPTED"]
    assert all(e["auditor_id"] == str(auditeur.id) for e in journal)
    session.expire_all()
    assert session.get(ESGMetric, management.id).review_status == MetricReviewStatus.OVERRIDDEN  # type: ignore[union-attr]
    assert session.get(ESGMetric, management.id).audited_value == 35.0  # type: ignore[union-attr]
    assert session.get(CarbonEmission, scope_1.id).review_status == MetricReviewStatus.NOT_FOUND  # type: ignore[union-attr]
    # Le score lit la valeur auditée ; une valeur non trouvée sortirait du calcul.
    valeurs = valeurs_des_rapports(session, [rapport.id])[rapport.id]
    assert valeurs[Pillar.SOCIAL]["femmes_management_pourcentage"] == 35.0
    assert valeurs[Pillar.GOUVERNANCE]["femmes_conseil_pourcentage"] == 40.0


def test_valeur_non_trouvee_sort_du_score(session, auditeur) -> None:
    rapport, conseil, _, _, _ = _dossier(session, auditeur.id)
    client = _login(auditeur.email, "s3cret-pass")

    client.post(_url(rapport), json={"metric_id": str(conseil.id), "decision": "NOT_FOUND", "reason": "NOT_IN_SOURCE"})
    session.expire_all()

    valeurs = valeurs_des_rapports(session, [rapport.id])[rapport.id]
    assert "femmes_conseil_pourcentage" not in valeurs[Pillar.GOUVERNANCE]


@pytest.mark.parametrize(
    "corps",
    [
        {"decision": "OVERRIDDEN", "reason": "UNIT_ERROR"},  # correction sans valeur
        {"decision": "NOT_FOUND"},  # sans motif
        {"decision": "ACCEPTED", "new_value": 3.0},  # valeur sans correction
        {"decision": "PENDING"},
    ],
    ids=["correction-sans-valeur", "non-trouve-sans-motif", "valeur-sans-correction", "pending"],
)
def test_revue_incoherente_refusee(session, auditeur, corps) -> None:
    rapport, conseil, _, _, _ = _dossier(session, auditeur.id)

    reponse = _login(auditeur.email, "s3cret-pass").post(_url(rapport), json={"metric_id": str(conseil.id), **corps})

    assert reponse.status_code == 422


def test_separation_des_taches(session, auditeur) -> None:
    rapport, conseil, _, _, _ = _dossier(session, auditeur.id)
    autre_dossier, valeur_ailleurs, _, _, _ = _dossier(session, auditeur.id)
    autre_auditeur = _login(_create_utilisateur(session, Role.AUDITOR).email, "s3cret-pass")
    admin = _login(_create_utilisateur(session, Role.ADMIN).email, "s3cret-pass")
    client = _login(auditeur.email, "s3cret-pass")
    corps = {"metric_id": str(conseil.id), "decision": "ACCEPTED"}

    # Seul l'auditeur affecté revoit ; l'administrateur lit le journal mais n'y écrit pas.
    assert autre_auditeur.post(_url(rapport), json=corps).status_code == 404
    assert admin.post(_url(rapport), json=corps).status_code == 403
    assert admin.get(f"/api/v1/admin/rapports/{rapport.id}/reviews").status_code == 200
    # Une valeur d'un autre rapport n'est jamais revue au titre de celui-ci.
    ailleurs = client.post(_url(rapport), json={"metric_id": str(valeur_ailleurs.id), "decision": "ACCEPTED"})
    assert ailleurs.status_code == 404 and ailleurs.json()["error"]["code"] == "valeur_introuvable"
    # L'auditeur ne décide pas ; l'administrateur ne rend pas d'avis.
    assert client.post(f"/api/v1/admin/rapports/{rapport.id}/valider", json={}).status_code == 403
    assert admin.post(f"/api/v1/audit/rapports/{rapport.id}/avis", json={"decision": "FAVORABLE"}).status_code == 403
    # L'avis rendu clôt la revue.
    assert client.post(f"/api/v1/audit/rapports/{rapport.id}/avis", json={"decision": "FAVORABLE"}).status_code == 201
    close = client.post(_url(rapport), json=corps)
    assert close.status_code == 422 and close.json()["error"]["code"] == "revue_close"
    assert autre_dossier.status == ReportStatus.IN_AUDIT


def test_pre_score_seulement_apres_l_avis(session, auditeur) -> None:
    rapport, _, management, _, _ = _dossier(session, auditeur.id)
    client = _login(auditeur.email, "s3cret-pass")
    client.post(
        _url(rapport),
        json={"metric_id": str(management.id), "decision": "OVERRIDDEN", "new_value": 50.0, "reason": "OTHER"},
    )
    url = f"/api/v1/audit/rapports/{rapport.id}/pre-score"

    avant = client.get(url)
    client.post(f"/api/v1/audit/rapports/{rapport.id}/avis", json={"decision": "FAVORABLE"})
    apres = client.get(url)

    assert avant.status_code == 409 and avant.json()["error"]["code"] == "avis_requis"
    assert apres.status_code == 200, apres.text
    assert apres.json()["computable"] is True
    assert apres.json()["social_score"] is not None
    assert "official_score" not in apres.json()


def test_l_entreprise_ne_voit_pas_la_revue_avant_validation(session, auditeur) -> None:
    rapport, _, management, _, titulaire = _dossier(session, auditeur.id)
    _login(auditeur.email, "s3cret-pass").post(
        _url(rapport),
        json={"metric_id": str(management.id), "decision": "OVERRIDDEN", "new_value": 35.0, "reason": "OTHER"},
    )

    vue = _login(titulaire.email, "s3cret-pass").get(f"/api/v1/company/rapports/{rapport.id}")

    assert vue.status_code == 200
    valeurs = {m["metric_code"]: m for m in vue.json()["metrics"]}
    assert valeurs["femmes_management_pourcentage"]["review_status"] is None
    assert valeurs["femmes_management_pourcentage"]["audited_value"] is None
    assert valeurs["femmes_management_pourcentage"]["value"] == 30.0


def test_le_journal_refuse_modification_et_suppression(session, auditeur) -> None:
    rapport, conseil, _, _, _ = _dossier(session, auditeur.id)
    _login(auditeur.email, "s3cret-pass").post(_url(rapport), json={"metric_id": str(conseil.id), "decision": "ACCEPTED"})
    revue_id = session.exec(select(MetricReview.id).where(MetricReview.report_id == rapport.id)).one()

    for requete in (
        "UPDATE metric_reviews SET comment = 'réécrit' WHERE id = :id",
        "DELETE FROM metric_reviews WHERE id = :id",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(requete), {"id": revue_id})
        session.rollback()
    # Une valeur revue ne disparaît pas sous sa trace.
    with pytest.raises(DBAPIError):
        session.execute(text("DELETE FROM esg_metrics WHERE id = :id"), {"id": conseil.id})
    session.rollback()


def test_le_module_carbone_lit_la_valeur_auditee_ou_ecarte_la_ligne(session, auditeur) -> None:
    from app.investor.carbon import _emissions

    corrige, _, _, scope_corrige, _ = _dossier(session, auditeur.id)
    ecarte, _, _, scope_ecarte, _ = _dossier(session, auditeur.id)
    client = _login(auditeur.email, "s3cret-pass")
    client.post(
        _url(corrige),
        json={"emission_id": str(scope_corrige.id), "decision": "OVERRIDDEN", "new_value": 1200.0, "reason": "UNIT_ERROR"},
    )
    client.post(_url(ecarte), json={"emission_id": str(scope_ecarte.id), "decision": "NOT_FOUND", "reason": "NOT_IN_SOURCE"})
    session.expire_all()

    emissions_corrigees = _emissions(session, session.get(ESGReport, corrige.id))
    emissions_ecartees = _emissions(session, session.get(ESGReport, ecarte.id))

    assert emissions_corrigees is not None and emissions_corrigees.scope_1 is not None
    assert emissions_corrigees.scope_1.tonnes_co2e == 1200.0
    # Jamais comptée comme zéro : simplement absente.
    assert emissions_ecartees is not None and emissions_ecartees.scope_1 is None
