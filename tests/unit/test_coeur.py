"""Extraction d'un PDF hors base de données → JSON aligné sur les référentiels (outil MCP)."""

import hashlib
from pathlib import Path

import pytest

from app.core.enums import MetricCoverageStatus
from app.ingestion import coeur, extractor
from app.ingestion.docling_pipeline import RapportConverti
from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait


def test_extraire_document_renvoie_le_json_du_rapport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = tmp_path / "helios-2025.pdf"
    pdf.write_bytes(b"%PDF-1.7 contenu")
    recus: dict = {}

    def analyser(source, dossier, *, nom_entreprise, rapport_id):
        recus.update(source=source, dossier=dossier, nom=nom_entreprise)
        codes = [c.code for c in extractor.INDICATEURS_CIBLES]
        return extractor.Analyse(
            conversion=RapportConverti(pages_total=250, pages_ocr=20, elapsed_s=900.0, document_de_la_page=lambda _p: None),
            codes=codes,
            extraction=ExtractionEntreprise(
                entreprise=nom_entreprise,
                indicateurs=[IndicateurExtrait(code="scope_1", valeur=48210.0, unite="tCO2e", page_source=88, trouve=True)],
            ),
            modele="llama-3.3-70b-versatile",
            pages_vues_par_code={c: {88} for c in codes},
            pages_par_code={},
            duree_llm_s=40.0,
            demo=False,
        )

    monkeypatch.setattr(extractor, "analyser_document", analyser)

    sortie = coeur.extraire_document(pdf, nom_entreprise=None, annee=2025, dossier_travail=tmp_path / "travail")

    # Nom d'entreprise par défaut : celui du fichier.
    empreinte = hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert recus == {"source": pdf, "dossier": tmp_path / "travail", "nom": "helios-2025"}
    assert (sortie.document.nom, sortie.document.pages, sortie.document.sha256) == ("helios-2025.pdf", 250, empreinte)
    assert sortie.execution.modele == "llama-3.3-70b-versatile"
    assert sortie.execution.pages_ocr == 20
    assert [i.code for i in sortie.indicateurs] == ["scope_1"]
    statuts = {c.code: c.statut for c in sortie.couverture}
    assert statuts["scope_1"] == MetricCoverageStatus.TROUVE
    assert len(statuts) == len(extractor.INDICATEURS_CIBLES)
