"""Prompt 4.3 — recherche semantique (bge-m3, en memoire) sur le corpus pilote.

Contenu appele a devenir la cellule de code du Prompt 4.3 dans validation_pipeline.ipynb — ecrit comme
script autonome pour l'executer dans le conteneur Docker de developpement (greenfinance-notebook).

Recharge les DoclingDocument persistes par le Prompt 4.2 (data_test/docling_json/*.json, ecrits via
doc.save_as_json()) -- ne relance PAS Docling, qui a deja tourne separement (~2h50). Indexe les chunks
de chaque rapport avec bge-m3 (FAISS local, IndexFlatIP), puis mesure le taux de rappel de la
page_attendue (verite terrain) dans le top-8 pour chaque indicateur.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import faiss
import yaml
from docling_core.types.doc.document import DoclingDocument
from FlagEmbedding import BGEM3FlagModel

PROJECT_ROOT = Path.cwd().resolve()
if PROJECT_ROOT.name == "notebooks":
    PROJECT_ROOT = PROJECT_ROOT.parent

GROUND_TRUTH_PATH = PROJECT_ROOT / "data_test" / "ground_truth.yaml"
DOCLING_JSON_DIR = PROJECT_ROOT / "data_test" / "docling_json"
OUT_PATH = PROJECT_ROOT / "data_test" / "prompt_4_3_indexation.json"


def parse_pages_attendues(value):
    """Normalise page_attendue (entier, ou plage texte "82-83") en une liste de numeros de page."""
    if isinstance(value, int):
        return [value]
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(value))
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        return list(range(start, end + 1))
    return [int(value)]


def iter_page_chunks(doc, max_chars=1200):
    """Reconstitue, a partir d'un DoclingDocument, des chunks de texte associes a leur page d'origine."""
    buffers = {}  # page_no -> list[str]
    for item in list(getattr(doc, "texts", [])) + list(getattr(doc, "tables", [])):
        prov = getattr(item, "prov", None)
        if not prov:
            continue
        page_no = prov[0].page_no
        content = None
        if getattr(item, "text", None):
            content = item.text
        elif hasattr(item, "export_to_markdown"):
            try:
                content = item.export_to_markdown(doc)
            except Exception:
                content = None
        if not content:
            continue
        buffers.setdefault(page_no, []).append(content)

    chunks = []
    for page_no, parts in buffers.items():
        text = "\n".join(parts)
        for i in range(0, len(text), max_chars):
            piece = text[i : i + max_chars].strip()
            if piece:
                chunks.append({"page": page_no, "text": piece})
    return chunks


def search(search_index, embed_model, query, k=8):
    q_emb = embed_model.encode([query])["dense_vecs"]
    q_emb = np.asarray(q_emb, dtype="float32")
    faiss.normalize_L2(q_emb)
    scores, idxs = search_index["index"].search(q_emb, k)
    return [search_index["chunks"][i] for i in idxs[0] if i != -1]


with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
    ground_truth = yaml.safe_load(f)
entreprises = ground_truth["entreprises"]

# Filtre optionnel en argument CLI (ex: `python3 _prompt_4_3_indexation.py microsoft`) -- pour valider
# l'indexation sur un seul rapport deja converti sans attendre les autres.
if len(sys.argv) > 1:
    noms_connus = {e["nom"] for e in entreprises}
    inconnus = [nom for nom in sys.argv[1:] if nom not in noms_connus]
    if inconnus:
        raise SystemExit(f"Rapport(s) inconnu(s) : {inconnus}. Choix possibles : {sorted(noms_connus)}")
    entreprises = [e for e in entreprises if e["nom"] in sys.argv[1:]]

for entreprise in entreprises:
    for indicateur in entreprise["indicateurs"]:
        indicateur["pages_attendues"] = parse_pages_attendues(indicateur["page_attendue"])

print("Chargement du modele bge-m3 (peut telecharger plusieurs Go au premier appel)...", flush=True)
embed_model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)

results = {}
recall_hits_global = 0
recall_total_global = 0

for entreprise in entreprises:
    nom = entreprise["nom"]
    doc_json_path = DOCLING_JSON_DIR / f"{nom}.json"
    if not doc_json_path.exists():
        print(f"\n=== {nom} : {doc_json_path} introuvable, ignore ===", flush=True)
        continue

    print(f"\n=== {nom} : chargement du DoclingDocument depuis {doc_json_path.name} ===", flush=True)
    doc = DoclingDocument.load_from_json(doc_json_path)

    chunks = iter_page_chunks(doc)
    if not chunks:
        print(f"{nom}: aucun chunk extrait, indexation ignoree", flush=True)
        continue

    embeddings = embed_model.encode([c["text"] for c in chunks], batch_size=8)["dense_vecs"]
    embeddings = np.asarray(embeddings, dtype="float32")
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    search_index = {"chunks": chunks, "index": index}
    print(f"{nom}: {len(chunks)} chunks indexes", flush=True)

    hits = 0
    n = len(entreprise["indicateurs"])
    details = []
    for indicateur in entreprise["indicateurs"]:
        query = indicateur["code"].replace("_", " ")
        found_chunks = search(search_index, embed_model, query, k=8)
        pages_found = sorted({c["page"] for c in found_chunks})
        hit = bool(set(pages_found) & set(indicateur["pages_attendues"]))
        hits += int(hit)
        recall_total_global += 1
        recall_hits_global += int(hit)
        details.append(
            {
                "code": indicateur["code"],
                "pages_attendues": indicateur["pages_attendues"],
                "pages_trouvees_top8": pages_found,
                "hit": hit,
            }
        )

    entry = {
        "n_chunks": len(chunks),
        "n_indicateurs": n,
        "rappel_hits": hits,
        "rappel_taux": round(hits / n, 4),
        "details": details,
    }
    results[nom] = entry
    print(f"{nom:15s} rappel top-8 : {hits}/{n} ({hits / n:.0%})", flush=True)

    # Ecrit apres CHAQUE entreprise, pas seulement a la fin du lot (meme logique que le Prompt 4.2).
    OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

taux_global = recall_hits_global / recall_total_global if recall_total_global else 0.0
print(
    f"\nRappel global (page attendue dans le top-8) : "
    f"{recall_hits_global}/{recall_total_global} ({taux_global:.1%})",
    flush=True,
)

results["_global"] = {
    "rappel_hits": recall_hits_global,
    "rappel_total": recall_total_global,
    "rappel_taux": round(taux_global, 4),
}
OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n=== TERMINE — resultats ecrits dans {OUT_PATH} ===")
