"""Recherche sémantique et appel du LLM d'extraction (tâche 4.5) — sans modèle ni réseau.

L'encodeur bge-m3 est remplacé par un encodeur déterministe (sac de mots haché) : deux textes qui
partagent des mots sont proches, deux textes sans mot commun sont orthogonaux. La vraie chaîne
FAISS (normalisation, index, recherche exhaustive), le découpage par page et la sélection du
contexte tournent, eux, pour de vrai. Le client Gemini est un double qui enregistre ses appels.
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest
from google.genai import errors as genai_errors

from app.ingestion import extractor

_DIMENSIONS = 256


class _EncodeurMots:
    """Même interface que BGEM3FlagModel.encode : {"dense_vecs": matrice}."""

    def encode(self, textes: list[str], batch_size: int = 8) -> dict[str, np.ndarray]:
        vecteurs = np.zeros((len(textes), _DIMENSIONS), dtype="float32")
        for ligne, texte in enumerate(textes):
            for mot in re.findall(r"[a-z0-9]+", texte.lower()):
                if len(mot) > 2:
                    indice = int(hashlib.sha256(mot.encode()).hexdigest(), 16) % _DIMENSIONS
                    vecteurs[ligne, indice] += 1
        return {"dense_vecs": vecteurs}


@dataclass
class _Provenance:
    page_no: int


@dataclass
class _Texte:
    text: str
    prov: list[_Provenance]


@dataclass
class _Tableau:
    markdown: str
    prov: list[_Provenance]
    echoue: bool = False

    def export_to_markdown(self, _doc: Any) -> str:
        if self.echoue:
            raise RuntimeError("tableau illisible")
        return self.markdown


@dataclass
class _Document:
    texts: list[Any] = field(default_factory=list)
    tables: list[Any] = field(default_factory=list)


def _texte(page: int, contenu: str) -> _Texte:
    return _Texte(contenu, [_Provenance(page)])


# --- découpage par page ---------------------------------------------------------------------------


def test_decoupage_un_chunk_par_item_tableaux_marques_erreurs_ignorees() -> None:
    document = _Document(
        texts=[
            _texte(1, "a" * 2500),  # découpé en 3 morceaux de 1 200 caractères au plus
            _Texte("sans provenance", []),  # ignoré : aucune page connue
            _texte(2, "   "),  # vide après nettoyage
        ],
        tables=[
            _Tableau("| Scope 1 | 1 200 |", [_Provenance(3)]),
            _Tableau("", [_Provenance(4)], echoue=True),  # journalisé, jamais avalé en silence
        ],
    )

    chunks = extractor._iter_page_chunks(document)  # type: ignore[arg-type]

    assert [(c["page"], len(c["text"]), c["is_table"]) for c in chunks] == [
        (1, 1200, False),
        (1, 1200, False),
        (1, 100, False),
        (3, len("| Scope 1 | 1 200 |"), True),
    ]


# --- index et recherche -----------------------------------------------------------------------------


@pytest.fixture()
def index_rapport(monkeypatch) -> dict:
    monkeypatch.setattr(extractor, "_get_embed_model", lambda: _EncodeurMots())
    document = _Document(
        texts=[
            _texte(1, "Message du président et gouvernance générale du groupe."),
            _texte(2, "Scope 1 direct greenhouse gas emissions: 1 200 tonnes of CO2 equivalent."),
            _texte(3, "Suite du bilan carbone, méthodologie de calcul."),
            _texte(7, "Politique de ressources humaines et formation des salariés."),
        ],
    )
    return extractor._build_search_index(document)  # type: ignore[arg-type]


def test_recherche_exhaustive_classe_la_page_pertinente_en_tete(index_rapport) -> None:
    resultats = extractor._search_all_chunks(
        index_rapport, _EncodeurMots(), extractor.REQUETES_PAR_CODE["scope_1"]
    )

    assert index_rapport["index"].ntotal == 4
    assert len(resultats) == 4  # k = ntotal : tous les morceaux sont classés, aucun tronqué
    assert resultats[0][0]["page"] == 2
    assert resultats[0][1] > resultats[1][1]


def test_contexte_page_pertinente_voisines_jamais_hors_sujet(index_rapport) -> None:
    contexte, pages, pages_par_code = extractor._build_context(
        index_rapport, _EncodeurMots(), ["scope_1"], extractor.CONTEXT_TOKEN_BUDGET
    )

    assert pages_par_code["scope_1"][0].page == 2
    # Page 2 retenue pour son score, 1 et 3 ajoutées comme voisines (NEIGHBOR_RADIUS = 1) ; la page
    # 7, sans aucun mot commun avec la requête, reste sous le plancher de pertinence.
    assert pages == [1, 2, 3]
    assert "--- Page 2 ---\nScope 1 direct greenhouse gas emissions" in contexte
    assert "ressources humaines" not in contexte


# --- appel du LLM -------------------------------------------------------------------------------------


@dataclass
class _AppelOutil:
    args: dict


@dataclass
class _Reponse:
    function_calls: list[_AppelOutil] | None


class _ClientGemini:
    def __init__(self, reponses: list[Any]) -> None:
        self._reponses = list(reponses)
        self.prompts: list[str] = []
        self.modeles: list[str] = []
        self.models = self

    def generate_content(self, *, model: str, contents: str, config: Any) -> _Reponse:
        self.prompts.append(contents)
        self.modeles.append(model)
        reponse = self._reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


_ARGS = {
    "entreprise": "Atlas Industries",
    "indicateurs": [{"code": "scope_1", "valeur": 1200.0, "unite": "tCO2e", "page_source": 2, "trouve": True}],
}


def _utiliser(monkeypatch, client: _ClientGemini) -> None:
    monkeypatch.setattr(extractor, "_get_gemini_client", lambda: client)
    monkeypatch.setattr(extractor.time, "sleep", lambda _s: None)


def test_appel_llm_transmet_contexte_et_codes_et_valide_la_reponse(monkeypatch) -> None:
    client = _ClientGemini([_Reponse([_AppelOutil(_ARGS)])])
    _utiliser(monkeypatch, client)

    extraction = extractor._call_llm_extraction(
        nom_entreprise="Atlas Industries", context="--- Page 2 ---\nScope 1 : 1 200 t", codes=["scope_1"]
    )

    assert extraction.indicateurs[0].valeur == 1200.0
    [prompt] = client.prompts
    assert "Atlas Industries" in prompt
    assert "--- Page 2 ---" in prompt
    assert "scope_1" in prompt


def test_appel_llm_retente_une_erreur_serveur_puis_abandonne(monkeypatch) -> None:
    panne = genai_errors.ServerError(503, {"error": {"message": "surcharge"}})
    client = _ClientGemini([panne, _Reponse([_AppelOutil(_ARGS)])])
    _utiliser(monkeypatch, client)

    extraction = extractor._call_llm_extraction(nom_entreprise="A", context="c", codes=["scope_1"])

    assert extraction.entreprise == "Atlas Industries"
    assert len(client.prompts) == 2  # une erreur serveur passagère, un seul nouvel essai

    client = _ClientGemini([panne] * extractor._TENTATIVES_APPEL_LLM)
    _utiliser(monkeypatch, client)
    with pytest.raises(genai_errors.ServerError):
        extractor._call_llm_extraction(nom_entreprise="A", context="c", codes=["scope_1"])
    assert len(client.prompts) == extractor._TENTATIVES_APPEL_LLM


def _quota_depasse(quota_id: str) -> genai_errors.ClientError:
    return genai_errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "details": [{"violations": [{"quotaId": quota_id, "quotaValue": "20"}]}],
            }
        },
    )


def test_quota_journalier_n_est_pas_transitoire() -> None:
    """Le quota du jour ne se lève qu'au lendemain : reprendre le job ne ferait qu'attendre."""
    journalier = _quota_depasse("GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    par_minute = _quota_depasse("GenerateRequestsPerMinutePerProjectPerModel-FreeTier")

    assert extractor.quota_journalier_epuise(journalier)
    assert not extractor._est_transitoire(journalier)
    assert not extractor.quota_journalier_epuise(par_minute)
    assert extractor._est_transitoire(par_minute)


def test_quota_journalier_du_modele_principal_bascule_sur_le_secours(monkeypatch) -> None:
    journalier = _quota_depasse("GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    client = _ClientGemini([journalier, _Reponse([_AppelOutil(_ARGS)])])
    _utiliser(monkeypatch, client)

    extraction, modele = extractor._appeler_avec_secours(
        extractor.EXTRACTION_MODEL, nom_entreprise="A", context="c", codes=["scope_1"]
    )

    assert extraction.entreprise == "Atlas Industries"
    assert modele == extractor.MODELE_SECOURS != extractor.EXTRACTION_MODEL
    assert client.modeles == [extractor.EXTRACTION_MODEL, extractor.MODELE_SECOURS]


def test_secours_epuise_ou_autre_erreur_remonte_telle_quelle(monkeypatch) -> None:
    journalier = _quota_depasse("GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    client = _ClientGemini([journalier, journalier])
    _utiliser(monkeypatch, client)
    with pytest.raises(genai_errors.ClientError) as erreur:
        extractor._appeler_avec_secours(
            extractor.EXTRACTION_MODEL, nom_entreprise="A", context="c", codes=["scope_1"]
        )
    assert extractor.quota_journalier_epuise(erreur.value)
    assert len(client.modeles) == 2  # un essai par modèle, pas plus

    # Un quota par minute n'est pas une raison de changer de modèle : la reprise du job s'en charge.
    client = _ClientGemini([_quota_depasse("GenerateRequestsPerMinutePerProjectPerModel-FreeTier")])
    _utiliser(monkeypatch, client)
    with pytest.raises(genai_errors.ClientError):
        extractor._appeler_avec_secours(
            extractor.EXTRACTION_MODEL, nom_entreprise="A", context="c", codes=["scope_1"]
        )
    assert client.modeles == [extractor.EXTRACTION_MODEL]

    # Déjà sur le secours (relance groupée) : appelé directement.
    client = _ClientGemini([_Reponse([_AppelOutil(_ARGS)])])
    _utiliser(monkeypatch, client)
    _, modele = extractor._appeler_avec_secours(
        extractor.MODELE_SECOURS, nom_entreprise="A", context="c", codes=["scope_1"]
    )
    assert client.modeles == [extractor.MODELE_SECOURS] and modele == extractor.MODELE_SECOURS


def test_requetes_encodees_en_un_seul_appel(index_rapport) -> None:
    """Toutes les requêtes en un encodage (≈45 s gagnées sur CPU), même classement qu'une à une."""

    class _Compteur(_EncodeurMots):
        appels = 0

        def encode(self, textes: list[str], batch_size: int = 8) -> dict[str, np.ndarray]:
            type(self).appels += 1
            return super().encode(textes, batch_size)

    codes = ["scope_1", "effectif_total", "taille_conseil"]
    encodeur = _Compteur()
    groupes = extractor._rechercher_par_code(index_rapport, encodeur, codes)

    assert _Compteur.appels == 1
    for code in codes:
        un_a_un = extractor._consolidate_by_page(
            extractor._search_all_chunks(index_rapport, _EncodeurMots(), extractor.REQUETES_PAR_CODE[code])
        )
        assert groupes[code] == un_a_un


def test_appel_llm_sans_appel_d_outil_est_une_erreur_explicite(monkeypatch) -> None:
    _utiliser(monkeypatch, _ClientGemini([_Reponse(None)]))

    with pytest.raises(ValueError, match="aucun appel"):
        extractor._call_llm_extraction(nom_entreprise="A", context="c", codes=["scope_1"])
