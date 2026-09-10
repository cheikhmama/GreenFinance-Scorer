"""Point d'entrée du pipeline d'extraction documentaire.

Orchestre l'extraction complète d'un rapport déposé : conversion Docling, recherche sémantique
(bge-m3 + FAISS, en mémoire — la persistance pgvector reste un stub réservé à l'Étape 7, voir
app/ingestion/semantic_search.py), extraction structurée via un LLM (Gemini, tool-calling forcé)
avec citation de page, et persistance des indicateurs/données carbone/preuves. Cœur porté depuis
notebooks/_prompt_4_3_indexation.py et notebooks/_prompt_4_4_extraction.py (validés à l'Étape 4).

Point d'entrée pour un déclenchement FastAPI BackgroundTasks (voir app/company/router.py) :
run_extraction_pipeline ouvre sa propre session DB (celle de la requête HTTP est déjà fermée quand
une tâche de fond s'exécute) et est sérialisé par un verrou process-wide — deux extractions
Docling/bge-m3 CPU de plusieurs heures en parallèle n'apportent rien et leur thread-safety n'est pas
documentée.
"""

import os

# Ceinture-bretelles : ce module importe aussi FlagEmbedding/torch (bge-m3), même garde-fou qu'en
# tête de app/ingestion/docling_pipeline.py, positionné avant tout import torch.
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

import json
import threading
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import faiss
import numpy as np
import structlog
from docling_core.types.doc.document import DoclingDocument
from FlagEmbedding import BGEM3FlagModel
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from sqlmodel import Session

from app.core import storage
from app.core.config import get_settings
from app.core.database import engine, utcnow
from app.core.enums import MethodeDonnee, Pilier, StatutRapport
from app.ingestion import docling_pipeline, proof_generator
from app.ingestion.models import (
    DonneeCarbone,
    IndicateurESG,
    PreuveDocumentaire,
    RapportESG,
)
from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait

logger = structlog.get_logger(__name__)

_extraction_lock = threading.Lock()

# Verbatim de notebooks/_prompt_4_3_indexation.py / _prompt_4_4_extraction.py pour les deux
# premières — requêtes fixes, identiques pour tous les rapports, jamais générées à la volée
# depuis un code d'indicateur. Troisième requête ajoutée en Phase 5 §9 (socle Social/Gouvernance
# harmonisé, voir config/weights/default.yaml) : sans elle, la recherche sémantique ne
# retrouverait que les pages carbone/climat et manquerait celles qui discutent la composition du
# conseil d'administration ou la sécurité au travail sur un rapport de plusieurs centaines de
# pages — sans effet sur les rapports courts du corpus de test, où CONTEXT_TOP_PAGES couvre déjà
# la totalité des pages.
REQUETES_FIXES = [
    (
        "Scope 1, Scope 2 location-based, Scope 2 market-based and Scope 3 greenhouse gas emissions "
        "in tonnes of CO2 equivalent (tCO2e)"
    ),
    "Greenhouse gas emissions intensity in grams of CO2 equivalent per kilowatt-hour (gCO2e/kWh)",
    (
        "Percentage of women in management and on the board of directors, workplace fatalities "
        "and occupational safety"
    ),
]

# Fenêtre d'extraction (Prompt 4.4) — distincte du seuil TOP_PAGES=8 du benchmark de recherche 4.3,
# qui ne mesure que la qualité de recherche, pas la fenêtre à donner au LLM d'extraction.
CONTEXT_TOP_PAGES = 20

# Modèle Gemini avec palier gratuit (voir Phase 5 — bascule Anthropic->Gemini, compte Anthropic
# sans crédit). gemini-2.5-flash n'est plus accessible aux nouveaux comptes (confirmé par erreur
# API 404 en direct) — gemini-3.6-flash est le modèle recommandé actuel. La précision (≥90%
# valeurs, ≥85% pages, 0% hallucination, data_test/ground_truth.yaml) a été mesurée avec Claude à
# l'Étape 4 — pas encore revalidée avec ce modèle sur du contenu réel.
EXTRACTION_MODEL = "gemini-3.6-flash"

# Score PCAF non calculé à cette étape (Étape 13, app/carbon/) — placeholder documenté plutôt
# qu'une valeur inventée qui se ferait passer pour une vraie notation.
PLACEHOLDER_SCORE_QUALITE_PCAF = 3

EXTRACTION_TOOL = genai_types.FunctionDeclaration(
    name="extraction_indicateurs",
    description=(
        "Extraction structuree des indicateurs ESG/carbone demandes, a partir des extraits de "
        "rapport fournis."
    ),
    # Schéma Pydantic passé verbatim (le champ dédié du SDK accepte du JSON Schema standard —
    # $defs/$ref/anyOf inclus — contrairement à l'ancien dialecte restreint `parameters`), pour ne
    # jamais dupliquer à la main la définition de app/ingestion/schemas.py::ExtractionEntreprise.
    parameters_json_schema=ExtractionEntreprise.model_json_schema(),
)


@dataclass(frozen=True)
class CibleIndicateur:
    code: str
    cible: Literal["donnee_carbone", "indicateur_esg"]
    scope: int | None = None
    categorie_ges: str | None = None
    pilier: Pilier | None = None


# Les 7 codes carbone/environnement déjà validés sur le corpus pilote (voir
# data_test/ground_truth.yaml), plus le socle Social/Gouvernance harmonisé retenu en Phase 5 §9
# (voir config/weights/default.yaml et le diagnostic associé — analyse de couverture sur
# data_test/reference_esg_8_entreprises.json). Pas de catalogue ESG générique ici : seuls les
# codes qu'une configuration de scoring référence réellement sont ciblés, pour ne jamais extraire
# une donnée qui n'aurait aucun consommateur en aval.
INDICATEURS_CIBLES: list[CibleIndicateur] = [
    CibleIndicateur("scope_1", "donnee_carbone", scope=1),
    CibleIndicateur(
        "scope_2_market_based", "donnee_carbone", scope=2, categorie_ges="market_based"
    ),
    CibleIndicateur(
        "scope_2_location_based", "donnee_carbone", scope=2, categorie_ges="location_based"
    ),
    CibleIndicateur("scope_3", "donnee_carbone", scope=3),
    CibleIndicateur(
        "intensite_scope_1_2_marketbased", "indicateur_esg", pilier=Pilier.ENVIRONNEMENT
    ),
    CibleIndicateur(
        "intensite_scope_1_2_3_hors_cat11", "indicateur_esg", pilier=Pilier.ENVIRONNEMENT
    ),
    CibleIndicateur(
        "intensite_scope_1_2_3_total", "indicateur_esg", pilier=Pilier.ENVIRONNEMENT
    ),
    CibleIndicateur("femmes_management_pourcentage", "indicateur_esg", pilier=Pilier.SOCIAL),
    CibleIndicateur("deces_professionnels", "indicateur_esg", pilier=Pilier.SOCIAL),
    CibleIndicateur("femmes_conseil_pourcentage", "indicateur_esg", pilier=Pilier.GOUVERNANCE),
]


@lru_cache
def _get_embed_model() -> BGEM3FlagModel:
    return BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)


@lru_cache
def _get_gemini_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def _iter_page_chunks(doc: DoclingDocument, max_chars: int = 1200) -> list[dict]:
    """Reconstitue des chunks de texte associés à leur page d'origine. Une erreur
    d'export_to_markdown n'est jamais avalée silencieusement — journalisée avec le numéro de page,
    même règle qu'au Prompt 4.3."""
    buffers: dict[int, list[str]] = {}
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
                logger.warning(
                    "export_to_markdown_echoue", page=page_no, error_type=type(exc).__name__
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


def _build_search_index(doc: DoclingDocument) -> dict:
    chunks = _iter_page_chunks(doc)
    embed_model = _get_embed_model()
    embeddings = embed_model.encode([c["text"] for c in chunks], batch_size=8)["dense_vecs"]
    embeddings = np.asarray(embeddings, dtype="float32")
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return {"chunks": chunks, "index": index}


def _search_all_chunks(
    search_index: dict, embed_model: BGEM3FlagModel, query: str
) -> list[tuple[dict, float]]:
    """Recherche EXHAUSTIVE (k=ntotal) — IndexFlatIP calcule déjà la similarité avec tous les
    vecteurs en interne quel que soit k, donc demander k=ntotal donne un rang exact sans coût
    supplémentaire par rapport à une troncature arbitraire."""
    q_emb = embed_model.encode([query])["dense_vecs"]
    q_emb = np.asarray(q_emb, dtype="float32")
    faiss.normalize_L2(q_emb)
    k = search_index["index"].ntotal
    scores, idxs = search_index["index"].search(q_emb, k)
    return [
        (search_index["chunks"][i], float(score)) for i, score in zip(idxs[0], scores[0]) if i != -1
    ]


def _consolidate_by_page(pairs: list[tuple[dict, float]]) -> list[tuple[int, float]]:
    best_by_page: dict[int, float] = {}
    for chunk, score in pairs:
        page = chunk["page"]
        if page not in best_by_page or score > best_by_page[page]:
            best_by_page[page] = score
    return sorted(best_by_page.items(), key=lambda item: item[1], reverse=True)


def _build_context(search_index: dict, embed_model: BGEM3FlagModel) -> tuple[str, list[int]]:
    chunk_scores = []
    for requete in REQUETES_FIXES:
        chunk_scores.extend(_search_all_chunks(search_index, embed_model, requete))

    classement = _consolidate_by_page(chunk_scores)
    top_pages = {page for page, _score in classement[:CONTEXT_TOP_PAGES]}

    pages_text: dict[int, list[str]] = {}
    for chunk in search_index["chunks"]:
        if chunk["page"] in top_pages:
            pages_text.setdefault(chunk["page"], []).append(chunk["text"])

    ordered_pages = sorted(pages_text)
    context = "\n\n".join(f"--- Page {p} ---\n" + "\n".join(pages_text[p]) for p in ordered_pages)
    return context, ordered_pages


# Nombre de tentatives face à une erreur serveur transitoire (503, surcharge du palier gratuit) —
# jamais sur une ClientError (4xx : clé invalide, modèle inconnu, quota dépassé), qui ne se
# résoudra pas en réessayant. Constaté en pratique sur gemini-3.6-flash, pas hypothétique.
_TENTATIVES_APPEL_LLM = 3


def _call_llm_extraction(
    *, nom_entreprise: str, context: str, codes: list[str]
) -> ExtractionEntreprise:
    """Tool-calling forcé (mode ANY, un seul outil déclaré), verbatim du protocole validé au
    Prompt 4.4 (initialement avec Claude, voir Phase 5 — bascule vers Gemini). Laisse remonter
    toute erreur non transitoire du fournisseur telle quelle — run_extraction_pipeline la classe,
    ne la masque jamais."""
    prompt = f"""Tu es un extracteur de donnees ESG/carbone. Voici des extraits d'un rapport d'entreprise
({nom_entreprise}), avec le numero de page physique indique avant chaque extrait.

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
    config = genai_types.GenerateContentConfig(
        tools=[genai_types.Tool(function_declarations=[EXTRACTION_TOOL])],
        tool_config=genai_types.ToolConfig(
            function_calling_config=genai_types.FunctionCallingConfig(
                mode=genai_types.FunctionCallingConfigMode.ANY
            )
        ),
    )
    for tentative in range(1, _TENTATIVES_APPEL_LLM + 1):
        try:
            response = _get_gemini_client().models.generate_content(
                model=EXTRACTION_MODEL, contents=prompt, config=config
            )
            break
        except genai_errors.ServerError:
            if tentative == _TENTATIVES_APPEL_LLM:
                raise
            logger.warning(
                "appel_llm_erreur_serveur_transitoire", tentative=tentative, nom_entreprise=nom_entreprise
            )
            time.sleep(2**tentative)
    function_calls = response.function_calls
    if not function_calls:
        raise ValueError(
            "Le modele n'a renvoye aucun appel a l'outil extraction_indicateurs."
        )
    return ExtractionEntreprise.model_validate(function_calls[0].args)


def _extraction_demo_synthetique(*, nom_entreprise: str, codes: list[str]) -> ExtractionEntreprise:
    """Résultat synthétique utilisé uniquement quand GEMINI_API_KEY est encore le placeholder
    de .env.example (Settings.gemini_api_key_is_placeholder) — jamais en production, où
    _rejeter_placeholders_en_production bloque le démarrage dans ce cas. Valeurs rondes et
    strictement croissantes par construction, pour ne jamais être prises pour une vraie
    extraction ; la preuve documentaire associée porte aussi un préfixe "[DEMO]" visible à
    l'écran (voir run_extraction_pipeline)."""
    return ExtractionEntreprise(
        entreprise=nom_entreprise,
        indicateurs=[
            IndicateurExtrait(code=code, valeur=1000.0 * (index + 1), unite="", page_source=1, trouve=True)
            for index, code in enumerate(codes)
        ],
    )


def run_extraction_pipeline(rapport_id: uuid.UUID, annee_reporting: int) -> None:
    """Point d'entrée pour un déclenchement BackgroundTasks (app/company/router.py). Ouvre sa
    propre session DB — celle de la requête HTTP est déjà fermée quand une tâche de fond s'exécute
    — et est sérialisé par _extraction_lock."""
    with _extraction_lock, Session(engine) as session:
        rapport = session.get(RapportESG, rapport_id)
        if rapport is None:
            logger.error("extraction_rapport_introuvable", rapport_id=str(rapport_id))
            return

        rapport.statut = StatutRapport.EN_EXTRACTION
        session.add(rapport)
        session.commit()

        etape = "erreur_inattendue"
        try:
            source_path = storage.resolve_path(rapport.fichier_source)
            nom_entreprise = rapport.entreprise.nom
            nom_document = Path(rapport.fichier_source).name
            demo = get_settings().gemini_api_key_is_placeholder
            if demo:
                nom_document = f"[DEMO] {nom_document}"

            # Doit s'exécuter AVANT tout appel à docling_pipeline.convert_pdf (Phase 5 §9,
            # trouvaille empirique) : bge-m3 (PyTorch) initialisé APRÈS que Docling ait chargé son
            # backend PaddleOCR (RapidOcrOptions(backend="paddle")) fait planter le process —
            # d'abord un segmentation fault natif pur (reproduit deux fois à l'identique),
            # puis, une fois la seule construction du modèle déplacée ici, un allocateur CPU
            # PyTorch corrompu signalant un "manque de mémoire" fantaisiste sur une allocation de
            # quelques Mo lors du chargement des modèles Docling (TableFormer, qui utilise aussi
            # PyTorch) — la construction seule ne suffit pas, PyTorch doit avoir réellement exécuté
            # une passe d'inférence (encode()) pour que son runtime CPU soit stabilisé avant que
            # PaddleOCR ne s'initialise. Les deux runtimes coexistent sans problème si PyTorch a
            # réellement tourné en premier, jamais dans l'ordre inverse. _get_embed_model est mis
            # en cache (@lru_cache) : cet appel ne recharge rien la deuxième fois qu'un process a
            # déjà traité un rapport, mais encode() retourne vite (une seule courte chaîne).
            etape = "chargement_modele_embedding_echoue"
            _get_embed_model().encode(["initialisation"])

            etape = "docling_conversion_echouee"
            logger.info("docling_conversion_demarree", rapport_id=str(rapport_id))
            conversion = docling_pipeline.convert_pdf(source_path)
            docling_json_path = storage.resolve_path(f"docling_json/{rapport_id}.json")
            docling_pipeline.persist_docling_json(conversion.document, docling_json_path)
            logger.info(
                "docling_conversion_terminee",
                rapport_id=str(rapport_id),
                elapsed_s=conversion.elapsed_s,
                pages=conversion.pages_docling,
            )

            etape = "indexation_semantique_echouee"
            search_index = _build_search_index(conversion.document)
            embed_model = _get_embed_model()
            context, pages_used = _build_context(search_index, embed_model)
            logger.info("contexte_assemble", rapport_id=str(rapport_id), n_pages=len(pages_used))

            etape = "appel_llm_echoue"
            codes = [cible.code for cible in INDICATEURS_CIBLES]
            if demo:
                logger.warning(
                    "extraction_demo_synthetique_utilisee",
                    rapport_id=str(rapport_id),
                    raison="GEMINI_API_KEY est un placeholder (.env) — extraction simulee",
                )
                extraction = _extraction_demo_synthetique(nom_entreprise=nom_entreprise, codes=codes)
            else:
                extraction = _call_llm_extraction(
                    nom_entreprise=nom_entreprise, context=context, codes=codes
                )
            logger.info("extraction_llm_terminee", rapport_id=str(rapport_id), demo=demo)

            etape = "persistance_echouee"
            cibles_par_code = {cible.code: cible for cible in INDICATEURS_CIBLES}
            preuves_par_page: dict[int, PreuveDocumentaire] = {}
            for indicateur in extraction.indicateurs:
                if (
                    not indicateur.trouve
                    or indicateur.valeur is None
                    or indicateur.page_source is None
                ):
                    logger.warning(
                        "indicateur_non_trouve", rapport_id=str(rapport_id), code=indicateur.code
                    )
                    continue

                cible = cibles_par_code.get(indicateur.code)
                if cible is None:
                    logger.warning(
                        "indicateur_code_inconnu", rapport_id=str(rapport_id), code=indicateur.code
                    )
                    continue

                page = indicateur.page_source
                if page not in preuves_par_page:
                    preuve = proof_generator.generate_page_proof(
                        source_pdf_path=source_path,
                        nom_document=nom_document,
                        annee=annee_reporting,
                        nombre_pages_total=conversion.pages_docling,
                        page=page,
                        rapport_id=rapport_id,
                    )
                    session.add(preuve)
                    session.flush()
                    preuves_par_page[page] = preuve
                preuve = preuves_par_page[page]

                if cible.cible == "donnee_carbone":
                    assert cible.scope is not None  # invariant garanti par INDICATEURS_CIBLES
                    session.add(
                        DonneeCarbone(
                            rapport_id=rapport_id,
                            scope=cible.scope,
                            categorie_ges=cible.categorie_ges,
                            valeur_tonnes_co2e=indicateur.valeur,
                            annee=annee_reporting,
                            methode=MethodeDonnee.RAPPORTEE,
                            score_qualite_pcaf=PLACEHOLDER_SCORE_QUALITE_PCAF,
                            preuve_id=preuve.id,
                        )
                    )
                else:
                    assert cible.pilier is not None  # invariant garanti par INDICATEURS_CIBLES
                    session.add(
                        IndicateurESG(
                            rapport_id=rapport_id,
                            pilier=cible.pilier,
                            code=cible.code,
                            valeur=indicateur.valeur,
                            unite=indicateur.unite or "",
                            methode=MethodeDonnee.RAPPORTEE,
                            preuve_id=preuve.id,
                        )
                    )

            rapport.extraction_terminee_le = utcnow()
            session.add(rapport)
            session.commit()
            logger.info("extraction_pipeline_reussie", rapport_id=str(rapport_id))

        except Exception as exc:  # noqa: BLE001 — frontière délibérée du pipeline de fond : toute
            # erreur (Docling, réseau, Anthropic, DB) doit être classée et journalisée, jamais
            # remonter silencieusement dans une BackgroundTask sans observateur.
            session.rollback()
            rapport.extraction_erreur = etape
            session.add(rapport)
            session.commit()
            logger.error(
                "extraction_pipeline_echouee",
                rapport_id=str(rapport_id),
                error_type=type(exc).__name__,
                etape=etape,
            )
