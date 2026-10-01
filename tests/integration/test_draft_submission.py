"""Brouillon analysé avant soumission, liste de complétude et verrouillage (tâche 5.8)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import col, select

from app.auth.models import User
from app.core.enums import ConfidenceLevel, ReportStatus, Role
from app.core.models import AuditLogEntry, Notification
from app.ingestion.models import ESGReport
from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait
from app.ingestion.supervision import echouer_extractions_bloquees
from tests.integration.test_company_router import (
    _create_entreprise_utilisateur,
    _login,
    _minimal_pdf_bytes,
    _simuler_pipeline_extraction,
)
from tests.integration.test_reporting_sessions import _utilisateur

URL = "/api/v1/reports"

EXTRACTION = ExtractionEntreprise(
    entreprise="Cible Test",
    indicateurs=[
        IndicateurExtrait(
            code="scope_1",
            valeur=100.0,
            unite="tCO2e",
            page_source=3,
            trouve=True,
            valeur_brute="100 tCO2e",
            confiance=ConfidenceLevel.ELEVE,
        ),
        IndicateurExtrait(
            code="femmes_conseil_pourcentage", valeur=40.0, unite="%", page_source=3, trouve=True
        ),
        # Un score auto-déclaré trouvé ne compte pas : ce n'est pas un indicateur à fournir.
        IndicateurExtrait(
            code="score_social_declare", valeur=70.0, unite="/100", page_source=3, trouve=True
        ),
    ],
)


@pytest.fixture()
def entreprise(session, jobs_enfiles) -> tuple[User, TestClient]:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    return user, _login(user.email, "s3cret-pass")


def _brouillon_joint(client: TestClient) -> str:
    ouvert = client.post(URL, json={"fiscal_year": 2024, "report_type": "RAPPORT_ESG"})
    assert ouvert.status_code == 201, ouvert.text
    rapport_id = ouvert.json()["id"]
    joint = client.post(
        f"{URL}/{rapport_id}/file",
        files={"file": ("rapport-2024.pdf", _minimal_pdf_bytes(), "application/pdf")},
    )
    assert joint.status_code == 200, joint.text
    return rapport_id


def _notifications(session, type_: str, rapport_id: str) -> list[Notification]:
    session.expire_all()
    return list(
        session.exec(
            select(Notification).where(
                col(Notification.type) == type_,
                col(Notification.resource_id) == uuid.UUID(rapport_id),
            )
        ).all()
    )


def test_analyse_du_brouillon_puis_soumission_verrouillee(
    session, entreprise, monkeypatch, jobs_enfiles
) -> None:
    from app.ingestion.extractor import run_extraction_pipeline

    _admin, _client_admin = _utilisateur(session, Role.ADMIN)
    _user, client = entreprise
    rapport_id = _brouillon_joint(client)
    assert client.get(f"{URL}/{rapport_id}/checklist").json() == []
    _simuler_pipeline_extraction(monkeypatch, EXTRACTION)

    run_extraction_pipeline(uuid.UUID(rapport_id), 2024)

    session.expire_all()
    rapport = session.get(ESGReport, uuid.UUID(rapport_id))
    assert rapport is not None
    assert rapport.status == ReportStatus.DRAFT
    assert rapport.submitted_at is None
    assert rapport.extraction_finished_at is not None
    # Rien chez l'Admin, pas de PDF de synthèse : le rapport n'est pas soumis.
    assert rapport.synthesis_report_path is None
    assert _notifications(session, "RAPPORT_PRET_A_AFFECTER", rapport_id) == []
    assert len(_notifications(session, "RAPPORT_ANALYSE_TERMINEE", rapport_id)) == 1

    liste = client.get(f"{URL}/{rapport_id}/checklist").json()
    assert liste == [
        {"group": "CARBON", "expected": 5, "found": 1},
        {"group": "ENVIRONNEMENT", "expected": 5, "found": 0},
        {"group": "SOCIAL", "expected": 6, "found": 0},
        {"group": "GOUVERNANCE", "expected": 3, "found": 1},
    ]
    # Des comptes seulement : le détail Entreprise d'un brouillon ne montre aucune valeur.
    detail = client.get(f"/api/v1/company/rapports/{rapport_id}").json()
    assert detail["metrics"] == [] and detail["carbon_data"] == []
    assert detail["declared_global_score"] is None
    assert detail["coverage"]["found"] == 3

    soumis = client.post(f"{URL}/{rapport_id}/submit")
    encore = client.post(f"{URL}/{rapport_id}/submit")
    remplacer = client.post(
        f"{URL}/{rapport_id}/file",
        files={"file": ("autre.pdf", _minimal_pdf_bytes(), "application/pdf")},
    )

    assert soumis.status_code == 200, soumis.text
    recu = soumis.json()
    assert recu["status"] == ReportStatus.AWAITING_ASSIGNMENT.value
    assert recu["submitted_at"] is not None
    assert recu["checksum_sha256"] == rapport.checksum_sha256
    for refus in (encore, remplacer):
        assert refus.status_code == 422
        assert refus.json()["error"]["code"] == "transition_invalide"
    assert len(_notifications(session, "RAPPORT_PRET_A_AFFECTER", rapport_id)) >= 1
    assert len(_notifications(session, "RAPPORT_DEPOSE", rapport_id)) == 1
    journal = session.exec(
        select(AuditLogEntry).where(col(AuditLogEntry.resource_id) == uuid.UUID(rapport_id))
    ).all()
    assert [(e.action, e.new_value) for e in journal] == [
        ("report_submitted", rapport.checksum_sha256)
    ]
    assert ("generate_synthesis_pdf", rapport_id) in [
        (fonction, str(args[0])) for fonction, args, _job_id, _file in jobs_enfiles
    ]
    # Soumis : le détail suit la règle habituelle (valeurs visibles, revue masquée).
    apres = client.get(f"/api/v1/company/rapports/{rapport_id}").json()
    assert len(apres["carbon_data"]) == 1


def test_echec_de_lanalyse_ramene_le_brouillon_et_bloque_la_soumission(
    session, entreprise, monkeypatch
) -> None:
    from app.ingestion.extractor import run_extraction_pipeline

    _user, client = entreprise
    rapport_id = _brouillon_joint(client)
    _simuler_pipeline_extraction(monkeypatch, EXTRACTION)

    def _echec(*_args, **_kwargs):
        raise RuntimeError("docling indisponible pour ce test")

    monkeypatch.setattr("app.ingestion.extractor.docling_pipeline.convert_pdf", _echec)

    run_extraction_pipeline(uuid.UUID(rapport_id), 2024)

    session.expire_all()
    rapport = session.get(ESGReport, uuid.UUID(rapport_id))
    assert rapport is not None
    assert rapport.status == ReportStatus.DRAFT
    assert rapport.extraction_error == "docling_conversion_echouee"
    refus = client.post(f"{URL}/{rapport_id}/submit")
    assert refus.status_code == 422
    assert refus.json()["error"]["code"] == "analyse_non_terminee"
    assert client.get(f"{URL}/{rapport_id}/checklist").json() == []
    # Le même fichier peut être joint de nouveau : ce n'est pas un doublon de lui-même.
    relance = client.post(
        f"{URL}/{rapport_id}/file",
        files={"file": ("rapport-2024.pdf", _minimal_pdf_bytes(), "application/pdf")},
    )
    assert relance.status_code == 200, relance.text
    assert relance.json()["status"] == ReportStatus.EXTRACTING.value
    assert relance.json()["extraction_error"] is None


def test_soumettre_sans_fichier_est_refuse(session, entreprise) -> None:
    _user, client = entreprise
    ouvert = client.post(URL, json={"fiscal_year": 2024, "report_type": "RAPPORT_ESG"}).json()

    refus = client.post(f"{URL}/{ouvert['id']}/submit")

    assert refus.status_code == 422
    assert refus.json()["error"]["code"] == "fichier_manquant"


def test_analyse_bloquee_dun_brouillon_revient_en_brouillon(session, entreprise) -> None:
    from datetime import timedelta

    from app.core.database import utcnow

    _user, client = entreprise
    rapport_id = _brouillon_joint(client)
    session.expire_all()
    rapport = session.get(ESGReport, uuid.UUID(rapport_id))
    assert rapport is not None
    rapport.extraction_started_at = utcnow() - timedelta(days=1)
    session.add(rapport)
    session.commit()

    assert uuid.UUID(rapport_id) in echouer_extractions_bloquees(session)
    session.commit()

    session.refresh(rapport)
    assert rapport.status == ReportStatus.DRAFT
    assert rapport.extraction_error == "delai_depasse"


def test_seuls_lentreprise_et_ladmin_soumettent(session, entreprise) -> None:
    _user, client = entreprise
    rapport_id = _brouillon_joint(client)
    _auditeur, client_auditeur = _utilisateur(session, Role.AUDITOR)

    assert client_auditeur.post(f"{URL}/{rapport_id}/submit").status_code == 403


def test_ouvrir_avec_les_donnees_financieres_de_lexercice(session, entreprise) -> None:
    from datetime import date
    from decimal import Decimal

    from app.core.enums import Currency

    _user, client = entreprise
    sans_devise = client.post(
        URL, json={"fiscal_year": 2024, "report_type": "RAPPORT_ESG", "revenue": "1000"}
    )
    ouvert = client.post(
        URL,
        json={
            "fiscal_year": 2024,
            "report_type": "RAPPORT_ESG",
            "currency": "EUR",
            "revenue": "820000000",
            "enterprise_value": "1450000000",
        },
    )

    assert sans_devise.status_code == 422
    assert ouvert.status_code == 201, ouvert.text
    session.expire_all()
    rapport = session.get(ESGReport, uuid.UUID(ouvert.json()["id"]))
    assert rapport is not None
    assert rapport.revenue == Decimal(820000000)
    assert rapport.revenue_currency == Currency.EUR
    assert rapport.enterprise_value_currency == Currency.EUR
    # Sans date fournie, l'EVIC est datée de la clôture de l'exercice.
    assert rapport.evic_date == date(2024, 12, 31)


def test_la_liste_resume_le_score_officiel_et_la_synthese(session, entreprise) -> None:
    from app.core.database import utcnow

    user, client = entreprise
    valide = ESGReport(
        company_id=user.company.id,
        type="RAPPORT_ESG",
        channel="ENTREPRISE",
        fiscal_year=2023,
        status=ReportStatus.VALIDATED,
        source_file="rapports/test/v.pdf",
        submitted_at=utcnow(),
        checksum_sha256="b" * 64,
        official_score=74.5,
        coverage_rate=0.88,
        config_hash="c" * 64,
        synthesis_report_path="synthese/v.pdf",
    )
    session.add(valide)
    session.commit()

    ligne = next(
        r for r in client.get("/api/v1/company/rapports").json() if r["id"] == str(valide.id)
    )

    assert ligne["official_global_score"] == 74.5
    assert ligne["coverage_rate"] == 0.88
    assert ligne["config_hash"] == "c" * 64
    assert ligne["synthesis_available"] is True
    assert "synthesis_report_path" not in ligne
