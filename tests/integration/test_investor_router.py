import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.auth.hashing import hash_password
from app.auth.models import Utilisateur
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Entreprise
from app.core.database import utcnow
from app.core.enums import CanalDepot, MethodeDonnee, Role, StatutRapport, TypeRapport
from app.ingestion.models import (
    DonneeCarbone,
    PreuveDocumentaire,
    RapportESG,
)
from app.main import app
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


def _login(email: str, password: str = "s3cret-pass") -> TestClient:
    authed_client = TestClient(app, base_url="https://testserver")
    response = authed_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})
    return authed_client


def _entreprise_publiee(
    session,
    *,
    secteur: str = "Industrie",
    pays: str = "France",
    actif: bool = True,
    montant_minimum: float | None = None,
    score_global: float = 70.0,
    score_e: float | None = 65.0,
    score_s: float | None = 75.0,
    score_g: float | None = 80.0,
    scope_1: float = 100.0,
) -> Entreprise:
    entreprise = Entreprise(
        nom=f"Cible {uuid.uuid4()}",
        secteur=secteur,
        pays=pays,
        actif=actif,
        montant_minimum_investissement=montant_minimum,
        date_publication=utcnow(),
    )
    session.add(entreprise)
    session.commit()

    rapport = RapportESG(
        entreprise_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        statut=StatutRapport.VALIDE,
        fichier_source="rapports/test/dummy.pdf",
    )
    session.add(rapport)
    session.commit()

    preuve = PreuveDocumentaire(
        nom_document="rapport-test.pdf",
        annee=2025,
        nombre_pages_total=1,
        page_debut=1,
        page_fin=1,
        pdf_extrait_genere="preuves/test/page_1.pdf",
    )
    session.add(preuve)
    session.commit()

    for scope, categorie, valeur in [
        (1, None, scope_1),
        (2, "market_based", 50.0),
        (2, "location_based", 60.0),
        (3, None, 1000.0),
    ]:
        session.add(
            DonneeCarbone(
                rapport_id=rapport.id,
                scope=scope,
                categorie_ges=categorie,
                valeur_tonnes_co2e=valeur,
                annee=2025,
                methode=MethodeDonnee.RAPPORTEE,
                score_qualite_pcaf=3,
                preuve_id=preuve.id,
            )
        )
    session.commit()

    configuration = obtenir_configuration_reference(session)
    session.add(
        ScoreESG(
            rapport_id=rapport.id,
            configuration_id=configuration.id,
            valeur_globale=score_global,
            score_environnement=score_e,
            score_social=score_s,
            score_gouvernance=score_g,
        )
    )
    session.commit()
    session.refresh(entreprise)
    return entreprise


def _entreprise_non_publiee(session) -> Entreprise:
    entreprise = Entreprise(nom=f"Cible {uuid.uuid4()}", secteur="Industrie", pays="France")
    session.add(entreprise)
    session.commit()
    session.refresh(entreprise)
    return entreprise


def test_lister_entreprises_ne_montre_que_les_publiees_avec_leur_score(session) -> None:
    publiee = _entreprise_publiee(session, score_global=72.4)
    _entreprise_non_publiee(session)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)

    response = authed.get("/api/v1/investor/entreprises", params={"recherche": publiee.nom})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(publiee.id)
    assert items[0]["score"]["valeur_globale"] == 72.4
    assert items[0]["carbone"]["scope_1"] == 100.0


def test_consulter_entreprise_publiee_retourne_indicateurs_et_carbone_avec_preuve(session) -> None:
    publiee = _entreprise_publiee(session)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)

    response = authed.get(f"/api/v1/investor/entreprises/{publiee.id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["donnees_carbone"]) == 4
    assert body["donnees_carbone"][0]["preuve"]["pdf_extrait_genere"] == "preuves/test/page_1.pdf"


def test_consulter_entreprise_non_publiee_est_introuvable(session) -> None:
    non_publiee = _entreprise_non_publiee(session)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)

    response = authed.get(f"/api/v1/investor/entreprises/{non_publiee.id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "entreprise_introuvable"


def test_comparer_deux_entreprises_publiees(session) -> None:
    a = _entreprise_publiee(session, score_global=60.0)
    b = _entreprise_publiee(session, score_global=90.0)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)

    response = authed.get("/api/v1/investor/comparaison", params={"entreprise_ids": [str(a.id), str(b.id)]})
    assert response.status_code == 200
    scores = {item["id"]: item["score"]["valeur_globale"] for item in response.json()}
    assert scores == {str(a.id): 60.0, str(b.id): 90.0}


def test_creer_portefeuille_puis_le_retrouver_dans_mes_portefeuilles(session) -> None:
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)

    creation = authed.post(
        "/api/v1/investor/portefeuilles", json={"nom": "Portefeuille vert", "devise_reference": "EUR"}
    )
    assert creation.status_code == 201
    portefeuille_id = creation.json()["id"]

    liste = authed.get("/api/v1/investor/portefeuilles", params={"recherche": "Portefeuille vert"})
    assert liste.status_code == 200
    assert [item["id"] for item in liste.json()["items"]] == [portefeuille_id]


def _creer_portefeuille(authed: TestClient, *, devise: str = "EUR") -> str:
    response = authed.post(
        "/api/v1/investor/portefeuilles", json={"nom": f"Portefeuille {uuid.uuid4()}", "devise_reference": devise}
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_ajouter_position_sur_entreprise_non_publiee_est_refuse(session) -> None:
    non_publiee = _entreprise_non_publiee(session)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed)

    response = authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
        json={
            "entreprise_id": str(non_publiee.id),
            "montant": 1000.0,
            "devise": "EUR",
            "type_duree": "OUVERTE",
            "date_debut": utcnow().isoformat(),
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "entreprise_introuvable"


def test_ajouter_position_sur_entreprise_suspendue_est_refuse(session) -> None:
    suspendue = _entreprise_publiee(session, actif=False)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed)

    response = authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
        json={
            "entreprise_id": str(suspendue.id),
            "montant": 1000.0,
            "devise": "EUR",
            "type_duree": "OUVERTE",
            "date_debut": utcnow().isoformat(),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "entreprise_suspendue"


def test_ajouter_position_sous_le_montant_minimum_est_refuse(session) -> None:
    cible = _entreprise_publiee(session, montant_minimum=5000.0)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed)

    response = authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
        json={
            "entreprise_id": str(cible.id),
            "montant": 100.0,
            "devise": "EUR",
            "type_duree": "OUVERTE",
            "date_debut": utcnow().isoformat(),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "montant_insuffisant"


def test_ajouter_position_fixe_sans_date_fin_est_refuse_proprement(session) -> None:
    """Une pydantic.ValidationError levée par PositionPortefeuille ne doit jamais devenir un 500
    (voir app/investor/portfolio.py::_construire_position)."""
    cible = _entreprise_publiee(session)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed)

    response = authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
        json={
            "entreprise_id": str(cible.id),
            "montant": 1000.0,
            "devise": "EUR",
            "type_duree": "FIXE",
            "date_debut": (utcnow() + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "position_invalide"


def test_ajouter_position_puis_consulter_le_portefeuille_calcule_le_score_agrege(session) -> None:
    a = _entreprise_publiee(session, score_global=60.0, score_e=50.0, score_s=70.0, score_g=80.0)
    b = _entreprise_publiee(session, score_global=90.0, score_e=95.0, score_s=None, score_g=95.0)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed, devise="EUR")

    for entreprise, montant in [(a, 1000.0), (b, 1000.0)]:
        reponse = authed.post(
            f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
            json={
                "entreprise_id": str(entreprise.id),
                "montant": montant,
                "devise": "EUR",
                "type_duree": "OUVERTE",
                "date_debut": utcnow().isoformat(),
            },
        )
        assert reponse.status_code == 201

    detail = authed.get(f"/api/v1/investor/portefeuilles/{portefeuille_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["nombre_positions"] == 2
    assert body["montant_total"] == 2000.0
    # (1000*60 + 1000*90) / 2000 = 75 ; score_social agrégé n'inclut QUE la position couverte (a).
    assert body["score_esg_agrege"] == 75.0
    assert body["score_social_agrege"] == 70.0
    assert body["couverture_esg"] == 100.0


def test_ajouter_position_fermer_puis_lister_etats(session) -> None:
    cible = _entreprise_publiee(session)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed)

    ajout = authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
        json={
            "entreprise_id": str(cible.id),
            "montant": 500.0,
            "devise": "EUR",
            "type_duree": "OUVERTE",
            "date_debut": utcnow().isoformat(),
        },
    )
    assert ajout.status_code == 201
    position_id = ajout.json()["id"]
    assert ajout.json()["etat"] == "ACTIVE"

    fermeture = authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions/{position_id}/fermer", json={}
    )
    assert fermeture.status_code == 200
    assert fermeture.json()["etat"] == "CLOTUREE"

    double_fermeture = authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions/{position_id}/fermer", json={}
    )
    assert double_fermeture.status_code == 422
    assert double_fermeture.json()["error"]["code"] == "position_deja_cloturee"


def test_position_planifiee_modifiable_et_supprimable(session) -> None:
    cible = _entreprise_publiee(session)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed)

    ajout = authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
        json={
            "entreprise_id": str(cible.id),
            "montant": 500.0,
            "devise": "EUR",
            "type_duree": "OUVERTE",
            "date_debut": (utcnow() + timedelta(days=5)).isoformat(),
        },
    )
    assert ajout.status_code == 201
    assert ajout.json()["etat"] == "PLANIFIEE"
    position_id = ajout.json()["id"]

    modification = authed.patch(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions/{position_id}",
        json={
            "montant": 800.0,
            "devise": "EUR",
            "type_duree": "OUVERTE",
            "date_debut": (utcnow() + timedelta(days=5)).isoformat(),
        },
    )
    assert modification.status_code == 200
    assert modification.json()["montant_investi"] == 800.0
    nouvelle_position_id = modification.json()["id"]

    suppression = authed.delete(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions/{nouvelle_position_id}"
    )
    assert suppression.status_code == 204

    detail = authed.get(f"/api/v1/investor/portefeuilles/{portefeuille_id}")
    assert detail.json()["nombre_positions"] == 0


def test_position_active_non_modifiable_ni_supprimable(session) -> None:
    cible = _entreprise_publiee(session)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed)

    ajout = authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
        json={
            "entreprise_id": str(cible.id),
            "montant": 500.0,
            "devise": "EUR",
            "type_duree": "OUVERTE",
            "date_debut": utcnow().isoformat(),
        },
    )
    position_id = ajout.json()["id"]

    suppression = authed.delete(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions/{position_id}"
    )
    assert suppression.status_code == 422
    assert suppression.json()["error"]["code"] == "position_non_supprimable"


def test_portefeuille_avec_positions_ne_peut_pas_etre_supprime_seulement_archive(session) -> None:
    cible = _entreprise_publiee(session)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed)

    authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
        json={
            "entreprise_id": str(cible.id),
            "montant": 500.0,
            "devise": "EUR",
            "type_duree": "OUVERTE",
            "date_debut": utcnow().isoformat(),
        },
    )

    suppression = authed.delete(f"/api/v1/investor/portefeuilles/{portefeuille_id}")
    assert suppression.status_code == 422
    assert suppression.json()["error"]["code"] == "suppression_impossible"

    archivage = authed.post(f"/api/v1/investor/portefeuilles/{portefeuille_id}/archiver")
    assert archivage.status_code == 200
    assert archivage.json()["archive"] is True

    restauration = authed.post(f"/api/v1/investor/portefeuilles/{portefeuille_id}/restaurer")
    assert restauration.status_code == 200
    assert restauration.json()["archive"] is False


def test_portefeuille_vide_est_supprimable(session) -> None:
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed)

    suppression = authed.delete(f"/api/v1/investor/portefeuilles/{portefeuille_id}")
    assert suppression.status_code == 204


def test_investisseur_ne_voit_pas_le_portefeuille_dun_autre(session) -> None:
    autre_investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    autre_authed = _login(autre_investisseur.email)
    portefeuille_id = _creer_portefeuille(autre_authed)

    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)

    response = authed.get(f"/api/v1/investor/portefeuilles/{portefeuille_id}")
    assert response.status_code == 404


def test_tableau_de_bord_compte_portefeuilles_et_entreprises_suivies_suspendues(session) -> None:
    suspendue = _entreprise_publiee(session, actif=True)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed)

    authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
        json={
            "entreprise_id": str(suspendue.id),
            "montant": 500.0,
            "devise": "EUR",
            "type_duree": "OUVERTE",
            "date_debut": utcnow().isoformat(),
        },
    )

    # Suspendue APRÈS la prise de position (voir "position conservée, nouvelle opération bloquée").
    suspendue.actif = False
    session.add(suspendue)
    session.commit()

    dashboard = authed.get("/api/v1/investor/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["nombre_portefeuilles"] == 1
    assert any(e["id"] == str(suspendue.id) for e in body["entreprises_suivies_suspendues"])
    assert len(body["positions_principales"]) >= 1


def test_export_portefeuille_csv(session) -> None:
    cible = _entreprise_publiee(session)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    authed = _login(investisseur.email)
    portefeuille_id = _creer_portefeuille(authed)

    authed.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
        json={
            "entreprise_id": str(cible.id),
            "montant": 500.0,
            "devise": "EUR",
            "type_duree": "OUVERTE",
            "date_debut": utcnow().isoformat(),
        },
    )

    export = authed.get(f"/api/v1/investor/portefeuilles/{portefeuille_id}/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert cible.nom in export.text
