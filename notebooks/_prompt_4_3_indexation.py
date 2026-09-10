"""Prompt 4.3 — recherche semantique (bge-m3, en memoire) sur le corpus pilote.

Contenu appele a devenir la cellule de code du Prompt 4.3 dans validation_pipeline.ipynb — ecrit comme
script autonome pour l'executer dans le conteneur Docker de developpement (greenfinance-notebook).

Recharge les DoclingDocument persistes par le Prompt 4.2 (data_test/docling_json/*.json, ecrits via
doc.save_as_json()) -- ne relance PAS Docling, qui a deja tourne separement (~2h50).

Protocole (deuxieme correction, apres le passage non valide puis le rang tronque a k=25) :
  - DEUX_REQUETES_FIXES ci-dessous sont les seules requetes utilisees, identiques pour tous les
    rapports -- plus de requete generee a la volee depuis le code de l'indicateur ;
  - chaque requete est cherchee avec k=index.ntotal (TOUS les chunks du rapport, pas un
    sous-echantillon) -- IndexFlatIP calcule de toute facon la similarite exhaustive en interne, donc
    demander k=ntotal au lieu de k=25 ne coute rien de plus : ca ne fait que renvoyer le classement
    complet plutot qu'une troncature ;
  - les resultats des deux requetes sont consolides par page physique (le meilleur score est conserve
    quand plusieurs chunks d'une meme page apparaissent, y compris entre les deux requetes) ;
  - le CLASSEMENT COMPLET des pages (rang + score, toutes les pages du rapport) est conserve dans le
    JSON, pas seulement le top-8 -- le top-8 en est une simple troncature ;
  - pour chaque indicateur, le rang exact de sa (meilleure) page attendue est le rang REEL dans ce
    classement complet -- plus une approximation bornee par un k arbitraire ;
  - hit_top8 (alias retrieval_recall_at_8) est UNIQUEMENT une metrique technique de qualite de
    recherche : est-ce qu'au moins une page attendue figure dans les 8 mieux classees ? Ce n'est PAS
    une limite du pipeline metier -- le systeme final (Prompt 4.4+) traite l'integralite du rapport,
    jamais seulement un top-8 ;
  - pour les indicateurs a plusieurs pages attendues (ex. "82-83"), la couverture est mesuree page par
    page : pages_attendues_retrouvees, pages_attendues_absentes, couverture_pages_attendues (ratio),
    all_expected_pages_retrieved (bool) -- distinct de hit_top8, qui ne regarde que la meilleure page ;
  - la verite terrain (data_test/ground_truth.yaml) n'est jamais modifiee pour ameliorer les resultats ;
  - une erreur d'extraction (export_to_markdown) n'est jamais masquee silencieusement -- elle est
    journalisee avec le numero de page et le message d'erreur, pour qu'une perte de contenu reste
    detectable.

Usage attendu : valider d'abord sur Microsoft seul (rapport le plus court, corpus de test rapide) avant
de lancer le corpus complet :
    python3 _prompt_4_3_indexation.py microsoft
    python3 _prompt_4_3_indexation.py   # tout le corpus, apres validation Microsoft uniquement
"""

import json
import re
import sys
from pathlib import Path

import faiss
import numpy as np
import yaml
from docling_core.types.doc.document import DoclingDocument
from FlagEmbedding import BGEM3FlagModel

PROJECT_ROOT = Path.cwd().resolve()
if PROJECT_ROOT.name == "notebooks":
    PROJECT_ROOT = PROJECT_ROOT.parent

GROUND_TRUTH_PATH = PROJECT_ROOT / "data_test" / "ground_truth.yaml"
DOCLING_JSON_DIR = PROJECT_ROOT / "data_test" / "docling_json"
OUT_PATH = PROJECT_ROOT / "data_test" / "prompt_4_3_indexation.json"

# Les deux requetes fixes du protocole -- identiques pour tous les rapports. La requete 1 vise les
# emissions absolues (scope_1/2/3, les 4 entreprises) ; la requete 2 vise l'intensite carbone
# (Orsted uniquement) -- mais les deux sont executees et fusionnees pour CHAQUE rapport, sans
# branchement par indicateur : c'est la fusion qui decide, pas une regle codee en dur.
DEUX_REQUETES_FIXES = [
    (
        "Scope 1, Scope 2 location-based, Scope 2 market-based and Scope 3 greenhouse gas emissions "
        "in tonnes of CO2 equivalent (tCO2e)"
    ),
    "Greenhouse gas emissions intensity in grams of CO2 equivalent per kilowatt-hour (gCO2e/kWh)",
]

TOP_PAGES = 8  # troncature du classement complet pour le benchmark retrieval_recall_at_8


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
    """Reconstitue, a partir d'un DoclingDocument, des chunks de texte associes a leur page d'origine.

    Une erreur d'export_to_markdown n'est jamais avalee silencieusement : elle est journalisee avec le
    numero de page concerne, pour qu'une perte de contenu (donc un biais potentiel du benchmark) reste
    detectable au lieu de disparaitre dans un `content = None` muet.
    """
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
            except Exception as exc:  # noqa: BLE001 — journalisé, jamais avalé (voir docstring)
                print(
                    f"AVERTISSEMENT: export_to_markdown a echoue page {page_no} "
                    f"({type(exc).__name__}: {exc}) -- contenu de cet element perdu",
                    file=sys.stderr,
                    flush=True,
                )
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


def search_all_chunks(search_index, embed_model, query):
    """Recherche EXHAUSTIVE (k=ntotal) : renvoie des paires (chunk, score) pour tous les chunks du
    rapport, pas encore consolidees par page. IndexFlatIP calcule deja la similarite avec tous les
    vecteurs en interne quel que soit k -- demander k=ntotal ne coute rien de plus qu'un k tronque,
    et c'est la seule facon d'obtenir un rang exact plutot qu'approxime par une troncature arbitraire."""
    q_emb = embed_model.encode([query])["dense_vecs"]
    q_emb = np.asarray(q_emb, dtype="float32")
    faiss.normalize_L2(q_emb)
    k = search_index["index"].ntotal
    scores, idxs = search_index["index"].search(q_emb, k)
    return [
        (search_index["chunks"][i], float(score))
        for i, score in zip(idxs[0], scores[0])
        if i != -1
    ]


def consolidate_by_page(chunk_score_pairs):
    """Regroupe des paires (chunk, score) par page physique -- conserve le MEILLEUR score par page
    (regle explicite du protocole) -- renvoie [(page, meilleur_score), ...] trie par score decroissant.
    Avec une recherche exhaustive en entree, ce classement couvre TOUTES les pages du rapport."""
    best_by_page = {}
    for chunk, score in chunk_score_pairs:
        page = chunk["page"]
        if page not in best_by_page or score > best_by_page[page]:
            best_by_page[page] = score
    return sorted(best_by_page.items(), key=lambda item: item[1], reverse=True)


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

    # Les deux requetes fixes, executees telles quelles sur TOUT l'index, resultats bruts fusionnes
    # avant tout classement -- rang exact, pas une approximation tronquee a un k arbitraire.
    chunk_scores = []
    for requete in DEUX_REQUETES_FIXES:
        chunk_scores.extend(search_all_chunks(search_index, embed_model, requete))

    classement_complet = consolidate_by_page(chunk_scores)  # [(page, score), ...] decroissant, TOUTES les pages
    rang_par_page = {page: rang + 1 for rang, (page, _score) in enumerate(classement_complet)}
    score_par_page = dict(classement_complet)
    top8 = classement_complet[:TOP_PAGES]

    hits = 0
    n = len(entreprise["indicateurs"])
    details = []
    for indicateur in entreprise["indicateurs"]:
        pages_attendues = indicateur["pages_attendues"]
        pages_retrouvees = [p for p in pages_attendues if p in rang_par_page]
        pages_absentes = [p for p in pages_attendues if p not in rang_par_page]

        if pages_retrouvees:
            rang_trouve = min(rang_par_page[p] for p in pages_retrouvees)
            score_trouve = score_par_page[
                next(p for p in pages_retrouvees if rang_par_page[p] == rang_trouve)
            ]
        else:
            rang_trouve, score_trouve = None, None

        # hit_top8 (= retrieval_recall_at_8) : metrique technique de qualite de recherche uniquement --
        # au moins une page attendue figure-t-elle dans les 8 mieux classees ? Ne mesure PAS une
        # limite du pipeline metier : le systeme final traite l'integralite du rapport, jamais
        # seulement un top-8. Voir couverture_pages_attendues ci-dessous pour la mesure multi-pages.
        hit_top8 = rang_trouve is not None and rang_trouve <= TOP_PAGES
        hits += int(hit_top8)
        recall_total_global += 1
        recall_hits_global += int(hit_top8)

        details.append(
            {
                "code": indicateur["code"],
                "pages_attendues": pages_attendues,
                "rang_trouve": rang_trouve,
                "score_trouve": round(score_trouve, 4) if score_trouve is not None else None,
                "hit_top8": hit_top8,
                "pages_attendues_retrouvees": pages_retrouvees,
                "pages_attendues_absentes": pages_absentes,
                "couverture_pages_attendues": round(len(pages_retrouvees) / len(pages_attendues), 4),
                "all_expected_pages_retrieved": len(pages_absentes) == 0,
            }
        )

    entry = {
        "n_chunks": len(chunks),
        "n_indicateurs": n,
        "requetes": DEUX_REQUETES_FIXES,
        # Classement complet (toutes les pages du rapport, rang exact) -- texte des chunks
        # volontairement exclu, seuls page/rang/score sont utiles au diagnostic.
        "classement_complet": [
            {"page": page, "score": round(score, 4), "rang": rang + 1}
            for rang, (page, score) in enumerate(classement_complet)
        ],
        "pages_top8": [
            {"page": page, "score": round(score, 4), "rang": rang + 1}
            for rang, (page, score) in enumerate(top8)
        ],
        "rappel_hits": hits,
        "rappel_taux": round(hits / n, 4),
        "details": details,
    }
    results[nom] = entry
    print(
        f"{nom:15s} retrieval_recall_at_8 (benchmark recherche) : {hits}/{n} ({hits / n:.0%})",
        flush=True,
    )

    # Ecrit apres CHAQUE entreprise, pas seulement a la fin du lot (meme logique que le Prompt 4.2).
    OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

taux_global = recall_hits_global / recall_total_global if recall_total_global else 0.0
print(
    f"\nretrieval_recall_at_8 global (benchmark technique de recherche, pas une limite du pipeline "
    f"metier) : {recall_hits_global}/{recall_total_global} ({taux_global:.1%})",
    flush=True,
)

results["_global"] = {
    "requetes": DEUX_REQUETES_FIXES,
    "note": (
        "hit_top8 / retrieval_recall_at_8 est un benchmark de qualite de recherche documentaire. "
        "Il ne limite pas l'analyse integrale des rapports dans le systeme metier (Prompt 4.4+), "
        "qui traite l'integralite du contenu extrait, pas seulement les 8 meilleures pages."
    ),
    "rappel_hits": recall_hits_global,
    "rappel_total": recall_total_global,
    "rappel_taux": round(taux_global, 4),
}
OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n=== TERMINE — resultats ecrits dans {OUT_PATH} ===")
