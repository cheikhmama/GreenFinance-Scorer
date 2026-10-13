"""Fournisseur OpenAI-compatible : modèles ouverts (Llama 3.3 70B, DeepSeek-V3…) servis par un
palier gratuit (Groq, OpenRouter) ou tout serveur exposant /chat/completions (vLLM, Ollama).

Même protocole que le chemin Gemini : appel d'outil forcé, arguments validés par le schéma
Pydantic ExtractionEntreprise — jamais de texte libre interprété. Un fournisseur ou modèle qui
n'accepte pas les outils bascule en mode JSON (response_format json_object, schéma dans le prompt),
retenu pour les appels suivants.
"""

import copy
import json
import re
import time
from collections.abc import Callable
from typing import Any

import openai
import structlog
from pydantic import ValidationError

from app.ingestion.llm.base import (
    ContexteLLMTropGrand,
    ErreurLLMTransitoire,
    QuotaLLMEpuise,
    ReponseLLMInvalide,
)
from app.ingestion.schemas import ExtractionEntreprise

logger = structlog.get_logger(__name__)

NOM_OUTIL = "extraction_indicateurs"


def _sans_references(schema: dict[str, Any]) -> dict[str, Any]:
    """Déplie les $ref vers $defs du schéma Pydantic : les modèles ouverts suivent mal les
    références et produisent alors des appels d'outil invalides (Groq : tool_use_failed)."""
    definitions = schema.get("$defs", {})

    def deplier(noeud: Any) -> Any:
        if isinstance(noeud, dict):
            if "$ref" in noeud:
                cible = definitions[noeud["$ref"].rsplit("/", 1)[-1]]
                autres = {k: v for k, v in noeud.items() if k != "$ref"}
                return deplier({**copy.deepcopy(cible), **autres})
            return {k: deplier(v) for k, v in noeud.items() if k != "$defs"}
        if isinstance(noeud, list):
            return [deplier(v) for v in noeud]
        return noeud

    return deplier(schema)


SCHEMA = _sans_references(ExtractionEntreprise.model_json_schema())
OUTIL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": NOM_OUTIL,
        "description": (
            "Extraction structuree des indicateurs ESG/carbone demandes, a partir des extraits de "
            "rapport fournis."
        ),
        "parameters": SCHEMA,
    },
}
CONSIGNE_JSON = (
    "Réponds uniquement par un objet JSON (aucun texte autour) conforme à ce schéma JSON :\n"
    + json.dumps(SCHEMA, ensure_ascii=False)
)

# Groq : « tokens per day (TPD) », « requests per day (RPD) » ; OpenRouter : « free-models-per-day ».
_QUOTA_JOURNALIER = re.compile(r"per[ -]day|\bTPD\b|\bRPD\b|daily", re.IGNORECASE)
# Fournisseur ou modèle sans appel d'outil (OpenRouter « No endpoints found that support tool use »,
# serveurs qui refusent tool_choice).
_OUTILS_NON_PRIS_EN_CHARGE = re.compile(r"tool", re.IGNORECASE)
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
        if tentatives < 1:
            raise ValueError("Au moins une tentative.")
        self._client = client
        self._attendre = attendre
        self._tentatives = tentatives
        self._mode_json = False

    def extraire(self, prompt: str, modele: str) -> ExtractionEntreprise:
        """Une relance au plus si la réponse est inexploitable, avec l'erreur rappelée au modèle :
        les modèles ouverts oublient plus souvent l'outil que Gemini, mais le corrigent quand on
        le leur signale."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        try:
            return self._interroger(messages, modele)
        except ReponseLLMInvalide as exc:
            logger.warning("reponse_llm_invalide_relance", modele=modele, erreur=str(exc)[:200])
            consigne = (
                "un objet JSON conforme au schéma"
                if self._mode_json
                else f"l'outil {NOM_OUTIL} avec des arguments conformes à son schéma"
            )
            relance = messages + [
                {
                    "role": "user",
                    "content": (
                        f"Ta réponse précédente était inexploitable ({str(exc)[:300]}). Renvoie "
                        f"obligatoirement {consigne}."
                    ),
                }
            ]
            return self._interroger(relance, modele)

    def _interroger(self, messages: list[dict[str, Any]], modele: str) -> ExtractionEntreprise:
        if not self._mode_json:
            try:
                return self._valider_outil(self._appeler(messages, modele, outils=True))
            except _OutilsNonPrisEnCharge:
                logger.warning("llm_sans_outils_bascule_mode_json", modele=modele)
                self._mode_json = True
        return self._valider_json(self._appeler(messages, modele, outils=False))

    def _appeler(self, messages: list[dict[str, Any]], modele: str, *, outils: bool) -> Any:
        parametres: dict[str, Any] = {"model": modele, "temperature": 0}
        if outils:
            parametres |= {
                "messages": messages,
                "tools": [OUTIL],
                "tool_choice": {"type": "function", "function": {"name": NOM_OUTIL}},
            }
        else:
            parametres |= {
                "messages": [{"role": "system", "content": CONSIGNE_JSON}, *messages],
                "response_format": {"type": "json_object"},
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
            except openai.APIStatusError as exc:
                raise _classer_refus(exc, outils=outils) from exc
            if tentative < self._tentatives:
                logger.warning("appel_llm_transitoire", modele=modele, tentative=tentative)
                self._attendre(min(attente, _ATTENTE_MAX_S))
        raise ErreurLLMTransitoire(str(derniere)) from derniere

    @staticmethod
    def _message(reponse: Any) -> Any:
        # Certains fournisseurs (OpenRouter) renvoient un 200 sans choix, avec une erreur en corps.
        choix = getattr(reponse, "choices", None)
        if not choix:
            raise ReponseLLMInvalide("Réponse du fournisseur sans aucun choix.")
        return choix[0].message

    def _valider_outil(self, reponse: Any) -> ExtractionEntreprise:
        message = self._message(reponse)
        appels = [a for a in (message.tool_calls or []) if a.function.name == NOM_OUTIL]
        if not appels:
            raise ReponseLLMInvalide(f"Le modele n'a renvoye aucun appel a l'outil {NOM_OUTIL}.")
        return _valider(appels[0].function.arguments, f"Arguments de {NOM_OUTIL} invalides")

    def _valider_json(self, reponse: Any) -> ExtractionEntreprise:
        return _valider(self._message(reponse).content or "", "Réponse JSON invalide")


class _OutilsNonPrisEnCharge(Exception):
    """Interne : le fournisseur refuse les outils, à rejouer en mode JSON."""


def _valider(texte: str, contexte: str) -> ExtractionEntreprise:
    try:
        return ExtractionEntreprise.model_validate(json.loads(texte))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ReponseLLMInvalide(f"{contexte} : {exc}") from exc


def _classer_refus(exc: openai.APIStatusError, *, outils: bool) -> Exception:
    """4xx non transitoires : appel d'outil mal formé par le modèle (relance avec correction),
    requête au-delà de la limite de tokens (échec clair), outils non pris en charge (mode JSON).
    Toute autre erreur (clé refusée, modèle inconnu) remonte telle quelle."""
    corps = exc.body if isinstance(exc.body, dict) else {}
    erreur = corps.get("error", corps) if isinstance(corps, dict) else {}
    code = erreur.get("code") if isinstance(erreur, dict) else None
    if code == "tool_use_failed":
        tentative = erreur.get("failed_generation", "")
        return ReponseLLMInvalide(f"Appel d'outil mal formé par le modèle : {str(tentative)[:300]}")
    if exc.status_code == 413:
        return ContexteLLMTropGrand(
            "Requête au-delà de la limite de tokens du fournisseur : réduire LLM_CONTEXT_TOKENS. "
            f"({exc.message[:200]})"
        )
    if outils and exc.status_code in (400, 404) and _OUTILS_NON_PRIS_EN_CHARGE.search(str(exc)):
        return _OutilsNonPrisEnCharge(str(exc))
    return exc


def _retry_after(exc: openai.APIStatusError) -> float | None:
    valeur = exc.response.headers.get("retry-after")
    try:
        return float(valeur) if valeur else None
    except ValueError:
        return None
