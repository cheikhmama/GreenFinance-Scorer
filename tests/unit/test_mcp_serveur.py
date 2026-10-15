"""Serveur MCP (stdio) : outils extract_esg_report et list_esg_indicators, vus par un vrai client
MCP en mémoire. L'extraction elle-même est remplacée : seul le contrat de l'outil est testé ici."""

from pathlib import Path
from typing import Any

import anyio
import pymupdf
import pytest
from mcp.client import Client

from app.ingestion.cibles import INDICATEURS_CIBLES
from app.ingestion.sortie import DocumentSortie, ExecutionSortie, RapportExtraitJSON
from app.mcp.serveur import creer_serveur


def _pdf(chemin: Path) -> Path:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Rapport ESG")
    doc.save(chemin)
    return chemin


def _sortie(nom: str) -> RapportExtraitJSON:
    return RapportExtraitJSON(
        entreprise="Helios",
        annee=2025,
        document=DocumentSortie(nom=nom, pages=1, sha256="0" * 64),
        execution=ExecutionSortie(
            modele="m", prompt_version="v", docling_version="d", pages_ocr=0,
            duree_conversion_s=1.0, duree_llm_s=1.0, pic_memoire_mo=100,
        ),
        indicateurs=[],
        couverture=[],
    )


@pytest.fixture
def racine(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir()
    return tmp_path / "data"


def _appeler(serveur, outil: str, arguments: dict[str, Any]):
    async def principal():
        async with Client(serveur) as client:
            return await client.call_tool(outil, arguments)

    return anyio.run(principal)


def test_outils_exposes(racine: Path) -> None:
    async def principal():
        async with Client(creer_serveur(racine)) as client:
            return await client.list_tools()

    noms = {outil.name for outil in anyio.run(principal).tools}
    assert noms == {"extract_esg_report", "list_esg_indicators"}


def test_extrait_un_pdf_de_la_racine(racine: Path) -> None:
    _pdf(racine / "helios.pdf")
    appels: list[tuple] = []

    def extraire(chemin, *, nom_entreprise, annee):
        appels.append((chemin, nom_entreprise, annee))
        return _sortie(chemin.name)

    resultat = _appeler(
        creer_serveur(racine, est_demo=lambda: False, extraire=extraire),
        "extract_esg_report",
        {"file_path": "helios.pdf", "company_name": "Helios", "fiscal_year": 2025},
    )

    assert not resultat.is_error
    assert appels == [((racine / "helios.pdf").resolve(), "Helios", 2025)]
    assert resultat.structured_content["document"]["nom"] == "helios.pdf"


@pytest.mark.parametrize(
    ("chemin", "attendu"),
    [
        ("../secret.pdf", "hors du dossier autorisé"),
        ("absent.pdf", "introuvable"),
        ("note.txt", "PDF"),
    ],
)
def test_chemins_refuses_sans_extraction(racine: Path, chemin: str, attendu: str) -> None:
    _pdf(racine.parent / "secret.pdf")
    (racine / "note.txt").write_text("pas un pdf")

    def extraire(*_a, **_k):
        raise AssertionError("aucune extraction ne doit être lancée")

    resultat = _appeler(creer_serveur(racine, est_demo=lambda: False, extraire=extraire), "extract_esg_report", {"file_path": chemin})

    assert resultat.is_error
    assert attendu in resultat.content[0].text


def test_chemin_absolu_dans_la_racine_accepte(racine: Path) -> None:
    pdf = _pdf(racine / "absolu.pdf")

    resultat = _appeler(
        creer_serveur(racine, est_demo=lambda: False, extraire=lambda c, **_k: _sortie(c.name)),
        "extract_esg_report",
        {"file_path": str(pdf)},
    )

    assert not resultat.is_error


def test_catalogue_des_indicateurs_avec_referentiels(racine: Path) -> None:
    resultat = _appeler(creer_serveur(racine), "list_esg_indicators", {})

    indicateurs = resultat.structured_content["result"]
    assert len(indicateurs) == len(INDICATEURS_CIBLES)
    scope_1 = next(i for i in indicateurs if i["code"] == "scope_1")
    assert scope_1["famille"] == "CARBONE" and scope_1["referentiels"]["gri"] == "GRI 305-1"


def test_une_seule_extraction_a_la_fois(racine: Path) -> None:
    """Deux extractions simultanées dépasseraient la mémoire du conteneur : la seconde est refusée
    clairement (typiquement la relance d'un client qui a cessé d'attendre)."""
    import threading

    _pdf(racine / "a.pdf")
    _pdf(racine / "b.pdf")
    demarree, liberer = threading.Event(), threading.Event()

    def extraire(chemin, **_k):
        demarree.set()
        liberer.wait(10)
        return _sortie(chemin.name)

    serveur = creer_serveur(racine, extraire=extraire, est_demo=lambda: False)
    resultats: dict[str, Any] = {}

    async def principal():
        async with Client(serveur) as client:
            async def appeler(nom: str) -> None:
                resultats[nom] = await client.call_tool("extract_esg_report", {"file_path": f"{nom}.pdf"})

            async with anyio.create_task_group() as groupe:
                groupe.start_soon(appeler, "a")
                await anyio.to_thread.run_sync(demarree.wait, 10)
                await appeler("b")
                liberer.set()

    anyio.run(principal)

    assert not resultats["a"].is_error
    assert resultats["b"].is_error and "déjà en cours" in resultats["b"].content[0].text


def test_refuse_de_rendre_des_valeurs_de_demonstration(racine: Path) -> None:
    """Sans vraie clé LLM, le pipeline produit des valeurs synthétiques : un agent les prendrait
    pour une vraie extraction."""
    _pdf(racine / "a.pdf")

    def extraire(*_a, **_k):
        raise AssertionError("aucune extraction en mode démonstration")

    resultat = _appeler(
        creer_serveur(racine, extraire=extraire, est_demo=lambda: True), "extract_esg_report", {"file_path": "a.pdf"}
    )

    assert resultat.is_error and "LLM_API_KEY" in resultat.content[0].text
