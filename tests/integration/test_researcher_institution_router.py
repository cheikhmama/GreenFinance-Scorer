import uuid

from fastapi.testclient import TestClient

from app.auth.hashing import hash_password
from app.auth.models import InstitutionProfil, Utilisateur
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Entreprise
from app.core.database import utcnow
from app.core.enums import Role
from app.main import app

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


def _create_institution(session, *, quota_export: int = 10) -> Utilisateur:
    institution = _create_utilisateur(session, Role.INSTITUTION)
    session.add(InstitutionProfil(utilisateur_id=institution.id, quota_export=quota_export))
    session.commit()
    return institution


def _entreprise_publiee(session) -> Entreprise:
    entreprise = Entreprise(
        nom=f"Cible {uuid.uuid4()}", secteur="Industrie", pays="France", date_publication=utcnow()
    )
    session.add(entreprise)
    session.commit()
    session.refresh(entreprise)
    return entreprise


def _login(email: str, password: str = "s3cret-pass") -> TestClient:
    authed_client = TestClient(app, base_url="https://testserver")
    response = authed_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})
    return authed_client


def test_inviter_chercheur_puis_disponibles_ne_le_montre_plus(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.CHERCHEUR)
    institution_authed = _login(institution.email)

    disponibles_avant = institution_authed.get("/api/v1/institution/chercheurs/disponibles").json()
    assert any(c["id"] == str(chercheur.id) for c in disponibles_avant)

    invitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter", json={"chercheur_id": str(chercheur.id)}
    )
    assert invitation.status_code == 201
    assert invitation.json()["statut"] == "EN_ATTENTE"

    disponibles_apres = institution_authed.get("/api/v1/institution/chercheurs/disponibles").json()
    assert not any(c["id"] == str(chercheur.id) for c in disponibles_apres)


def test_chercheur_accepte_invitation(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.CHERCHEUR)
    institution_authed = _login(institution.email)
    invitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter", json={"chercheur_id": str(chercheur.id)}
    ).json()

    chercheur_authed = _login(chercheur.email)
    mes_rattachements = chercheur_authed.get("/api/v1/researcher/rattachements").json()
    assert any(r["id"] == invitation["id"] and r["statut"] == "EN_ATTENTE" for r in mes_rattachements)

    acceptation = chercheur_authed.post(f"/api/v1/researcher/rattachements/{invitation['id']}/accepter")
    assert acceptation.status_code == 200
    assert acceptation.json()["statut"] == "ACCEPTE"

    double_reponse = chercheur_authed.post(f"/api/v1/researcher/rattachements/{invitation['id']}/refuser")
    assert double_reponse.status_code == 422
    assert double_reponse.json()["error"]["code"] == "invitation_deja_traitee"


def test_chercheur_refuse_puis_institution_peut_reinviter(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.CHERCHEUR)
    institution_authed = _login(institution.email)
    invitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter", json={"chercheur_id": str(chercheur.id)}
    ).json()

    chercheur_authed = _login(chercheur.email)
    refus = chercheur_authed.post(f"/api/v1/researcher/rattachements/{invitation['id']}/refuser")
    assert refus.json()["statut"] == "REFUSE"

    reinvitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter", json={"chercheur_id": str(chercheur.id)}
    )
    assert reinvitation.status_code == 201
    assert reinvitation.json()["id"] == invitation["id"]  # même ligne, pas de doublon
    assert reinvitation.json()["statut"] == "EN_ATTENTE"


def _accepter_rattachement(institution_authed, chercheur_authed, chercheur_id: str) -> None:
    invitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter", json={"chercheur_id": chercheur_id}
    ).json()
    chercheur_authed.post(f"/api/v1/researcher/rattachements/{invitation['id']}/accepter")


def test_affecter_chercheur_non_accepte_est_refuse(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.CHERCHEUR)
    institution_authed = _login(institution.email)
    institution_authed.post(
        "/api/v1/institution/chercheurs/inviter", json={"chercheur_id": str(chercheur.id)}
    )

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]

    affectation = institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter", json={"chercheur_id": str(chercheur.id)}
    )
    assert affectation.status_code == 422
    assert affectation.json()["error"]["code"] == "rattachement_requis"


def test_workflow_complet_analyse_validee(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.CHERCHEUR)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert", "description": "Analyse ESG mines"}
    ).json()["id"]
    institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter", json={"chercheur_id": str(chercheur.id)}
    )

    mes_projets = chercheur_authed.get("/api/v1/researcher/projets").json()
    assert [p["id"] for p in mes_projets] == [projet_id]

    creation = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_id}/analyses",
        json={"titre": "Analyse initiale", "contenu": "Comparaison ESG.", "entreprise_ids": [str(entreprise.id)]},
    )
    assert creation.status_code == 201
    analyse_id = creation.json()["id"]
    assert creation.json()["statut"] == "BROUILLON"

    soumission = chercheur_authed.post(f"/api/v1/researcher/analyses/{analyse_id}/soumettre")
    assert soumission.status_code == 200
    assert soumission.json()["statut"] == "SOUMISE"

    detail_institution = institution_authed.get(f"/api/v1/institution/analyses/{analyse_id}")
    assert detail_institution.status_code == 200
    assert detail_institution.json()["entreprise_ids"] == [str(entreprise.id)]

    validation = institution_authed.post(
        f"/api/v1/institution/analyses/{analyse_id}/valider", json={"commentaire": "Bon travail."}
    )
    assert validation.status_code == 200
    assert validation.json()["statut"] == "VALIDEE"

    double_decision = institution_authed.post(
        f"/api/v1/institution/analyses/{analyse_id}/valider", json={}
    )
    assert double_decision.status_code == 422
    assert double_decision.json()["error"]["code"] == "decision_impossible"


def test_workflow_correction_cree_une_nouvelle_version(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.CHERCHEUR)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post("/api/v1/institution/projets", json={"nom": "Projet vert"}).json()["id"]
    institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter", json={"chercheur_id": str(chercheur.id)}
    )
    analyse_id = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_id}/analyses",
        json={"titre": "V1", "contenu": "Premier jet.", "entreprise_ids": [str(entreprise.id)]},
    ).json()["id"]
    chercheur_authed.post(f"/api/v1/researcher/analyses/{analyse_id}/soumettre")

    correction_demandee = institution_authed.post(
        f"/api/v1/institution/analyses/{analyse_id}/demander-correction",
        json={"commentaire": "Manque le pilier social."},
    )
    assert correction_demandee.status_code == 200
    assert correction_demandee.json()["statut"] == "CORRECTION_DEMANDEE"

    correction = chercheur_authed.post(
        f"/api/v1/researcher/analyses/{analyse_id}/corriger",
        json={"titre": "V2", "contenu": "Ajout du pilier social.", "entreprise_ids": [str(entreprise.id)]},
    )
    assert correction.status_code == 201
    assert correction.json()["version"] == 2
    assert correction.json()["analyse_precedente_id"] == analyse_id
    assert correction.json()["statut"] == "BROUILLON"

    # L'ancienne version reste consultable, inchangée (CORRECTION_DEMANDEE, jamais réécrite).
    ancienne = chercheur_authed.get(f"/api/v1/researcher/analyses/{analyse_id}")
    assert ancienne.json()["statut"] == "CORRECTION_DEMANDEE"
    assert ancienne.json()["titre"] == "V1"


def test_cloturer_projet_bloque_nouvelle_affectation(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.CHERCHEUR)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post("/api/v1/institution/projets", json={"nom": "Projet vert"}).json()["id"]
    cloture = institution_authed.post(f"/api/v1/institution/projets/{projet_id}/cloturer")
    assert cloture.status_code == 200
    assert cloture.json()["statut"] == "CLOTURE"

    affectation = institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter", json={"chercheur_id": str(chercheur.id)}
    )
    assert affectation.status_code == 422
    assert affectation.json()["error"]["code"] == "projet_cloture"


def test_export_analyse_decremente_le_quota_et_bloque_a_zero(session) -> None:
    institution = _create_institution(session, quota_export=1)
    chercheur = _create_utilisateur(session, Role.CHERCHEUR)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post("/api/v1/institution/projets", json={"nom": "Projet vert"}).json()["id"]
    institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter", json={"chercheur_id": str(chercheur.id)}
    )
    analyse_id = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_id}/analyses",
        json={"titre": "V1", "contenu": "Contenu.", "entreprise_ids": [str(entreprise.id)]},
    ).json()["id"]
    chercheur_authed.post(f"/api/v1/researcher/analyses/{analyse_id}/soumettre")

    premier_export = institution_authed.get(f"/api/v1/institution/analyses/{analyse_id}/export")
    assert premier_export.status_code == 200
    assert premier_export.headers["content-type"].startswith("text/csv")

    deuxieme_export = institution_authed.get(f"/api/v1/institution/analyses/{analyse_id}/export")
    assert deuxieme_export.status_code == 422
    assert deuxieme_export.json()["error"]["code"] == "quota_export_epuise"


def test_chercheur_ne_peut_pas_creer_analyse_sur_projet_non_affecte(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.CHERCHEUR)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)

    projet_id = institution_authed.post("/api/v1/institution/projets", json={"nom": "Projet vert"}).json()["id"]

    creation = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_id}/analyses",
        json={"titre": "V1", "contenu": "Contenu.", "entreprise_ids": [str(entreprise.id)]},
    )
    assert creation.status_code == 404
    assert creation.json()["error"]["code"] == "projet_introuvable"
