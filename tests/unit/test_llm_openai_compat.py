"""Fournisseur LLM OpenAI-compatible (Groq, OpenRouter… : Llama 3.3, DeepSeek) — transport HTTP
simulé, client openai réel : on vérifie la requête envoyée et l'interprétation des réponses."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import openai
import pytest

from app.ingestion.llm.base import (
    ErreurLLMTransitoire,
    QuotaLLMEpuise,
    ReponseLLMInvalide,
)
from app.ingestion.llm.openai_compat import NOM_OUTIL, FournisseurOpenAICompat

EXTRACTION = {
    "entreprise": "Atlas",
    "indicateurs": [
        {"code": "scope_1", "valeur": 1200.5, "unite": "tCO2e", "page_source": 4, "trouve": True}
    ],
}


def _reponse_outil(arguments: Any) -> httpx.Response:
    texte = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return httpx.Response(
        200,
        json={
            "id": "c1",
            "object": "chat.completion",
            "created": 0,
            "model": "llama-3.3-70b-versatile",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "t1",
                                "type": "function",
                                "function": {"name": NOM_OUTIL, "arguments": texte},
                            }
                        ],
                    },
                }
            ],
        },
    )


def _reponse_texte(texte: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "c2",
            "object": "chat.completion",
            "created": 0,
            "model": "m",
            "choices": [
                {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": texte}}
            ],
        },
    )


def _erreur(statut: int, message: str, entetes: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(statut, json={"error": {"message": message}}, headers=entetes or {})


def _fournisseur(
    reponses: list[httpx.Response], requetes: list[dict[str, Any]], attentes: list[float] | None = None
) -> FournisseurOpenAICompat:
    file = iter(reponses)

    def gerer(requete: httpx.Request) -> httpx.Response:
        requetes.append(json.loads(requete.content))
        return next(file)

    client = openai.OpenAI(
        api_key="cle",
        base_url="https://llm.example/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(gerer)),
        max_retries=0,
    )
    attendre: Callable[[float], None] = (attentes.append if attentes is not None else lambda _s: None)
    return FournisseurOpenAICompat(client, attendre=attendre)


def test_force_l_appel_de_l_outil_et_valide_la_reponse() -> None:
    requetes: list[dict[str, Any]] = []
    fournisseur = _fournisseur([_reponse_outil(EXTRACTION)], requetes)

    extraction = fournisseur.extraire("PROMPT", "llama-3.3-70b-versatile")

    assert extraction.indicateurs[0].valeur == 1200.5
    assert extraction.indicateurs[0].page_source == 4
    envoi = requetes[0]
    assert envoi["model"] == "llama-3.3-70b-versatile"
    assert envoi["messages"][-1] == {"role": "user", "content": "PROMPT"}
    assert envoi["tool_choice"] == {"type": "function", "function": {"name": NOM_OUTIL}}
    assert envoi["tools"][0]["function"]["name"] == NOM_OUTIL
    assert "indicateurs" in envoi["tools"][0]["function"]["parameters"]["properties"]
    assert envoi["temperature"] == 0


def test_reponse_sans_outil_relancee_une_fois_avec_l_erreur() -> None:
    requetes: list[dict[str, Any]] = []
    fournisseur = _fournisseur([_reponse_texte("Voici les données…"), _reponse_outil(EXTRACTION)], requetes)

    extraction = fournisseur.extraire("PROMPT", "m")

    assert extraction.entreprise == "Atlas"
    assert len(requetes) == 2
    # La relance rappelle au modèle ce qui n'allait pas, sans perdre le prompt d'origine.
    assert requetes[1]["messages"][0] == {"role": "user", "content": "PROMPT"}
    assert NOM_OUTIL in requetes[1]["messages"][-1]["content"]


def test_arguments_hors_schema_deux_fois_reponse_invalide() -> None:
    requetes: list[dict[str, Any]] = []
    fournisseur = _fournisseur(
        [_reponse_outil({"entreprise": "Atlas"}), _reponse_outil("{pas du json")], requetes
    )

    with pytest.raises(ReponseLLMInvalide):
        fournisseur.extraire("PROMPT", "m")
    assert len(requetes) == 2


def test_quota_journalier_epuise_sans_nouvelle_tentative() -> None:
    requetes: list[dict[str, Any]] = []
    fournisseur = _fournisseur(
        [_erreur(429, "Rate limit reached for model on tokens per day (TPD): Limit 100000")], requetes
    )

    with pytest.raises(QuotaLLMEpuise):
        fournisseur.extraire("PROMPT", "m")
    assert len(requetes) == 1


def test_limite_par_minute_attend_retry_after_puis_reussit() -> None:
    requetes: list[dict[str, Any]] = []
    attentes: list[float] = []
    fournisseur = _fournisseur(
        [
            _erreur(429, "Rate limit reached on tokens per minute (TPM)", {"retry-after": "7"}),
            _reponse_outil(EXTRACTION),
        ],
        requetes,
        attentes,
    )

    fournisseur.extraire("PROMPT", "m")

    assert attentes == [7.0]
    assert len(requetes) == 2


def test_erreurs_serveur_repetees_deviennent_transitoires() -> None:
    requetes: list[dict[str, Any]] = []
    fournisseur = _fournisseur([_erreur(503, "overloaded")] * 3, requetes)

    with pytest.raises(ErreurLLMTransitoire):
        fournisseur.extraire("PROMPT", "m")
    assert len(requetes) == 3


def test_cle_invalide_n_est_ni_transitoire_ni_quota() -> None:
    fournisseur = _fournisseur([_erreur(401, "Invalid API key")], [])

    with pytest.raises(openai.AuthenticationError):
        fournisseur.extraire("PROMPT", "m")
