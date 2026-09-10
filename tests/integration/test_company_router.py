import uuid

import pymupdf
from fastapi.testclient import TestClient
from sqlmodel import select

from app.auth.hashing import hash_password
from app.auth.models import Utilisateur
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Entreprise
from app.core.enums import CanalDepot, Role, StatutRapport, TypeRapport
from app.ingestion.models import (
    DonneeCarbone,
    IndicateurESG,
    PreuveDocumentaire,
    RapportESG,
)
from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait
from app.main import app

client = TestClient(app, base_url="https://testserver")


def _minimal_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def _create_entreprise_utilisateur(session, *, password: str, avec_entreprise: bool = True) -> Utilisateur:
    entreprise = None
    if avec_entreprise:
        entreprise = Entreprise(nom=f"Entreprise {uuid.uuid4()}", secteur="Technologies", pays="France")
        session.add(entreprise)
        session.commit()
        session.refresh(entreprise)

    user = Utilisateur(
        email=f"entreprise-{uuid.uuid4()}@example.com",
        mot_de_passe_hache=hash_password(password),
        role=Role.ENTREPRISE,
        actif=True,
    )
    session.add(user)
    session.commit()

    if entreprise is not None:
        entreprise.utilisateur_id = user.id
        session.add(entreprise)
        session.commit()

    session.refresh(user)
    return user


def _login(email: str, password: str) -> TestClient:
    authed_client = TestClient(app, base_url="https://testserver")
    response = authed_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})
    return authed_client


def test_deposer_rapport_avec_pdf_valide_retourne_201_statut_envoye(session, monkeypatch) -> None:
    monkeypatch.setattr("app.company.rapports.run_extraction_pipeline", lambda *_args, **_kwargs: None)
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 201
    assert response.json()["statut"] == StatutRapport.ENVOYE.value
    assert response.json()["canal"] == CanalDepot.ENTREPRISE.value


def test_deposer_rapport_sans_authentification_est_rejete() -> None:
    response = client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_deposer_rapport_avec_role_investisseur_est_rejete(session) -> None:
    user = Utilisateur(
        email=f"investisseur-{uuid.uuid4()}@example.com",
        mot_de_passe_hache=hash_password("s3cret-pass"),
        role=Role.INVESTISSEUR,
        actif=True,
    )
    session.add(user)
    session.commit()
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_deposer_rapport_fichier_non_pdf_est_rejete(session) -> None:
    """Le Content-Type et l'extension sont fournis par le client, donc falsifiables — seule la
    signature binaire réelle (app/company/upload_validation.py::valider_pdf) fait foi."""
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.txt", b"pas un pdf", "text/plain")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "signature_invalide"


def test_deposer_rapport_sans_entreprise_associee_est_rejete(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass", avec_entreprise=False)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "entreprise_non_rattachee"


def test_deposer_rapport_sur_entreprise_suspendue_est_rejete(session, monkeypatch) -> None:
    monkeypatch.setattr("app.company.rapports.run_extraction_pipeline", lambda *_args, **_kwargs: None)
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    user.entreprise.actif = False
    session.add(user.entreprise)
    session.commit()
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "entreprise_suspendue"


def test_lister_rapports_ne_montre_que_ceux_de_lentreprise_courante(session) -> None:
    proprietaire = _create_entreprise_utilisateur(session, password="s3cret-pass")
    autre = _create_entreprise_utilisateur(session, password="s3cret-pass")
    mien = RapportESG(
        entreprise_id=proprietaire.entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        fichier_source="rapports/test/mien.pdf",
    )
    dautrui = RapportESG(
        entreprise_id=autre.entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        fichier_source="rapports/test/dautrui.pdf",
    )
    session.add(mien)
    session.add(dautrui)
    session.commit()
    session.refresh(mien)

    authed_client = _login(proprietaire.email, "s3cret-pass")
    response = authed_client.get("/api/v1/company/rapports")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert str(mien.id) in ids
    assert str(dautrui.id) not in ids


def test_lister_rapports_sans_authentification_est_rejete() -> None:
    response = client.get("/api/v1/company/rapports")

    assert response.status_code == 401


def test_deposer_rapport_genere_le_nom_de_stockage_cote_serveur(session, monkeypatch) -> None:
    """Phase 4 §4.2 : le nom de fichier fourni par le client n'apparaît jamais dans le chemin de
    stockage, même assaini — seuls des identifiants déjà connus côté serveur le déterminent."""
    monkeypatch.setattr("app.company.rapports.run_extraction_pipeline", lambda *_a, **_k: None)
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("../../etc/passwd-mais-pdf.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 201
    fichier_source = response.json()["fichier_source"]
    assert "passwd" not in fichier_source
    assert fichier_source == f"rapports/{user.entreprise.id}/{response.json()['id']}.pdf"


def test_deposer_rapport_fichier_trop_volumineux_est_rejete(session, monkeypatch) -> None:
    monkeypatch.setattr("app.company.upload_validation.TAILLE_MAX_OCTETS", 100)
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "fichier_trop_volumineux"


def test_deposer_rapport_fichier_vide_est_rejete(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", b"", "application/pdf")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "fichier_vide"


def test_deposer_rapport_pdf_chiffre_est_rejete(session) -> None:
    doc = pymupdf.open()
    doc.new_page()
    contenu_chiffre = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="s3cret", owner_pw="s3cret"
    )
    doc.close()
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", contenu_chiffre, "application/pdf")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pdf_chiffre"


def test_deposer_rapport_doublon_est_rejete(session, monkeypatch) -> None:
    monkeypatch.setattr("app.company.rapports.run_extraction_pipeline", lambda *_a, **_k: None)
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")
    contenu = _minimal_pdf_bytes()

    premier = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", contenu, "application/pdf")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )
    assert premier.status_code == 201

    deuxieme = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("copie.pdf", contenu, "application/pdf")},
        data={"type": TypeRapport.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert deuxieme.status_code == 422
    assert deuxieme.json()["error"]["code"] == "doublon_detecte"


def test_creer_correction_happy_path_incremente_la_version(session, monkeypatch) -> None:
    monkeypatch.setattr("app.company.rapports.run_extraction_pipeline", lambda *_a, **_k: None)
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    original = RapportESG(
        entreprise_id=user.entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        statut=StatutRapport.DEMANDE_CORRECTION,
        fichier_source="rapports/test/original.pdf",
    )
    session.add(original)
    session.commit()
    session.refresh(original)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        f"/api/v1/company/rapports/{original.id}/corrections",
        files={"fichier": ("correction.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"annee_reporting": "2024"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["version"] == 2
    assert body["rapport_precedent_id"] == str(original.id)
    assert body["statut"] == StatutRapport.ENVOYE.value
    assert body["id"] != str(original.id)

    # L'original n'est jamais réécrit — il reste DEMANDE_CORRECTION indéfiniment (Phase 0).
    session.refresh(original)
    assert original.statut == StatutRapport.DEMANDE_CORRECTION
    assert original.fichier_source == "rapports/test/original.pdf"


def test_creer_correction_sur_un_rapport_pas_en_attente_est_rejetee(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    rapport = RapportESG(
        entreprise_id=user.entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        statut=StatutRapport.EN_VALIDATION,
        fichier_source="rapports/test/dummy.pdf",
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        f"/api/v1/company/rapports/{rapport.id}/corrections",
        files={"fichier": ("correction.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "transition_invalide"


def test_creer_correction_sur_le_rapport_dune_autre_entreprise_est_404(session) -> None:
    proprietaire = _create_entreprise_utilisateur(session, password="s3cret-pass")
    autre = _create_entreprise_utilisateur(session, password="s3cret-pass")
    rapport = RapportESG(
        entreprise_id=proprietaire.entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        statut=StatutRapport.DEMANDE_CORRECTION,
        fichier_source="rapports/test/dummy.pdf",
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)
    authed_client = _login(autre.email, "s3cret-pass")

    response = authed_client.post(
        f"/api/v1/company/rapports/{rapport.id}/corrections",
        files={"fichier": ("correction.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"annee_reporting": "2024"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "rapport_introuvable"


def test_consulter_rapport_dune_autre_entreprise_est_404(session) -> None:
    proprietaire = _create_entreprise_utilisateur(session, password="s3cret-pass")
    autre = _create_entreprise_utilisateur(session, password="s3cret-pass")
    rapport = RapportESG(
        entreprise_id=proprietaire.entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        fichier_source="rapports/test/dummy.pdf",
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)

    authed_client = _login(autre.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/company/rapports/{rapport.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "rapport_introuvable"


def test_consulter_rapport_inexistant_est_404(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.get(f"/api/v1/company/rapports/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "rapport_introuvable"


def test_consulter_rapport_retourne_le_statut_courant(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    rapport = RapportESG(
        entreprise_id=user.entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        fichier_source="rapports/test/dummy.pdf",
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)

    authed_client = _login(user.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/company/rapports/{rapport.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(rapport.id)
    assert response.json()["statut"] == StatutRapport.ENVOYE.value


def test_pipeline_echec_docling_marque_extraction_erreur_sans_terminee_le(session, monkeypatch) -> None:
    from app.ingestion.extractor import run_extraction_pipeline

    def _echec(*_args, **_kwargs):
        raise RuntimeError("docling indisponible pour ce test")

    monkeypatch.setattr("app.ingestion.extractor.docling_pipeline.convert_pdf", _echec)

    entreprise = Entreprise(nom="Cible Test", secteur="Technologies", pays="France")
    session.add(entreprise)
    session.commit()
    rapport = RapportESG(
        entreprise_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        fichier_source="rapports/test/dummy.pdf",
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)

    run_extraction_pipeline(rapport.id, 2024)

    session.refresh(rapport)
    assert rapport.extraction_erreur == "docling_conversion_echouee"
    assert rapport.extraction_terminee_le is None
    assert rapport.statut == StatutRapport.EN_EXTRACTION


def test_pipeline_reussi_persiste_donnee_carbone_et_indicateur_esg_et_marque_termine(
    session, monkeypatch
) -> None:
    from app.ingestion import extractor
    from app.ingestion.docling_pipeline import ConversionResult

    fake_conversion = ConversionResult(
        document=object(),
        status="ok",
        errors=[],
        pages_docling=5,
        pages_pymupdf=5,
        pages_correspondent=True,
        elapsed_s=0.1,
    )
    monkeypatch.setattr(
        "app.ingestion.extractor.docling_pipeline.convert_pdf", lambda *_a, **_k: fake_conversion
    )
    monkeypatch.setattr(
        "app.ingestion.extractor.docling_pipeline.persist_docling_json", lambda *_a, **_k: None
    )
    monkeypatch.setattr("app.ingestion.extractor._build_search_index", lambda *_a, **_k: {})

    class _FakeEmbedModel:
        """Stub minimal : app/ingestion/extractor.py::run_extraction_pipeline appelle désormais
        .encode() sur ce modèle AVANT la conversion Docling (Phase 5 §9, contournement d'un
        conflit d'initialisation natif Docling/PaddleOCR + PyTorch), même quand la recherche
        sémantique elle-même est mockée ci-dessous."""

        def encode(self, *_a, **_k):
            return {"dense_vecs": []}

    monkeypatch.setattr("app.ingestion.extractor._get_embed_model", lambda: _FakeEmbedModel())
    monkeypatch.setattr(
        "app.ingestion.extractor._build_context", lambda *_a, **_k: ("contexte factice", [3])
    )

    fake_extraction = ExtractionEntreprise(
        entreprise="Cible Test",
        indicateurs=[
            IndicateurExtrait(code="scope_1", valeur=100.0, unite="tCO2e", page_source=3, trouve=True),
            IndicateurExtrait(
                code="intensite_scope_1_2_marketbased",
                valeur=42.0,
                unite="gCO2e/kWh",
                page_source=3,
                trouve=True,
            ),
            IndicateurExtrait(code="scope_3", valeur=None, unite=None, page_source=None, trouve=False),
        ],
    )
    monkeypatch.setattr(
        "app.ingestion.extractor._call_claude_extraction", lambda **_k: fake_extraction
    )

    def _fake_proof(*, source_pdf_path, nom_document, annee, nombre_pages_total, page, rapport_id):
        return PreuveDocumentaire(
            nom_document=nom_document,
            annee=annee,
            nombre_pages_total=nombre_pages_total,
            page_debut=page,
            page_fin=page,
            pdf_extrait_genere=f"preuves/{rapport_id}/page_{page}.pdf",
        )

    monkeypatch.setattr("app.ingestion.extractor.proof_generator.generate_page_proof", _fake_proof)

    entreprise = Entreprise(nom="Cible Test", secteur="Technologies", pays="France")
    session.add(entreprise)
    session.commit()
    rapport = RapportESG(
        entreprise_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        fichier_source="rapports/test/dummy.pdf",
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)

    extractor.run_extraction_pipeline(rapport.id, 2024)

    session.refresh(rapport)
    assert rapport.extraction_erreur is None
    assert rapport.extraction_terminee_le is not None

    donnees_carbone = session.exec(
        select(DonneeCarbone).where(DonneeCarbone.rapport_id == rapport.id)
    ).all()
    indicateurs = session.exec(
        select(IndicateurESG).where(IndicateurESG.rapport_id == rapport.id)
    ).all()
    assert len(donnees_carbone) == 1
    assert donnees_carbone[0].scope == 1
    assert donnees_carbone[0].valeur_tonnes_co2e == 100.0
    assert len(indicateurs) == 1
    assert indicateurs[0].code == "intensite_scope_1_2_marketbased"

    # Les deux valeurs trouvées sont sur la même page (3) : une seule preuve doit être créée et
    # partagée, pas une par indicateur.
    assert donnees_carbone[0].preuve_id == indicateurs[0].preuve_id
