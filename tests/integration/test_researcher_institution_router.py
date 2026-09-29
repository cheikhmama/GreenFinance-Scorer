import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import select

from app.auth.hashing import hash_password
from app.auth.models import InstitutionProfil, User
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import CanalDepot, ReportStatus, Role, TypeRapport
from app.core.models import Notification
from app.ingestion.models import ESGReport
from app.main import app
from app.scoring.engine import obtenir_configuration_reference
from app.scoring.models import ScoreESG

client = TestClient(app, base_url="https://testserver")


def _create_utilisateur(
    session, role: Role, *, password: str = "s3cret-pass"
) -> User:
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


def _create_institution(session, *, quota_export: int = 10) -> User:
    institution = _create_utilisateur(session, Role.INSTITUTION)
    session.add(
        InstitutionProfil(utilisateur_id=institution.id, quota_export=quota_export)
    )
    session.commit()
    return institution


def _entreprise_publiee(session, *, score_global: float = 70.0, nom: str | None = None) -> Company:
    """Publiée avec un rapport VALIDE et un ScoreESG officiel — invariant réel de
    publier_entreprise (app/admin/review_queue.py), jamais une entreprise « publiée » sans
    évaluation, sans quoi _verifier_perimetre_et_recuperer_snapshots ne trouverait jamais de
    rapport/score à figer."""
    entreprise = Company(
        name=nom or f"Cible {uuid.uuid4()}",
        sector="Industrie",
        country="France",
        published_at=utcnow(),
    )
    session.add(entreprise)
    session.commit()

    rapport = ESGReport(
        company_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.ENTREPRISE,
        status=ReportStatus.VALIDATED,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()

    configuration = obtenir_configuration_reference(session)
    session.add(
        ScoreESG(
            rapport_id=rapport.id,
            configuration_id=configuration.id,
            valeur_globale=score_global,
            score_environnement=65.0,
            score_social=75.0,
            score_gouvernance=80.0,
        )
    )
    session.commit()
    session.refresh(entreprise)
    return entreprise


def _ajouter_perimetre(
    institution_authed, projet_id: str, entreprise_id: uuid.UUID
) -> None:
    reponse = institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/perimetre",
        json={"entreprise_id": str(entreprise_id)},
    )
    assert reponse.status_code == 201, reponse.json()


def _login(email: str, password: str = "s3cret-pass") -> TestClient:
    authed_client = TestClient(app, base_url="https://testserver")
    response = authed_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    authed_client.headers.update(
        {CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]}
    )
    return authed_client


def test_inviter_chercheur_puis_disponibles_ne_le_montre_plus(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    institution_authed = _login(institution.email)

    disponibles_avant = institution_authed.get(
        "/api/v1/institution/chercheurs/disponibles"
    ).json()
    assert any(c["id"] == str(chercheur.id) for c in disponibles_avant)

    invitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter",
        json={"chercheur_id": str(chercheur.id)},
    )
    assert invitation.status_code == 201
    assert invitation.json()["statut"] == "EN_ATTENTE"

    disponibles_apres = institution_authed.get(
        "/api/v1/institution/chercheurs/disponibles"
    ).json()
    assert not any(c["id"] == str(chercheur.id) for c in disponibles_apres)


def test_inviter_chercheur_puis_acceptation_notifient_les_deux_parties(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    institution_authed = _login(institution.email)

    invitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter",
        json={"chercheur_id": str(chercheur.id)},
    ).json()

    invitation_notif = session.exec(
        select(Notification).where(
            Notification.utilisateur_id == chercheur.id,
            Notification.type == "RATTACHEMENT_INVITATION",
        )
    ).one()
    assert institution.email in invitation_notif.message

    chercheur_authed = _login(chercheur.email)
    chercheur_authed.post(
        f"/api/v1/researcher/rattachements/{invitation['id']}/accepter"
    )

    acceptation_notif = session.exec(
        select(Notification).where(
            Notification.utilisateur_id == institution.id,
            Notification.type == "RATTACHEMENT_ACCEPTE",
        )
    ).one()
    assert chercheur.email in acceptation_notif.message


def test_chercheur_accepte_invitation(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    institution_authed = _login(institution.email)
    invitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter",
        json={"chercheur_id": str(chercheur.id)},
    ).json()

    chercheur_authed = _login(chercheur.email)
    mes_rattachements = chercheur_authed.get("/api/v1/researcher/rattachements").json()
    assert any(
        r["id"] == invitation["id"] and r["statut"] == "EN_ATTENTE"
        for r in mes_rattachements
    )

    acceptation = chercheur_authed.post(
        f"/api/v1/researcher/rattachements/{invitation['id']}/accepter"
    )
    assert acceptation.status_code == 200
    assert acceptation.json()["statut"] == "ACCEPTE"

    double_reponse = chercheur_authed.post(
        f"/api/v1/researcher/rattachements/{invitation['id']}/refuser"
    )
    assert double_reponse.status_code == 422
    assert double_reponse.json()["error"]["code"] == "invitation_deja_traitee"


def test_chercheur_refuse_puis_institution_peut_reinviter(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    institution_authed = _login(institution.email)
    invitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter",
        json={"chercheur_id": str(chercheur.id)},
    ).json()

    chercheur_authed = _login(chercheur.email)
    refus = chercheur_authed.post(
        f"/api/v1/researcher/rattachements/{invitation['id']}/refuser"
    )
    assert refus.json()["statut"] == "REFUSE"

    reinvitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter",
        json={"chercheur_id": str(chercheur.id)},
    )
    assert reinvitation.status_code == 201
    assert reinvitation.json()["id"] == invitation["id"]  # même ligne, pas de doublon
    assert reinvitation.json()["statut"] == "EN_ATTENTE"


def _accepter_rattachement(
    institution_authed, chercheur_authed, chercheur_id: str
) -> None:
    invitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter", json={"chercheur_id": chercheur_id}
    ).json()
    chercheur_authed.post(
        f"/api/v1/researcher/rattachements/{invitation['id']}/accepter"
    )


def test_affecter_chercheur_non_accepte_est_refuse(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    institution_authed = _login(institution.email)
    institution_authed.post(
        "/api/v1/institution/chercheurs/inviter",
        json={"chercheur_id": str(chercheur.id)},
    )

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]

    affectation = institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter",
        json={"chercheur_id": str(chercheur.id)},
    )
    assert affectation.status_code == 422
    assert affectation.json()["error"]["code"] == "rattachement_requis"


def test_workflow_complet_analyse_validee(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post(
        "/api/v1/institution/projets",
        json={"nom": "Projet vert", "description": "Analyse ESG mines"},
    ).json()["id"]
    institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter",
        json={"chercheur_id": str(chercheur.id)},
    )
    _ajouter_perimetre(institution_authed, projet_id, entreprise.id)

    mes_projets = chercheur_authed.get("/api/v1/researcher/projets").json()
    assert [p["id"] for p in mes_projets] == [projet_id]

    creation = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_id}/analyses",
        json={
            "titre": "Analyse initiale",
            "contenu": "Comparaison ESG.",
            "entreprise_ids": [str(entreprise.id)],
        },
    )
    assert creation.status_code == 201
    analyse_id = creation.json()["id"]
    assert creation.json()["statut"] == "BROUILLON"

    soumission = chercheur_authed.post(
        f"/api/v1/researcher/analyses/{analyse_id}/soumettre"
    )
    assert soumission.status_code == 200
    assert soumission.json()["statut"] == "SOUMISE"

    detail_institution = institution_authed.get(
        f"/api/v1/institution/analyses/{analyse_id}"
    )
    assert detail_institution.status_code == 200
    assert detail_institution.json()["entreprise_ids"] == [str(entreprise.id)]

    validation = institution_authed.post(
        f"/api/v1/institution/analyses/{analyse_id}/valider",
        json={"commentaire": "Bon travail."},
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
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]
    institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter",
        json={"chercheur_id": str(chercheur.id)},
    )
    _ajouter_perimetre(institution_authed, projet_id, entreprise.id)
    analyse_id = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_id}/analyses",
        json={
            "titre": "V1",
            "contenu": "Premier jet.",
            "entreprise_ids": [str(entreprise.id)],
        },
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
        json={
            "titre": "V2",
            "contenu": "Ajout du pilier social.",
            "entreprise_ids": [str(entreprise.id)],
        },
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
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]
    cloture = institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/cloturer"
    )
    assert cloture.status_code == 200
    assert cloture.json()["statut"] == "CLOTURE"

    affectation = institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter",
        json={"chercheur_id": str(chercheur.id)},
    )
    assert affectation.status_code == 422
    assert affectation.json()["error"]["code"] == "projet_cloture"


def test_export_analyse_decremente_le_quota_et_bloque_a_zero(session) -> None:
    institution = _create_institution(session, quota_export=1)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]
    institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter",
        json={"chercheur_id": str(chercheur.id)},
    )
    _ajouter_perimetre(institution_authed, projet_id, entreprise.id)
    analyse_id = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_id}/analyses",
        json={
            "titre": "V1",
            "contenu": "Contenu.",
            "entreprise_ids": [str(entreprise.id)],
        },
    ).json()["id"]
    chercheur_authed.post(f"/api/v1/researcher/analyses/{analyse_id}/soumettre")

    premier_export = institution_authed.get(
        f"/api/v1/institution/analyses/{analyse_id}/export"
    )
    assert premier_export.status_code == 200
    assert premier_export.headers["content-type"].startswith("text/csv")

    deuxieme_export = institution_authed.get(
        f"/api/v1/institution/analyses/{analyse_id}/export"
    )
    assert deuxieme_export.status_code == 422
    assert deuxieme_export.json()["error"]["code"] == "quota_export_epuise"

    # Le quota consommé ci-dessus (1 -> 0 après le premier export) doit être visible via le
    # profil — jamais seulement déductible en observant les erreurs 422 d'un futur export.
    profil = institution_authed.get("/api/v1/institution/profil")
    assert profil.status_code == 200
    assert profil.json()["quota_export"] == 0


def test_chercheur_ne_peut_pas_creer_analyse_sur_projet_non_affecte(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]

    creation = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_id}/analyses",
        json={
            "titre": "V1",
            "contenu": "Contenu.",
            "entreprise_ids": [str(entreprise.id)],
        },
    )
    assert creation.status_code == 404
    assert creation.json()["error"]["code"] == "projet_introuvable"


def test_creer_analyse_refuse_entreprise_hors_perimetre(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]
    institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter",
        json={"chercheur_id": str(chercheur.id)},
    )
    # Jamais ajoutée au périmètre du projet, bien que publiée et évaluée.

    creation = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_id}/analyses",
        json={
            "titre": "V1",
            "contenu": "Contenu.",
            "entreprise_ids": [str(entreprise.id)],
        },
    )
    assert creation.status_code == 422
    assert creation.json()["error"]["code"] == "entreprise_hors_perimetre"


def test_ajouter_entreprise_perimetre_refuse_entreprise_non_publiee(session) -> None:
    institution = _create_institution(session)
    institution_authed = _login(institution.email)
    entreprise_non_publiee = Company(
        name=f"Cible {uuid.uuid4()}", sector="Industrie", country="France"
    )
    session.add(entreprise_non_publiee)
    session.commit()
    session.refresh(entreprise_non_publiee)

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]

    reponse = institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/perimetre",
        json={"entreprise_id": str(entreprise_non_publiee.id)},
    )
    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "entreprise_non_publiee"


def test_ajouter_document_refuse_hors_perimetre_et_rapport_perime(session) -> None:
    institution = _create_institution(session)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)

    ancien_rapport_id = (
        session.exec(
            select(ESGReport).where(ESGReport.company_id == entreprise.id)
        )
        .one()
        .id
    )

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]

    # Hors périmètre : refusé avant même de regarder le rapport.
    hors_perimetre = institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/documents",
        json={"rapport_id": str(ancien_rapport_id)},
    )
    assert hors_perimetre.status_code == 422
    assert hors_perimetre.json()["error"]["code"] == "entreprise_hors_perimetre"

    _ajouter_perimetre(institution_authed, projet_id, entreprise.id)

    # Une nouvelle évaluation supplante l'ancienne (nouveau ESGReport VALIDE, plus récent) —
    # l'ancien rapport reste littéralement VALIDE en base mais n'est plus le rapport publié.
    nouveau_rapport = ESGReport(
        company_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.ENTREPRISE,
        status=ReportStatus.VALIDATED,
        source_file="rapports/test/dummy-v2.pdf",
        submitted_at=utcnow() + timedelta(days=1),
    )
    session.add(nouveau_rapport)
    session.commit()
    configuration = obtenir_configuration_reference(session)
    session.add(
        ScoreESG(
            rapport_id=nouveau_rapport.id,
            configuration_id=configuration.id,
            valeur_globale=80.0,
        )
    )
    session.commit()

    perime = institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/documents",
        json={"rapport_id": str(ancien_rapport_id)},
    )
    assert perime.status_code == 422
    assert perime.json()["error"]["code"] == "rapport_non_publie"

    courant = institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/documents",
        json={"rapport_id": str(nouveau_rapport.id)},
    )
    assert courant.status_code == 201
    assert courant.json()["rapport_id"] == str(nouveau_rapport.id)


def test_decisions_analyse_notifient_le_chercheur(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]
    institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter",
        json={"chercheur_id": str(chercheur.id)},
    )
    _ajouter_perimetre(institution_authed, projet_id, entreprise.id)

    analyse_id = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_id}/analyses",
        json={
            "titre": "V1",
            "contenu": "Contenu.",
            "entreprise_ids": [str(entreprise.id)],
        },
    ).json()["id"]
    chercheur_authed.post(f"/api/v1/researcher/analyses/{analyse_id}/soumettre")

    institution_authed.post(
        f"/api/v1/institution/analyses/{analyse_id}/demander-correction",
        json={"commentaire": "Manque le pilier social."},
    )
    correction_notif = session.exec(
        select(Notification).where(
            Notification.utilisateur_id == chercheur.id,
            Notification.type == "ANALYSE_CORRECTION_DEMANDEE",
        )
    ).one()
    assert "Manque le pilier social." in correction_notif.message
    assert str(analyse_id) == str(correction_notif.id_ressource)

    correction_id = chercheur_authed.post(
        f"/api/v1/researcher/analyses/{analyse_id}/corriger",
        json={
            "titre": "V2",
            "contenu": "Contenu corrigé.",
            "entreprise_ids": [str(entreprise.id)],
        },
    ).json()["id"]
    chercheur_authed.post(f"/api/v1/researcher/analyses/{correction_id}/soumettre")
    institution_authed.post(
        f"/api/v1/institution/analyses/{correction_id}/valider",
        json={"commentaire": "Très bien."},
    )
    validation_notif = session.exec(
        select(Notification).where(
            Notification.utilisateur_id == chercheur.id,
            Notification.type == "ANALYSE_VALIDEE",
        )
    ).one()
    assert str(correction_id) == str(validation_notif.id_ressource)

    # Historique complet, depuis n'importe quelle version de la chaîne.
    historique_depuis_v1 = chercheur_authed.get(
        f"/api/v1/researcher/analyses/{analyse_id}/historique"
    )
    historique_depuis_v2 = institution_authed.get(
        f"/api/v1/institution/analyses/{correction_id}/historique"
    )
    assert [a["version"] for a in historique_depuis_v1.json()] == [1, 2]
    assert [a["id"] for a in historique_depuis_v1.json()] == [
        a["id"] for a in historique_depuis_v2.json()
    ]
    assert historique_depuis_v1.json()[0]["statut"] == "CORRECTION_DEMANDEE"
    assert historique_depuis_v1.json()[1]["statut"] == "VALIDEE"


def test_creer_projet_refuse_dates_incoherentes(session) -> None:
    institution = _create_institution(session)
    institution_authed = _login(institution.email)
    debut = utcnow()

    periode_inversee = institution_authed.post(
        "/api/v1/institution/projets",
        json={
            "nom": "Projet vert",
            "date_debut": debut.isoformat(),
            "date_fin_prevue": (debut - timedelta(days=1)).isoformat(),
        },
    )
    assert periode_inversee.status_code == 422
    assert periode_inversee.json()["error"]["code"] == "periode_incoherente"

    limite_avant_debut = institution_authed.post(
        "/api/v1/institution/projets",
        json={
            "nom": "Projet vert",
            "date_debut": debut.isoformat(),
            "date_limite": (debut - timedelta(days=1)).isoformat(),
        },
    )
    assert limite_avant_debut.status_code == 422
    assert limite_avant_debut.json()["error"]["code"] == "date_limite_incoherente"


def test_inviter_chercheur_persiste_les_conditions_de_collaboration(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    institution_authed = _login(institution.email)

    invitation = institution_authed.post(
        "/api/v1/institution/chercheurs/inviter",
        json={
            "chercheur_id": str(chercheur.id),
            "conditions_collaboration": "Analyse ESG du secteur minier, 3 mois, résultats confidentiels.",
        },
    )
    assert invitation.status_code == 201
    assert invitation.json()["conditions_collaboration"] == (
        "Analyse ESG du secteur minier, 3 mois, résultats confidentiels."
    )

    chercheur_authed = _login(chercheur.email)
    mes_rattachements = chercheur_authed.get("/api/v1/researcher/rattachements").json()
    assert mes_rattachements[0]["conditions_collaboration"] == (
        "Analyse ESG du secteur minier, 3 mois, résultats confidentiels."
    )


def test_affecter_chercheur_notifie_le_chercheur(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]
    institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter",
        json={"chercheur_id": str(chercheur.id)},
    )

    notification = session.exec(
        select(Notification).where(
            Notification.utilisateur_id == chercheur.id,
            Notification.type == "PROJET_AFFECTATION",
        )
    ).one()
    assert "Projet vert" in notification.message
    assert str(notification.id_ressource) == projet_id


def test_soumettre_analyse_notifie_institution(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet vert"}
    ).json()["id"]
    institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter",
        json={"chercheur_id": str(chercheur.id)},
    )
    _ajouter_perimetre(institution_authed, projet_id, entreprise.id)

    analyse_id = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_id}/analyses",
        json={
            "titre": "Analyse ESG",
            "contenu": "Contenu.",
            "entreprise_ids": [str(entreprise.id)],
        },
    ).json()["id"]
    chercheur_authed.post(f"/api/v1/researcher/analyses/{analyse_id}/soumettre")

    notification = session.exec(
        select(Notification).where(
            Notification.utilisateur_id == institution.id,
            Notification.type == "ANALYSE_SOUMISE",
        )
    ).one()
    assert "Analyse ESG" in notification.message
    assert str(notification.id_ressource) == analyse_id


def test_lister_mes_analyses_toutes_projets_confondus(session) -> None:
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    entreprise = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_a = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet A"}
    ).json()["id"]
    projet_b = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet B"}
    ).json()["id"]
    for projet_id in (projet_a, projet_b):
        institution_authed.post(
            f"/api/v1/institution/projets/{projet_id}/affecter",
            json={"chercheur_id": str(chercheur.id)},
        )
        _ajouter_perimetre(institution_authed, projet_id, entreprise.id)

    analyse_a = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_a}/analyses",
        json={
            "titre": "Analyse A",
            "contenu": "Contenu.",
            "entreprise_ids": [str(entreprise.id)],
        },
    ).json()["id"]
    chercheur_authed.post(f"/api/v1/researcher/analyses/{analyse_a}/soumettre")

    # Brouillon sur le projet B — pas encore soumis : espace de travail privé du chercheur, ne
    # doit apparaître ni dans la liste globale, ni être consultable/exportable directement par
    # l'Institution avant que le chercheur ne choisisse de le soumettre (voir
    # app/institution/analyses.py::analyse_de_institution).
    analyse_b = chercheur_authed.post(
        f"/api/v1/researcher/projets/{projet_b}/analyses",
        json={
            "titre": "Analyse B",
            "contenu": "Contenu.",
            "entreprise_ids": [str(entreprise.id)],
        },
    ).json()["id"]

    toutes = institution_authed.get("/api/v1/institution/analyses")
    assert toutes.status_code == 200
    par_id = {a["id"]: a for a in toutes.json()}
    assert set(par_id) == {analyse_a}
    assert par_id[analyse_a]["projet_id"] == projet_a
    assert par_id[analyse_a]["projet_nom"] == "Projet A"
    assert par_id[analyse_a]["statut"] == "SOUMISE"

    seulement_soumises = institution_authed.get(
        "/api/v1/institution/analyses", params={"statut": "SOUMISE"}
    )
    assert [a["id"] for a in seulement_soumises.json()] == [analyse_a]

    detail_brouillon = institution_authed.get(f"/api/v1/institution/analyses/{analyse_b}")
    assert detail_brouillon.status_code == 404

    export_brouillon = institution_authed.get(f"/api/v1/institution/analyses/{analyse_b}/export")
    assert export_brouillon.status_code == 404


def test_chercheur_ne_voit_que_les_entreprises_du_perimetre_de_ses_projets(session) -> None:
    """Décision de gouvernance du 2026-09-02 : un Chercheur ne doit jamais consulter, comparer ou
    lister une entreprise publiée hors du périmètre que son Institution a explicitement construit
    pour ses projets affectés — même si l'entreprise est publiée sur la plateforme (voir
    app/researcher/projets.py::entreprises_perimetre_chercheur)."""
    institution = _create_institution(session)
    chercheur = _create_utilisateur(session, Role.RESEARCHER)
    dans_le_perimetre = _entreprise_publiee(session)
    hors_perimetre = _entreprise_publiee(session)
    institution_authed = _login(institution.email)
    chercheur_authed = _login(chercheur.email)
    _accepter_rattachement(institution_authed, chercheur_authed, str(chercheur.id))

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet"}
    ).json()["id"]
    institution_authed.post(
        f"/api/v1/institution/projets/{projet_id}/affecter",
        json={"chercheur_id": str(chercheur.id)},
    )
    _ajouter_perimetre(institution_authed, projet_id, dans_le_perimetre.id)

    liste = chercheur_authed.get("/api/v1/researcher/entreprises")
    assert liste.status_code == 200
    assert [item["id"] for item in liste.json()["items"]] == [str(dans_le_perimetre.id)]

    detail_autorise = chercheur_authed.get(f"/api/v1/researcher/entreprises/{dans_le_perimetre.id}")
    assert detail_autorise.status_code == 200

    detail_refuse = chercheur_authed.get(f"/api/v1/researcher/entreprises/{hors_perimetre.id}")
    assert detail_refuse.status_code == 404

    comparaison = chercheur_authed.get(
        "/api/v1/researcher/comparaison",
        params={"entreprise_ids": [str(dans_le_perimetre.id), str(hors_perimetre.id)]},
    )
    assert comparaison.status_code == 404


def test_institution_ne_consulte_le_detail_dune_entreprise_que_dans_son_propre_perimetre(
    session,
) -> None:
    """Même principe côté Institution que côté Chercheur, mais la liste de recherche reste
    volontairement ouverte (curation d'un périmètre) — seule la fiche détail est restreinte
    (voir app/institution/projets.py::entreprises_perimetre_institution)."""
    marqueur = f"marqueur-{uuid.uuid4()}"
    institution = _create_institution(session)
    dans_le_perimetre = _entreprise_publiee(session, nom=f"{marqueur} Dans Perimetre")
    hors_perimetre = _entreprise_publiee(session, nom=f"{marqueur} Hors Perimetre")
    institution_authed = _login(institution.email)

    projet_id = institution_authed.post(
        "/api/v1/institution/projets", json={"nom": "Projet"}
    ).json()["id"]
    _ajouter_perimetre(institution_authed, projet_id, dans_le_perimetre.id)

    # Catalogue global, non scopé par institution (curation) : recherche par marqueur pour isoler
    # ces deux entreprises de la base partagée des tests, jamais une égalité de liste absolue
    # (voir test_lister_rapports_a_affecter_filtre_correctement).
    liste = institution_authed.get("/api/v1/institution/entreprises", params={"recherche": marqueur})
    assert liste.status_code == 200
    ids_liste = {item["id"] for item in liste.json()["items"]}
    assert ids_liste == {str(dans_le_perimetre.id), str(hors_perimetre.id)}

    detail_autorise = institution_authed.get(f"/api/v1/institution/entreprises/{dans_le_perimetre.id}")
    assert detail_autorise.status_code == 200

    detail_refuse = institution_authed.get(f"/api/v1/institution/entreprises/{hors_perimetre.id}")
    assert detail_refuse.status_code == 404
