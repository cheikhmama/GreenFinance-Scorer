"""Banc mémoire/temps de la conversion par lots + indexation (la partie qui borne la mémoire du
worker), sans LLM ni base de données. À lancer dans l'image worker, sous la limite visée :

    docker compose run --rm --no-deps -v "$PWD/bench:/bench" \\
        -e EXTRACTION_THREADS=3 --memory 12g --cpus 3 worker-extraction \\
        python scripts/bench_extraction_memoire.py /bench/synthetique-250p/rapport.pdf \\
            --lot 20 --threads 3 --csv /bench/resultats.csv

(scripts/ n'est pas dans l'image : monter le dépôt ou copier le script.) Matrice suggérée : --lot
10/20/40, --threads 2/3/4, --forcer-ocr. Une ligne CSV par exécution : pages, lots, pages OCR,
durée, pages par minute et pic mémoire (cgroup du conteneur si disponible, sinon processus).
"""

import argparse
import csv
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path


def _rss_mo() -> int | None:
    try:
        for ligne in Path("/proc/self/status").read_text().splitlines():
            if ligne.startswith("VmRSS:"):
                return int(ligne.split()[1]) // 1024
    except OSError:
        return None
    return None


def mesurer(pdf: Path, *, lot: int, threads: int, forcer_ocr: bool) -> dict:
    from app.ingestion import docling_pipeline, extractor, lots
    from app.ingestion.memoire import pic_memoire_mo

    if forcer_ocr:
        planifier = lots.planifier_lots

        def tout_en_ocr(chemin, **kw):  # type: ignore[no-untyped-def]
            return [lots.Lot(lt.debut, lt.fin, ocr=True) for lt in planifier(chemin, **kw)]

        lots.planifier_lots = tout_en_ocr  # type: ignore[assignment]

    echantillons: list[int] = []
    fini = threading.Event()

    def echantillonner() -> None:
        while not fini.wait(1.0):
            rss = _rss_mo()
            if rss is not None:
                echantillons.append(rss)

    threading.Thread(target=echantillonner, daemon=True).start()
    t0 = time.monotonic()
    embed = extractor._get_embed_model()
    embed.encode(["initialisation"])
    index = extractor.IndexIncremental(embed)
    with tempfile.TemporaryDirectory() as dossier:
        rapport = docling_pipeline.convertir_rapport(
            pdf, Path(dossier), taille=lot, pages_max=10_000, threads=threads, indexer=index.ajouter
        )
    duree = time.monotonic() - t0
    fini.set()
    return {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "pdf": pdf.name,
        "pages": rapport.pages_total,
        "lot": lot,
        "threads": threads,
        "ocr_force": forcer_ocr,
        "pages_ocr": rapport.pages_ocr,
        "chunks": len(index.chunks),
        "duree_s": round(duree, 1),
        "pages_par_minute": round(rapport.pages_total / duree * 60, 1),
        "rss_max_echantillonne_mo": max(echantillons, default=None),
        "pic_memoire_mo": pic_memoire_mo(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--lot", type=int, default=20)
    parser.add_argument("--threads", type=int, default=3)
    parser.add_argument("--forcer-ocr", action="store_true")
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()

    ligne = mesurer(args.pdf, lot=args.lot, threads=args.threads, forcer_ocr=args.forcer_ocr)
    for cle, valeur in ligne.items():
        print(f"{cle:>26} : {valeur}")
    if args.csv:
        nouveau = not args.csv.exists()
        with args.csv.open("a", newline="", encoding="utf-8") as fichier:
            ecrivain = csv.DictWriter(fichier, fieldnames=list(ligne))
            if nouveau:
                ecrivain.writeheader()
            ecrivain.writerow(ligne)


if __name__ == "__main__":
    main()
