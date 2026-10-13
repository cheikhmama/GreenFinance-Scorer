"""Options de conversion Docling (sans lancer de conversion : aucun modèle chargé)."""

import pytest
from docling.datamodel.pipeline_options import RapidOcrOptions

from app.ingestion.docling_pipeline import options_pipeline


def test_ocr_passe_par_onnxruntime_disponible_sur_arm() -> None:
    """paddlepaddle n'a pas de roue Linux aarch64 : le moteur OCR doit être ONNX Runtime pour que
    l'image worker se construise sur l'hôte ARM (Oracle Always Free)."""
    options = options_pipeline()

    assert isinstance(options.ocr_options, RapidOcrOptions)
    assert options.ocr_options.backend == "onnxruntime"


def test_options_par_lot_sans_ocr_threads_bornes_tableaux_precis() -> None:
    from docling.datamodel.accelerator_options import AcceleratorDevice
    from docling.datamodel.pipeline_options import TableFormerMode

    options = options_pipeline(ocr=False, threads=3)

    assert options.do_ocr is False
    assert options.accelerator_options.num_threads == 3
    assert options.accelerator_options.device == AcceleratorDevice.CPU
    assert options.do_table_structure is True
    assert options.table_structure_options.mode == TableFormerMode.ACCURATE
    assert options.generate_page_images is False


def test_conversion_par_lots_reprend_les_lots_deja_convertis(tmp_path) -> None:
    from docling_core.types.doc.document import DoclingDocument

    from app.ingestion.docling_pipeline import (
        DocumentParLots,
        chemin_lot,
        convertir_par_lots,
        persist_docling_json,
    )
    from app.ingestion.lots import Lot

    lots = [Lot(1, 2, ocr=False), Lot(3, 4, ocr=True)]
    persist_docling_json(DoclingDocument(name="lot-1"), chemin_lot(tmp_path, lots[0]))
    convertis: list[Lot] = []

    def convertir(_pdf, lot):
        convertis.append(lot)
        return DoclingDocument(name=f"lot-{lot.debut}")

    resultats = list(convertir_par_lots(tmp_path / "r.pdf", tmp_path, lots, threads=2, convertir=convertir))

    # Le lot déjà sur disque (exécution interrompue) n'est jamais reconverti.
    assert convertis == [lots[1]]
    assert [(r.lot, r.repris, r.document.name) for r in resultats] == [
        (lots[0], True, "lot-1"),
        (lots[1], False, "lot-3"),
    ]
    assert chemin_lot(tmp_path, lots[1]).exists()
    assert DocumentParLots(tmp_path, lots).document_de_la_page(4).name == "lot-3"


def test_convertir_rapport_indexe_chaque_lot_puis_le_relache(tmp_path) -> None:
    import pymupdf
    from docling_core.types.doc.document import DoclingDocument

    from app.ingestion.docling_pipeline import convertir_rapport

    pdf = tmp_path / "r.pdf"
    doc = pymupdf.open()
    for numero in range(1, 6):
        page = doc.new_page()
        if numero != 4:  # page 4 : scannée, sans couche texte
            page.insert_text((72, 72), "Indicateurs ESG et emissions de gaz a effet de serre. " * 3)
    doc.save(pdf)
    indexes: list[str] = []

    rapport = convertir_rapport(
        pdf,
        tmp_path / "json",
        taille=2,
        pages_max=600,
        threads=2,
        indexer=lambda d: indexes.append(d.name),
        convertir=lambda _p, lot: DoclingDocument(name=f"lot-{lot.debut}"),
    )

    assert indexes == ["lot-1", "lot-3", "lot-5"]
    assert rapport.pages_total == 5
    assert rapport.pages_ocr == 2  # le lot 3-4, seul à contenir une page scannée
    assert rapport.document_de_la_page(5).name == "lot-5"


def test_dossier_des_lots_change_avec_le_contenu_du_pdf_et_les_options(tmp_path, monkeypatch) -> None:
    """Un brouillon dont le PDF est remplacé garde son identifiant de rapport : ses lots doivent
    quand même être reconvertis, jamais repris depuis l'ancien PDF. Idem si Docling ou ses options
    changent."""
    from app.ingestion import docling_pipeline

    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF-1.7 version A")
    dossier_a = docling_pipeline.dossier_lots(tmp_path / "json", pdf)
    assert docling_pipeline.dossier_lots(tmp_path / "json", pdf) == dossier_a
    assert dossier_a.parent == tmp_path / "json"

    pdf.write_bytes(b"%PDF-1.7 version B, corrigee")
    dossier_b = docling_pipeline.dossier_lots(tmp_path / "json", pdf)
    assert dossier_b != dossier_a

    monkeypatch.setattr(docling_pipeline, "_signature_conversion", lambda: "autre-version")
    assert docling_pipeline.dossier_lots(tmp_path / "json", pdf) != dossier_b


def test_pdf_remplace_jamais_repris_depuis_les_lots_de_l_ancien(tmp_path) -> None:
    import pymupdf
    from docling_core.types.doc.document import DoclingDocument

    from app.ingestion.docling_pipeline import convertir_rapport

    def pdf(texte: str):
        chemin = tmp_path / "r.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), texte * 5)
        doc.save(chemin)
        return chemin

    convertis: list[str] = []

    def convertir(chemin, _lot):
        convertis.append(chemin.read_bytes()[-40:].hex())
        return DoclingDocument(name="lot")

    base = tmp_path / "docling_json" / "rapport-1"
    for texte in ("Rapport A, version initiale. ", "Rapport B, version corrigee. "):
        convertir_rapport(
            pdf(texte), base, taille=20, pages_max=600, threads=1, indexer=lambda _d: None, convertir=convertir
        )

    assert len(convertis) == 2  # le second PDF est converti, pas repris depuis le premier


def _lots_deux():
    from app.ingestion.lots import Lot

    return [Lot(1, 2, ocr=False), Lot(3, 4, ocr=False)]


def test_lot_json_tronque_reconverti_au_lieu_d_echouer_a_chaque_reprise(tmp_path) -> None:
    """Un conteneur tué pendant l'écriture laisse un JSON coupé : la reprise le reconvertit."""
    from docling_core.types.doc.document import DoclingDocument

    from app.ingestion.docling_pipeline import chemin_lot, convertir_par_lots

    lots = _lots_deux()
    chemin_lot(tmp_path, lots[0]).write_text('{"schema_name": "DoclingDocument", "na')
    convertis = []

    def convertir(_p, lot):
        convertis.append(lot)
        return DoclingDocument(name=f"lot-{lot.debut}")

    resultats = list(convertir_par_lots(tmp_path / "r.pdf", tmp_path, lots, threads=1, convertir=convertir))

    assert convertis == lots
    assert resultats[0].document.name == "lot-1" and not resultats[0].repris


def test_ecriture_interrompue_ne_laisse_aucun_lot_sur_disque(tmp_path, monkeypatch) -> None:
    from docling_core.types.doc.document import DoclingDocument

    from app.ingestion.docling_pipeline import persist_docling_json

    def ecriture_coupee(self, filename, **_k):
        filename.write_text('{"tronque": ')
        raise MemoryError("conteneur tué")

    monkeypatch.setattr(DoclingDocument, "save_as_json", ecriture_coupee)
    cible = tmp_path / "p0001-0002.json"

    with pytest.raises(MemoryError):
        persist_docling_json(DoclingDocument(name="x"), cible)
    assert not cible.exists()


def test_conversion_partielle_jamais_sauvegardee(tmp_path) -> None:
    """Un lot converti partiellement (erreurs Docling) sert à cette exécution, mais n'est pas repris
    par les suivantes : elles retentent la conversion."""
    from docling_core.types.doc.document import DoclingDocument

    from app.ingestion.docling_pipeline import (
        ConversionPartielle,
        chemin_lot,
        convertir_par_lots,
    )

    lots = _lots_deux()

    def convertir(_p, lot):
        raise ConversionPartielle(DoclingDocument(name=f"partiel-{lot.debut}"))

    resultats = list(convertir_par_lots(tmp_path / "r.pdf", tmp_path, lots, threads=1, convertir=convertir))

    assert [r.document.name for r in resultats] == ["partiel-1", "partiel-3"]
    assert not any(chemin_lot(tmp_path, lot).exists() for lot in lots)


def test_reprise_apres_interruption_au_deuxieme_lot(tmp_path) -> None:
    """Exécution tuée pendant le lot 2 (mémoire, délai) : la suivante ne reconvertit que le lot 2."""
    from docling_core.types.doc.document import DoclingDocument

    from app.ingestion.docling_pipeline import convertir_par_lots

    lots = _lots_deux()

    def premier_essai(_p, lot):
        if lot.debut == 3:
            raise MemoryError("tué au lot 2")
        return DoclingDocument(name="lot-1")

    with pytest.raises(MemoryError):
        list(convertir_par_lots(tmp_path / "r.pdf", tmp_path, lots, threads=1, convertir=premier_essai))

    convertis = []
    list(
        convertir_par_lots(
            tmp_path / "r.pdf",
            tmp_path,
            lots,
            threads=1,
            convertir=lambda _p, lot: convertis.append(lot) or DoclingDocument(name="lot-3"),
        )
    )
    assert convertis == [lots[1]]


def test_delai_de_conversion_borne_par_lot() -> None:
    assert options_pipeline(ocr=True, threads=2, delai_s=600).document_timeout == 600
