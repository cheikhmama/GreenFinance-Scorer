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

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from app.core.enums import Pilier

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
    piliers: dict[Pilier, PilierConfig]

    @model_validator(mode="after")
    def _trois_piliers_et_sommes_correctes(self) -> "ConfigurationScoring":
        manquants = set(Pilier) - set(self.piliers)
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


def charger_configuration_depuis_fichier(chemin: Path) -> ConfigurationScoring:
    contenu = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    return ConfigurationScoring.model_validate(contenu)
