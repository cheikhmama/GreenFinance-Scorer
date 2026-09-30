"""Validation croisée contre un jeu de données public (tâche 3.3)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import col, select

from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import ReportStatus, ReportType, Role, SubmissionChannel
from app.ingestion.models import ESGReport
from app.institution.models import Project, ProjectAssignment, ProjectCompany
from app.researcher.models import ReferenceDatasetRow
from app.scoring.engine import obtenir_configuration_reference
from app.scoring.models import Score
from tests.integration.test_company_registration import _isin_aleatoire, _lei_aleatoire
from tests.integration.test_investor_router import _create_utilisateur, _login

URL = "/api/v1/researcher/reference-datasets"
META = {
    "name": "Kaggle ESG 2024",
    "source_url": "https://www.kaggle.com/datasets/exemple",
    "licence": "CC BY 4.0",
    "scale_min": "0",
    "scale_max": "1000",
    "higher_is_better": "true",
}


def _entreprise(session, global_score: float, *, isin=None, lei=None, publiee=True) -> Company:
    entreprise = Company(
        name=f"Cible {uuid.uuid4()}", sector="Industrie", country="MR", isin=isin, lei=lei,
        published_at=utcnow() if publiee else None,
    )
    session.add(entreprise)
    session.flush()
    rapport = ESGReport(
        company_id=entreprise.id, type=ReportType.RAPPORT_ESG, channel=SubmissionChannel.ENTREPRISE,
        status=ReportStatus.VALIDATED, source_file="rapports/x.pdf", submitted_at=utcnow(),
    )
    session.add(rapport)
    session.flush()
    session.add(
        Score(
            report_id=rapport.id, config_id=obtenir_configuration_reference(session).id,
            global_score=global_score, environmental_score=global_score,
        )
    )
    session.commit()
    return entreprise


def _chercheur_avec_perimetre(session, entreprises: list[Company]):
    institution = _create_utilisateur(session, Role.INSTITUTION)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    projet = Project(institution_id=institution.id, name="Validation")
    session.add(projet)
    session.flush()
    session.add(ProjectAssignment(project_id=projet.id, researcher_id=chercheur.id))
    session.add_all(ProjectCompany(project_id=projet.id, company_id=e.id) for e in entreprises)
    session.commit()
    return chercheur


def _importer(client: TestClient, contenu: str, **meta):
    return client.post(
        URL,
        data={**META, **meta},
        files={"file": ("jeu.csv", contenu.encode("utf-8"), "text/csv")},
    )


def test_validation_croisee_de_bout_en_bout(session) -> None:
    # Plateforme : 40, 60, 80 (global = environnemental). Jeu : même ordre, sur 1 000.
    a = _entreprise(session, 40, isin=_isin_aleatoire())
    b = _entreprise(session, 60, lei=_lei_aleatoire())
    c = _entreprise(session, 80, isin=_isin_aleatoire())
    hors_perimetre = _entreprise(session, 50, isin=_isin_aleatoire())
    sans_score = Company(name="Sans score", sector="X", country="MR", isin=_isin_aleatoire(), published_at=utcnow())
    session.add(sans_score)
    session.commit()
    chercheur = _chercheur_avec_perimetre(session, [a, b, c, sans_score])
    client = _login(chercheur.email)
    contenu = (
        "Company Name;ISIN;LEI;Environmental;Total;Sector\n"
        f"A;{a.isin};;450;450;Industrie\n"
        f"B;;{b.lei};550;550,5;Industrie\n"
        f"C;{c.isin};;900;900;Industrie\n"
        f"C bis;{c.isin};;100;100;Industrie\n"
        f"Hors;{hors_perimetre.isin};;500;500;Industrie\n"
        f"Sans score;{sans_score.isin};;500;500;X\n"
        "Sans id;;;500;500;X\n"
        f"Illisible;{_isin_aleatoire()};;abc;;X\n"
        f"Hors échelle;{_isin_aleatoire()};;1200;;X\n"
    )

    importe = _importer(client, contenu)
    rapport = client.get(f"{URL}/{importe.json()['dataset']['id']}/cross-validation")

    assert importe.status_code == 201, importe.text
    assert importe.json()["imported"] == 6
    assert importe.json()["skipped"] == 3
    assert {ligne["line"] for ligne in importe.json()["skipped_lines"]} == {8, 9, 10}
    assert rapport.status_code == 200, rapport.text
    corps = rapport.json()
    assert corps["matched"] == 3
    motifs = {ligne["line"]: ligne["reason"] for ligne in corps["unmatched_lines"]}
    # L'entreprise hors périmètre n'est jamais distinguée d'une entreprise inconnue.
    assert motifs == {5: "DUPLICATE", 6: "UNKNOWN", 7: "NO_PLATFORM_SCORE"}
    accord = {a["score"]: a for a in corps["agreement"]}
    assert accord["GLOBAL"]["pairs"] == 3
    assert accord["GLOBAL"]["spearman"] == pytest.approx(1)
    # |45 − 40| + |55,05 − 60| + |90 − 80|, sur 3.
    assert accord["GLOBAL"]["mean_absolute_difference"] == pytest.approx((5 + 4.95 + 10) / 3)
    assert accord["SOCIAL"] == {"score": "SOCIAL", "pairs": 0, "spearman": None, "mean_absolute_difference": None}


def test_jeu_sans_ligne_importable_rien_n_est_enregistre(session) -> None:
    chercheur = _chercheur_avec_perimetre(session, [])
    client = _login(chercheur.email)

    reponse = _importer(client, "isin,total\n,10\nFR0000000000,20\n")

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "import_vide"
    assert set(reponse.json()["error"]["fields"]) == {"line_2", "line_3"}
    assert client.get(URL).json() == []


@pytest.mark.parametrize(
    ("meta", "contenu"),
    [
        ({"scale_max": "0"}, "isin,total\nX,1\n"),  # échelle vide
        ({"source_url": "kaggle"}, "isin,total\nX,1\n"),
        ({}, "nom,total\nA,1\n"),  # ni isin ni lei
        ({}, "isin,secteur\nX,Y\n"),  # aucun score
    ],
)
def test_import_refuse(session, meta, contenu) -> None:
    client = _login(_chercheur_avec_perimetre(session, []).email)

    assert _importer(client, contenu, **meta).status_code == 422


def test_jeux_de_donnees_propres_a_leur_auteur(session) -> None:
    entreprise = _entreprise(session, 50, isin=_isin_aleatoire())
    auteur = _login(_chercheur_avec_perimetre(session, [entreprise]).email)
    autre = _login(_chercheur_avec_perimetre(session, []).email)
    investisseur = _login(_create_utilisateur(session, Role.INVESTOR).email)
    dataset_id = _importer(auteur, f"isin,total\n{entreprise.isin},500\n").json()["dataset"]["id"]

    assert autre.get(f"{URL}/{dataset_id}/cross-validation").status_code == 404
    assert autre.delete(f"{URL}/{dataset_id}").status_code == 404
    assert investisseur.get(URL).status_code == 403
    assert [d["id"] for d in auteur.get(URL).json()] == [dataset_id]
    assert auteur.delete(f"{URL}/{dataset_id}").status_code == 204
    session.expire_all()
    assert session.exec(
        select(ReferenceDatasetRow).where(col(ReferenceDatasetRow.dataset_id) == uuid.UUID(dataset_id))
    ).all() == []
