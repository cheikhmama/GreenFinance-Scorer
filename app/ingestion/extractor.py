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
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import faiss
import httpx
import numpy as np
import structlog
from docling_core.types.doc.document import DoclingDocument
from FlagEmbedding import BGEM3FlagModel
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from sqlmodel import Session, col, select

from app.auth.models import User
from app.carbon.pcaf import qualite_donnee_pcaf
from app.core import storage
from app.core.config import get_settings
from app.core.database import engine, utcnow
from app.core.enums import DataMethod, ExtractionStatus, Pillar, Role
from app.core.notifications import notifier
from app.ingestion import docling_pipeline, proof_generator
from app.ingestion.completeness import calculer_couverture
from app.ingestion.etat_extraction import ExtractionTransitoire, marquer_echec
from app.ingestion.models import (
    CarbonEmission,
    ESGMetric,
    ESGReport,
    Evidence,
    MetricCoverage,
)
from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait

logger = structlog.get_logger(__name__)



def _est_transitoire(exc: BaseException) -> bool:
    if isinstance(exc, genai_errors.ServerError):
        return True
    if isinstance(exc, genai_errors.ClientError) and getattr(exc, "code", None) == 429:
        return True
    return isinstance(exc, ConnectionError | TimeoutError | httpx.TransportError)


# Une requête sémantique dédiée par code cible (Phase 6) — remplace les 3 requêtes génériques
# d'origine (Prompt 4.3/4.4). Sur un rapport de plusieurs centaines de pages, les ~23 codes de
# INDICATEURS_CIBLES (ci-dessous) sont dispersés sur bien plus de pages qu'un plafond fixe ne peut
# en couvrir ; une requête générique par thème (carbone/social/gouvernance) noierait un code précis
# (ex. "administrateurs_independants_pourcentage") derrière des pages plus génériquement
# pertinentes pour le thème mais pas pour CE code. L'assertion juste après INDICATEURS_CIBLES
# garantit qu'aucun code n'est jamais invisible à la recherche par simple omission ici.
REQUETES_PAR_CODE: dict[str, str] = {
    "scope_1": "Scope 1 direct greenhouse gas emissions in tonnes of CO2 equivalent",
    "scope_2": (
        "Scope 2 greenhouse gas emissions (not split market/location-based) in tonnes of "
        "CO2 equivalent"
    ),
    "scope_2_market_based": (
        "Scope 2 market-based greenhouse gas emissions in tonnes of CO2 equivalent"
    ),
    "scope_2_location_based": (
        "Scope 2 location-based greenhouse gas emissions in tonnes of CO2 equivalent"
    ),
    "scope_3": (
        "Scope 3 value chain greenhouse gas emissions in tonnes of CO2 equivalent, including "
        "any single reported category"
    ),
    "intensite_scope_1_2_marketbased": (
        "Greenhouse gas emissions intensity, market-based, in grams of CO2 equivalent per "
        "kilowatt-hour"
    ),
    "intensite_scope_1_2_3_hors_cat11": (
        "Greenhouse gas emissions intensity excluding Scope 3 category 11 (use of sold products)"
    ),
    "intensite_scope_1_2_3_total": (
        "Total greenhouse gas emissions intensity including all scopes"
    ),
    "femmes_management_pourcentage": "Percentage of women in management positions",
    "deces_professionnels": "Number of workplace fatalities / occupational deaths",
    "femmes_conseil_pourcentage": "Percentage of women on the board of directors",
    "taille_conseil": "Size of the board of directors, number of board members",
    "administrateurs_independants_pourcentage": (
        "Percentage of independent directors on the board"
    ),
    "effectif_total": "Total number of employees, total workforce headcount",
    "femmes_effectif_pourcentage": "Percentage of women in the total workforce",
    "heures_formation_par_employe": "Average training hours per employee",
    "taux_frequence_accidents": (
        "Workplace accident frequency rate, lost time injury frequency rate"
    ),
    "part_renouvelable_pourcentage": (
        "Percentage of renewable energy in total energy consumption"
    ),
    "dechets_valorises_pourcentage": (
        "Percentage of waste diverted from disposal / recovered / recycled"
    ),
    "score_environnement_declare": "Company's self-reported overall Environmental score or rating",
    "score_social_declare": "Company's self-reported overall Social score or rating",
    "score_gouvernance_declare": "Company's self-reported overall Governance score or rating",
    "score_global_declare": "Company's self-reported overall ESG score or rating",
}

# Sélection adaptative du contexte envoyé au LLM (Phase 6, remplace l'ancien CONTEXT_TOP_PAGES=20
# fixe) — la recherche sémantique porte déjà sur 100% des pages (FAISS exhaustif, voir
# _search_all_chunks) ; ces constantes bornent uniquement ce qui est effectivement montré au LLM,
# pour ne jamais envoyer un rapport de plusieurs centaines de pages en entier à chaque appel.
# Constantes de code (pas de Settings) — même convention que _TENTATIVES_APPEL_LLM ci-dessous,
# ajustées via PR et revalidées au besoin par scripts/evaluate_extraction_pipeline.py.
CHARS_PER_TOKEN_ESTIME = 4
CONTEXT_TOKEN_BUDGET = 24_000
CONTEXT_TOKEN_BUDGET_RETRY = 12_000
RELEVANCE_FLOOR_RATIO = 0.5
NEIGHBOR_RADIUS = 1
TABLE_SCORE_BOOST = 1.15

# Modèle Gemini avec palier gratuit (voir Phase 5 — bascule Anthropic->Gemini, compte Anthropic
# sans crédit). gemini-2.5-flash n'est plus accessible aux nouveaux comptes (confirmé par erreur
# API 404 en direct) — gemini-3.6-flash est le modèle recommandé actuel. La précision (≥90%
# valeurs, ≥85% pages, 0% hallucination, data_test/ground_truth.yaml) a été mesurée avec Claude à
# l'Étape 4 — pas encore revalidée avec ce modèle sur du contenu réel.
EXTRACTION_MODEL = "gemini-3.6-flash"

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
    # "rapport_score_global" : score transversal auto-déclaré par l'entreprise (ex. "Score global
    # ESG : 66/100"), écrit directement sur ESGReport.declared_global_score — aucun pilier E/S/G
    # ne convient à une valeur transversale aux trois.
    cible: Literal["donnee_carbone", "indicateur_esg", "rapport_score_global"]
    scope: int | None = None
    categorie_ges: str | None = None
    pilier: Pillar | None = None


# Les 7 codes carbone/environnement déjà validés sur le corpus pilote (voir
# data_test/ground_truth.yaml), plus le socle Social/Gouvernance harmonisé retenu en Phase 5 §9
# (voir config/weights/default.yaml et le diagnostic associé — analyse de couverture sur
# data_test/reference_esg_8_entreprises.json), plus un second lot (ci-dessous) ajouté pour la
# transparence humaine (Admin/Auditeur/Investisseur consultant un rapport doit voir ce qui y est
# réellement écrit, avec preuve page par page — garantie G1) : un consommateur légitime distinct
# du moteur de scoring, qui continue de ne lire que les codes présents dans
# config/weights/default.yaml (app/scoring/engine.py ignore silencieusement tout code inconnu du
# YAML — confirmé par lecture directe, aucun risque de modifier un score déjà calculé).
INDICATEURS_CIBLES: list[CibleIndicateur] = [
    CibleIndicateur("scope_1", "donnee_carbone", scope=1),
    # Scope 2 non différencié marché/localisation — le cas le plus courant en pratique (voir
    # data_test/reference_esg_8_entreprises.json, "Scope 2 communiqué comme une valeur unique...
    # pour les 8 entreprises") : sans ce code, un Scope 2 pourtant explicite dans le rapport ne
    # matche jamais scope_2_market_based/location_based et disparaît silencieusement.
    CibleIndicateur("scope_2", "donnee_carbone", scope=2),
    CibleIndicateur(
        "scope_2_market_based", "donnee_carbone", scope=2, categorie_ges="market_based"
    ),
    CibleIndicateur(
        "scope_2_location_based", "donnee_carbone", scope=2, categorie_ges="location_based"
    ),
    CibleIndicateur("scope_3", "donnee_carbone", scope=3),
    CibleIndicateur(
        "intensite_scope_1_2_marketbased", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT
    ),
    CibleIndicateur(
        "intensite_scope_1_2_3_hors_cat11", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT
    ),
    CibleIndicateur(
        "intensite_scope_1_2_3_total", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT
    ),
    CibleIndicateur("femmes_management_pourcentage", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("deces_professionnels", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("femmes_conseil_pourcentage", "indicateur_esg", pilier=Pillar.GOUVERNANCE),
    # Second lot — transparence humaine, repris du catalogue déjà pensé dans
    # data_test/reference_esg_8_entreprises.json (codes déjà nommés, jamais branchés jusqu'ici).
    # Liste non exhaustive : le pattern (un CibleIndicateur par fait numérique avec page-preuve)
    # se répète, d'autres codes pourront s'ajouter au fil des rapports rencontrés.
    CibleIndicateur("taille_conseil", "indicateur_esg", pilier=Pillar.GOUVERNANCE),
    CibleIndicateur(
        "administrateurs_independants_pourcentage", "indicateur_esg", pilier=Pillar.GOUVERNANCE
    ),
    CibleIndicateur("effectif_total", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("femmes_effectif_pourcentage", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("heures_formation_par_employe", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("taux_frequence_accidents", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur(
        "part_renouvelable_pourcentage", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT
    ),
    CibleIndicateur(
        "dechets_valorises_pourcentage", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT
    ),
    # Scores auto-déclarés par l'entreprise dans sa propre synthèse ESG — par pilier uniquement
    # (pas de "global" : Pilier n'a que 3 valeurs, et la plateforme calcule déjà son propre score
    # officiel via Score/config/weights/default.yaml ; ajouter un score global auto-déclaré à
    # côté créerait une confusion entre "ce que l'entreprise prétend" et "ce que la plateforme
    # calcule" — décision produit à part entière, pas un ajout silencieux ici).
    CibleIndicateur("score_environnement_declare", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT),
    CibleIndicateur("score_social_declare", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("score_gouvernance_declare", "indicateur_esg", pilier=Pillar.GOUVERNANCE),
    CibleIndicateur("score_global_declare", "rapport_score_global"),
]

assert {c.code for c in INDICATEURS_CIBLES} == set(REQUETES_PAR_CODE), (
    "Chaque code de INDICATEURS_CIBLES doit avoir exactement une requête sémantique dédiée "
    "dans REQUETES_PAR_CODE."
)

@lru_cache
def _get_embed_model() -> BGEM3FlagModel:
    return BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)


@lru_cache
def _get_gemini_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def _iter_page_chunks(doc: DoclingDocument, max_chars: int = 1200) -> list[dict]:
    """Reconstitue des chunks de texte associés à leur page d'origine, un chunk par item source
    (texte OU tableau) — jamais deux items fusionnés dans un même chunk avant découpage, contrairement
    à la version d'origine qui concatenait tout le contenu d'une page avant de trancher en morceaux
    de max_chars (perdant ainsi la frontière d'un tableau). Chaque chunk porte is_table, lu par
    _consolidate_by_page pour prioriser légèrement les tableaux (TABLE_SCORE_BOOST) où vivent
    disproportionnellement les données ESG chiffrées. Une erreur d'export_to_markdown n'est jamais
    avalée silencieusement — journalisée avec le numéro de page, même règle qu'au Prompt 4.3."""
    chunks: list[dict] = []
    # Any (pas object) : les items Docling (TextItem, TableItem...) n'ont pas de base commune
    # exposant .text/.export_to_markdown — un typage object ferait échouer mypy sur les accès
    # ci-dessous alors que le code les protège déjà par getattr/hasattr, en duck-typing délibéré.
    items: list[tuple[bool, Any]] = [(False, t) for t in getattr(doc, "texts", [])] + [
        (True, t) for t in getattr(doc, "tables", [])
    ]
    for is_table, item in items:
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
        for i in range(0, len(content), max_chars):
            piece = content[i : i + max_chars].strip()
            if piece:
                chunks.append({"page": page_no, "text": piece, "is_table": is_table})
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


@dataclass(frozen=True)
class PageCandidat:
    """Page candidate au contexte LLM pour UNE requête, avec son meilleur score (déjà boosté si
    is_table — voir _consolidate_by_page)."""

    page: int
    score: float
    is_table: bool


def _consolidate_by_page(pairs: list[tuple[dict, float]]) -> list[PageCandidat]:
    """Meilleur score par page pour une requête. Un chunk table reçoit TABLE_SCORE_BOOST avant
    comparaison — un score "boosté", utilisé seulement pour ce classement, jamais confondu avec une
    vraie similarité cosinus ailleurs."""
    best_by_page: dict[int, tuple[float, bool]] = {}
    for chunk, score in pairs:
        page = chunk["page"]
        boosted = score * TABLE_SCORE_BOOST if chunk["is_table"] else score
        if page not in best_by_page or boosted > best_by_page[page][0]:
            best_by_page[page] = (boosted, chunk["is_table"])
    return sorted(
        (PageCandidat(page=p, score=s, is_table=t) for p, (s, t) in best_by_page.items()),
        key=lambda c: c.score,
        reverse=True,
    )


def _rechercher_par_code(
    search_index: dict, embed_model: BGEM3FlagModel, codes: list[str]
) -> dict[str, list[PageCandidat]]:
    """Une recherche FAISS exhaustive par code (REQUETES_PAR_CODE[code]), consolidée par page.
    REQUETES_PAR_CODE[code] (jamais .get) : un code sans requête dédiée doit lever une KeyError
    explicite plutôt que disparaître silencieusement de la recherche."""
    return {
        code: _consolidate_by_page(
            _search_all_chunks(search_index, embed_model, REQUETES_PAR_CODE[code])
        )
        for code in codes
    }


def _fusionner_classements(pages_par_code: dict[str, list[PageCandidat]]) -> list[PageCandidat]:
    """Score global par page = max des scores (déjà boostés table) sur tous les codes fournis —
    généralise le pooling multi-requêtes de l'ancien _build_context (3 REQUETES_FIXES) à une
    requête par code."""
    best: dict[int, PageCandidat] = {}
    for candidats in pages_par_code.values():
        for c in candidats:
            if c.page not in best or c.score > best[c.page].score:
                best[c.page] = c
    return sorted(best.values(), key=lambda c: c.score, reverse=True)


def _estimer_tokens(texte: str) -> int:
    """Heuristique caractères→tokens (aucun tokenizer importé aujourd'hui) — CHARS_PER_TOKEN_ESTIME."""
    return max(1, len(texte) // CHARS_PER_TOKEN_ESTIME)


def _selectionner_pages_adaptatif(
    classement_global: list[PageCandidat], texte_par_page: dict[int, str], budget_tokens: int
) -> list[int]:
    """Glouton sur un classement déjà trié décroissant : arrête dès qu'un score tombe sous le
    plancher de pertinence (RELEVANCE_FLOOR_RATIO du meilleur score — le classement étant trié,
    tout le reste est encore plus bas, un seul arrêt suffit), ou dès que le budget de tokens serait
    dépassé — sauf pour la toute première page, toujours incluse même si elle dépasse seule le
    budget (jamais un contexte vide envoyé au LLM)."""
    if not classement_global:
        return []
    plancher = classement_global[0].score * RELEVANCE_FLOOR_RATIO
    selection: list[int] = []
    tokens_cumules = 0
    for i, candidat in enumerate(classement_global):
        if candidat.score < plancher:
            break
        cout = _estimer_tokens(texte_par_page.get(candidat.page, ""))
        if i > 0 and tokens_cumules + cout > budget_tokens:
            break
        selection.append(candidat.page)
        tokens_cumules += cout
    return selection


def _elargir_aux_voisins(pages: list[int], pages_disponibles: set[int], radius: int) -> list[int]:
    """Ajout pur de pages adjacentes (±radius), hors budget et hors plancher : récupère un tableau
    ou un paragraphe coupé par la page choisie pour son score, jamais un re-filtrage par pertinence.
    Filtré aux pages qui existent réellement dans le document (pas de page 0, pas au-delà de la
    dernière)."""
    elargi = set(pages)
    for p in pages:
        for delta in range(-radius, radius + 1):
            if (p + delta) in pages_disponibles:
                elargi.add(p + delta)
    return sorted(elargi)


def _build_context(
    search_index: dict, embed_model: BGEM3FlagModel, codes: list[str], budget_tokens: int
) -> tuple[str, list[int], dict[str, list[PageCandidat]]]:
    """Remplace l'ancienne fonction à 2 arguments (REQUETES_FIXES/CONTEXT_TOP_PAGES implicites) :
    codes et budget_tokens explicites pour être appelable identiquement au 1er passage (tous les
    codes, CONTEXT_TOKEN_BUDGET) et à la relance (codes manquants seulement,
    CONTEXT_TOKEN_BUDGET_RETRY — voir run_extraction_pipeline). Renvoie aussi pages_par_code
    (candidats bruts pré-sélection, un par code) — nécessaire pour juger l'exhaustivité de la
    recherche par code (statut ABSENT_CONFIRME, voir completeness._absence_confirmee)."""
    pages_par_code = _rechercher_par_code(search_index, embed_model, codes)
    classement_global = _fusionner_classements(pages_par_code)

    texte_par_page: dict[int, list[str]] = {}
    for chunk in search_index["chunks"]:
        texte_par_page.setdefault(chunk["page"], []).append(chunk["text"])
    texte_par_page_str = {page: "\n".join(parts) for page, parts in texte_par_page.items()}

    pages_coeur = _selectionner_pages_adaptatif(classement_global, texte_par_page_str, budget_tokens)
    pages_finales = _elargir_aux_voisins(pages_coeur, set(texte_par_page_str), NEIGHBOR_RADIUS)

    context = "\n\n".join(
        f"--- Page {p} ---\n{texte_par_page_str[p]}" for p in pages_finales if p in texte_par_page_str
    )
    return context, pages_finales, pages_par_code


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
    ne la masque jamais. Signature inchangée par le passage à la sélection adaptative (Phase 6) :
    c'est ce qui permet d'appeler cette fonction une seconde fois pour la relance groupée sans la
    modifier (voir run_extraction_pipeline)."""
    prompt = f"""Tu es un extracteur de donnees ESG/carbone. Voici des extraits d'un rapport d'entreprise
({nom_entreprise}), avec le numero de page physique indique avant chaque extrait.

Pour CHACUN des indicateurs suivants, trouve sa valeur numerique la plus recente dans les extraits fournis :
{json.dumps(codes, ensure_ascii=False)}

Regles strictes :
- Si un indicateur n'apparait pas explicitement dans les extraits fournis, "trouve" doit etre false et
  "valeur" doit etre null. Ne jamais inventer une valeur ni une page.
- "page_source" doit etre le numero de page (indique par "--- Page N ---") ou tu as trouve la valeur.
- Pour "scope_3" : si le rapport ne donne qu'une seule categorie du Scope 3 (ex. "Scope 3
  categorie 11"), utilise quand meme cette valeur pour "scope_3" plutot que de repondre "trouve":
  false - c'est la seule donnee Scope 3 disponible dans ce rapport.
- Quand "trouve" est true, remplis aussi si possible : "valeur_brute" (la valeur telle qu'ecrite
  litteralement, avec sa mise en forme d'origine), "section" (le titre ou la rubrique la plus
  proche visible dans les extraits), "citation_source" (une courte citation verbatim, quelques mots,
  qui justifie la valeur), "annee_valeur" (l'annee a laquelle se rapporte la valeur telle
  qu'indiquee dans le document, qui peut differer de l'annee de reporting), "confiance" (ELEVE,
  MOYEN ou FAIBLE selon la clarte de la donnee dans le texte). Laisse ces champs vides plutot que
  de deviner s'ils ne sont pas clairs.
- Quand "trouve" est false ET que le document declare EXPLICITEMENT que cet indicateur n'est pas
  divulgue cette annee (ex. "non communique", "not disclosed"), remplis "non_divulgation_citation"
  (citation verbatim de cette declaration) et "non_divulgation_page" (sa page). Sinon laisse ces
  deux champs vides — ne jamais les remplir sur une simple absence silencieuse du document.
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


def _indicateur_trouve(extraction: ExtractionEntreprise, code: str) -> bool:
    """Même critère que completeness.calculer_couverture : un code compte comme trouvé seulement
    si le LLM l'a explicitement marqué trouve=true ET fourni une valeur non nulle."""
    extrait = next((i for i in extraction.indicateurs if i.code == code), None)
    return bool(extrait and extrait.trouve and extrait.valeur is not None)


def _fusionner_extractions(
    premiere: ExtractionEntreprise, retry: ExtractionEntreprise, codes_manquants: list[str]
) -> ExtractionEntreprise:
    """Fusion à sens unique : pour un code de codes_manquants, la réponse de retry REMPLACE celle
    de premiere (recherche re-ciblée, potentiellement porteuse d'une citation de non-divulgation
    absente du 1er passage) — jamais l'inverse. Les codes hors codes_manquants restent inchangés,
    retry ne les a jamais reçus en entrée (voir run_extraction_pipeline) ; un code hors périmètre
    que le LLM aurait quand même renvoyé par erreur est ignoré."""
    fusion = {i.code: i for i in premiere.indicateurs}
    fusion.update({i.code: i for i in retry.indicateurs if i.code in codes_manquants})
    return ExtractionEntreprise(entreprise=premiere.entreprise, indicateurs=list(fusion.values()))


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


def run_extraction_pipeline(
    rapport_id: uuid.UUID, annee_reporting: int, *, derniere_tentative: bool = True
) -> None:
    """Exécuté par le worker (app/worker/jobs.py::extract_report, file d'extraction à un job à la
    fois — plus de verrou applicatif). Ouvre sa propre session DB.

    derniere_tentative=False : un échec transitoire (_est_transitoire) remet le rapport en QUEUED
    et lève ExtractionTransitoire pour que le worker retente plus tard ; toute autre erreur, ou un
    échec transitoire à la dernière tentative, marque le rapport FAILED comme avant."""
    with Session(engine) as session:
        rapport = session.get(ESGReport, rapport_id)
        if rapport is None:
            logger.error("extraction_rapport_introuvable", rapport_id=str(rapport_id))
            return
        if rapport.source_file is None:
            # Un brouillon (tâche 1.5) n'a pas de fichier : rien à extraire. Jamais programmé
            # par l'application, gardé en défense.
            logger.error("extraction_sans_fichier", rapport_id=str(rapport_id))
            return
        fichier_source = rapport.source_file

        # Seul extraction_status avance ici, jamais le statut métier (ReportStatus) : rejouer
        # l'extraction (ex. après élargissement d'INDICATEURS_CIBLES) sur un rapport déjà affecté
        # à un auditeur ne doit jamais le faire régresser dans le workflow — un vrai bug rencontré
        # en pratique avec l'ancien statut unique (SMH/SNDE repassés en extraction alors que déjà
        # affectés).
        #
        # extraction_started_at est posé à CHAQUE entrée dans le pipeline (dépôt initial ou
        # relance manuelle après échec) — sert de référence à la tâche planifiée
        # (app/ingestion/supervision.py) pour détecter un traitement interrompu ; une relance doit
        # repartir d'un chronomètre frais, pas de celui de la toute première tentative.
        rapport.extraction_status = ExtractionStatus.RUNNING
        rapport.extraction_started_at = utcnow()
        session.add(rapport)
        session.commit()

        etape = "erreur_inattendue"
        try:
            source_path = storage.resolve_path(fichier_source)
            nom_entreprise = rapport.company.name
            nom_document = Path(fichier_source).name
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
            codes = [cible.code for cible in INDICATEURS_CIBLES]
            context, pages_used, pages_par_code = _build_context(
                search_index, embed_model, codes, CONTEXT_TOKEN_BUDGET
            )
            logger.info("contexte_assemble", rapport_id=str(rapport_id), n_pages=len(pages_used))
            pages_vues_par_code: dict[str, set[int]] = {code: set(pages_used) for code in codes}

            etape = "appel_llm_echoue"
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

                # Relance groupee (Phase 6) : UN SEUL appel supplementaire couvrant tous les codes
                # encore manquants apres le 1er passage, jamais un appel par code — le pipeline
                # tourne sur le palier gratuit Gemini, sans infrastructure de rate-limiting ;
                # borner a 2 appels/rapport au maximum est la protection qui ne depend pas de
                # connaitre le quota exact de ce palier.
                codes_manquants = [code for code in codes if not _indicateur_trouve(extraction, code)]
                if codes_manquants:
                    etape = "relance_llm_echouee"
                    contexte_retry, pages_retry, pages_par_code_retry = _build_context(
                        search_index, embed_model, codes_manquants, CONTEXT_TOKEN_BUDGET_RETRY
                    )
                    if pages_retry:
                        extraction_retry = _call_llm_extraction(
                            nom_entreprise=nom_entreprise,
                            context=contexte_retry,
                            codes=codes_manquants,
                        )
                        extraction = _fusionner_extractions(extraction, extraction_retry, codes_manquants)
                        for code in codes_manquants:
                            pages_vues_par_code[code] |= set(pages_retry)
                        pages_par_code.update(pages_par_code_retry)
                    etape = "appel_llm_echoue"
            logger.info("extraction_llm_terminee", rapport_id=str(rapport_id), demo=demo)

            etape = "persistance_echouee"
            # Purge des données dérivées d'une extraction précédente sur ce même rapport, pour que
            # run_extraction_pipeline soit rejouable (ex. après élargissement d'INDICATEURS_CIBLES)
            # sans dupliquer les lignes. Ne touche jamais ESGReport (le PDF déposé) ni AuditOpinion —
            # seules les données automatiques, best-effort et remplaçables sont concernées.
            # Evidence n'a pas de rapport_id direct (liée uniquement via le preuve_id des
            # lignes ci-dessous, et son fichier est stocké sous preuves/{rapport_id}/page_N.pdf,
            # app/ingestion/proof_generator.py — jamais partagée entre rapports) : ses ids doivent
            # être collectés avant de supprimer les lignes qui les référencent.
            anciens_indicateurs = session.exec(
                select(ESGMetric).where(ESGMetric.report_id == rapport_id)
            ).all()
            anciennes_donnees_carbone = session.exec(
                select(CarbonEmission).where(CarbonEmission.report_id == rapport_id)
            ).all()
            anciennes_couvertures = session.exec(
                select(MetricCoverage).where(MetricCoverage.report_id == rapport_id)
            ).all()
            for ancienne_couverture in anciennes_couvertures:
                session.delete(ancienne_couverture)
            anciennes_preuve_ids = {i.proof_id for i in anciens_indicateurs} | {
                d.proof_id for d in anciennes_donnees_carbone
            }
            if rapport.declared_global_score_proof_id is not None:
                anciennes_preuve_ids.add(rapport.declared_global_score_proof_id)
            rapport.declared_global_score = None
            rapport.declared_global_score_proof_id = None
            session.add(rapport)
            for ancienne_ligne in [*anciens_indicateurs, *anciennes_donnees_carbone]:
                session.delete(ancienne_ligne)
            if anciennes_preuve_ids:
                for ancienne_preuve in session.exec(
                    select(Evidence).where(
                        col(Evidence.id).in_(anciennes_preuve_ids)
                    )
                ).all():
                    session.delete(ancienne_preuve)
            session.flush()

            cibles_par_code = {cible.code: cible for cible in INDICATEURS_CIBLES}
            preuves_par_page: dict[int, Evidence] = {}
            # Le LLM peut renvoyer deux fois le même code : la première occurrence exploitable
            # l'emporte, jamais deux lignes pour un même code (uq_esg_metrics_report_metric_code
            # l'impose en base pour ESGMetric ; le même principe évite un double comptage des
            # émissions pour CarbonEmission).
            codes_persistes: set[str] = set()
            for indicateur in extraction.indicateurs:
                if indicateur.code in codes_persistes:
                    logger.warning(
                        "indicateur_duplique_ignore", rapport_id=str(rapport_id), code=indicateur.code
                    )
                    continue
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

                codes_persistes.add(indicateur.code)
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
                        CarbonEmission(
                            report_id=rapport_id,
                            scope=cible.scope,
                            ghg_category=cible.categorie_ges,
                            tonnes_co2e=indicateur.valeur,
                            year=annee_reporting,
                            method=DataMethod.RAPPORTEE,
                            pcaf_data_quality=qualite_donnee_pcaf(DataMethod.RAPPORTEE),
                            proof_id=preuve.id,
                            raw_value=indicateur.valeur_brute,
                            section=indicateur.section,
                            proof_text=indicateur.citation_source,
                            value_year=indicateur.annee_valeur,
                            confidence=indicateur.confiance,
                        )
                    )
                elif cible.cible == "indicateur_esg":
                    assert cible.pilier is not None  # invariant garanti par INDICATEURS_CIBLES
                    session.add(
                        ESGMetric(
                            report_id=rapport_id,
                            pillar=cible.pilier,
                            metric_code=cible.code,
                            value=indicateur.valeur,
                            unit=indicateur.unite or "",
                            method=DataMethod.RAPPORTEE,
                            proof_id=preuve.id,
                            raw_value=indicateur.valeur_brute,
                            section=indicateur.section,
                            proof_text=indicateur.citation_source,
                            value_year=indicateur.annee_valeur,
                            confidence=indicateur.confiance,
                        )
                    )
                else:  # "rapport_score_global"
                    rapport.declared_global_score = indicateur.valeur
                    rapport.declared_global_score_proof_id = preuve.id
                    session.add(rapport)

            # Exhaustivité par code (statut ABSENT_CONFIRME, voir completeness._absence_confirmee) :
            # un code est "recherché exhaustivement" si TOUTES ses pages candidates au-dessus de son
            # propre plancher de pertinence ont effectivement été montrées au LLM (1er passage +
            # relance) — jamais déduit du budget global, qui peut avoir écarté des pages pertinentes
            # pour CE code au profit d'autres codes dans le classement fusionné.
            pages_examinees_par_code = {code: len(pages_vues_par_code[code]) for code in codes}
            recherche_exhaustive_par_code = {
                code: {
                    candidat.page
                    for candidat in pages_par_code[code]
                    if candidat.score >= pages_par_code[code][0].score * RELEVANCE_FLOOR_RATIO
                }.issubset(pages_vues_par_code[code])
                for code in codes
                if pages_par_code.get(code)
            }
            for couverture in calculer_couverture(
                rapport_id, extraction, codes, pages_examinees_par_code, recherche_exhaustive_par_code
            ):
                session.add(couverture)

            rapport.extraction_finished_at = utcnow()
            rapport.extraction_error = None
            rapport.extraction_status = ExtractionStatus.DONE
            session.add(rapport)

            # Import différé : app.ingestion.synthesis_report importe
            # CODES_AUTO_DECLARES_PAR_PILIER depuis ce module -- un import en tête de fichier
            # créerait un cycle (ce module ne serait pas encore entièrement chargé au moment où
            # synthesis_report tenterait de lire cette constante).
            from app.ingestion import synthesis_report

            # Best-effort, délibérément (Phase 6) : un échec de génération du PDF de synthèse ne
            # doit jamais faire échouer l'extraction elle-même -- les indicateurs sont le résultat
            # porteur, le PDF de synthèse n'en est qu'une présentation dérivée, régénérable plus
            # tard (voir aussi app/admin/review_queue.py::valider_rapport, second déclencheur).
            try:
                contenu_synthese = synthesis_report.generer_rapport_synthese(session, rapport)
                storage.save_bytes(f"synthese/{rapport_id}.pdf", contenu_synthese)
                rapport.synthesis_report_path = f"synthese/{rapport_id}.pdf"
                session.add(rapport)
            except Exception as exc_synthese:  # noqa: BLE001 — best-effort assumé, voir ci-dessus.
                logger.error(
                    "synthese_pdf_generation_echouee",
                    rapport_id=str(rapport_id),
                    error_type=type(exc_synthese).__name__,
                )

            admins = session.exec(
                select(User).where(
                    col(User.role) == Role.ADMIN, col(User.active).is_(True)
                )
            ).all()
            for admin in admins:
                notifier(
                    session,
                    admin.id,
                    "RAPPORT_PRET_A_AFFECTER",
                    f"Le rapport {rapport.type.value} ({rapport.fiscal_year}) de "
                    f"{nom_entreprise} est prêt à être affecté à un auditeur.",
                    id_ressource=rapport_id,
                )
            session.commit()
            logger.info("extraction_pipeline_reussie", rapport_id=str(rapport_id))

        except Exception as exc:
            # erreur (Docling, réseau, Anthropic, DB) doit être classée et journalisée, jamais
            # remonter silencieusement dans une BackgroundTask sans observateur.
            session.rollback()
            if not derniere_tentative and _est_transitoire(exc):
                rapport.extraction_status = ExtractionStatus.QUEUED
                session.add(rapport)
                session.commit()
                logger.warning(
                    "extraction_echec_transitoire",
                    rapport_id=str(rapport_id),
                    error_type=type(exc).__name__,
                    etape=etape,
                )
                raise ExtractionTransitoire(etape) from exc
            marquer_echec(session, rapport, etape)
            session.commit()
            logger.error(
                "extraction_pipeline_echouee",
                rapport_id=str(rapport_id),
                error_type=type(exc).__name__,
                etape=etape,
            )
