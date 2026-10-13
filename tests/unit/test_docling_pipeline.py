"""Options de conversion Docling (sans lancer de conversion : aucun modèle chargé)."""

from docling.datamodel.pipeline_options import RapidOcrOptions

from app.ingestion.docling_pipeline import options_pipeline


def test_ocr_passe_par_onnxruntime_disponible_sur_arm() -> None:
    """paddlepaddle n'a pas de roue Linux aarch64 : le moteur OCR doit être ONNX Runtime pour que
    l'image worker se construise sur l'hôte ARM (Oracle Always Free)."""
    options = options_pipeline()

    assert isinstance(options.ocr_options, RapidOcrOptions)
    assert options.ocr_options.backend == "onnxruntime"
