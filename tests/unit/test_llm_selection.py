"""Choix du fournisseur LLM par la configuration, et son branchement dans le pipeline."""

from typing import Any

import pytest

from app.core.config import Settings
from app.ingestion import extractor
from app.ingestion.llm.base import ErreurLLMTransitoire, QuotaLLMEpuise
from app.ingestion.schemas import ExtractionEntreprise

REQUIS: dict[str, Any] = {
    "secret_key": "s" * 40,
    "mfa_issuer_name": "GF",
    "storage_backend": "local",
    "storage_path": "./storage",
    "default_scoring_config": "config/weights/default.yaml",
    "fx_rates_path": "config/fx_rates.yaml",
    "emission_factors_path": "config/emission_factors.yaml",
    "environment": "development",
}


def _settings(**valeurs: Any) -> Settings:
    return Settings(_env_file=None, **{**REQUIS, **valeurs})  # type: ignore[call-arg]


def test_fournisseur_openai_compat_sans_cle_gemini() -> None:
    s = _settings(llm_provider="openai_compat", llm_api_key="gsk_reelle")

    assert s.llm_demo is False
    assert s.llm_model == "llama-3.3-70b-versatile"


def test_cle_llm_absente_ou_factice_passe_en_demonstration() -> None:
    assert _settings(llm_provider="openai_compat", llm_api_key="").llm_demo is True
    assert _settings(llm_provider="openai_compat", llm_api_key="llm-api-key-example-replace-me").llm_demo
    assert _settings(gemini_api_key="gemini-api-key-example-replace-me").llm_demo is True


def test_gemini_exige_sa_cle() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        _settings(llm_provider="gemini", gemini_api_key="")


def test_production_refuse_une_cle_llm_factice() -> None:
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        _settings(
            environment="production",
            database_url="postgresql+psycopg://u:vrai@db/gf",
            llm_provider="openai_compat",
            llm_api_key="llm-api-key-example-replace-me",
        )


class _FournisseurFactice:
    def __init__(self, erreurs: dict[str, BaseException] | None = None) -> None:
        self.appels: list[tuple[str, str]] = []
        self._erreurs = erreurs or {}

    def extraire(self, prompt: str, modele: str) -> ExtractionEntreprise:
        self.appels.append((prompt, modele))
        if modele in self._erreurs:
            raise self._erreurs[modele]
        return ExtractionEntreprise(entreprise="Atlas", indicateurs=[])


@pytest.fixture
def openai_compat(monkeypatch: pytest.MonkeyPatch) -> _FournisseurFactice:
    s = _settings(
        llm_provider="openai_compat",
        llm_api_key="gsk_reelle",
        llm_model="llama-3.3-70b-versatile",
        llm_model_secours="llama-3.1-8b-instant",
    )
    monkeypatch.setattr(extractor, "get_settings", lambda: s)
    fournisseur = _FournisseurFactice({"llama-3.3-70b-versatile": QuotaLLMEpuise("TPD")})
    monkeypatch.setattr(extractor, "_get_fournisseur_openai", lambda: fournisseur)
    return fournisseur


def test_appel_route_vers_le_fournisseur_configure(openai_compat: _FournisseurFactice) -> None:
    extraction, modele = extractor._appeler_avec_secours(
        extractor.modele_principal(), nom_entreprise="Atlas", context="--- Page 1 ---\nx", codes=["scope_1"]
    )

    # Quota journalier du modèle principal : même prompt rejoué sur le modèle de secours.
    assert modele == "llama-3.1-8b-instant"
    assert [m for _p, m in openai_compat.appels] == ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    assert "Atlas" in openai_compat.appels[0][0] and "scope_1" in openai_compat.appels[0][0]
    assert extraction.entreprise == "Atlas"


def test_erreurs_normalisees_classees_par_le_pipeline() -> None:
    assert extractor.quota_journalier_epuise(QuotaLLMEpuise("TPD"))
    assert extractor._est_transitoire(ErreurLLMTransitoire("503"))
    assert not extractor._est_transitoire(QuotaLLMEpuise("TPD"))
