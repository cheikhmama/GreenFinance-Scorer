"""Prompt 4.2 — structuration Docling (backend OCR PaddleOCR via RapidOCR) sur le corpus pilote.

Contenu appelé à devenir la cellule de code du Prompt 4.2 dans validation_pipeline.ipynb — écrit comme
script autonome pour l'exécuter dans le conteneur Docker de développement (greenfinance-notebook), puis
recopié dans le notebook une fois les résultats validés.
"""

import os

# Docling utilise des modeles PyTorch (TableFormer, layout) qui tentent par defaut de se compiler
# via torch.compile (backend inductor) pour accelerer l'inference. Cette compilation a besoin d'un
# compilateur C++ (cl.exe sous Windows) absent de cet environnement : sans le desactiver, chaque appel
# modele echoue et retente en boucle sur des centaines de pages, jusqu'a saturer la memoire et tuer le
# kernel. torch.compile n'est qu'une optimisation de vitesse (inutile pour ce script d'un seul run) ;
# le desactiver evite d'avoir a installer une chaine de compilation C++ pour un gain qu'on n'exploite
# qu'une fois. Doit etre positionne AVANT tout import de torch/docling.
os.environ["TORCHDYNAMO_DISABLE"] = "1"

import json
import sys
import time
from pathlib import Path

import pymupdf
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.base import ImageRefMode

# schneider_electric retire du corpus actif (2026-08-20) : PDF source introuvable, se.com bloque les
# telechargements automatises par anti-bot (Akamai) -- voir la note en tete de data_test/ground_truth.yaml.
CORPUS = {
    "microsoft": "storage/pilot_corpus/microsoft.pdf",
    "orsted": "storage/pilot_corpus/orsted.pdf",
    "ingka_group": "storage/pilot_corpus/ingka_group.pdf",
}

# Filtre optionnel en argument CLI (ex: `python3 _prompt_4_2_structuration.py microsoft`) -- permet de
# valider le flux complet (conversion + save_as_json + Prompt 4.3) sur un seul rapport rapide avant
# d'engager le traitement complet des 4 (~2h50).
if len(sys.argv) > 1:
    inconnus = [nom for nom in sys.argv[1:] if nom not in CORPUS]
    if inconnus:
        raise SystemExit(f"Rapport(s) inconnu(s) : {inconnus}. Choix possibles : {list(CORPUS)}")
    CORPUS = {nom: CORPUS[nom] for nom in sys.argv[1:]}

# Backend OCR "PaddleOCR" convenu au plan : Docling ne l'expose pas comme classe dédiée, seulement via
# RapidOcrOptions(backend="paddle") — RapidOCR utilisé comme frontal, moteur d'inférence Paddle dessous.
ocr_options = RapidOcrOptions(backend="paddle")
pipeline_options = PdfPipelineOptions(do_ocr=True, ocr_options=ocr_options)
converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)

Path("data_test").mkdir(exist_ok=True)
out_path = Path("data_test/prompt_4_2_structuration.json")
docling_json_dir = Path("data_test/docling_json")
docling_json_dir.mkdir(exist_ok=True)

# Reprise sur crash : les runs précédents ont été tués deux fois par un arrêt de Docker Desktop
# indépendant de ce script. On recharge ce qui existe déjà et on ne refait pas ce qui a réussi.
# Un rapport n'est considéré acquis que si SON JSON DoclingDocument existe aussi -- le tout premier
# run (2026-08-13) avait marqué les 4 rapports SUCCESS sans jamais persister l'objet document
# (jeté après calcul des stats), donc le seul statut "SUCCESS" ne suffit plus a lui seul.
results = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}

for nom, path in CORPUS.items():
    doc_json_path = docling_json_dir / f"{nom}.json"
    if results.get(nom, {}).get("status") == "ConversionStatus.SUCCESS" and doc_json_path.exists():
        print(f"\n=== {nom} : déjà traité avec succès (document JSON présent), ignoré ===", flush=True)
        continue

    print(f"\n=== {nom} ({path}) ===", flush=True)
    t0 = time.time()
    conv = converter.convert(path)
    elapsed = time.time() - t0
    doc = conv.document

    pages_docling = doc.num_pages()
    with pymupdf.open(path) as pm:
        pages_pymupdf = pm.page_count

    # PLACEHOLDER (pas EMBEDDED, le défaut) : on n'a besoin que du texte/tableaux pour la recherche
    # sémantique du Prompt 4.3, jamais des images -- les embarquer en base64 gonflerait le JSON pour rien.
    doc.save_as_json(doc_json_path, image_mode=ImageRefMode.PLACEHOLDER)

    entry = {
        "status": str(conv.status),
        "elapsed_s": round(elapsed, 1),
        "pages_docling": pages_docling,
        "pages_pymupdf_independant": pages_pymupdf,
        "pages_correspondent": pages_docling == pages_pymupdf,
        "num_tables": len(doc.tables),
        "erreurs": [str(e) for e in conv.errors],
        "docling_json_path": str(doc_json_path),
    }
    results[nom] = entry
    print(json.dumps(entry, indent=2, ensure_ascii=False), flush=True)

    # Écrit après CHAQUE rapport, pas seulement à la fin du lot — un crash ne doit plus faire perdre
    # le travail déjà terminé (cf. note Étape 8 : traitement par rapport, pas par batch monolithique).
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"\n=== TERMINE — résultats écrits dans {out_path} ===")
