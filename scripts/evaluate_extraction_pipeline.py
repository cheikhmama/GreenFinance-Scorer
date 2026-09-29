"""Évaluation de fidélité du pipeline d'extraction (Gemini) contre data_test/ground_truth.yaml.

Script autonome, hors DB/HTTP — appelle directement les fonctions internes de
app/ingestion/{docling_pipeline,extractor}.py, comme scripts/generate_reference_e2e_reports.py
appelle directement pymupdf plutôt que de passer par l'API.

Ne réutilise PAS run_extraction_pipeline (qui exige une session DB et un ESGReport) : ce script
mesure la fidélité de l'extraction elle-même, indépendamment du reste du cycle de vie applicatif.

Usage : uv run python scripts/evaluate_extraction_pipeline.py [--limit N]
Résultat : scripts/evaluation_extraction_resultats.json (+ un résumé lisible sur stdout).

Mesure, séparément, exactement ce que le cahier des charges demande :
  - détection (présence/omission) par code cible
  - exactitude valeur/unité pour les codes couverts par ground_truth.yaml
  - exactitude de la référence de preuve (page)
  - taux de valeurs produites pour un code sans vérité terrain disponible (non vérifiables
    indépendamment ici — PAS des hallucinations confirmées, la nuance est volontaire)

Limite assumée du corpus, à ne jamais dissimuler dans le résultat : ground_truth.yaml ne couvre
que 3 documents et seulement les codes carbone (scope_1/2/3, intensités) — aucun des ~19 autres
codes de INDICATEURS_CIBLES (social/gouvernance/scores auto-déclarés) n'a de valeur vérifiée
indépendamment dans ce corpus, et aucun des 3 documents n'a été explicitement choisi comme cas de
tableau complexe / unité ambiguë / document de qualité variable.
"""

from __future__ import annotations

import os

# Doit être posé avant tout import numpy/torch/paddle/faiss (mêmes garde-fous que
# app/ingestion/{docling_pipeline,extractor}.py pour TORCHDYNAMO_DISABLE) : un script autonome qui
# charge à la fois PyTorch (bge-m3) et PaddlePaddle (OCR Docling) dans le même process peut charger
# deux runtimes OpenMP concurrents sur Windows, un cas connu de segfault natif — jamais rencontré
# dans le process serveur au long cours (uvicorn), mais reproduit ici de façon répétée.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
# Tentative supplémentaire : conflit de threads OpenMP/MKL entre bge-m3 (PyTorch), Docling
# (PaddlePaddle) et faiss, plutôt qu'un conflit de symboles dupliqués — cause distincte de
# KMP_DUPLICATE_LIB_OK ci-dessus, l'autre suspect classique pour ce symptôme exact sous Windows.
# EVAL_NUM_THREADS (variable d'environnement, jamais un argument CLI) permet de desserrer ce
# mono-thread QUAND ce garde-fou natif ne s'applique pas — confirmé Phase 6 : ce crash Windows ne
# se reproduit PAS sous Linux (ex. ce même script dans le conteneur Docker du projet), où forcer 1
# thread rend juste l'encodage bge-m3 ~40x plus lent sans bénéfice de stabilité. Défaut "1" inchangé
# pour toute exécution Windows native.
_EVAL_NUM_THREADS = os.environ.get("EVAL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", _EVAL_NUM_THREADS)
os.environ.setdefault("MKL_NUM_THREADS", _EVAL_NUM_THREADS)
# Segmentation fault reproduite ici (Phase 6, hors cause Docling/Paddle : reproduite même en
# chargeant un DoclingDocument depuis un JSON en cache, donc sans jamais toucher PaddleOCR) —
# crash pendant le tout premier encode() bge-m3 sur un VRAI batch de chunks (plusieurs textes,
# batch_size=8), après qu'un encode() d'échauffement sur une chaîne unique a réussi. Cause probable
# : le pool de threads interne du tokenizer Rust (HuggingFace `tokenizers`) entre en conflit avec
# OMP_NUM_THREADS=1 forcé ci-dessus — désactiver son parallélisme interne est le correctif standard
# documenté pour cette classe de crash.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Dernière tentative de stabilisation, avant tout autre import : le pipeline réel n'exécute qu'une
# passe d'inférence bge-m3 avant Docling, mais Docling utilise LUI-MÊME deux runtimes PyTorch
# distincts en interne (TableFormer, et le détecteur de mise en page "docling-layout-heron" via
# transformers) en plus de PaddleOCR — une seule passe bge-m3 s'est révélée insuffisante ici
# (crash reproduit à un point différent à chaque essai, toujours juste après un premier appel
# PyTorch qui suit une init Paddle). Force le runtime PyTorch à s'initialiser et tourner réellement
# AVANT le tout premier import lié à Paddle/Docling, mono-thread, la combinaison la plus stable
# documentée pour ce conflit connu (PyTorch+Paddle dans le même process, Windows CPU).
import torch

torch.set_num_threads(int(_EVAL_NUM_THREADS))
_ = torch.zeros(1).sum().item()

import argparse
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from docling_core.types.doc.document import DoclingDocument

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import UNIQUEMENT app.ingestion.extractor, jamais app.ingestion.docling_pipeline en direct avant
# lui : extractor.py importe docling_pipeline lui-même, dans l'ordre qu'il a déjà validé (bge-m3
# importé et utilisé avant que Docling ne charge son backend PaddleOCR — un import indépendant de
# docling_pipeline en premier dans ce script a provoqué un segfault natif reproductible lors du
# premier essai, cohérent avec la fragilité déjà documentée dans extractor.py). docling_pipeline
# reste accessible via l'attribut du module extractor.
from app.ingestion import completeness, extractor
from app.ingestion.extractor import (
    INDICATEURS_CIBLES,
    _build_context,
    _build_search_index,
    _call_llm_extraction,
    _get_embed_model,
)

docling_pipeline = extractor.docling_pipeline

GROUND_TRUTH_PATH = Path("data_test/ground_truth.yaml")
RESULTAT_PATH = Path("scripts/evaluation_extraction_resultats.json")

# Phase 6 (validation empirique de la sélection adaptative) : réutilise le JSON Docling déjà
# généré et validé pour ce document (image_mode=PLACEHOLDER, voir docling_pipeline.py) au lieu de
# refaire la conversion OCR complète — Docling/OCR sont inchangés par ce chantier (déjà validés
# séparément), seule la recherche/sélection/extraction en aval a changé. Économise des dizaines de
# minutes par document long (orsted.pdf fait 218 pages) sans rien retirer à la validité du test :
# les appels Gemini restent réels. --no-docling-cache force une reconversion complète si besoin.
DOCLING_CACHE_DIR = Path("data_test/docling_json")

# Tolérance relative pour comparer une valeur flottante extraite à la valeur attendue — les
# rapports arrondissent parfois différemment (ex. 143 510 vs 143 500), jamais un écart de fond.
TOLERANCE_RELATIVE = 0.01


@dataclass
class ResultatIndicateur:
    code: str
    couvert_par_ground_truth: bool
    attendu_trouve: bool | None  # None si le code n'a pas de vérité terrain
    valeur_attendue: float | None
    unite_attendue: str | None
    page_attendue: int | None
    extrait_trouve: bool
    valeur_extraite: float | None
    unite_extraite: str | None
    page_extraite: int | None
    valeur_correcte: bool | None  # None si non vérifiable (pas de vérité terrain)
    page_correcte: bool | None
    verdict: str  # voir _verdict()
    # Champs étendus (Phase 6) — jamais fabriqués, None si le LLM ne les a pas fournis.
    statut: str | None  # TROUVE / NON_TROUVE / ABSENT_CONFIRME (voir completeness.calculer_couverture)
    valeur_brute: str | None
    annee_valeur: int | None
    section: str | None
    citation_source: str | None
    confiance: str | None
    non_divulgation_citation: str | None
    non_divulgation_page: int | None


def _verdict(r: ResultatIndicateur) -> str:
    if not r.couvert_par_ground_truth:
        return "non_verifiable_extrait" if r.extrait_trouve else "non_verifiable_absent"
    if r.attendu_trouve and r.extrait_trouve:
        return "detecte_correct" if r.valeur_correcte else "detecte_valeur_incorrecte"
    if r.attendu_trouve and not r.extrait_trouve:
        return "omission"
    if not r.attendu_trouve and r.extrait_trouve:
        return "invente"  # ne devrait jamais arriver dans ce corpus (tous les indicateurs GT sont présents)
    return "correctement_absent"


def _valeurs_proches(a: float, b: float) -> bool:
    if a == b:
        return True
    if b == 0:
        return abs(a) < 1e-6
    return abs(a - b) / abs(b) <= TOLERANCE_RELATIVE


def _charger_conversion(document: Path, cache_dir: Path | None):
    """Charge le DoclingDocument déjà converti depuis data_test/docling_json/<nom>.json si
    disponible (voir DOCLING_CACHE_DIR ci-dessus), sinon reconvertit le PDF normalement."""
    if cache_dir is not None:
        cache_path = cache_dir / f"{document.stem}.json"
        if cache_path.exists():
            t0 = time.time()
            doc = DoclingDocument.load_from_json(cache_path)
            elapsed = round(time.time() - t0, 2)
            print(
                f"  Docling (JSON en cache, {cache_path.name}) : {doc.num_pages()} pages, "
                f"chargé en {elapsed}s",
                flush=True,
            )
            return docling_pipeline.ConversionResult(
                document=doc,
                status="cache_json",
                errors=[],
                pages_docling=doc.num_pages(),
                pages_pymupdf=doc.num_pages(),
                pages_correspondent=True,
                elapsed_s=elapsed,
            )
    conversion = docling_pipeline.convert_pdf(document)
    print(
        f"  Docling: {conversion.pages_docling} pages, {conversion.elapsed_s}s, "
        f"status={conversion.status}",
        flush=True,
    )
    return conversion


def evaluer_entreprise(entree: dict, *, cache_docling_dir: Path | None) -> dict:
    nom = entree["nom"]
    document = Path(entree["document"])
    print(f"\n=== {nom} ({document}) ===", flush=True)

    if not document.exists():
        return {"nom": nom, "erreur": f"document introuvable : {document}"}

    t0 = time.time()
    # ORDRE OBLIGATOIRE, verbatim run_extraction_pipeline (app/ingestion/extractor.py) : bge-m3
    # (PyTorch) doit avoir réellement exécuté une passe d'inférence AVANT que Docling ne charge son
    # backend OCR PaddleOCR — dans l'autre sens, segfault natif reproductible (constaté ici même,
    # premier essai de ce script sans cette précaution : crash pendant "Processing document").
    embed_model = _get_embed_model()
    embed_model.encode(["initialisation"])

    conversion = _charger_conversion(document, cache_docling_dir)

    search_index = _build_search_index(conversion.document)
    codes = [cible.code for cible in INDICATEURS_CIBLES]

    # 1er passage — identique à run_extraction_pipeline.
    context, pages_used, pages_par_code = _build_context(
        search_index, embed_model, codes, extractor.CONTEXT_TOKEN_BUDGET
    )
    print(f"  Pages retenues (1er passage, {len(pages_used)}) : {pages_used}", flush=True)
    extraction = _call_llm_extraction(nom_entreprise=nom, context=context, codes=codes)

    pages_vues_par_code: dict[str, set[int]] = {code: set(pages_used) for code in codes}
    codes_manquants = [code for code in codes if not extractor._indicateur_trouve(extraction, code)]
    diagnostic_relance = {
        "codes_manquants_1er_passage": codes_manquants,
        "declenchee": False,
        "codes_soumis_au_2e_appel": [],
        "pages_2e_passage": [],
    }
    if codes_manquants:
        contexte_retry, pages_retry, pages_par_code_retry = _build_context(
            search_index, embed_model, codes_manquants, extractor.CONTEXT_TOKEN_BUDGET_RETRY
        )
        diagnostic_relance["pages_2e_passage"] = pages_retry
        if pages_retry:
            diagnostic_relance["declenchee"] = True
            diagnostic_relance["codes_soumis_au_2e_appel"] = codes_manquants
            print(
                f"  Relance groupée déclenchée pour {len(codes_manquants)} code(s) {codes_manquants} "
                f"— pages {pages_retry}",
                flush=True,
            )
            extraction_retry = _call_llm_extraction(
                nom_entreprise=nom, context=contexte_retry, codes=codes_manquants
            )
            extraction = extractor._fusionner_extractions(extraction, extraction_retry, codes_manquants)
            for code in codes_manquants:
                pages_vues_par_code[code] |= set(pages_retry)
            pages_par_code.update(pages_par_code_retry)
        else:
            print(
                f"  {len(codes_manquants)} code(s) manquant(s) mais aucune page supplémentaire "
                f"trouvée — relance non déclenchée : {codes_manquants}",
                flush=True,
            )

    elapsed = time.time() - t0

    # Statut à 3 valeurs — identique à run_extraction_pipeline.
    pages_examinees_par_code = {code: len(pages_vues_par_code[code]) for code in codes}
    recherche_exhaustive_par_code = {
        code: {
            candidat.page
            for candidat in pages_par_code[code]
            if candidat.score >= pages_par_code[code][0].score * extractor.RELEVANCE_FLOOR_RATIO
        }.issubset(pages_vues_par_code[code])
        for code in codes
        if pages_par_code.get(code)
    }
    couvertures = completeness.calculer_couverture(
        uuid.uuid4(), extraction, codes, pages_examinees_par_code, recherche_exhaustive_par_code
    )
    statut_par_code = {c.code: c.statut.value for c in couvertures}

    # Diagnostic mesure-seule (ne modifie rien à extractor.py) : rejoue les étapes internes du 1er
    # passage pour isoler l'effet de _elargir_aux_voisins et de TABLE_SCORE_BOOST.
    classement_global = extractor._fusionner_classements(pages_par_code)
    texte_par_page: dict[int, list[str]] = {}
    for chunk in search_index["chunks"]:
        texte_par_page.setdefault(chunk["page"], []).append(chunk["text"])
    texte_par_page_str = {p: "\n".join(parts) for p, parts in texte_par_page.items()}
    pages_coeur = extractor._selectionner_pages_adaptatif(
        classement_global, texte_par_page_str, extractor.CONTEXT_TOKEN_BUDGET
    )
    pages_voisines_ajoutees = sorted(set(pages_used) - set(pages_coeur))
    plancher = classement_global[0].score * extractor.RELEVANCE_FLOOR_RATIO if classement_global else 0.0
    pages_boost_table_decisives = sorted(
        c.page
        for c in classement_global
        if c.page in pages_coeur
        and c.is_table
        and (c.score / extractor.TABLE_SCORE_BOOST) < plancher <= c.score
    )
    print(f"  Pages ajoutées par élargissement aux voisins : {pages_voisines_ajoutees}", flush=True)
    print(
        f"  Pages incluses grâce au boost table (n'auraient pas passé le plancher sans lui) : "
        f"{pages_boost_table_decisives}",
        flush=True,
    )

    extraits_par_code = {i.code: i for i in extraction.indicateurs}
    attendus_par_code = {i["code"]: i for i in entree.get("indicateurs", [])}

    resultats: list[ResultatIndicateur] = []
    for code in codes:
        attendu = attendus_par_code.get(code)
        extrait = extraits_par_code.get(code)

        couvert = attendu is not None
        extrait_trouve = bool(extrait and extrait.trouve and extrait.valeur is not None)
        valeur_correcte = None
        page_correcte = None
        if couvert and attendu is not None:
            attendu_trouve = True  # tout code présent dans ground_truth.yaml a été vérifié comme trouvable
            if extrait_trouve and extrait is not None and extrait.valeur is not None:
                valeur_correcte = _valeurs_proches(extrait.valeur, attendu["valeur_attendue"])
                page_correcte = extrait.page_source == attendu["page_attendue"]
        else:
            attendu_trouve = None

        resultats.append(
            ResultatIndicateur(
                code=code,
                couvert_par_ground_truth=couvert,
                attendu_trouve=attendu_trouve,
                valeur_attendue=attendu["valeur_attendue"] if attendu else None,
                unite_attendue=attendu.get("unite") if attendu else None,
                page_attendue=attendu["page_attendue"] if attendu else None,
                extrait_trouve=extrait_trouve,
                valeur_extraite=extrait.valeur if extrait else None,
                unite_extraite=extrait.unite if extrait else None,
                page_extraite=extrait.page_source if extrait else None,
                valeur_correcte=valeur_correcte,
                page_correcte=page_correcte,
                verdict="",
                statut=statut_par_code.get(code),
                valeur_brute=extrait.valeur_brute if extrait else None,
                annee_valeur=extrait.annee_valeur if extrait else None,
                section=extrait.section if extrait else None,
                citation_source=extrait.citation_source if extrait else None,
                confiance=extrait.confiance.value if extrait and extrait.confiance else None,
                non_divulgation_citation=extrait.non_divulgation_citation if extrait else None,
                non_divulgation_page=extrait.non_divulgation_page if extrait else None,
            )
        )
    for r in resultats:
        r.verdict = _verdict(r)

    verifiables = [r for r in resultats if r.couvert_par_ground_truth]
    print(
        f"  Codes couverts par ground_truth : {len(verifiables)}/{len(codes)}. "
        f"Détectés corrects : {sum(1 for r in verifiables if r.verdict == 'detecte_correct')} — "
        f"omissions : {sum(1 for r in verifiables if r.verdict == 'omission')} — "
        f"valeur incorrecte : {sum(1 for r in verifiables if r.verdict == 'detecte_valeur_incorrecte')}",
        flush=True,
    )

    return {
        "nom": nom,
        "document": str(document),
        "pages_docling": conversion.pages_docling,
        "pages_retenues_1er_passage": pages_used,
        "pages_voisines_ajoutees": pages_voisines_ajoutees,
        "pages_boost_table_decisives": pages_boost_table_decisives,
        "diagnostic_relance": diagnostic_relance,
        "statut_par_code": statut_par_code,
        "duree_s": round(elapsed, 1),
        "resultats": [asdict(r) for r in resultats],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Limiter aux N premières entreprises")
    parser.add_argument(
        "--no-docling-cache",
        action="store_true",
        help="Force une reconversion Docling complète même si un JSON en cache existe (voir DOCLING_CACHE_DIR).",
    )
    args = parser.parse_args()
    cache_docling_dir = None if args.no_docling_cache else DOCLING_CACHE_DIR

    ground_truth = yaml.safe_load(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    entreprises = ground_truth["entreprises"]
    if args.limit:
        entreprises = entreprises[: args.limit]

    resultats_par_entreprise = []
    for entree in entreprises:
        resultat = evaluer_entreprise(entree, cache_docling_dir=cache_docling_dir)
        resultats_par_entreprise.append(resultat)
        # Écrit après CHAQUE entreprise (pas seulement à la fin) : un document de 200+ pages peut
        # prendre longtemps, un résultat partiel doit survivre à une interruption.
        RESULTAT_PATH.write_text(
            json.dumps(
                {"genere_le": time.strftime("%Y-%m-%dT%H:%M:%S"), "entreprises": resultats_par_entreprise},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    print(f"\nRésultats écrits dans {RESULTAT_PATH}", flush=True)


if __name__ == "__main__":
    main()
