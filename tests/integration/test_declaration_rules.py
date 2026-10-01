"""Règles d'une nouvelle déclaration (tâche 5.9) : une seule déclaration active à la fois, et un
exercice validé ne se déclare plus — sur tous les chemins qui créent un rapport."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.models import User
from app.core.database import utcnow
from app.core.enums import ReportStatus, ReportType, SubmissionChannel
from app.ingestion.models import ESGReport
from tests.integration.test_company_router import (
    _create_entreprise_utilisateur,
    _login,
    _minimal_pdf_bytes,
)

URL = "/api/v1/reports"


@pytest.fixture()
def entreprise(session, jobs_enfiles) -> tuple[User, TestClient]:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    return user, _login(user.email, "s3cret-pass")


def _rapport(session, user: User, statut: ReportStatus, exercice: int, **champs) -> ESGReport:
    assert user.company is not None
    rapport = ESGReport(
        company_id=user.company.id,
        type=champs.pop("type", ReportType.RAPPORT_ESG),
        channel=SubmissionChannel.ENTREPRISE,
        fiscal_year=exercice,
        status=statut,
        source_file="rapports/test/regle.pdf",
        submitted_at=utcnow(),
        **champs,
    )
    session.add(rapport)
    session.commit()
    return rapport


def _ouvrir(client: TestClient, exercice: int, type_: str = "RAPPORT_ESG"):
    return client.post(URL, json={"fiscal_year": exercice, "report_type": type_})


def _deposer(client: TestClient, exercice: int):
    return client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": "RAPPORT_ESG", "annee_reporting": str(exercice)},
    )


@pytest.mark.parametrize(
    "statut", [ReportStatus.IN_AUDIT, ReportStatus.PENDING_DECISION, ReportStatus.REVISION_REQUESTED]
)
def test_une_declaration_en_examen_bloque_toute_nouvelle_declaration(
    session, entreprise, statut
) -> None:
    user, client = entreprise
    _rapport(session, user, statut, 2024)

    ouverture = _ouvrir(client, 2025)
    depot = _deposer(client, 2025)

    for refus in (ouverture, depot):
        assert refus.status_code == 422
        assert refus.json()["error"]["code"] == "declaration_en_cours"
        assert "2024" in refus.json()["error"]["message"]


def test_un_exercice_valide_ne_se_declare_plus_quel_que_soit_le_type(session, entreprise) -> None:
    user, client = entreprise
    _rapport(session, user, ReportStatus.VALIDATED, 2024)

    meme_type = _ouvrir(client, 2024)
    autre_type = _ouvrir(client, 2024, "RAPPORT_CLIMAT")
    depot = _deposer(client, 2024)
    exercice_suivant = _ouvrir(client, 2025)

    for refus in (meme_type, autre_type, depot):
        assert refus.status_code == 422
        assert refus.json()["error"]["code"] == "exercice_deja_valide"
    assert exercice_suivant.status_code == 201


@pytest.mark.parametrize("statut", [ReportStatus.REJECTED, ReportStatus.EXTRACTION_FAILED])
def test_un_rapport_clos_ou_en_echec_ne_retient_pas_lentreprise(session, entreprise, statut) -> None:
    user, client = entreprise
    _rapport(session, user, statut, 2024)

    assert _ouvrir(client, 2024).status_code == 201


def test_une_correction_poursuit_la_declaration_et_libere_lentreprise_apres_decision(
    session, entreprise
) -> None:
    user, client = entreprise
    original = _rapport(session, user, ReportStatus.REVISION_REQUESTED, 2024)

    correction = client.post(
        f"/api/v1/company/rapports/{original.id}/corrections",
        files={"fichier": ("v2.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"annee_reporting": "2024"},
    )
    assert correction.status_code == 201, correction.text
    # La version 2 est maintenant la déclaration active ; la version remplacée ne compte plus.
    assert _ouvrir(client, 2025).json()["error"]["code"] == "declaration_en_cours"

    v2 = session.get(ESGReport, uuid.UUID(correction.json()["id"]))
    assert v2 is not None
    v2.status = ReportStatus.VALIDATED
    session.add(v2)
    session.commit()

    assert _ouvrir(client, 2025).status_code == 201
