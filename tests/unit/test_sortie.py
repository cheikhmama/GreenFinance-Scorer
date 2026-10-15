"""Sortie JSON de l'extraction (outil MCP extract_esg_report, export)."""

import json

from app.core.enums import MetricCoverageStatus
from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait
from app.ingestion.sortie import DocumentSortie, ExecutionSortie, construire_sortie

EXTRACTION = ExtractionEntreprise(
    entreprise="Atlas Industries",
    indicateurs=[
        IndicateurExtrait(
            code="scope_1",
            valeur=12500.0,
            unite="tCO2e",
            page_source=4,
            trouve=True,
            citation_source="Scope 1 : 12 500 tCO2e",
        ),
        # Trouvée mais sans page : aucune preuve, jamais publiée (même règle que l'enregistrement).
        IndicateurExtrait(code="femmes_conseil_pourcentage", valeur=40.0, unite="%", trouve=True),
        IndicateurExtrait(code="scope_3", valeur=None, unite="", trouve=False),
    ],
)


def _sortie():
    return construire_sortie(
        EXTRACTION,
        annee=2025,
        document=DocumentSortie(nom="rapport.pdf", pages=250, sha256="ab" * 32),
        execution=ExecutionSortie(
            modele="llama-3.3-70b-versatile",
            prompt_version="2026-10-01",
            docling_version="2.119.0",
            pages_ocr=10,
            duree_conversion_s=900.0,
            duree_llm_s=42.0,
            pic_memoire_mo=8100,
        ),
        statuts={
            "scope_1": MetricCoverageStatus.TROUVE,
            "femmes_conseil_pourcentage": MetricCoverageStatus.NON_TROUVE,
            "scope_3": MetricCoverageStatus.ABSENT_CONFIRME,
        },
    )


def test_seules_les_valeurs_avec_page_sont_publiees_avec_leurs_referentiels() -> None:
    sortie = _sortie()

    assert [i.code for i in sortie.indicateurs] == ["scope_1"]
    scope_1 = sortie.indicateurs[0]
    assert (scope_1.valeur, scope_1.page_source, scope_1.famille) == (12500.0, 4, "CARBONE")
    assert scope_1.referentiels.gri == "GRI 305-1"
    assert scope_1.referentiels.ghg_protocol == "Scope 1"
    assert scope_1.citation == "Scope 1 : 12 500 tCO2e"


def test_couverture_et_contexte_d_execution_dans_un_json_serialisable() -> None:
    donnees = json.loads(_sortie().model_dump_json())

    assert donnees["entreprise"] == "Atlas Industries" and donnees["annee"] == 2025
    assert donnees["document"]["pages"] == 250
    assert donnees["execution"]["pic_memoire_mo"] == 8100
    assert {c["code"]: c["statut"] for c in donnees["couverture"]} == {
        "scope_1": "TROUVE",
        "femmes_conseil_pourcentage": "NON_TROUVE",
        "scope_3": "ABSENT_CONFIRME",
    }
