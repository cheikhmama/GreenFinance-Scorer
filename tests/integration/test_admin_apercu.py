"""Tests de l'Aperçu global multi-acteurs Administrateur (app/admin/apercu.py) — statistiques par
acteur, performance ESG agrégée, et listes de détail (indicateur → liste filtrée).

Pas d'isolation transactionnelle entre tests sur cette base (voir tests/integration/
test_admin_router.py) : chaque test qui compte des éléments filtre sur un marqueur unique plutôt
que d'asserter un total exact sur une table partagée entre sessions de test.
"""

import uuid

from fastapi.testclient import TestClient

from app.auth.hashing import hash_password
from app.auth.models import Utilisateur
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import (
    CanalDepot,
    DevisePosition,
    ReportStatus,
    Role,
    StatutAnalyse,
    StatutProjet,
    TypeRapport,
)
from app.ingestion.models import ESGReport
from app.institution.models import Projet
from app.investor.models import Portefeuille
from app.main import app
from app.researcher.models import Analyse
from app.scoring.engine import obtenir_configuration_reference
from app.scoring.models import ScoreESG

client = TestClient(app, base_url="https://testserver")


def _create_utilisateur(session, role: Role, *, password: str = "s3cret-pass") -> Utilisateur:
    user = Utilisateur(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        mot_de_passe_hache=hash_password(password),
        role=role,
        actif=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _login(email: str, password: str) -> TestClient:
    authed_client = TestClient(app, base_url="https://testserver")
    response = authed_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})
    return authed_client


def test_apercu_acteurs_renvoie_les_quatre_blocs(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.get("/api/v1/admin/apercu-acteurs")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"auditeurs", "investisseurs", "chercheurs", "institutions"}
    assert set(body["auditeurs"]) == {"dossiers_affectes", "avis_rendus"}
    assert set(body["investisseurs"]) == {
        "portefeuilles_non_archives",
        "positions_declarees",
        "entreprises_distinctes",
    }


def test_performance_esg_a_une_couverture_coherente(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.get("/api/v1/admin/performance-esg")

    assert response.status_code == 200
    body = response.json()
    # Jamais plus d'entreprises avec un score que d'entreprises dans le périmètre.
    assert body["entreprises_avec_score"] <= body["entreprises_perimetre"]
    assert len(body["distribution"]) == 5
    # La couverture ne fabrique jamais une moyenne sans substance.
    if body["entreprises_avec_score"] == 0:
        assert body["score_global_moyen"] is None


def test_entreprises_avec_score_distingue_score_absent_de_zero(session) -> None:
    marqueur = f"secteur-{uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)

    entreprise_sans_score = Company(
        name=f"Sans score {uuid.uuid4()}",
        sector=marqueur,
        country="France",
        published_at=utcnow(),
    )
    session.add(entreprise_sans_score)

    entreprise_avec_score = Company(
        name=f"Avec score {uuid.uuid4()}", sector=marqueur, country="France", published_at=utcnow()
    )
    session.add(entreprise_avec_score)
    session.commit()

    rapport = ESGReport(
        company_id=entreprise_avec_score.id,
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.ENTREPRISE,
        status=ReportStatus.VALIDATED,
        source_file="rapports/test/dummy.pdf",
    )
    session.add(rapport)
    session.commit()
    configuration = obtenir_configuration_reference(session)
    session.add(
        ScoreESG(
            rapport_id=rapport.id,
            configuration_id=configuration.id,
            valeur_globale=72.0,
            score_environnement=80.0,
            score_social=None,
            score_gouvernance=65.0,
        )
    )
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/entreprises/scores", params={"secteur": marqueur, "page_size": 50}
    )

    assert response.status_code == 200
    par_id = {item["id"]: item for item in response.json()["items"]}
    assert par_id[str(entreprise_sans_score.id)]["score_global"] is None
    assert par_id[str(entreprise_avec_score.id)]["score_global"] == 72.0
    assert par_id[str(entreprise_avec_score.id)]["score_social"] is None


def test_charge_auditeurs_reflete_les_dossiers_affectes(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    auditeur = _create_utilisateur(session, Role.AUDITEUR)
    entreprise = Company(name=f"Cible {uuid.uuid4()}", sector="Technologies", country="France")
    session.add(entreprise)
    session.commit()
    session.add(
        ESGReport(
            company_id=entreprise.id,
            type=TypeRapport.RAPPORT_ESG,
            channel=CanalDepot.ENTREPRISE,
            status=ReportStatus.PENDING_AUDIT,
            source_file="rapports/test/dummy.pdf",
            auditor_id=auditeur.id,
            assigned_at=utcnow(),
        )
    )
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/auditeurs/charge", params={"recherche": auditeur.email, "page_size": 10}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["dossiers_affectes"] == 1
    assert items[0]["dossiers_en_retard"] == 0


def test_portefeuilles_admin_liste_un_portefeuille_non_archive(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    marqueur = f"portefeuille-{uuid.uuid4()}"
    session.add(
        Portefeuille(
            investisseur_id=investisseur.id, nom=marqueur, devise_reference=DevisePosition.EUR
        )
    )
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/portefeuilles", params={"recherche": marqueur, "page_size": 10}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["investisseur_email"] == investisseur.email
    assert items[0]["nombre_positions"] == 0


def test_projets_admin_filtre_par_statut(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    institution = _create_utilisateur(session, Role.INSTITUTION)
    marqueur = f"projet-{uuid.uuid4()}"
    session.add(Projet(institution_id=institution.id, nom=marqueur, statut=StatutProjet.OUVERT))
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/projets", params={"statut": "OUVERT", "page_size": 50}
    )

    assert response.status_code == 200
    noms = [item["nom"] for item in response.json()["items"]]
    assert marqueur in noms


def test_analyses_admin_filtre_par_statut(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    institution = _create_utilisateur(session, Role.INSTITUTION)
    chercheur = _create_utilisateur(session, Role.CHERCHEUR)
    marqueur = f"analyse-{uuid.uuid4()}"
    projet = Projet(institution_id=institution.id, nom=f"Projet {marqueur}")
    session.add(projet)
    session.commit()
    session.add(
        Analyse(
            projet_id=projet.id,
            chercheur_id=chercheur.id,
            titre=marqueur,
            contenu="contenu de test",
            statut=StatutAnalyse.SOUMISE,
        )
    )
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/analyses", params={"statut": "SOUMISE", "page_size": 50}
    )

    assert response.status_code == 200
    titres = [item["titre"] for item in response.json()["items"]]
    assert marqueur in titres
