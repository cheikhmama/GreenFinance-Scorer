"""Prompt 4.4 — extraction structuree via Claude, avec citation de page.

Contenu appele a devenir la cellule de code du Prompt 4.4 dans validation_pipeline.ipynb — ecrit comme
script autonome, meme convention que _prompt_4_2_structuration.py et _prompt_4_3_indexation.py.

iter_page_chunks / search_all_chunks / consolidate_by_page / DEUX_REQUETES_FIXES sont dupliques depuis
_prompt_4_3_indexation.py -- choix de conception deja etabli pour ces scripts (chacun autonome, meme
si ca duplique quelques fonctions), pas un oubli.

Protocole :
  - reindexe chaque rapport exactement comme le Prompt 4.3 (memes deux requetes fixes, recherche
    exhaustive, consolidation par page, meilleur score conserve) ;
  - CONTEXT_TOP_PAGES = 20 (PAS TOP_PAGES = 8, qui reste le seuil du benchmark retrieval_recall_at_8
    du Prompt 4.3, une mesure de qualite de recherche, pas la fenetre d'extraction) -- choisi pour
    couvrir avec marge le pire rang observe au 4.3 (rang 10, Microsoft) tout en restant tres inferieur
    au nombre de pages des gros rapports (218 pour Orsted). A reevaluer seulement apres les resultats
    complets Microsoft/Orsted -- jamais ajuste retroactivement pour ameliorer un score ;
  - le texte COMPLET (tous les chunks, pas seulement le meilleur par page) des CONTEXT_TOP_PAGES
    meilleures pages consolidees est fourni a Claude en un seul appel par entreprise, avec le numero de
    page physique indique avant chaque extrait ;
  - reponse contrainte par un schema Pydantic strict (tool-use force) : valeur, unite, page_source,
    trouve -- feuille explicite "ne jamais inventer une valeur ni une page" si l'indicateur n'apparait
    pas dans le contexte fourni ;
  - resultats bruts (avant comparaison a la verite terrain, qui est le Prompt 4.5) ecrits dans
    data_test/extraction_results.json.

Usage attendu : meme discipline que les prompts precedents -- Microsoft d'abord.
    python3 _prompt_4_4_extraction.py microsoft
    python3 _prompt_4_4_extraction.py   # tout le corpus, apres validation Microsoft
"""

import json
import os
import sys
from pathlib import Path

import anthropic
import faiss
import numpy as np
import yaml
from docling_core.types.doc.document import DoclingDocument
from dotenv import load_dotenv
from FlagEmbedding import BGEM3FlagModel
from pydantic import BaseModel, Field

PROJECT_ROOT = Path.cwd().resolve()
if PROJECT_ROOT.name == "notebooks":
    PROJECT_ROOT = PROJECT_ROOT.parent

GROUND_TRUTH_PATH = PROJECT_ROOT / "data_test" / "ground_truth.yaml"
DOCLING_JSON_DIR = PROJECT_ROOT / "data_test" / "docling_json"
OUT_PATH = PROJECT_ROOT / "data_test" / "extraction_results.json"

# Memes deux requetes fixes que le Prompt 4.3 -- jamais generees a la volee depuis le code de
# l'indicateur. Voir _prompt_4_3_indexation.py pour la justification complete de chaque requete.
DEUX_REQUETES_FIXES = [
    (
        "Scope 1, Scope 2 location-based, Scope 2 market-based and Scope 3 greenhouse gas emissions "
        "in tonnes of CO2 equivalent (tCO2e)"
    ),
    "Greenhouse gas emissions intensity in grams of CO2 equivalent per kilowatt-hour (gCO2e/kWh)",
]

CONTEXT_TOP_PAGES = 20  # fenetre d'extraction -- distincte de TOP_PAGES=8 (benchmark 4.3), voir docstring

load_dotenv(PROJECT_ROOT / ".env")
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
CLAUDE_MODEL = "claude-sonnet-5"


class IndicateurExtrait(BaseModel):
    code: str
    valeur: float | None = Field(
        default=None, description="Valeur numerique trouvee, null si absente des extraits fournis"
    )
    unite: str | None = Field(default=None, description="Unite de la valeur, telle qu'ecrite dans le document")
    page_source: int | None = Field(
        default=None, description="Numero de page physique (indique par --- Page N ---) ou la valeur a ete trouvee"
    )
    trouve: bool = Field(description="False si l'indicateur n'apparait pas explicitement dans les extraits fournis")


class ExtractionEntreprise(BaseModel):
    entreprise: str
    indicateurs: list[IndicateurExtrait]


EXTRACTION_TOOL = {
    "name": "extraction_indicateurs",
    "description": "Extraction structuree des indicateurs ESG/carbone demandes, a partir des extraits de rapport fournis.",
    "input_schema": ExtractionEntreprise.model_json_schema(),
}


def iter_page_chunks(doc, max_chars=1200):
    """Reconstitue, a partir d'un DoclingDocument, des chunks de texte associes a leur page d'origine.

    Une erreur d'export_to_markdown est journalisee (page + erreur), jamais masquee silencieusement --
    meme regle que _prompt_4_3_indexation.py.
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
    """Recherche EXHAUSTIVE (k=ntotal), identique a _prompt_4_3_indexation.py."""
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
    """Regroupe par page physique -- conserve le MEILLEUR score par page -- trie decroissant."""
    best_by_page = {}
    for chunk, score in chunk_score_pairs:
        page = chunk["page"]
        if page not in best_by_page or score > best_by_page[page]:
            best_by_page[page] = score
    return sorted(best_by_page.items(), key=lambda item: item[1], reverse=True)


def build_context(search_index, embed_model):
    """Assemble le texte COMPLET (tous les chunks, pas seulement le meilleur par page) des
    CONTEXT_TOP_PAGES meilleures pages consolidees des deux requetes fixes -- une seule fois pour tous
    les indicateurs de l'entreprise, jamais une requete/un contexte different par indicateur."""
    chunk_scores = []
    for requete in DEUX_REQUETES_FIXES:
        chunk_scores.extend(search_all_chunks(search_index, embed_model, requete))

    classement = consolidate_by_page(chunk_scores)
    top_pages = {page for page, _score in classement[:CONTEXT_TOP_PAGES]}

    pages_text = {}
    for chunk in search_index["chunks"]:
        if chunk["page"] in top_pages:
            pages_text.setdefault(chunk["page"], []).append(chunk["text"])

    ordered_pages = sorted(pages_text)
    context = "\n\n".join(f"--- Page {p} ---\n" + "\n".join(pages_text[p]) for p in ordered_pages)
    return context, ordered_pages


with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
    ground_truth = yaml.safe_load(f)
entreprises = ground_truth["entreprises"]

# Filtre optionnel en argument CLI (ex: `python3 _prompt_4_4_extraction.py microsoft`) -- meme
# discipline que les prompts precedents : valider sur Microsoft avant le corpus complet.
if len(sys.argv) > 1:
    noms_connus = {e["nom"] for e in entreprises}
    inconnus = [nom for nom in sys.argv[1:] if nom not in noms_connus]
    if inconnus:
        raise SystemExit(f"Rapport(s) inconnu(s) : {inconnus}. Choix possibles : {sorted(noms_connus)}")
    entreprises = [e for e in entreprises if e["nom"] in sys.argv[1:]]

print("Chargement du modele bge-m3 (peut telecharger plusieurs Go au premier appel)...", flush=True)
embed_model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)

extraction_results = {}

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
        print(f"{nom}: aucun chunk extrait, extraction ignoree", flush=True)
        continue

    embeddings = embed_model.encode([c["text"] for c in chunks], batch_size=8)["dense_vecs"]
    embeddings = np.asarray(embeddings, dtype="float32")
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    search_index = {"chunks": chunks, "index": index}
    print(f"{nom}: {len(chunks)} chunks indexes", flush=True)

    context, pages_used = build_context(search_index, embed_model)
    codes = [i["code"] for i in entreprise["indicateurs"]]
    print(f"{nom}: contexte assemble sur {len(pages_used)} pages ({CONTEXT_TOP_PAGES} demandees)", flush=True)

    prompt = f"""Tu es un extracteur de donnees ESG/carbone. Voici des extraits d'un rapport d'entreprise
({nom}), avec le numero de page physique indique avant chaque extrait.

Pour CHACUN des indicateurs suivants, trouve sa valeur numerique la plus recente dans les extraits fournis :
{json.dumps(codes, ensure_ascii=False)}

Regles strictes :
- Si un indicateur n'apparait pas explicitement dans les extraits fournis, "trouve" doit etre false et
  "valeur" doit etre null. Ne jamais inventer une valeur ni une page.
- "page_source" doit etre le numero de page (indique par "--- Page N ---") ou tu as trouve la valeur.
- Reponds pour chacun des {len(codes)} indicateurs demandes, dans le meme ordre.

Extraits du rapport :
{context}
"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "extraction_indicateurs"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    result = tool_use.input
    extraction_results[nom] = result
    print(
        f"{nom}: {len(result.get('indicateurs', []))} indicateurs extraits "
        f"(contexte : {len(pages_used)} pages)",
        flush=True,
    )

    # Ecrit apres CHAQUE entreprise, pas seulement a la fin du lot (meme logique que les Prompts 4.2/4.3).
    OUT_PATH.write_text(json.dumps(extraction_results, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"\n=== TERMINE — resultats ecrits dans {OUT_PATH} ===")
