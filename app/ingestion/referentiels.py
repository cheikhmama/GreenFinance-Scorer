"""Correspondance code extrait → référentiels ESG publics (config/referentiels/esg_frameworks.yaml).

Lue par la sortie JSON de l'extraction (app/ingestion/sortie.py) : un consommateur externe (agent
via MCP, export) retrouve chaque valeur dans le référentiel qu'il connaît, sans apprendre le
vocabulaire interne des codes.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

FICHIER = Path(__file__).resolve().parents[2] / "config" / "referentiels" / "esg_frameworks.yaml"


class Referentiels(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ghg_protocol: str | None
    gri: str | None
    esrs: str | None
    unite: str


@lru_cache
def charger_referentiels(chemin: Path = FICHIER) -> dict[str, Referentiels]:
    brut = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    return {code: Referentiels.model_validate(valeurs) for code, valeurs in brut.items()}
