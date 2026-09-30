"""Sessions de déclaration et périmètre multi-tenant (tâche 1.5, /api/v1/reports)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.auth.hashing import hash_password
from app.auth.models import User
from app.core.database import utcnow
from app.core.enums import (
    CompanyStatus,
    ExtractionStatus,
    ReportStatus,
    ReportType,
    Role,
    SubmissionChannel,
)
from app.ingestion.models import ESGReport
from tests.integration.test_company_router import (
    _create_entreprise_utilisateur,
    _login,
    _minimal_pdf_bytes,
)

URL = "/api/v1/reports"


@pytest.fixture()
def _extraction_simulee(jobs_enfiles) -> list:
    """Aucune extraction réelle : on vérifie seulement qu'elle est mise en file au dépôt (tâche 4.1,
    enregistrée par tests/conftest.py::jobs_enfiles)."""
    return jobs_enfiles


@pytest.fixture()
def entreprise(session) -> tuple[User, TestClient]:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    return user, _login(user.email, "s3cret-pass")


def _utilisateur(session, role: Role) -> tuple[User, TestClient]:
    user = User(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        role=role,
        password_hash=hash_password("s3cret-pass"),
    )
    session.add(user)
    session.commit()
    return user, _login(user.email, "s3cret-pass")


def _ouvrir(client: TestClient, **surcharges) -> dict:
    corps = {"fiscal_year": 2024, "report_type": ReportType.RAPPORT_ESG.value, **surcharges}
    reponse = client.post(URL, json=corps)
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def test_ouvrir_une_declaration_cree_un_brouillon_sans_fichier(session, entreprise) -> None:
    user, client = entreprise

    brouillon = _ouvrir(client)

    assert brouillon["status"] == ReportStatus.DRAFT.value
    assert brouillon["extraction_status"] == ExtractionStatus.NOT_STARTED.value
    assert brouillon["company_id"] == str(user.company.id)
    assert brouillon["submitted_at"] is None
    # Les listes historiques de l'espace Entreprise l'affichent aussi (contrat rendu nullable).
    anciens = client.get("/api/v1/company/rapports").json()
    ligne = next(r for r in anciens if r["id"] == brouillon["id"])
    assert ligne["status"] == ReportStatus.DRAFT.value
    assert ligne["submitted_at"] is None
    assert ligne["source_file"] is None


def test_un_seul_brouillon_par_exercice_et_type(session, entreprise) -> None:
    _user, client = entreprise
    _ouvrir(client)

    doublon = client.post(URL, json={"fiscal_year": 2024, "report_type": "RAPPORT_ESG"})
    autre_type = client.post(URL, json={"fiscal_year": 2024, "report_type": "RAPPORT_CLIMAT"})

    assert doublon.status_code == 422
    assert doublon.json()["error"]["code"] == "brouillon_existant"
    assert autre_type.status_code == 201


@pytest.mark.parametrize("annee", [1999, utcnow().year + 1])
def test_exercice_hors_bornes_refuse(session, entreprise, annee) -> None:
    _user, client = entreprise

    assert client.post(URL, json={"fiscal_year": annee, "report_type": "RAPPORT_ESG"}).status_code == 422


def test_entreprise_suspendue_ne_declare_pas(session, entreprise) -> None:
    user, client = entreprise
    user.company.status = CompanyStatus.SUSPENDED
    session.add(user.company)
    session.commit()

    reponse = client.post(URL, json={"fiscal_year": 2024, "report_type": "RAPPORT_ESG"})

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "entreprise_suspendue"


def test_ladministrateur_declare_pour_une_entreprise_designee(session, entreprise) -> None:
    user, _client = entreprise
    _admin, admin = _utilisateur(session, Role.ADMIN)

    sans = admin.post(URL, json={"fiscal_year": 2024, "report_type": "RAPPORT_ESG"})
    avec = _ouvrir(admin, company_id=str(user.company.id))

    assert sans.status_code == 422
    assert sans.json()["error"]["code"] == "entreprise_requise"
    assert avec["company_id"] == str(user.company.id)


def test_perimetre_entreprise_et_auditeur(session, entreprise) -> None:
    _user, client = entreprise
    autre_user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert autre_user.company is not None
    autre = _login(autre_user.email, "s3cret-pass")
    mien = _ouvrir(client)
    dautrui = _ouvrir(autre)
    auditeur, client_auditeur = _utilisateur(session, Role.AUDITOR)
    affecte = ESGReport(
        company_id=autre_user.company.id,
        type=ReportType.RAPPORT_CLIMAT,
        channel=SubmissionChannel.ENTREPRISE,
        fiscal_year=2023,
        status=ReportStatus.PENDING_AUDIT,
        source_file="rapports/test/affecte.pdf",
        submitted_at=utcnow(),
        auditor_id=auditeur.id,
    )
    session.add(affecte)
    session.commit()

    ids_entreprise = {r["id"] for r in client.get(URL).json()["items"]}
    filtre_dautrui = client.get(URL, params={"company_id": str(autre_user.company.id)}).json()
    ids_auditeur = {r["id"] for r in client_auditeur.get(URL).json()["items"]}

    assert mien["id"] in ids_entreprise and dautrui["id"] not in ids_entreprise
    # Le filtre s'ajoute au périmètre, jamais ne le remplace.
    assert filtre_dautrui["items"] == [] and filtre_dautrui["total"] == 0
    assert ids_auditeur == {str(affecte.id)}
    # Hors périmètre : 404, jamais 403 — ne pas confirmer l'existence du rapport d'autrui.
    assert client.get(f"{URL}/{dautrui['id']}").status_code == 404
    assert client_auditeur.get(f"{URL}/{mien['id']}").status_code == 404
    assert client_auditeur.get(f"{URL}/{affecte.id}").status_code == 200


def test_un_role_sans_rapports_est_refuse(session) -> None:
    _investisseur, client = _utilisateur(session, Role.INVESTOR)

    assert client.get(URL).status_code == 403
    assert client.post(URL, json={"fiscal_year": 2024, "report_type": "RAPPORT_ESG"}).status_code == 403


def test_soumettre_un_brouillon_le_depose_et_programme_lextraction(
    session, entreprise, _extraction_simulee
) -> None:
    _user, client = entreprise
    brouillon = _ouvrir(client)

    soumis = client.post(
        f"{URL}/{brouillon['id']}/submit",
        files={"file": ("rapport-2024.pdf", _minimal_pdf_bytes(), "application/pdf")},
    )
    seconde = client.post(
        f"{URL}/{brouillon['id']}/submit",
        files={"file": ("rapport-2024.pdf", _minimal_pdf_bytes(), "application/pdf")},
    )

    assert soumis.status_code == 200
    corps = soumis.json()
    assert corps["id"] == brouillon["id"]
    assert corps["status"] == ReportStatus.SUBMITTED.value
    assert corps["extraction_status"] == ExtractionStatus.QUEUED.value
    assert corps["submitted_at"] is not None
    assert corps["original_filename"] == "rapport-2024.pdf"
    assert [
        (fonction, str(args[0]), args[1], job_id, file)
        for fonction, args, job_id, file in _extraction_simulee
        if fonction == "extract_report"
    ] == [
        ("extract_report", brouillon["id"], 2024, f"extract:{brouillon['id']}", "arq:extraction")
    ]
    assert seconde.status_code == 422
    assert seconde.json()["error"]["code"] == "transition_invalide"


def test_un_fichier_invalide_laisse_le_brouillon_intact(session, entreprise) -> None:
    _user, client = entreprise
    brouillon = _ouvrir(client)

    reponse = client.post(
        f"{URL}/{brouillon['id']}/submit",
        files={"file": ("faux.pdf", b"pas un PDF", "application/pdf")},
    )

    assert reponse.status_code == 422
    session.expire_all()
    rapport = session.get(ESGReport, uuid.UUID(brouillon["id"]))
    assert rapport is not None
    assert rapport.status == ReportStatus.DRAFT
    assert rapport.source_file is None


def test_abandonner_seulement_un_brouillon(session, entreprise) -> None:
    _user, client = entreprise
    brouillon = _ouvrir(client)
    soumis = _ouvrir(client, report_type="RAPPORT_CLIMAT")
    client.post(
        f"{URL}/{soumis['id']}/submit",
        files={"file": ("climat.pdf", _minimal_pdf_bytes(), "application/pdf")},
    )

    abandon = client.delete(f"{URL}/{brouillon['id']}")
    refus = client.delete(f"{URL}/{soumis['id']}")

    assert abandon.status_code == 204
    assert refus.status_code == 422
    session.expire_all()
    assert session.exec(
        select(ESGReport).where(ESGReport.id == uuid.UUID(brouillon["id"]))
    ).first() is None
    # Le brouillon abandonné libère la période : une nouvelle déclaration peut être ouverte.
    assert client.post(URL, json={"fiscal_year": 2024, "report_type": "RAPPORT_ESG"}).status_code == 201
