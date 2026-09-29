"""Sélection adaptative du contexte LLM (Phase 6, remplace CONTEXT_TOP_PAGES=20 fixe) et
classification NON_TROUVE/ABSENT_CONFIRME. Fonctions pures testées directement — aucun appel
réseau, Gemini, bge-m3, FAISS ou Docling n'est déclenché par ces tests eux-mêmes (l'import
app.main plus bas ne fait qu'enregistrer les modèles SQLModel, sans I/O)."""

import uuid

from app.core.enums import StatutCouvertureIndicateur
from app.ingestion import extractor
from app.ingestion.completeness import _absence_confirmee, calculer_couverture
from app.ingestion.extractor import (
    INDICATEURS_CIBLES,
    REQUETES_PAR_CODE,
    PageCandidat,
    _consolidate_by_page,
    _elargir_aux_voisins,
    _fusionner_classements,
    _fusionner_extractions,
    _selectionner_pages_adaptatif,
)
from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait

# Import pour effet de bord uniquement : force l'enregistrement de TOUS les modèles SQLModel de
# l'application (relations à référence différée par nom de classe, ex. Utilisateur -> Entreprise)
# avant que calculer_couverture ne construise une instance de MetricCoverage ci-dessous —
# sans cet import, la configuration paresseuse du mapper SQLAlchemy échoue avec une
# InvalidRequestError dès la première instanciation d'une table dans un test qui n'importe que
# app.ingestion.*.
from app.main import app as _app  # noqa: F401


def test_toutes_les_cibles_ont_une_requete_dediee() -> None:
    assert {c.code for c in INDICATEURS_CIBLES} == set(REQUETES_PAR_CODE)


def test_selectionner_pages_adaptatif_respecte_le_plancher_de_pertinence() -> None:
    classement = [
        PageCandidat(page=1, score=0.9, is_table=False),
        PageCandidat(page=2, score=0.85, is_table=False),
        PageCandidat(page=3, score=0.82, is_table=False),
        PageCandidat(page=4, score=0.30, is_table=False),
        PageCandidat(page=5, score=0.28, is_table=False),
    ]
    texte_par_page = {c.page: "x" for c in classement}
    selection = _selectionner_pages_adaptatif(classement, texte_par_page, budget_tokens=1_000_000)
    assert selection == [1, 2, 3]


def test_selectionner_pages_adaptatif_respecte_le_budget_de_tokens() -> None:
    # Scores plats (aucun ne passe sous le plancher) — seul le budget doit couper la sélection.
    classement = [
        PageCandidat(page=1, score=1.0, is_table=False),
        PageCandidat(page=2, score=1.0, is_table=False),
        PageCandidat(page=3, score=1.0, is_table=False),
    ]
    texte_par_page = {1: "a" * 100, 2: "b" * 100, 3: "c" * 1000}
    # CHARS_PER_TOKEN_ESTIME=4 -> page1/2 coutent 25 tokens chacune, page3 en coute 250.
    selection = _selectionner_pages_adaptatif(classement, texte_par_page, budget_tokens=60)
    assert selection == [1, 2]


def test_selectionner_pages_adaptatif_inclut_toujours_au_moins_une_page() -> None:
    classement = [PageCandidat(page=1, score=1.0, is_table=False)]
    texte_par_page = {1: "x" * 4000}  # coûte largement plus que le budget, seule candidate
    selection = _selectionner_pages_adaptatif(classement, texte_par_page, budget_tokens=1)
    assert selection == [1]


def test_selectionner_pages_adaptatif_sur_classement_vide_retourne_liste_vide() -> None:
    assert _selectionner_pages_adaptatif([], {}, budget_tokens=1000) == []


def test_elargir_aux_voisins_ajoute_les_pages_adjacentes_disponibles() -> None:
    resultat = _elargir_aux_voisins([10], {8, 9, 10, 11, 12}, radius=1)
    assert resultat == [9, 10, 11]


def test_elargir_aux_voisins_ignore_les_pages_hors_document() -> None:
    # Page 1 est la première du document : pas de page 0 fantôme malgré radius=1.
    resultat = _elargir_aux_voisins([1], {1, 2}, radius=1)
    assert resultat == [1, 2]


def test_consolidate_by_page_priorise_un_chunk_table_a_score_egal() -> None:
    pairs = [
        ({"page": 1, "is_table": False}, 0.5),
        ({"page": 2, "is_table": True}, 0.5),
    ]
    resultat = _consolidate_by_page(pairs)
    assert resultat[0].page == 2
    assert resultat[0].is_table is True
    assert resultat[1].page == 1


def test_fusionner_classements_prend_le_max_entre_codes() -> None:
    pages_par_code = {
        "code1": [PageCandidat(page=1, score=0.5, is_table=False)],
        "code2": [PageCandidat(page=1, score=0.8, is_table=False)],
    }
    resultat = _fusionner_classements(pages_par_code)
    assert len(resultat) == 1
    assert resultat[0].page == 1
    assert resultat[0].score == 0.8


def test_fusionner_extractions_remplace_uniquement_les_codes_manquants() -> None:
    premiere = ExtractionEntreprise(
        entreprise="X",
        indicateurs=[
            IndicateurExtrait(code="A", valeur=1.0, trouve=True),
            IndicateurExtrait(code="B", valeur=None, trouve=False),
        ],
    )
    retry = ExtractionEntreprise(
        entreprise="X",
        indicateurs=[
            IndicateurExtrait(code="B", valeur=2.0, trouve=True),
            IndicateurExtrait(code="C", valeur=99.0, trouve=True),  # hors périmètre, doit être ignoré
        ],
    )
    fusion = _fusionner_extractions(premiere, retry, codes_manquants=["B"])
    par_code = {i.code: i for i in fusion.indicateurs}
    assert set(par_code) == {"A", "B"}
    assert par_code["A"].valeur == 1.0
    assert par_code["B"].valeur == 2.0


def test_absence_confirmee_par_citation_explicite() -> None:
    extrait = IndicateurExtrait(
        code="X", trouve=False, non_divulgation_citation="non communique", non_divulgation_page=12
    )
    assert _absence_confirmee(extrait, recherche_exhaustive=False) is True


def test_absence_confirmee_par_recherche_exhaustive() -> None:
    extrait = IndicateurExtrait(code="X", trouve=False)
    assert _absence_confirmee(extrait, recherche_exhaustive=True) is True


def test_absence_confirmee_sans_extrait_suit_lexhaustivite() -> None:
    assert _absence_confirmee(None, recherche_exhaustive=True) is True
    assert _absence_confirmee(None, recherche_exhaustive=False) is False


def test_non_trouve_quand_ni_citation_ni_recherche_exhaustive() -> None:
    extrait = IndicateurExtrait(code="X", trouve=False)
    assert _absence_confirmee(extrait, recherche_exhaustive=False) is False


def test_calculer_couverture_classe_les_trois_statuts() -> None:
    extraction = ExtractionEntreprise(
        entreprise="X",
        indicateurs=[
            IndicateurExtrait(code="A", valeur=1.0, trouve=True),
            IndicateurExtrait(
                code="B",
                valeur=None,
                trouve=False,
                non_divulgation_citation="non communique cette annee",
                non_divulgation_page=5,
            ),
            IndicateurExtrait(code="C", valeur=None, trouve=False),
        ],
    )
    codes = ["A", "B", "C"]
    pages_examinees_par_code = {"A": 10, "B": 20, "C": 5}
    recherche_exhaustive_par_code = {"A": False, "B": False, "C": False}

    couvertures = calculer_couverture(
        uuid.uuid4(), extraction, codes, pages_examinees_par_code, recherche_exhaustive_par_code
    )
    par_code = {c.metric_code: c for c in couvertures}

    assert par_code["A"].status == StatutCouvertureIndicateur.TROUVE
    assert par_code["B"].status == StatutCouvertureIndicateur.ABSENT_CONFIRME
    assert par_code["C"].status == StatutCouvertureIndicateur.NON_TROUVE
    # pages_examinees est bien lu par code, jamais un entier partagé.
    assert par_code["A"].pages_examined == 10
    assert par_code["B"].pages_examined == 20
    assert par_code["C"].pages_examined == 5


def test_selectionner_pages_adaptatif_sur_un_grand_corpus_synthetique() -> None:
    """Simule un rapport de 500 pages sans PDF réel : Docling/OCR/bge-m3 sont déjà indépendants du
    nombre de pages (voir app/ingestion/docling_pipeline.py), seule la logique de coupure a besoin
    d'être vérifiée à cette échelle. 30 pages pertinentes dispersées non contiguës (comme les ~23
    codes cibles le seraient sur un vrai rapport long) — bien au-dessus de l'ancien plafond fixe
    CONTEXT_TOP_PAGES=20, pour prouver que la sélection s'adapte plutôt que de tronquer."""
    pages_pertinentes = [
        10, 11, 45, 90, 91, 92, 150, 151, 205, 206, 250, 251, 252, 300, 301, 302, 303,
        350, 351, 400, 401, 402, 403, 404, 450, 451, 452, 480, 481, 482,
    ]
    pertinentes = [
        PageCandidat(page=p, score=0.95 - i * 0.015, is_table=False)
        for i, p in enumerate(pages_pertinentes)
    ]
    plancher_attendu = pertinentes[0].score * extractor.RELEVANCE_FLOOR_RATIO
    # Un chunk-tableau qui ne passe le plancher que grâce au boost déjà appliqué à son score
    # (simulé ici directement — le boost lui-même est couvert par test_consolidate_by_page_...).
    tableau_via_boost = [PageCandidat(page=500, score=plancher_attendu + 0.005, is_table=True)]

    queue_peu_pertinente = [
        PageCandidat(page=p, score=0.1 + (p % 10) / 100, is_table=False)
        for p in range(1, 501)
        if p not in {c.page for c in pertinentes + tableau_via_boost}
    ]
    assert all(c.score < plancher_attendu for c in queue_peu_pertinente)  # sanité de construction

    classement_global = sorted(
        pertinentes + tableau_via_boost + queue_peu_pertinente, key=lambda c: c.score, reverse=True
    )

    texte_par_page = {c.page: "x" * 400 for c in classement_global}  # 100 tokens/page
    budget_tokens = 5_000
    selection = _selectionner_pages_adaptatif(classement_global, texte_par_page, budget_tokens)

    assert 0 < len(selection) < 500
    assert len(selection) > 20  # bien au-dessus de l'ancien plafond fixe CONTEXT_TOP_PAGES=20

    plancher = classement_global[0].score * extractor.RELEVANCE_FLOOR_RATIO
    scores_par_page = {c.page: c.score for c in classement_global}
    assert all(scores_par_page[p] >= plancher for p in selection)

    tokens_cumules = sum(len(texte_par_page[p]) // extractor.CHARS_PER_TOKEN_ESTIME for p in selection)
    assert tokens_cumules <= budget_tokens or len(selection) == 1

    pages_disponibles = set(range(1, 501))
    elargie = _elargir_aux_voisins(selection, pages_disponibles, extractor.NEIGHBOR_RADIUS)
    assert set(selection).issubset(elargie)
    assert len(elargie) > len(selection)  # au moins un voisin ajouté (pages 50/51/300/301 adjacentes)
