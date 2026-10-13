"""Fournisseur OpenAI-compatible : modèles ouverts (Llama 3.3 70B, DeepSeek-V3…) servis par un
palier gratuit (Groq, OpenRouter) ou tout serveur exposant /chat/completions (vLLM, Ollama).

Même protocole que le chemin Gemini : appel d'outil forcé, arguments validés par le schéma
Pydantic ExtractionEntreprise — jamais de texte libre interprété.
"""

import json
import re
import time
from collections.abc import Callable
from typing import Any

import openai
import structlog
from pydantic import ValidationError

from app.ingestion.llm.base import (
    ErreurLLMTransitoire,
    QuotaLLMEpuise,
    ReponseLLMInvalide,
)
from app.ingestion.schemas import ExtractionEntreprise

logger = structlog.get_logger(__name__)

NOM_OUTIL = "extraction_indicateurs"
OUTIL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": NOM_OUTIL,
        "description": (
            "Extraction structuree des indicateurs ESG/carbone demandes, a partir des extraits de "
            "rapport fournis."
        ),
        "parameters": ExtractionEntreprise.model_json_schema(),
    },
}

# Groq : « tokens per day (TPD) », « requests per day (RPD) » ; OpenRouter : « free-models-per-day ».
_QUOTA_JOURNALIER = re.compile(r"per[ -]day|\bTPD\b|\bRPD\b|daily", re.IGNORECASE)
_TENTATIVES = 3
_ATTENTE_MAX_S = 60.0


class FournisseurOpenAICompat:
    def __init__(
        self,
        client: openai.OpenAI,
        *,
        attendre: Callable[[float], None] = time.sleep,
        tentatives: int = _TENTATIVES,
    ) -> None:
        self._client = client
        self._attendre = attendre
        self._tentatives = tentatives

    def extraire(self, prompt: str, modele: str) -> ExtractionEntreprise:
        """Une relance au plus si la réponse est inexploitable, avec l'erreur rappelée au modèle :
        les modèles ouverts oublient plus souvent l'outil que Gemini, mais le corrigent quand on
        le leur signale."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        try:
            return self._valider(self._appeler(messages, modele))
        except ReponseLLMInvalide as exc:
            logger.warning("reponse_llm_invalide_relance", modele=modele, erreur=str(exc)[:200])
            relance = messages + [
                {
                    "role": "user",
                    "content": (
                        f"Ta réponse précédente était inexploitable ({str(exc)[:300]}). Appelle "
                        f"obligatoirement l'outil {NOM_OUTIL} avec des arguments conformes à son "
                        "schéma."
                    ),
                }
            ]
            return self._valider(self._appeler(relance, modele))

    def _appeler(self, messages: list[dict[str, Any]], modele: str) -> Any:
        parametres: dict[str, Any] = {
            "model": modele,
            "messages": messages,
            "tools": [OUTIL],
            "tool_choice": {"type": "function", "function": {"name": NOM_OUTIL}},
            "temperature": 0,
        }
        derniere: Exception | None = None
        for tentative in range(1, self._tentatives + 1):
            try:
                return self._client.chat.completions.create(**parametres)
            except openai.RateLimitError as exc:
                if _QUOTA_JOURNALIER.search(str(exc)):
                    raise QuotaLLMEpuise(str(exc)) from exc
                derniere = exc
                attente = _retry_after(exc) or float(2**tentative)
            except (openai.InternalServerError, openai.APIConnectionError) as exc:
                derniere = exc
                attente = float(2**tentative)
            if tentative < self._tentatives:
                logger.warning("appel_llm_transitoire", modele=modele, tentative=tentative)
                self._attendre(min(attente, _ATTENTE_MAX_S))
        raise ErreurLLMTransitoire(str(derniere)) from derniere

    @staticmethod
    def _valider(reponse: Any) -> ExtractionEntreprise:
        message = reponse.choices[0].message
        appels = [a for a in (message.tool_calls or []) if a.function.name == NOM_OUTIL]
        if not appels:
            raise ReponseLLMInvalide(f"Le modele n'a renvoye aucun appel a l'outil {NOM_OUTIL}.")
        try:
            return ExtractionEntreprise.model_validate(json.loads(appels[0].function.arguments))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ReponseLLMInvalide(f"Arguments de {NOM_OUTIL} invalides : {exc}") from exc


def _retry_after(exc: openai.APIStatusError) -> float | None:
    valeur = exc.response.headers.get("retry-after")
    try:
        return float(valeur) if valeur else None
    except ValueError:
        return None
