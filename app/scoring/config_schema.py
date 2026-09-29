"""Schéma de validation des fichiers de configuration de pondération du scoring.

Un fichier sous config/weights/ (ex. default.yaml) décrit, par pilier E/S/G : le poids du pilier
dans le score global, et pour chacun de ses indicateurs, son poids dans le pilier et les bornes
de normalisation (Phase 5 §9). C'est ce qui rend la méthodologie « versionnée » au sens du
cahier des charges — un chiffre changé ici est une nouvelle version de la méthodologie, jamais
une constante enfouie dans app/scoring/engine.py.

Les poids ne sont pas obligés de sommer exactement à 1 dans le fichier : le moteur (engine.py)
renormalise toujours sur ce qui est effectivement présent (indicateur manquant, voire pilier
entier absent pour un rapport donné) — mais un fichier dont les poids déclarés ne somment pas à
1 est rejeté ici, à la lecture, pour qu'une erreur de méthodologie soit visible tout de suite
plutôt que de se traduire en un score silencieusement biaisé.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from app.core.enums import Pillar

_TOLERANCE_SOMME_POIDS = 1e-6


class IndicateurPondere(BaseModel):
    poids: float = Field(gt=0)
    plus_haut_est_meilleur: bool
    borne_min: float
    borne_max: float

    @model_validator(mode="after")
    def _bornes_distinctes(self) -> "IndicateurPondere":
        if self.borne_max <= self.borne_min:
            raise ValueError("borne_max doit être strictement supérieure à borne_min")
        return self


class PilierConfig(BaseModel):
    poids: float = Field(gt=0)
    indicateurs: dict[str, IndicateurPondere]

    @model_validator(mode="after")
    def _au_moins_un_indicateur(self) -> "PilierConfig":
        if not self.indicateurs:
            raise ValueError("un pilier doit référencer au moins un indicateur")
        return self


class ConfigurationScoring(BaseModel):
    version: int
    nom: str
    piliers: dict[Pillar, PilierConfig]
    # Seuil facultatif (tâche 3.1) : un rapport dont la couverture pondérée des indicateurs de
    # cette configuration est inférieure ne peut pas être validé sous elle — un score calculé sur
    # trop peu de données ne se publie pas.
    min_coverage: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def _trois_piliers_et_sommes_correctes(self) -> "ConfigurationScoring":
        manquants = set(Pillar) - set(self.piliers)
        if manquants:
            raise ValueError(f"piliers manquants : {sorted(p.value for p in manquants)}")

        somme_piliers = sum(pilier.poids for pilier in self.piliers.values())
        if abs(somme_piliers - 1.0) > _TOLERANCE_SOMME_POIDS:
            raise ValueError(f"la somme des poids des piliers doit valoir 1.0, obtenu {somme_piliers}")

        for nom_pilier, pilier in self.piliers.items():
            somme_indicateurs = sum(ind.poids for ind in pilier.indicateurs.values())
            if abs(somme_indicateurs - 1.0) > _TOLERANCE_SOMME_POIDS:
                raise ValueError(
                    f"pilier {nom_pilier.value} : la somme des poids de ses indicateurs doit "
                    f"valoir 1.0, obtenu {somme_indicateurs}"
                )
        return self


def _lire_yaml(contenu_yaml: str) -> Any:
    try:
        return yaml.safe_load(contenu_yaml)
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML illisible : {exc}") from exc


def charger_configuration(contenu_yaml: str) -> ConfigurationScoring:
    """ValueError (ou pydantic.ValidationError, sous-classe) si le contenu est illisible ou
    invalide."""
    return ConfigurationScoring.model_validate(_lire_yaml(contenu_yaml))


def empreinte_configuration(contenu_yaml: str) -> str:
    """SHA-256 de la forme canonique : le YAML parsé, resérialisé en JSON à clés triées. Un
    commentaire, une indentation ou un ordre de clés différents ne changent donc pas l'empreinte ;
    un poids, une borne ou un numéro de version, si. Figée : la migration c1d4a8e2f935 recalcule
    la même empreinte à l'identique, la modifier invaliderait toutes les empreintes en base."""
    canonique = json.dumps(
        _lire_yaml(contenu_yaml), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonique.encode("utf-8")).hexdigest()


def charger_configuration_depuis_fichier(chemin: Path) -> ConfigurationScoring:
    return charger_configuration(chemin.read_text(encoding="utf-8"))
