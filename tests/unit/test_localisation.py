"""Localisation d'une valeur sur sa page (app/ingestion/localisation.py, tâche 5.5), sur des sorties
Docling réelles : le rapport synthétique Atlas (avec son PDF, pour vérifier que les boîtes tombent
bien sur la valeur dans le vrai fichier) et la fiche Microsoft du corpus pilote."""

import json
from pathlib import Path

import pymupdf
import pytest
from docling_core.types.doc import DoclingDocument

from app.ingestion.localisation import (
    MAX_CORRESPONDANCES,
    Boite,
    lire_nombre,
    localiser,
)

ATLAS = Path("data_test/reference_e2e/atlas_industries")


@pytest.fixture(scope="module")
def atlas() -> DoclingDocument:
    return DoclingDocument.load_from_json(ATLAS / "docling.json")


@pytest.fixture(scope="module")
def microsoft() -> DoclingDocument:
    return DoclingDocument.load_from_json(Path("data_test/docling_json/microsoft.json"))


def _texte_dans(boite: Boite) -> str:
    with pymupdf.open(ATLAS / "rapport.pdf") as pdf:
        page = pdf[boite.page - 1]
        largeur, hauteur = page.rect.width, page.rect.height
        zone = pymupdf.Rect(
            boite.x0 * largeur - 1, boite.y0 * hauteur - 1, boite.x1 * largeur + 1, boite.y1 * hauteur + 1
        )
        return page.get_textbox(zone).strip()


@pytest.mark.parametrize(
    ("ecrit", "attendu"),
    [
        ("12 500.0", 12500.0),
        ("143,510", 143510.0),
        ("1.234.567,8", 1234567.8),
        ("1,234.5", 1234.5),
        ("22,5", 22.5),
        ("0.000", 0.0),
        ("12 500", 12500.0),
    ],
)
def test_lecture_des_nombres_ecrits(ecrit, attendu) -> None:
    assert lire_nombre(ecrit) == attendu


def test_chaque_valeur_du_scenario_atlas_est_encadree_dans_le_vrai_pdf(atlas) -> None:
    """Bout en bout des coordonnées : la boîte, reportée sur le PDF d'origine, contient la valeur
    telle qu'imprimée — repère (origine en haut à gauche) et échelle (fractions) corrects."""
    scenario = json.loads((ATLAS / "scenario.json").read_text(encoding="utf-8"))
    for attendu in scenario["extraction_attendue"]["indicateurs"]:
        boites = localiser(
            atlas, attendu["page_attendue"], citation=None, valeur_brute=None, valeur=attendu["valeur_attendue"]
        )

        assert len(boites) == 1, attendu["code"]
        assert lire_nombre(_texte_dans(boites[0])) == attendu["valeur_attendue"], attendu["code"]
        assert 0 <= boites[0].x0 < boites[0].x1 <= 1 and 0 <= boites[0].y0 < boites[0].y1 <= 1


def test_la_citation_designe_le_bloc_de_texte(atlas) -> None:
    boites = localiser(
        atlas, 6, citation="calculées selon le GHG Protocol", valeur_brute=None, valeur=None
    )

    assert len(boites) == 1
    assert "GHG Protocol" in _texte_dans(boites[0]).replace("\n", " ")


def test_valeur_ecrite_avec_separateurs_dans_une_fiche_reelle(microsoft) -> None:
    for valeur_brute, valeur in [("143,510", 143510.0), ("259,090", 259090.0)]:
        boites = localiser(microsoft, 3, citation=None, valeur_brute=valeur_brute, valeur=valeur)

        assert len(boites) == 1
        assert boites[0].page == 3


@pytest.mark.parametrize(
    ("page", "valeur"),
    [
        (3, 2025.0),  # ressemble à une année : jamais localisée
        (3, 999_999.0),  # absente de la page
        (42, 12500.0),  # page inexistante
    ],
    ids=["annee", "absente", "page-inexistante"],
)
def test_pas_de_boite_plutot_qu_une_fausse(atlas, page, valeur) -> None:
    assert localiser(atlas, page, citation=None, valeur_brute=None, valeur=valeur) == []


def test_valeur_trop_frequente_non_localisee(atlas, monkeypatch) -> None:
    """« tCO2e » revient sur plusieurs lignes ; une valeur qui revient plus de
    MAX_CORRESPONDANCES fois sur la page n'est pas localisée."""
    monkeypatch.setattr("app.ingestion.localisation.MAX_CORRESPONDANCES", 0)

    assert localiser(atlas, 3, citation=None, valeur_brute=None, valeur=12500.0) == []
    assert MAX_CORRESPONDANCES == 3
