import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import select

from app.audit.models import AvisAudit
from app.auth.hashing import hash_password
from app.auth.models import Utilisateur
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Entreprise
from app.core import storage
from app.core.audit import auditer
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import (
    CanalDepot,
    DecisionAudit,
    MethodeDonnee,
    Pilier,
    Role,
    StatutRapport,
    TypeRapport,
)
from app.core.models import JournalAudit, Notification
from app.ingestion.models import IndicateurESG, PreuveDocumentaire, RapportESG
from app.main import app
from app.scoring.engine import obtenir_configuration_reference
from app.scoring.models import ScoreESG

client = TestClient(app, base_url="https://testserver")


def _create_utilisateur(session, role: Role, *, password: str = "s3cret-pass", actif: bool = True) -> Utilisateur:
    user = Utilisateur(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        mot_de_passe_hache=hash_password(password),
        role=role,
        actif=actif,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_utilisateur_avec_email(
    session, role: Role, email: str, *, password: str = "s3cret-pass"
) -> Utilisateur:
    user = Utilisateur(email=email, mot_de_passe_hache=hash_password(password), role=role, actif=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_entreprise_avec_utilisateur(session) -> tuple[Entreprise, Utilisateur]:
    entreprise = Entreprise(nom=f"Cible {uuid.uuid4()}", secteur="Technologies", pays="France")
    session.add(entreprise)
    session.commit()
    utilisateur = _create_utilisateur(session, Role.ENTREPRISE)
    entreprise.utilisateur_id = utilisateur.id
    session.add(entreprise)
    session.commit()
    session.refresh(entreprise)
    return entreprise, utilisateur


def _create_rapport(session, entreprise_id: uuid.UUID, **overrides) -> RapportESG:
    valeurs = {
        "entreprise_id": entreprise_id,
        "type": TypeRapport.RAPPORT_ESG,
        "canal": CanalDepot.ENTREPRISE,
        "statut": StatutRapport.ENVOYE,
        "fichier_source": "rapports/test/dummy.pdf",
    }
    valeurs.update(overrides)
    rapport = RapportESG(**valeurs)
    session.add(rapport)
    session.commit()
    session.refresh(rapport)
    return rapport


def _create_rapport_en_validation(session, entreprise_id: uuid.UUID, auditeur_id: uuid.UUID) -> RapportESG:
    rapport = _create_rapport(
        session,
        entreprise_id,
        statut=StatutRapport.EN_VALIDATION,
        extraction_terminee_le=utcnow(),
        auditeur_id=auditeur_id,
    )
    session.add(
        AvisAudit(
            rapport_id=rapport.id,
            auditeur_id=auditeur_id,
            decision=DecisionAudit.RECOMMANDE_VALIDATION,
        )
    )
    # Au moins un IndicateurESG (Phase 5 §9) : valider_rapport calcule désormais un score dans la
    # même transaction que la transition VALIDE (app/admin/review_queue.py) -- sans indicateur,
    # calculer_score lèverait score_incalculable et /valider échouerait pour ce fixture partagé.
    preuve = PreuveDocumentaire(
        nom_document="rapport-test.pdf",
        annee=2025,
        nombre_pages_total=1,
        page_debut=1,
        page_fin=1,
        pdf_extrait_genere="preuves/test/page_1.pdf",
    )
    session.add(preuve)
    session.flush()
    session.add(
        IndicateurESG(
            rapport_id=rapport.id,
            pilier=Pilier.GOUVERNANCE,
            code="femmes_conseil_pourcentage",
            valeur=40.0,
            unite="%",
            methode=MethodeDonnee.RAPPORTEE,
            preuve_id=preuve.id,
        )
    )
    session.commit()
    return rapport


def _create_score(session, rapport_id: uuid.UUID) -> ScoreESG:
    """Sème un ScoreESG directement (sans passer par app/scoring/engine.py::calculer_score) --
    utile pour les tests qui seedent un rapport VALIDE directement via _create_rapport plutôt
    que via le vrai parcours /valider (donc sans score réellement calculé). Réutilise la vraie
    configuration de référence (obtenir_configuration_reference) plutôt que d'en créer une
    seconde : une ConfigurationPonderation ad hoc avec utilisateur_id=None aurait exactement la
    forme d'une configuration de référence et fausserait tout test d'idempotence sur celle-ci."""
    configuration = obtenir_configuration_reference(session)
    score = ScoreESG(
        rapport_id=rapport_id,
        configuration_id=configuration.id,
        valeur_globale=70.0,
        score_environnement=70.0,
        score_social=70.0,
        score_gouvernance=70.0,
    )
    session.add(score)
    session.commit()
    return score


def _login(email: str, password: str) -> TestClient:
    authed_client = TestClient(app, base_url="https://testserver")
    response = authed_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    # Toute requête mutante ultérieure passe par CSRFMiddleware (app/auth/csrf.py) : le jeton
    # posé par le cookie __Host-csrf_token à la connexion doit être rejoué dans l'en-tête dédié.
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})
    return authed_client


def test_lister_utilisateurs_par_role_ne_montre_que_le_role_et_les_actifs(session) -> None:
    # `recherche` scope la requête aux seuls comptes de ce test — la base de développement
    # partagée (voir tests/integration : pas d'isolation transactionnelle par test) accumule des
    # dizaines de comptes AUDITEUR au fil des sessions, qui dépasseraient une simple page_size
    # large et masqueraient les comptes créés ici.
    marqueur = f"marqueur-{uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    auditeur_actif = _create_utilisateur_avec_email(session, Role.AUDITEUR, f"{marqueur}-actif@example.com")
    auditeur_inactif = _create_utilisateur_avec_email(
        session, Role.AUDITEUR, f"{marqueur}-inactif@example.com"
    )
    auditeur_inactif.actif = False
    session.add(auditeur_inactif)
    chercheur = _create_utilisateur_avec_email(session, Role.CHERCHEUR, f"{marqueur}-chercheur@example.com")
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITEUR", "recherche": marqueur, "page_size": 50},
    )

    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body["items"]]
    assert str(auditeur_actif.id) in ids
    assert str(auditeur_inactif.id) not in ids
    assert str(chercheur.id) not in ids


def test_lister_utilisateurs_pagine_par_defaut_a_trois_par_page(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    role_isole = f"pagination-{uuid.uuid4()}"
    crees = [
        _create_utilisateur_avec_email(
            session, Role.AUDITEUR, f"{role_isole}-{i}@example.com"
        )
        for i in range(5)
    ]

    authed_client = _login(admin.email, "s3cret-pass")
    premiere_page = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITEUR", "recherche": role_isole, "page": 1},
    ).json()
    deuxieme_page = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITEUR", "recherche": role_isole, "page": 2},
    ).json()

    assert premiere_page["total"] == 5
    assert premiere_page["pages"] == 2
    assert len(premiere_page["items"]) == 3
    assert len(deuxieme_page["items"]) == 2
    # Aucun chevauchement entre les deux pages -- l'offset avance bien de page_size.
    ids_page_1 = {item["id"] for item in premiere_page["items"]}
    ids_page_2 = {item["id"] for item in deuxieme_page["items"]}
    assert ids_page_1.isdisjoint(ids_page_2)
    assert ids_page_1 | ids_page_2 == {str(u.id) for u in crees}


def test_lister_utilisateurs_recherche_filtre_par_email(session) -> None:
    # Le domaine porte l'uuid, pas seulement la partie locale -- une exécution précédente de ce
    # même test laisse un compte "@audit-conseil.test" en base (pas d'isolation transactionnelle
    # inter-tests), donc un motif de recherche statique ramasserait aussi ce résidu.
    domaine_unique = f"audit-conseil-{uuid.uuid4().hex}.test"
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    cible = _create_utilisateur_avec_email(session, Role.AUDITEUR, f"cible@{domaine_unique}")
    _create_utilisateur_avec_email(session, Role.AUDITEUR, f"autre-{uuid.uuid4()}@example.com")

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITEUR", "recherche": domaine_unique},
    )

    body = response.json()
    ids = [item["id"] for item in body["items"]]
    assert ids == [str(cible.id)]


def test_lister_utilisateurs_avec_role_entreprise_est_rejete(session) -> None:
    user = _create_utilisateur(session, Role.ENTREPRISE)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.get("/api/v1/admin/utilisateurs", params={"role": "AUDITEUR"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_creer_utilisateur_genere_un_mot_de_passe_temporaire_qui_fonctionne(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    authed_client = _login(admin.email, "s3cret-pass")
    email_cible = f"nouveau-{uuid.uuid4()}@example.com"

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={"email": email_cible, "nom": "Nouvel Auditeur", "role": "AUDITEUR"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email_cible
    assert body["role"] == "AUDITEUR"
    assert body["actif"] is True
    mot_de_passe_temporaire = body["mot_de_passe_temporaire"]
    assert len(mot_de_passe_temporaire) > 8

    # Le mot de passe temporaire fonctionne réellement pour se connecter.
    login_response = client.post(
        "/api/v1/auth/login", json={"email": email_cible, "password": mot_de_passe_temporaire}
    )
    assert login_response.status_code == 200
    assert login_response.json()["doit_changer_mot_de_passe"] is True


def test_creer_utilisateur_sans_nom_le_deduit_de_lemail(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    authed_client = _login(admin.email, "s3cret-pass")
    email_cible = f"jean.dupont-{uuid.uuid4()}@example.com"

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={"email": email_cible, "role": "AUDITEUR"},
    )

    assert response.status_code == 201
    assert response.json()["nom"] == email_cible.split("@")[0]


def test_lister_utilisateurs_recherche_filtre_aussi_par_nom(session) -> None:
    marqueur = f"marqueur-{uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    cible = _create_utilisateur_avec_email(session, Role.AUDITEUR, f"autre-email-{uuid.uuid4()}@example.com")
    cible.nom = f"{marqueur} Dupont"
    session.add(cible)
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITEUR", "recherche": marqueur},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(cible.id)


def test_creer_utilisateur_refuse_le_role_administrateur(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={
            "email": f"nouvel-admin-{uuid.uuid4()}@example.com",
            "nom": "Nouvel Admin",
            "role": "ADMINISTRATEUR",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "role_non_autorise"


def test_creer_utilisateur_refuse_un_email_deja_utilise(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    existant = _create_utilisateur(session, Role.CHERCHEUR)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={"email": existant.email, "nom": "Doublon", "role": "AUDITEUR"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "email_deja_utilise"


def test_creer_utilisateur_avec_role_entreprise_cree_le_profil_entreprise(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    authed_client = _login(admin.email, "s3cret-pass")
    email_cible = f"nouvelle-entreprise-{uuid.uuid4()}@example.com"

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={
            "email": email_cible,
            "role": "ENTREPRISE",
            "nom": "Contact Acme",
            "nom_entreprise": "Acme Corp",
            "secteur": "Industrie",
            "pays": "France",
        },
    )

    assert response.status_code == 201
    utilisateur_id = uuid.UUID(response.json()["id"])
    entreprise = session.exec(
        select(Entreprise).where(Entreprise.utilisateur_id == utilisateur_id)
    ).first()
    assert entreprise is not None
    assert entreprise.nom == "Acme Corp"
    assert entreprise.secteur == "Industrie"
    assert entreprise.pays == "France"

    # Le compte peut immédiatement déposer un rapport — la relation n'est plus manquante.
    authed_entreprise = _login(email_cible, response.json()["mot_de_passe_temporaire"])
    authed_entreprise.post(
        "/api/v1/auth/changer-mot-de-passe",
        json={
            "mot_de_passe_actuel": response.json()["mot_de_passe_temporaire"],
            "nouveau_mot_de_passe": "nouveau-mdp-1234",
        },
    )
    liste_response = authed_entreprise.get("/api/v1/company/rapports")
    assert liste_response.status_code == 200


def test_creer_utilisateur_role_entreprise_sans_profil_est_rejete(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={
            "email": f"sans-profil-{uuid.uuid4()}@example.com",
            "nom": "Compte Sans Profil",
            "role": "ENTREPRISE",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "profil_entreprise_requis"
    assert set(body["error"]["fields"]) == {"nom_entreprise", "secteur", "pays"}


def test_creer_utilisateur_avec_role_entreprise_est_rejete(session) -> None:
    user = _create_utilisateur(session, Role.ENTREPRISE)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/admin/utilisateurs",
        json={"email": f"x-{uuid.uuid4()}@example.com", "nom": "X", "role": "AUDITEUR"},
    )

    assert response.status_code == 403


def test_un_compte_avec_mot_de_passe_temporaire_ne_peut_pas_encore_utiliser_lapi_metier(session) -> None:
    """Preuve d'intégration du garde posé dans get_current_user (app/core/dependencies.py) —
    voir aussi tests/unit/test_dependencies.py pour la version isolée de cette règle."""
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    admin_client = _login(admin.email, "s3cret-pass")
    email_cible = f"temp-{uuid.uuid4()}@example.com"
    create_response = admin_client.post(
        "/api/v1/admin/utilisateurs",
        json={"email": email_cible, "nom": "Compte Temporaire", "role": "AUDITEUR"},
    )
    mot_de_passe_temporaire = create_response.json()["mot_de_passe_temporaire"]

    nouveau_client = _login(email_cible, mot_de_passe_temporaire)

    blocked_response = nouveau_client.get("/api/v1/audit/rapports")
    assert blocked_response.status_code == 403
    assert blocked_response.json()["error"]["code"] == "password_change_required"

    # /auth/me reste accessible, c'est ce qui permet au frontend de détecter l'état et de
    # rediriger vers l'écran de changement de mot de passe.
    assert nouveau_client.get("/api/v1/auth/me").status_code == 200

    change_response = nouveau_client.post(
        "/api/v1/auth/changer-mot-de-passe",
        json={
            "mot_de_passe_actuel": mot_de_passe_temporaire,
            "nouveau_mot_de_passe": "un-nouveau-secret-3",
        },
    )
    assert change_response.status_code == 200

    unblocked_response = nouveau_client.get("/api/v1/audit/rapports")
    assert unblocked_response.status_code == 200


def test_desactiver_utilisateur_revoque_ses_sessions_en_cours(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    admin_client = _login(admin.email, "s3cret-pass")
    cible = _create_utilisateur(session, Role.AUDITEUR)
    cible_client = _login(cible.email, "s3cret-pass")
    assert cible_client.get("/api/v1/auth/me").status_code == 200

    response = admin_client.post(f"/api/v1/admin/utilisateurs/{cible.id}/desactiver")

    assert response.status_code == 200
    assert response.json()["actif"] is False
    assert cible_client.get("/api/v1/auth/me").status_code == 401


def test_desactiver_utilisateur_inconnu_est_404(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    admin_client = _login(admin.email, "s3cret-pass")

    response = admin_client.post(f"/api/v1/admin/utilisateurs/{uuid.uuid4()}/desactiver")

    assert response.status_code == 404


def test_changer_role_revoque_les_sessions_en_cours_et_change_bien_le_role(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    admin_client = _login(admin.email, "s3cret-pass")
    cible = _create_utilisateur(session, Role.CHERCHEUR)
    cible_client = _login(cible.email, "s3cret-pass")
    assert cible_client.get("/api/v1/auth/me").status_code == 200

    response = admin_client.post(
        f"/api/v1/admin/utilisateurs/{cible.id}/role", json={"role": "AUDITEUR"}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "AUDITEUR"
    # L'ancienne session, qui porte encore le rôle CHERCHEUR dans son jeton, ne doit plus
    # fonctionner : la laisser vivre laisserait agir sous une autorisation périmée.
    assert cible_client.get("/api/v1/auth/me").status_code == 401

    relogged = _login(cible.email, "s3cret-pass")
    assert relogged.get("/api/v1/auth/me").json()["role"] == "AUDITEUR"


def test_changer_role_refuse_le_role_administrateur(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    admin_client = _login(admin.email, "s3cret-pass")
    cible = _create_utilisateur(session, Role.CHERCHEUR)

    response = admin_client.post(
        f"/api/v1/admin/utilisateurs/{cible.id}/role", json={"role": "ADMINISTRATEUR"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "role_non_autorise"


def test_creation_desactivation_et_changement_de_role_sont_journalises(session) -> None:
    """Phase 3 §3.5 — ces trois actions de cycle de vie de compte tracent l'acteur qui a agi
    (l'administrateur), pas le compte cible, avec les anciennes/nouvelles valeurs pour le
    changement de rôle."""
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    admin_client = _login(admin.email, "s3cret-pass")
    cible = _create_utilisateur(session, Role.CHERCHEUR)

    admin_client.post(
        "/api/v1/admin/utilisateurs",
        json={"email": f"journal-{uuid.uuid4()}@example.com", "nom": "Journal", "role": "AUDITEUR"},
    )
    admin_client.post(f"/api/v1/admin/utilisateurs/{cible.id}/role", json={"role": "AUDITEUR"})
    admin_client.post(f"/api/v1/admin/utilisateurs/{cible.id}/desactiver")

    entrees = session.exec(
        select(JournalAudit).where(JournalAudit.acteur_id == admin.id)
    ).all()
    actions = [e.action for e in entrees]
    assert "creation_compte" in actions
    assert "changement_role" in actions
    assert "desactivation_compte" in actions

    changement = next(e for e in entrees if e.action == "changement_role")
    assert changement.ancienne_valeur == "CHERCHEUR"
    assert changement.nouvelle_valeur == "AUDITEUR"
    assert changement.id_ressource == cible.id


def test_lister_rapports_a_affecter_filtre_correctement(session) -> None:
    # Requête globale par conception (file d'attente admin, pas scopée par entreprise) : la base
    # partagée des tests peut déjà contenir d'autres rapports qualifiants issus d'autres tests ou
    # d'une vérification manuelle -- on vérifie une inclusion/exclusion relative, jamais une
    # égalité de liste absolue.
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    non_extrait = _create_rapport(session, entreprise.id, statut=StatutRapport.ENVOYE)
    en_cours = _create_rapport(session, entreprise.id, statut=StatutRapport.EN_EXTRACTION)
    qualifiant = _create_rapport(
        session,
        entreprise.id,
        statut=StatutRapport.EN_EXTRACTION,
        extraction_terminee_le=utcnow(),
    )

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get("/api/v1/admin/rapports/a-affecter")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(qualifiant.id) in ids
    assert str(non_extrait.id) not in ids
    assert str(en_cours.id) not in ids


def test_affecter_happy_path(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    auditeur = _create_utilisateur(session, Role.AUDITEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(
        session,
        entreprise.id,
        statut=StatutRapport.EN_EXTRACTION,
        extraction_terminee_le=utcnow(),
    )

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/affecter", json={"auditeur_id": str(auditeur.id)}
    )

    assert response.status_code == 200
    assert response.json()["statut"] == StatutRapport.AFFECTE_AUDITEUR.value

    notifications = session.exec(
        select(Notification).where(Notification.utilisateur_id == auditeur.id)
    ).all()
    assert len(notifications) == 1


def test_affecter_rapport_deja_affecte(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    auditeur = _create_utilisateur(session, Role.AUDITEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(session, entreprise.id, statut=StatutRapport.VALIDE)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/affecter", json={"auditeur_id": str(auditeur.id)}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "rapport_deja_affecte"


def test_affecter_extraction_non_terminee(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    auditeur = _create_utilisateur(session, Role.AUDITEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(session, entreprise.id, statut=StatutRapport.EN_EXTRACTION)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/affecter", json={"auditeur_id": str(auditeur.id)}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "extraction_non_terminee"


def test_affecter_auditeur_invalide(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    investisseur = _create_utilisateur(session, Role.INVESTISSEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(
        session,
        entreprise.id,
        statut=StatutRapport.EN_EXTRACTION,
        extraction_terminee_le=utcnow(),
    )

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/affecter", json={"auditeur_id": str(investisseur.id)}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "auditeur_invalide"


def test_lister_rapports_en_validation_respecte_lordre_des_avis(session) -> None:
    # Requête globale par conception, même remarque que le test précédent : on vérifie l'ordre
    # RELATIF de nos deux rapports l'un par rapport à l'autre, jamais une liste exacte -- la base
    # partagée des tests peut contenir d'autres rapports EN_VALIDATION issus d'ailleurs.
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    auditeur = _create_utilisateur(session, Role.AUDITEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)

    second = _create_rapport_en_validation(session, entreprise.id, auditeur.id)
    avis_second = session.exec(
        select(AvisAudit).where(AvisAudit.rapport_id == second.id)
    ).first()
    avis_second.date_avis = utcnow()
    session.add(avis_second)

    premier = _create_rapport_en_validation(session, entreprise.id, auditeur.id)
    avis_premier = session.exec(
        select(AvisAudit).where(AvisAudit.rapport_id == premier.id)
    ).first()
    avis_premier.date_avis = utcnow() - timedelta(hours=1)
    session.add(avis_premier)
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get("/api/v1/admin/rapports/en-validation")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(premier.id) in ids
    assert str(second.id) in ids
    assert ids.index(str(premier.id)) < ids.index(str(second.id))


def test_valider_happy_path(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    auditeur = _create_utilisateur(session, Role.AUDITEUR)
    entreprise, utilisateur_entreprise = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport_en_validation(session, entreprise.id, auditeur.id)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/valider", json={"commentaire": "Conforme."}
    )

    assert response.status_code == 200
    assert response.json()["statut"] == StatutRapport.VALIDE.value
    notifications = session.exec(
        select(Notification).where(Notification.utilisateur_id == utilisateur_entreprise.id)
    ).all()
    assert any(n.type == "RAPPORT_VALIDE" for n in notifications)
    score = session.exec(select(ScoreESG).where(ScoreESG.rapport_id == rapport.id)).first()
    assert score is not None
    assert score.score_gouvernance == 80.0  # femmes_conseil_pourcentage=40 -> 40/50 borne -> 80
    assert score.score_environnement is None  # aucun indicateur ENVIRONNEMENT semé pour ce test
    assert score.score_social is None


def test_rejeter_happy_path(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    auditeur = _create_utilisateur(session, Role.AUDITEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport_en_validation(session, entreprise.id, auditeur.id)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/rapports/{rapport.id}/rejeter", json={})

    assert response.status_code == 200
    assert response.json()["statut"] == StatutRapport.REJETE.value


def test_demander_correction_happy_path(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    auditeur = _create_utilisateur(session, Role.AUDITEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport_en_validation(session, entreprise.id, auditeur.id)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(
        f"/api/v1/admin/rapports/{rapport.id}/demander-correction", json={}
    )

    assert response.status_code == 200
    assert response.json()["statut"] == StatutRapport.DEMANDE_CORRECTION.value


def test_decision_avec_statut_invalide_est_rejetee(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(session, entreprise.id, statut=StatutRapport.ENVOYE)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/rapports/{rapport.id}/valider", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "transition_invalide"


def test_valider_sans_aucun_indicateur_est_rejete(session) -> None:
    """Distinct de test_decision_sans_avis_est_rejetee : ici l'avis existe, mais le rapport n'a
    aucun IndicateurESG -- calculer_score (Phase 5 §9) refuse de fabriquer un score sans
    substance, et la transition VALIDE n'a pas lieu (transaction unique, voir valider_rapport)."""
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    auditeur = _create_utilisateur(session, Role.AUDITEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(
        session,
        entreprise.id,
        statut=StatutRapport.EN_VALIDATION,
        extraction_terminee_le=utcnow(),
        auditeur_id=auditeur.id,
    )
    session.add(
        AvisAudit(
            rapport_id=rapport.id, auditeur_id=auditeur.id, decision=DecisionAudit.RECOMMANDE_VALIDATION
        )
    )
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/rapports/{rapport.id}/valider", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "score_incalculable"
    session.refresh(rapport)
    assert rapport.statut == StatutRapport.EN_VALIDATION  # transition annulée, pas de VALIDE partiel


def test_decision_sans_avis_est_rejetee(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    # EN_VALIDATION semé directement, sans AvisAudit -- état normalement inatteignable via l'API.
    rapport = _create_rapport(session, entreprise.id, statut=StatutRapport.EN_VALIDATION)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/rapports/{rapport.id}/valider", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "avis_manquant"


def test_lister_entreprises_publiables_exclut_deja_publiees_et_sans_rapport_valide(session) -> None:
    # `recherche` scope la requête aux seules entreprises de ce test, même raison que
    # test_lister_utilisateurs_par_role_ne_montre_que_le_role_et_les_actifs ci-dessus.
    marqueur = f"Marqueur {uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)

    publiable, _ = _create_entreprise_avec_utilisateur(session)
    publiable.nom = f"{marqueur} publiable"
    session.add(publiable)
    session.commit()
    _create_rapport(session, publiable.id, statut=StatutRapport.VALIDE)

    deja_publiee, _ = _create_entreprise_avec_utilisateur(session)
    deja_publiee.nom = f"{marqueur} deja-publiee"
    _create_rapport(session, deja_publiee.id, statut=StatutRapport.VALIDE)
    deja_publiee.date_publication = utcnow()
    session.add(deja_publiee)

    sans_rapport_valide, _ = _create_entreprise_avec_utilisateur(session)
    sans_rapport_valide.nom = f"{marqueur} sans-rapport-valide"
    session.add(sans_rapport_valide)
    _create_rapport(session, sans_rapport_valide.id, statut=StatutRapport.REJETE)
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/entreprises/publiables", params={"recherche": marqueur, "page_size": 50}
    )

    ids = [item["id"] for item in response.json()["items"]]
    assert str(publiable.id) in ids
    assert str(deja_publiee.id) not in ids
    assert str(sans_rapport_valide.id) not in ids


def test_lister_entreprises_publiables_pagine_par_defaut_a_trois_par_page(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    prefixe = f"Pagination {uuid.uuid4()}"
    for i in range(4):
        entreprise = Entreprise(nom=f"{prefixe} {i}", secteur="Technologies", pays="France")
        session.add(entreprise)
        session.commit()
        _create_rapport(session, entreprise.id, statut=StatutRapport.VALIDE)

    authed_client = _login(admin.email, "s3cret-pass")
    premiere_page = authed_client.get(
        "/api/v1/admin/entreprises/publiables", params={"recherche": prefixe, "page": 1}
    ).json()
    deuxieme_page = authed_client.get(
        "/api/v1/admin/entreprises/publiables", params={"recherche": prefixe, "page": 2}
    ).json()

    assert premiere_page["total"] == 4
    assert premiere_page["pages"] == 2
    assert len(premiere_page["items"]) == 3
    assert len(deuxieme_page["items"]) == 1


def test_lister_entreprises_publiables_recherche_filtre_par_nom(session) -> None:
    # Le nom complet (uuid inclus) sert de motif de recherche, pas juste "Ferme Solaire" -- une
    # exécution précédente de ce test laisse une autre "Ferme Solaire ..." en base (même raison
    # que test_lister_utilisateurs_recherche_filtre_par_email ci-dessus).
    nom_cible = f"Ferme Solaire {uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    cible, _ = _create_entreprise_avec_utilisateur(session)
    cible.nom = nom_cible
    session.add(cible)
    session.commit()
    _create_rapport(session, cible.id, statut=StatutRapport.VALIDE)

    autre, _ = _create_entreprise_avec_utilisateur(session)
    _create_rapport(session, autre.id, statut=StatutRapport.VALIDE)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/entreprises/publiables", params={"recherche": nom_cible}
    )

    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [str(cible.id)]


def test_lister_toutes_les_entreprises_inclut_celles_sans_rapport_ni_compte(session) -> None:
    # Contrairement à /admin/entreprises/publiables, cette route doit remonter une entreprise
    # même sans rapport (statut à None) et même sans compte utilisateur rattaché
    # (utilisateur_id à None) -- c'est précisément ce qui manquait pour piloter les entreprises
    # de référence orphelines (voir la conversation qui a motivé cette route).
    marqueur = f"Marqueur {uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)

    orpheline = Entreprise(nom=f"{marqueur} orpheline", secteur="Mines", pays="Mauritanie")
    session.add(orpheline)
    session.commit()
    session.refresh(orpheline)

    avec_compte, utilisateur = _create_entreprise_avec_utilisateur(session)
    avec_compte.nom = f"{marqueur} avec-compte"
    session.add(avec_compte)
    session.commit()
    _create_rapport(session, avec_compte.id, statut=StatutRapport.REJETE)
    plus_recent = _create_rapport(session, avec_compte.id, statut=StatutRapport.VALIDE)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get("/api/v1/admin/entreprises", params={"recherche": marqueur})

    items = {item["id"]: item for item in response.json()["items"]}
    assert str(orpheline.id) in items
    assert items[str(orpheline.id)]["utilisateur_id"] is None
    assert items[str(orpheline.id)]["nombre_rapports"] == 0
    assert items[str(orpheline.id)]["dernier_statut_rapport"] is None

    assert items[str(avec_compte.id)]["utilisateur_id"] == str(utilisateur.id)
    assert items[str(avec_compte.id)]["nombre_rapports"] == 2
    # Le plus récent des deux rapports (par date_depot), pas le premier créé.
    assert items[str(avec_compte.id)]["dernier_statut_rapport"] == plus_recent.statut.value


def test_publier_happy_path_et_idempotence(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    entreprise, utilisateur_entreprise = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(session, entreprise.id, statut=StatutRapport.VALIDE)
    _create_score(session, rapport.id)

    authed_client = _login(admin.email, "s3cret-pass")
    premiere = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/publier")
    assert premiere.status_code == 200
    assert premiere.json()["date_publication"] is not None

    deuxieme = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/publier")
    assert deuxieme.status_code == 200

    notifications = session.exec(
        select(Notification).where(Notification.utilisateur_id == utilisateur_entreprise.id)
    ).all()
    assert any(n.type == "ENTREPRISE_PUBLIEE" for n in notifications)


def test_publier_sans_rapport_valide_est_rejete(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/publier")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "aucun_rapport_valide"


def test_publier_sans_score_est_rejete(session) -> None:
    """Rapport VALIDE semé directement (sans passer par /valider, donc sans ScoreESG) -- état
    normalement inatteignable via l'API seule depuis que valider_rapport calcule toujours un
    score dans la même transaction (Phase 5 §9), gardé en défense dans publier_entreprise."""
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    _create_rapport(session, entreprise.id, statut=StatutRapport.VALIDE)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/publier")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "score_manquant"


def test_admin_routes_sans_authentification_sont_rejetees() -> None:
    # Un client dédié, jamais celui du module : `client` peut porter le cookie de session
    # laissé par un test antérieur qui s'est connecté avec (ex. les tests de création de
    # compte plus haut) — "sans authentification" doit être garanti, pas supposé par ordre
    # d'exécution.
    anonymous_client = TestClient(app, base_url="https://testserver")
    response = anonymous_client.get("/api/v1/admin/rapports/a-affecter")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_admin_routes_avec_role_entreprise_sont_rejetees(session) -> None:
    user = _create_utilisateur(session, Role.ENTREPRISE)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.get("/api/v1/admin/rapports/a-affecter")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_consulter_fichier_retourne_le_pdf_et_404_si_absent(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    chemin_relatif = f"rapports/test/{uuid.uuid4()}.pdf"
    storage.save_bytes(chemin_relatif, b"%PDF-1.4 contenu de test")
    rapport = _create_rapport(session, entreprise.id, fichier_source=chemin_relatif)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/admin/rapports/{rapport.id}/fichier")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 contenu de test"

    reponse_absente = authed_client.get(f"/api/v1/admin/rapports/{uuid.uuid4()}/fichier")
    assert reponse_absente.status_code == 404
    assert reponse_absente.json()["error"]["code"] == "rapport_introuvable"


def test_lister_versions_reconstruit_la_chaine_dans_l_ordre(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    original = _create_rapport(session, entreprise.id, version=1)
    correction_1 = _create_rapport(
        session, entreprise.id, version=2, rapport_precedent_id=original.id
    )
    correction_2 = _create_rapport(
        session, entreprise.id, version=3, rapport_precedent_id=correction_1.id
    )

    authed_client = _login(admin.email, "s3cret-pass")
    # Interroger depuis n'importe quel maillon de la chaîne doit renvoyer la même séquence
    # complète — c'est tout l'intérêt de remonter d'abord à l'original.
    response = authed_client.get(f"/api/v1/admin/rapports/{correction_1.id}/versions")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids == [str(original.id), str(correction_1.id), str(correction_2.id)]


def test_reactiver_utilisateur_reactive_et_journalise(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    cible = _create_utilisateur(session, Role.AUDITEUR, actif=False)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(f"/api/v1/admin/utilisateurs/{cible.id}/reactiver")

    assert response.status_code == 200
    assert response.json()["actif"] is True

    entree = session.exec(
        select(JournalAudit).where(
            JournalAudit.acteur_id == admin.id,
            JournalAudit.action == "reactivation_compte",
            JournalAudit.id_ressource == cible.id,
        )
    ).first()
    assert entree is not None
    assert entree.ancienne_valeur == "inactif"
    assert entree.nouvelle_valeur == "actif"


def test_lister_utilisateurs_inclut_les_inactifs_seulement_si_demande(session) -> None:
    marqueur = f"marqueur-{uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    inactif = _create_utilisateur_avec_email(session, Role.AUDITEUR, f"{marqueur}-inactif@example.com")
    inactif.actif = False
    session.add(inactif)
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")

    sans_flag = authed_client.get(
        "/api/v1/admin/utilisateurs", params={"role": "AUDITEUR", "recherche": marqueur}
    )
    assert sans_flag.json()["total"] == 0

    avec_flag = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITEUR", "recherche": marqueur, "inclure_inactifs": True},
    )
    assert avec_flag.json()["total"] == 1
    assert avec_flag.json()["items"][0]["id"] == str(inactif.id)


def test_lister_journal_audit_concerne_id_couvre_acteur_et_cible(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    autre_admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    cible = _create_utilisateur(session, Role.AUDITEUR)

    # cible agit elle-même (acteur_id=cible.id)
    auditer(session, cible.id, "connexion", "Utilisateur", cible.id, "succes")
    # un autre admin agit SUR cible (id_ressource=cible.id)
    auditer(session, autre_admin.id, "desactivation_compte", "Utilisateur", cible.id, "succes")
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/journal-audit", params={"concerne_id": str(cible.id), "page_size": 50}
    )

    assert response.status_code == 200
    actions = {item["action"] for item in response.json()["items"]}
    assert "connexion" in actions
    assert "desactivation_compte" in actions


def test_suspendre_et_reactiver_entreprise(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    authed_client = _login(admin.email, "s3cret-pass")

    suspension = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/suspendre")
    assert suspension.status_code == 200
    assert suspension.json()["actif"] is False

    reactivation = authed_client.post(f"/api/v1/admin/entreprises/{entreprise.id}/reactiver")
    assert reactivation.status_code == 200
    assert reactivation.json()["actif"] is True


def test_lister_rapports_entreprise_filtre_par_entreprise(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    autre_entreprise, _ = _create_entreprise_avec_utilisateur(session)
    mien = _create_rapport(session, entreprise.id)
    _create_rapport(session, autre_entreprise.id)

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/admin/entreprises/{entreprise.id}/rapports")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids == [str(mien.id)]


def test_lister_journal_audit_pagine_et_filtre_par_action(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    marqueur_action = f"action-test-{uuid.uuid4()}"
    autre_action = f"autre-action-{uuid.uuid4()}"
    for _ in range(3):
        auditer(session, admin.id, marqueur_action, "Utilisateur", admin.id, "succes")
    auditer(session, admin.id, autre_action, "Utilisateur", admin.id, "succes")
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/journal-audit",
        params={"action": marqueur_action, "page_size": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 2
    assert all(item["action"] == marqueur_action for item in body["items"])


def _dashboard(authed_client: TestClient) -> dict:
    response = authed_client.get("/api/v1/admin/dashboard")
    assert response.status_code == 200
    return response.json()


def test_dashboard_agrege_les_compteurs(session) -> None:
    # Base de test partagée, jamais vide entre les runs — on mesure une DELTA avant/après plutôt
    # qu'une valeur absolue (même principe que les autres listes globales de ce module).
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    authed_client = _login(admin.email, "s3cret-pass")
    avant = _dashboard(authed_client)

    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    _create_rapport(session, entreprise.id, statut=StatutRapport.VALIDE)
    _create_rapport(session, entreprise.id, statut=StatutRapport.REJETE)

    apres = _dashboard(authed_client)
    assert apres["entreprises_inscrites"] - avant["entreprises_inscrites"] == 1
    assert apres["rapports_soumis"] - avant["rapports_soumis"] == 2
    assert apres["rapports_valides"] - avant["rapports_valides"] == 1
    assert apres["rapports_rejetes"] - avant["rapports_rejetes"] == 1


def test_audits_en_retard_respecte_le_sla(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    authed_client = _login(admin.email, "s3cret-pass")
    sla = get_settings().sla_audit_jours
    entreprise, _ = _create_entreprise_avec_utilisateur(session)

    avant = _dashboard(authed_client)
    _create_rapport(
        session,
        entreprise.id,
        statut=StatutRapport.AFFECTE_AUDITEUR,
        date_affectation=utcnow() - timedelta(days=sla + 1),
    )
    _create_rapport(
        session,
        entreprise.id,
        statut=StatutRapport.AFFECTE_AUDITEUR,
        date_affectation=utcnow() - timedelta(days=sla - 1),
    )
    apres = _dashboard(authed_client)

    assert apres["audits_en_retard"] - avant["audits_en_retard"] == 1


def test_demandes_republication_detecte_le_rapport_posterieur(session) -> None:
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    authed_client = _login(admin.email, "s3cret-pass")
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    entreprise.date_publication = utcnow() - timedelta(days=5)
    session.add(entreprise)
    session.commit()

    avant = _dashboard(authed_client)
    _create_rapport(
        session,
        entreprise.id,
        statut=StatutRapport.VALIDE,
        date_depot=utcnow() - timedelta(days=10),
    )
    apres_anterieur = _dashboard(authed_client)
    assert apres_anterieur["demandes_republication"] - avant["demandes_republication"] == 0

    _create_rapport(
        session,
        entreprise.id,
        statut=StatutRapport.VALIDE,
        date_depot=utcnow() - timedelta(days=1),
    )
    apres_posterieur = _dashboard(authed_client)
    assert apres_posterieur["demandes_republication"] - avant["demandes_republication"] == 1


def test_lister_utilisateurs_filtre_par_mot_de_passe_temporaire(session) -> None:
    marqueur = f"marqueur-{uuid.uuid4()}"
    admin = _create_utilisateur(session, Role.ADMINISTRATEUR)
    en_attente = _create_utilisateur_avec_email(
        session, Role.AUDITEUR, f"{marqueur}-attente@example.com"
    )
    en_attente.doit_changer_mot_de_passe = True
    deja_change = _create_utilisateur_avec_email(
        session, Role.AUDITEUR, f"{marqueur}-ok@example.com"
    )
    deja_change.doit_changer_mot_de_passe = False
    session.add_all([en_attente, deja_change])
    session.commit()

    authed_client = _login(admin.email, "s3cret-pass")
    response = authed_client.get(
        "/api/v1/admin/utilisateurs",
        params={"role": "AUDITEUR", "recherche": marqueur, "doit_changer_mot_de_passe": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(en_attente.id)
