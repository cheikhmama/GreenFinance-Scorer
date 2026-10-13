"""Options de conversion Docling (sans lancer de conversion : aucun modèle chargé)."""

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
