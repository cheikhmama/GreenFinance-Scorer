"""Découpage des appels LLM sous un budget de contexte réduit (paliers gratuits limités en tokens
par minute, ex. Llama 3.3 70B sur Groq) — sans modèle ni réseau."""

from app.ingestion.cibles import INDICATEURS_CIBLES
from app.ingestion.extractor import (
    CHARS_PER_TOKEN_ESTIME,
    CONTEXT_TOKEN_BUDGET,
    _elargir_dans_le_plafond,
    groupes_d_appel,
)

CODES = [c.code for c in INDICATEURS_CIBLES]


def test_un_seul_appel_quand_le_budget_n_est_pas_contraint() -> None:
    assert groupes_d_appel(CODES, CONTEXT_TOKEN_BUDGET) == [CODES]


def test_un_appel_par_famille_sous_un_budget_reduit() -> None:
    groupes = groupes_d_appel(CODES, 6_000)

    assert len(groupes) == 4
    tous = [code for groupe in groupes for code in groupe]
    assert sorted(tous) == sorted(CODES)  # chaque code dans exactement un appel
    carbone = {c.code for c in INDICATEURS_CIBLES if c.cible == "donnee_carbone"}
    assert set(groupes[0]) == carbone


def test_voisins_ajoutes_seulement_dans_le_plafond() -> None:
    page_400_tokens = "x" * (400 * CHARS_PER_TOKEN_ESTIME)
    texte = {p: page_400_tokens for p in range(1, 31)}

    # Pages cœur 10 puis 20 (ordre de pertinence) : leurs voisins passent dans cet ordre, tant
    # que le total reste sous le plafond — 4 pages × 400 = 1600.
    pages = _elargir_dans_le_plafond([10, 20], texte, radius=1, plafond_tokens=1_600)

    assert pages == [9, 10, 11, 20]


def test_les_pages_coeur_restent_meme_au_dela_du_plafond() -> None:
    texte = {p: "x" * (2_000 * CHARS_PER_TOKEN_ESTIME) for p in range(1, 10)}

    assert _elargir_dans_le_plafond([5], texte, radius=1, plafond_tokens=100) == [5]


def test_pipeline_appelle_une_fois_par_famille_et_fusionne(monkeypatch) -> None:
    from app.ingestion import extractor
    from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait

    contextes: list[tuple[list[str], int, int | None]] = []
    appels: list[list[str]] = []

    def construire(_index, _embed, codes, budget, plafond_tokens=None):
        contextes.append((list(codes), budget, plafond_tokens))
        page = len(contextes)
        return f"--- Page {page} ---\nx", [page], {c: [] for c in codes}

    def appeler(modele, *, nom_entreprise, context, codes):
        appels.append(list(codes))
        # Chaque famille trouve son premier code, rien d'autre : la relance porte sur le reste.
        return (
            ExtractionEntreprise(
                entreprise=nom_entreprise,
                indicateurs=[
                    IndicateurExtrait(code=codes[0], valeur=1.0, unite="", page_source=1, trouve=True)
                ],
            ),
            modele,
        )

    monkeypatch.setattr(extractor, "_build_context", construire)
    monkeypatch.setattr(extractor, "_appeler_avec_secours", appeler)

    resultat = extractor._extraire_par_llm(
        {}, None, CODES, nom_entreprise="Atlas", budget_tokens=6_000, modele="m"
    )

    groupes = groupes_d_appel(CODES, 6_000)
    assert appels[:4] == groupes
    # Sous budget réduit : chaque contexte plafonné strictement, relance comprise.
    assert all(plafond == 6_000 for _c, _b, plafond in contextes[:4])
    retry_codes, retry_budget, retry_plafond = contextes[4]
    assert retry_budget <= 6_000 and retry_plafond == 6_000
    assert sorted(retry_codes) == sorted(set(CODES) - {g[0] for g in groupes})
    trouves = {i.code for i in resultat.extraction.indicateurs if i.trouve}
    assert {g[0] for g in groupes} <= trouves
    # Les pages vues par un code sont celles de SON appel (1er passage) puis de la relance.
    assert resultat.pages_vues_par_code[groupes[1][0]] == {2}


def test_pipeline_un_seul_appel_sans_contrainte(monkeypatch) -> None:
    from app.ingestion import extractor
    from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait

    contextes: list[tuple[int, int | None]] = []
    monkeypatch.setattr(
        extractor,
        "_build_context",
        lambda _i, _e, codes, budget, plafond_tokens=None: (
            contextes.append((budget, plafond_tokens)) or ("--- Page 1 ---\nx", [1], {})
        ),
    )
    monkeypatch.setattr(
        extractor,
        "_appeler_avec_secours",
        lambda modele, *, nom_entreprise, context, codes: (
            ExtractionEntreprise(
                entreprise="A",
                indicateurs=[
                    IndicateurExtrait(code=c, valeur=1.0, unite="", page_source=1, trouve=True)
                    for c in codes
                ],
            ),
            modele,
        ),
    )

    extractor._extraire_par_llm(
        {}, None, CODES, nom_entreprise="A", budget_tokens=CONTEXT_TOKEN_BUDGET, modele="m"
    )

    assert contextes == [(CONTEXT_TOKEN_BUDGET, None)]
