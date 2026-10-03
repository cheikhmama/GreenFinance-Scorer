import uuid

import pymupdf
from fastapi.testclient import TestClient
from sqlmodel import select

from app.auth.hashing import hash_password
from app.auth.models import User
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.company.models import Company
from app.core import storage
from app.core.database import utcnow
from app.core.enums import (
    ConfidenceLevel,
    DataMethod,
    MetricCoverageStatus,
    Pillar,
    RegistrationStatus,
    ReportStatus,
    ReportType,
    Role,
    SubmissionChannel,
)
from app.core.models import Notification
from app.ingestion.models import (
    CarbonEmission,
    ESGMetric,
    ESGReport,
    Evidence,
    MetricCoverage,
)
from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait
from app.investor.entreprises import couverture_publique
from app.main import app

client = TestClient(app, base_url="https://testserver")


def _minimal_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def _create_entreprise_utilisateur(session, *, password: str, avec_entreprise: bool = True) -> User:
    entreprise = None
    if avec_entreprise:
        entreprise = Company(name=f"Entreprise {uuid.uuid4()}", sector="Technologies", country="France")
        session.add(entreprise)
        session.commit()
        session.refresh(entreprise)

    user = User(
        email=f"entreprise-{uuid.uuid4()}@example.com",
        password_hash=hash_password(password),
        role=Role.ENTERPRISE,
        active=True,
    )
    session.add(user)
    session.commit()

    if entreprise is not None:
        entreprise.owner_user_id = user.id
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


def test_consulter_mon_profil_retourne_la_fiche_entreprise(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.get("/api/v1/company/profil")

    assert response.status_code == 200
    body = response.json()
    assert body["name"].startswith("Entreprise ")
    assert body["sector"] == "Technologies"
    assert body["country"] == "France"


def test_mon_profil_montre_mon_identifiant_fiscal_mais_pas_la_vue_investisseur(session) -> None:
    from app.company.models import Company as Entreprise
    from app.core.enums import TaxIdType
    from app.investor.schemas import EntreprisePublieePublic

    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    entreprise = session.exec(
        select(Entreprise).where(Entreprise.owner_user_id == user.id)
    ).one()
    entreprise.tax_id, entreprise.tax_id_type = "12345678", TaxIdType.NIF
    session.add(entreprise)
    session.commit()

    body = _login(user.email, "s3cret-pass").get("/api/v1/company/profil").json()

    assert (body["tax_id"], body["tax_id_type"]) == ("12345678", "NIF")
    # L'identifiant fiscal reste propre à l'entreprise : la fiche Investisseur ne le porte pas.
    assert "tax_id" not in EntreprisePublieePublic.model_fields


def test_consulter_mon_profil_sans_entreprise_rattachee_est_refuse_proprement(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass", avec_entreprise=False)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.get("/api/v1/company/profil")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "entreprise_non_rattachee"


def test_deposer_rapport_avec_pdf_valide_retourne_201_statut_envoye(session, monkeypatch) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == ReportStatus.EXTRACTING.value
    assert "extraction_status" not in response.json()
    assert response.json()["channel"] == SubmissionChannel.ENTREPRISE.value


def test_deposer_rapport_notifie_lentreprise(session, monkeypatch) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    rapport_id = uuid.UUID(response.json()["id"])
    notification = session.exec(
        select(Notification).where(
            Notification.user_id == user.id, Notification.type == "RAPPORT_DEPOSE"
        )
    ).one()
    assert notification.resource_id == rapport_id


def test_deposer_rapport_sans_authentification_est_rejete() -> None:
    response = client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_deposer_rapport_avec_role_investisseur_est_rejete(session) -> None:
    user = User(
        email=f"investisseur-{uuid.uuid4()}@example.com",
        password_hash=hash_password("s3cret-pass"),
        role=Role.INVESTOR,
        active=True,
    )
    session.add(user)
    session.commit()
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
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
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "signature_invalide"


def test_deposer_rapport_sans_entreprise_associee_est_rejete(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass", avec_entreprise=False)
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "entreprise_non_rattachee"


def test_deposer_rapport_sur_entreprise_suspendue_est_rejete(session, monkeypatch) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert user.company is not None
    user.company.status = RegistrationStatus.SUSPENDED
    session.add(user.company)
    session.commit()
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "entreprise_suspendue"


def test_lister_rapports_ne_montre_que_ceux_de_lentreprise_courante(session) -> None:
    proprietaire = _create_entreprise_utilisateur(session, password="s3cret-pass")
    autre = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert proprietaire.company is not None
    assert autre.company is not None
    mien = ESGReport(
        company_id=proprietaire.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/mien.pdf",
        submitted_at=utcnow(),
    )
    dautrui = ESGReport(
        company_id=autre.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/dautrui.pdf",
        submitted_at=utcnow(),
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
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert user.company is not None
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("../../etc/passwd-mais-pdf.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 201
    fichier_source = response.json()["source_file"]
    assert "passwd" not in fichier_source
    assert fichier_source == f"rapports/{user.company.id}/{response.json()['id']}.pdf"


def test_deposer_rapport_fichier_trop_volumineux_est_rejete(session, monkeypatch) -> None:
    monkeypatch.setattr("app.company.upload_validation.TAILLE_MAX_OCTETS", 100)
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", _minimal_pdf_bytes(), "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "fichier_trop_volumineux"


def test_deposer_rapport_fichier_vide_est_rejete(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", b"", "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "fichier_vide"


def test_deposer_rapport_pdf_chiffre_est_rejete(session) -> None:
    doc = pymupdf.open()
    doc.new_page()
    contenu_chiffre = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,  # type: ignore[attr-defined]  # absent des stubs pymupdf, existe au runtime
        user_pw="s3cret",
        owner_pw="s3cret",
    )
    doc.close()
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", contenu_chiffre, "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pdf_chiffre"


def test_deposer_rapport_doublon_est_rejete(session, monkeypatch) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")
    contenu = _minimal_pdf_bytes()

    premier = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("rapport.pdf", contenu, "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2024"},
    )
    assert premier.status_code == 201
    # Une seule déclaration active à la fois (tâche 5.9) : le premier rapport est clos, pour que
    # seul le doublon de fichier explique le refus.
    clos = session.get(ESGReport, uuid.UUID(premier.json()["id"]))
    assert clos is not None
    clos.status = ReportStatus.REJECTED
    session.add(clos)
    session.commit()

    deuxieme = authed_client.post(
        "/api/v1/company/rapports",
        files={"fichier": ("copie.pdf", contenu, "application/pdf")},
        data={"type": ReportType.RAPPORT_ESG.value, "annee_reporting": "2023"},
    )

    assert deuxieme.status_code == 422
    assert deuxieme.json()["error"]["code"] == "doublon_detecte"


def test_creer_correction_happy_path_incremente_la_version(session, monkeypatch) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert user.company is not None
    original = ESGReport(
        company_id=user.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        status=ReportStatus.REVISION_REQUESTED,
        source_file="rapports/test/original.pdf",
        submitted_at=utcnow(),
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
    assert body["previous_report_id"] == str(original.id)
    assert body["status"] == ReportStatus.EXTRACTING.value
    assert body["id"] != str(original.id)

    # L'original n'est jamais réécrit — il reste DEMANDE_CORRECTION indéfiniment (Phase 0).
    session.refresh(original)
    assert original.status == ReportStatus.REVISION_REQUESTED
    assert original.source_file == "rapports/test/original.pdf"


def test_creer_correction_sur_un_rapport_pas_en_attente_est_rejetee(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert user.company is not None
    rapport = ESGReport(
        company_id=user.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        status=ReportStatus.PENDING_DECISION,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
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
    assert proprietaire.company is not None
    rapport = ESGReport(
        company_id=proprietaire.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        status=ReportStatus.REVISION_REQUESTED,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
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
    assert proprietaire.company is not None
    rapport = ESGReport(
        company_id=proprietaire.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
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
    assert user.company is not None
    rapport = ESGReport(
        company_id=user.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)

    authed_client = _login(user.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/company/rapports/{rapport.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(rapport.id)
    assert response.json()["status"] == ReportStatus.EXTRACTING.value


def test_pipeline_echec_docling_marque_extraction_erreur_sans_terminee_le(session, monkeypatch) -> None:
    from app.ingestion.extractor import run_extraction_pipeline

    def _echec(*_args, **_kwargs):
        raise RuntimeError("docling indisponible pour ce test")

    monkeypatch.setattr("app.ingestion.extractor.docling_pipeline.convert_pdf", _echec)
    # _get_embed_model().encode(...) s'exécute désormais AVANT convert_pdf (Phase 5 §9,
    # contournement d'un conflit d'initialisation natif Docling/PaddleOCR + PyTorch) -- sans ce
    # mock, ce test censé échouer vite au niveau Docling chargeait pour de vrai le modèle bge-m3
    # avant même d'atteindre le point qu'il teste. Même stub minimal que le test voisin
    # (test_pipeline_reussi_persiste_donnee_carbone_et_indicateur_esg_et_marque_termine).
    class _FakeEmbedModel:
        def encode(self, *_a, **_k):
            return {"dense_vecs": []}

    monkeypatch.setattr("app.ingestion.extractor._get_embed_model", lambda: _FakeEmbedModel())

    entreprise = Company(name="Cible Test", sector="Technologies", country="France")
    session.add(entreprise)
    session.commit()
    rapport = ESGReport(
        company_id=entreprise.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)

    run_extraction_pipeline(rapport.id, 2024)

    session.refresh(rapport)
    assert rapport.extraction_error == "docling_conversion_echouee"
    assert rapport.extraction_finished_at is None
    assert rapport.status == ReportStatus.EXTRACTION_FAILED


def _simuler_pipeline_extraction(
    monkeypatch, extraction: ExtractionEntreprise, document: object | None = None
) -> None:
    """Remplace Docling, l'indexation, le modèle d'embedding, le LLM et la génération de preuve
    par des doubles : run_extraction_pipeline ne dépend plus que de `extraction`, la réponse
    simulée du LLM (un seul passage, la relance groupée est court-circuitée)."""
    from app.ingestion import extractor
    from app.ingestion.docling_pipeline import ConversionResult

    fake_conversion = ConversionResult(
        # Double minimal par défaut : la localisation des preuves (tâche 5.5) échoue alors sans
        # conséquence ; un test qui la vérifie passe une vraie sortie Docling.
        document=document if document is not None else object(),  # type: ignore[arg-type]
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

    def _fake_build_context(_search_index, _embed_model, codes, _budget_tokens):
        # Nouvelle signature à 4 arguments (Phase 6) et 3-tuple en retour. Ne renvoie des pages
        # que pour le 1er passage (tous les codes) — pour la relance groupée (codes_manquants,
        # un sous-ensemble), une liste vide court-circuite le 2e appel LLM (voir
        # run_extraction_pipeline) et garde ce test à un seul appel, comme avant.
        pages = [3] if len(codes) == len(extractor.INDICATEURS_CIBLES) else []
        return "contexte factice", pages, {code: [] for code in codes}

    monkeypatch.setattr("app.ingestion.extractor._build_context", _fake_build_context)

    monkeypatch.setattr("app.ingestion.extractor._call_llm_extraction", lambda **_k: extraction)

    def _fake_proof(*, source_pdf_path, nom_document, annee, nombre_pages_total, page, rapport_id):
        return Evidence(
            document_name=nom_document,
            year=annee,
            total_pages=nombre_pages_total,
            page_start=page,
            page_end=page,
            excerpt_pdf_path=f"preuves/{rapport_id}/page_{page}.pdf",
        )

    monkeypatch.setattr("app.ingestion.extractor.proof_generator.generate_page_proof", _fake_proof)


def _rapport_a_extraire(session) -> ESGReport:
    entreprise = Company(name="Cible Test", sector="Technologies", country="France")
    session.add(entreprise)
    session.commit()
    rapport = ESGReport(
        company_id=entreprise.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)
    return rapport


def test_pipeline_reussi_persiste_donnee_carbone_et_indicateur_esg_et_marque_termine(
    session, monkeypatch
) -> None:
    from app.ingestion import extractor

    fake_extraction = ExtractionEntreprise(
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
                code="intensite_scope_1_2_marketbased",
                valeur=42.0,
                unite="gCO2e/kWh",
                page_source=3,
                trouve=True,
            ),
            IndicateurExtrait(code="scope_3", valeur=None, unite=None, page_source=None, trouve=False),
        ],
    )
    _simuler_pipeline_extraction(monkeypatch, fake_extraction)
    rapport = _rapport_a_extraire(session)

    extractor.run_extraction_pipeline(rapport.id, 2024)

    session.refresh(rapport)
    assert rapport.extraction_error is None
    assert rapport.extraction_finished_at is not None
    assert rapport.status == ReportStatus.AWAITING_ASSIGNMENT

    donnees_carbone = session.exec(
        select(CarbonEmission).where(CarbonEmission.report_id == rapport.id)
    ).all()
    indicateurs = session.exec(
        select(ESGMetric).where(ESGMetric.report_id == rapport.id)
    ).all()
    assert len(donnees_carbone) == 1
    assert donnees_carbone[0].scope == 1
    assert donnees_carbone[0].tonnes_co2e == 100.0
    assert donnees_carbone[0].raw_value == "100 tCO2e"
    assert donnees_carbone[0].confidence == ConfidenceLevel.ELEVE
    assert len(indicateurs) == 1
    assert indicateurs[0].metric_code == "intensite_scope_1_2_marketbased"

    # Les deux valeurs trouvées sont sur la même page (3) : une seule preuve doit être créée et
    # partagée, pas une par indicateur.
    assert donnees_carbone[0].proof_id == indicateurs[0].proof_id


def test_pipeline_ne_persiste_quun_indicateur_par_code_meme_si_le_llm_le_repete(
    session, monkeypatch
) -> None:
    """Le LLM peut renvoyer deux fois le même code : la première occurrence exploitable
    l'emporte, jamais deux lignes (uq_esg_metrics_report_metric_code rejetterait sinon toute
    l'extraction)."""
    from app.ingestion import extractor

    code = "intensite_scope_1_2_marketbased"
    _simuler_pipeline_extraction(
        monkeypatch,
        ExtractionEntreprise(
            entreprise="Cible Test",
            indicateurs=[
                IndicateurExtrait(code=code, valeur=42.0, unite="gCO2e/kWh", page_source=3, trouve=True),
                IndicateurExtrait(code=code, valeur=None, unite=None, page_source=None, trouve=False),
                IndicateurExtrait(code=code, valeur=99.0, unite="gCO2e/kWh", page_source=3, trouve=True),
            ],
        ),
    )
    rapport = _rapport_a_extraire(session)

    extractor.run_extraction_pipeline(rapport.id, 2024)

    session.refresh(rapport)
    assert rapport.status == ReportStatus.AWAITING_ASSIGNMENT
    indicateurs = session.exec(select(ESGMetric).where(ESGMetric.report_id == rapport.id)).all()
    assert [(i.metric_code, i.value) for i in indicateurs] == [(code, 42.0)]


def test_pipeline_relance_llm_pour_les_codes_manquants_persiste_le_statut_couverture(
    session, monkeypatch
) -> None:
    """Un code encore manquant après le 1er passage déclenche UN SEUL appel LLM de rattrapage
    (jamais un par code, voir extractor.py) ; si ce 2e appel fournit une citation explicite de
    non-divulgation, le code passe à ABSENT_CONFIRME plutôt que de rester NON_TROUVE."""
    from app.ingestion import extractor
    from app.ingestion.docling_pipeline import ConversionResult

    fake_conversion = ConversionResult(
        document=object(),  # type: ignore[arg-type]  # double minimal, jamais inspecté comme un vrai DoclingDocument ici
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
        def encode(self, *_a, **_k):
            return {"dense_vecs": []}

    monkeypatch.setattr("app.ingestion.extractor._get_embed_model", lambda: _FakeEmbedModel())

    def _fake_build_context(_search_index, _embed_model, codes, _budget_tokens):
        # Pages non vides sur la relance (contrairement au test précédent) pour que le 2e appel
        # LLM ait effectivement lieu.
        pages = [3] if len(codes) == len(extractor.INDICATEURS_CIBLES) else [7]
        return "contexte factice", pages, {code: [] for code in codes}

    monkeypatch.setattr("app.ingestion.extractor._build_context", _fake_build_context)

    # Le LLM répond pour CHAQUE code demandé (comme l'exige le prompt réel) : tous trouvés sauf
    # scope_3, pour isoler ce seul code dans codes_manquants — sans ça, les ~21 codes non
    # mentionnés compteraient eux aussi comme manquants (_indicateur_trouve les traite comme
    # absents faute d'entrée), ce que ce test ne veut pas exercer ici.
    fake_extraction_premier_passage = ExtractionEntreprise(
        entreprise="Cible Test",
        indicateurs=[
            IndicateurExtrait(
                code=cible.code,
                valeur=None if cible.code == "scope_3" else 1.0,
                unite=None if cible.code == "scope_3" else "unite",
                page_source=None if cible.code == "scope_3" else 3,
                trouve=cible.code != "scope_3",
            )
            for cible in extractor.INDICATEURS_CIBLES
        ],
    )
    fake_extraction_relance = ExtractionEntreprise(
        entreprise="Cible Test",
        indicateurs=[
            IndicateurExtrait(
                code="scope_3",
                valeur=None,
                unite=None,
                page_source=None,
                trouve=False,
                non_divulgation_citation="Scope 3 non communique cette annee",
                non_divulgation_page=7,
            ),
        ],
    )
    appels_llm: list[list[str]] = []

    def _fake_call_llm_extraction(*, nom_entreprise, context, codes):
        appels_llm.append(list(codes))
        if len(codes) == len(extractor.INDICATEURS_CIBLES):
            return fake_extraction_premier_passage
        return fake_extraction_relance

    monkeypatch.setattr("app.ingestion.extractor._call_llm_extraction", _fake_call_llm_extraction)

    def _fake_proof(*, source_pdf_path, nom_document, annee, nombre_pages_total, page, rapport_id):
        return Evidence(
            document_name=nom_document,
            year=annee,
            total_pages=nombre_pages_total,
            page_start=page,
            page_end=page,
            excerpt_pdf_path=f"preuves/{rapport_id}/page_{page}.pdf",
        )

    monkeypatch.setattr("app.ingestion.extractor.proof_generator.generate_page_proof", _fake_proof)

    entreprise = Company(name="Cible Relance", sector="Technologies", country="France")
    session.add(entreprise)
    session.commit()
    rapport = ESGReport(
        company_id=entreprise.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)

    extractor.run_extraction_pipeline(rapport.id, 2024)

    session.refresh(rapport)
    assert rapport.extraction_error is None
    assert rapport.extraction_finished_at is not None

    assert len(appels_llm) == 2
    assert appels_llm[1] == ["scope_3"]

    couvertures = session.exec(
        select(MetricCoverage).where(MetricCoverage.report_id == rapport.id)
    ).all()
    par_code = {c.metric_code: c for c in couvertures}
    assert par_code["scope_1"].status == MetricCoverageStatus.TROUVE
    assert par_code["scope_3"].status == MetricCoverageStatus.ABSENT_CONFIRME
    assert len(couvertures) == len(extractor.INDICATEURS_CIBLES)

    # couverture_publique (app/investor/entreprises.py) lit désormais .statut au lieu de .trouve —
    # doit continuer à fonctionner après le passage au statut à 3 valeurs. scope_3 est le seul code
    # pas TROUVE (ABSENT_CONFIRME compte comme "manquant" au même titre que NON_TROUVE, voir
    # CouvertureResume.codes_manquants).
    resume = couverture_publique(session, rapport)
    assert resume.total_targets == len(extractor.INDICATEURS_CIBLES)
    assert resume.found == len(extractor.INDICATEURS_CIBLES) - 1
    assert resume.missing_codes == ["scope_3"]


def _create_admin_utilisateur(session, *, password: str = "s3cret-pass") -> User:
    user = User(
        email=f"admin-{uuid.uuid4()}@example.com",
        password_hash=hash_password(password),
        role=Role.ADMIN,
        active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_importer_rapport_par_url_entreprise_happy_path_marque_canal_automatique(
    session, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.company.rapports.telecharger_pdf_depuis_url", lambda _url: _minimal_pdf_bytes()
    )
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports/import-url",
        json={
            "url": "https://exemple-public.test/rapport.pdf",
            "type": ReportType.RAPPORT_ESG.value,
            "fiscal_year": 2024,
        },
    )

    assert response.status_code == 201
    assert response.json()["channel"] == SubmissionChannel.AUTOMATIQUE.value
    assert response.json()["status"] == ReportStatus.EXTRACTING.value


def test_importer_rapport_par_url_entreprise_ignore_un_entreprise_id_fourni(
    session, monkeypatch
) -> None:
    """Un Entreprise ne peut jamais désigner une autre entreprise que la sienne, même en le
    demandant explicitement dans le corps -- même posture que le reste de l'espace Entreprise."""
    monkeypatch.setattr(
        "app.company.rapports.telecharger_pdf_depuis_url", lambda _url: _minimal_pdf_bytes()
    )
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    autre = Company(name=f"Autre {uuid.uuid4()}", sector="Technologies", country="France")
    session.add(autre)
    session.commit()
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports/import-url",
        json={
            "url": "https://exemple-public.test/rapport.pdf",
            "type": ReportType.RAPPORT_ESG.value,
            "fiscal_year": 2024,
            "company_id": str(autre.id),
        },
    )

    assert response.status_code == 201
    rapport = session.get(ESGReport, uuid.UUID(response.json()["id"]))
    assert rapport is not None
    assert user.company is not None
    assert rapport.company_id == user.company.id
    assert rapport.company_id != autre.id


def test_importer_rapport_par_url_admin_sans_entreprise_id_est_rejete(session) -> None:
    admin = _create_admin_utilisateur(session)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports/import-url",
        json={
            "url": "https://exemple-public.test/rapport.pdf",
            "type": ReportType.RAPPORT_ESG.value,
            "fiscal_year": 2024,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "entreprise_id_requis"


def test_importer_rapport_par_url_admin_avec_entreprise_id_inconnu_est_404(session) -> None:
    admin = _create_admin_utilisateur(session)
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports/import-url",
        json={
            "url": "https://exemple-public.test/rapport.pdf",
            "type": ReportType.RAPPORT_ESG.value,
            "fiscal_year": 2024,
            "company_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "entreprise_introuvable"


def test_importer_rapport_par_url_admin_happy_path(session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.company.rapports.telecharger_pdf_depuis_url", lambda _url: _minimal_pdf_bytes()
    )
    admin = _create_admin_utilisateur(session)
    cible = Company(name=f"Cible {uuid.uuid4()}", sector="Technologies", country="France")
    session.add(cible)
    session.commit()
    authed_client = _login(admin.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports/import-url",
        json={
            "url": "https://exemple-public.test/rapport.pdf",
            "type": ReportType.RAPPORT_ESG.value,
            "fiscal_year": 2024,
            "company_id": str(cible.id),
        },
    )

    assert response.status_code == 201
    assert response.json()["channel"] == SubmissionChannel.AUTOMATIQUE.value


def test_importer_rapport_par_url_avec_role_investisseur_est_rejete(session) -> None:
    user = User(
        email=f"investisseur-{uuid.uuid4()}@example.com",
        password_hash=hash_password("s3cret-pass"),
        role=Role.INVESTOR,
        active=True,
    )
    session.add(user)
    session.commit()
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports/import-url",
        json={
            "url": "https://exemple-public.test/rapport.pdf",
            "type": ReportType.RAPPORT_ESG.value,
            "fiscal_year": 2024,
        },
    )

    assert response.status_code == 403


def test_importer_rapport_par_url_url_non_autorisee_propage_lerreur_de_validation(session) -> None:
    """Aucun mock de telecharger_pdf_depuis_url ici : une URL ciblant une adresse non routable
    (voir app/company/url_fetch.py) doit être rejetée avant tout dépôt, avec le code d'erreur
    exact du garde-fou anti-SSRF -- pas un succès silencieux ni une 500 générique."""
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(user.email, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/company/rapports/import-url",
        json={
            "url": "http://169.254.169.254/rapport.pdf",
            "type": ReportType.RAPPORT_ESG.value,
            "fiscal_year": 2024,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "url_cible_non_autorisee"


def test_consulter_rapport_sans_score_officiel_le_renvoie_a_null(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert user.company is not None
    rapport = ESGReport(
        company_id=user.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)

    authed_client = _login(user.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/company/rapports/{rapport.id}")

    assert response.status_code == 200
    assert response.json()["official_score"] is None


def test_consulter_rapport_avec_score_officiel_lexpose_distinctement_du_score_declare(
    session,
) -> None:
    from app.scoring.engine import calculer_score

    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert user.company is not None
    rapport = ESGReport(
        company_id=user.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
        declared_global_score=99.0,  # volontairement très différent du score officiel calculé
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()
    preuve = Evidence(
        document_name="rapport-test.pdf",
        year=2025,
        total_pages=1,
        page_start=1,
        page_end=1,
        excerpt_pdf_path="preuves/test/page_1.pdf",
    )
    session.add(preuve)
    session.flush()
    session.add(
        ESGMetric(
            report_id=rapport.id,
            pillar=Pillar.GOUVERNANCE,
            metric_code="femmes_conseil_pourcentage",
            value=40.0,
            unit="%",
            method=DataMethod.RAPPORTEE,
            proof_id=preuve.id,
        )
    )
    session.commit()
    calculer_score(session, rapport.id)
    session.commit()

    authed_client = _login(user.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/company/rapports/{rapport.id}")

    assert response.status_code == 200
    corps = response.json()
    assert corps["declared_global_score"] == 99.0
    assert corps["official_score"] is not None
    assert corps["official_score"]["global_score"] != 99.0


def test_telecharger_rapport_original_dune_autre_entreprise_est_404(session) -> None:
    proprietaire = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert proprietaire.company is not None
    rapport = ESGReport(
        company_id=proprietaire.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()

    autre = _create_entreprise_utilisateur(session, password="s3cret-pass")
    authed_client = _login(autre.email, "s3cret-pass")

    response = authed_client.get(f"/api/v1/company/rapports/{rapport.id}/fichier")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "rapport_introuvable"


def test_telecharger_rapport_original_propre_entreprise_retourne_le_pdf(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert user.company is not None
    chemin_relatif = f"rapports/test/{uuid.uuid4()}.pdf"
    storage.save_bytes(chemin_relatif, b"%PDF-1.4 contenu de test original")
    rapport = ESGReport(
        company_id=user.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file=chemin_relatif,
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()

    authed_client = _login(user.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/company/rapports/{rapport.id}/fichier")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 contenu de test original"


def test_telecharger_rapport_synthese_non_generee_est_404_dedie(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert user.company is not None
    rapport = ESGReport(
        company_id=user.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()

    authed_client = _login(user.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/company/rapports/{rapport.id}/synthese/fichier")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "synthese_non_generee"


def test_telecharger_rapport_synthese_generee_retourne_le_pdf(session) -> None:
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    assert user.company is not None
    chemin_relatif = f"synthese/{uuid.uuid4()}.pdf"
    storage.save_bytes(chemin_relatif, b"%PDF-1.4 contenu de synthese")
    rapport = ESGReport(
        company_id=user.company.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        source_file="rapports/test/dummy.pdf",
        synthesis_report_path=chemin_relatif,
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()

    authed_client = _login(user.email, "s3cret-pass")
    response = authed_client.get(f"/api/v1/company/rapports/{rapport.id}/synthese/fichier")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 contenu de synthese"
